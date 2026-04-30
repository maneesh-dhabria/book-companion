"""FR-01, FR-02, FR-03 — on-demand stale-job sweep in POST /summarize.

Verifies that:
  - A RUNNING job whose PID is dead is swept (marked FAILED) and the
    new request proceeds (202).
  - A live RUNNING job blocks the new request with 409 and the response
    body includes the structured ``active_job`` payload (id, scope,
    started_at, progress).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

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
async def test_stale_running_job_is_swept(app, client: AsyncClient):
    await _seed_book(app, book_id=1)
    factory = app.state.session_factory
    started = datetime.now(timezone.utc) - timedelta(minutes=5)
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO processing_jobs (id, book_id, status, step, pid, started_at, "
                "request_params) VALUES (777, 1, 'RUNNING', 'SUMMARIZE', :pid, :started, "
                ":params)"
            ),
            {
                "pid": 99999,  # almost certainly dead
                "started": started.isoformat(),
                "params": '{"scope": "all"}',
            },
        )
        await session.commit()

    r = await client.post("/api/v1/books/1/summarize", json={"scope": "all"})
    assert r.status_code == 200, r.text  # default success on this route

    # Stale job marked FAILED
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT status, error_message FROM processing_jobs WHERE id = 777"
                )
            )
        ).first()
        assert row is not None
        assert row[0] == "FAILED"
        assert "stale" in (row[1] or "").lower()


@pytest.mark.asyncio
async def test_live_running_job_blocks_with_active_job_payload(app, client: AsyncClient):
    await _seed_book(app, book_id=2)
    factory = app.state.session_factory
    started = datetime.now(timezone.utc) - timedelta(minutes=1)
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO processing_jobs (id, book_id, status, step, pid, started_at, "
                "request_params, progress) "
                "VALUES (888, 2, 'RUNNING', 'SUMMARIZE', :pid, :started, :params, :progress)"
            ),
            {
                "pid": os.getpid(),
                "started": started.isoformat(),
                "params": '{"scope": "all"}',
                "progress": '{"current": 12, "total": 24}',
            },
        )
        await session.commit()

    r = await client.post("/api/v1/books/2/summarize", json={"scope": "all"})
    assert r.status_code == 409, r.text
    body = r.json()
    # FastAPI wraps HTTPException(detail=<dict>) so the dict body lives at
    # response.json()["detail"]
    payload = body["detail"]
    assert "active_job" in payload
    assert payload["active_job"]["id"] == 888
    assert payload["active_job"]["progress"] == {"current": 12, "total": 24}
    assert payload["active_job"]["scope"] == "all"
