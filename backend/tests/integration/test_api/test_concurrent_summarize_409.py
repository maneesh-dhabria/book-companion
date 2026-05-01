"""FR-A7.3 / A7.6 — 409 on concurrent summarize."""

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed_book(app, book_id: int = 1):
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (:id, 'T', x'00', :hash, 'epub', 1, 'COMPLETED')
                """
            ),
            {"id": book_id, "hash": f"h{book_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                "section_type, content_md) VALUES (:sid, :bid, 'Ch', 0, 0, 'chapter', 'c')"
            ),
            {"sid": book_id * 10, "bid": book_id},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_second_summarize_gets_409(app, client: AsyncClient):
    await _seed_book(app, book_id=1)
    # Pre-seed an active job to force the application-level 409.
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO processing_jobs (book_id, status, step, pid) "
                "VALUES (1, 'RUNNING', 'SUMMARIZE', :pid)"
            ),
            {"pid": os.getpid()},
        )
        await session.commit()

    r = await client.post("/api/v1/books/1/summarize", json={})
    assert r.status_code == 409, r.text
    # FR-02: 409 body is now a structured dict so the UI can deep-link to the
    # active job. The legacy "already running" string lives at .detail.detail.
    payload = r.json()["detail"]
    assert "already running" in payload["detail"].lower()
    assert "active_job" in payload


@pytest.mark.asyncio
async def test_409_when_pending_job_exists(app, client: AsyncClient):
    await _seed_book(app, book_id=2)
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO processing_jobs (book_id, status, step, pid) "
                "VALUES (2, 'PENDING', 'SUMMARIZE', :pid)"
            ),
            {"pid": os.getpid()},
        )
        await session.commit()

    r = await client.post("/api/v1/books/2/summarize", json={})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_completed_jobs_do_not_block_new_requests(app, client: AsyncClient):
    await _seed_book(app, book_id=3)
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO processing_jobs (book_id, status, step, pid) "
                "VALUES (3, 'COMPLETED', 'SUMMARIZE', :pid)"
            ),
            {"pid": os.getpid()},
        )
        await session.commit()

    r = await client.post("/api/v1/books/3/summarize", json={})
    # Should not 409; response is 200/202/400 depending on LLM provider.
    assert r.status_code != 409, r.text


@pytest.mark.asyncio
async def test_orphan_sweep_unblocks_new_job(app, client: AsyncClient):
    """Dead-PID orphan rows no longer block a new POST.

    FR-01 changed the semantics: the POST /summarize route runs an
    on-demand stale-job sweep before deciding 409. A dead-PID orphan
    is treated as stale, marked FAILED in-place, and the new job is
    queued — without needing the offline ``orphan_sweep()`` first.
    """
    await _seed_book(app, book_id=42)
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO processing_jobs (book_id, status, step, pid) "
                "VALUES (42, 'RUNNING', 'SUMMARIZE', 999999)"
            )
        )
        await session.commit()

    r_unblocked = await client.post("/api/v1/books/42/summarize", json={})
    assert r_unblocked.status_code != 409, r_unblocked.text
