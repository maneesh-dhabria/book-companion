"""Tests for POST /api/v1/books/:id/book-summary."""

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed_book_with_section_summaries(app, *, book_id: int):
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO books (id, title, file_data, file_hash, file_format, "
                "file_size_bytes, status) VALUES (:b, 'T', x'00', :h, 'epub', 1, 'COMPLETED')"
            ),
            {"b": book_id, "h": f"h{book_id}"},
        )
        # Create a section with a default summary pointing at a real row.
        await session.execute(
            text(
                "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                "section_type, content_md) "
                "VALUES (:sid, :bid, 'Ch', 0, 0, 'chapter', 'body')"
            ),
            {"sid": book_id * 100, "bid": book_id},
        )
        await session.execute(
            text(
                "INSERT INTO summaries (id, content_type, content_id, book_id, "
                "facets_used, prompt_text_sent, model_used, "
                "input_char_count, summary_char_count, summary_md) VALUES "
                "(:id, 'section', :cid, :bid, '{}', 'p', 'm', 10, 5, 'real summary')"
            ),
            {"id": book_id * 1000, "cid": book_id * 100, "bid": book_id},
        )
        await session.execute(
            text(
                "UPDATE book_sections SET default_summary_id = :sid WHERE id = :bsid"
            ),
            {"sid": book_id * 1000, "bsid": book_id * 100},
        )
        await session.commit()


async def _seed_book_no_summaries(app, *, book_id: int):
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO books (id, title, file_data, file_hash, file_format, "
                "file_size_bytes, status) VALUES (:b, 'T', x'00', :h, 'epub', 1, 'COMPLETED')"
            ),
            {"b": book_id, "h": f"h{book_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                "section_type, content_md) "
                "VALUES (:sid, :bid, 'Ch', 0, 0, 'chapter', 'body')"
            ),
            {"sid": book_id * 100, "bid": book_id},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_post_book_summary_returns_201(app, client: AsyncClient):
    await _seed_book_with_section_summaries(app, book_id=10)
    r = await client.post(
        "/api/v1/books/10/book-summary",
        json={"preset_name": "executive_brief"},
    )
    assert r.status_code == 201, r.text
    assert "job_id" in r.json()


@pytest.mark.asyncio
async def test_post_book_summary_404_for_unknown_book(app, client: AsyncClient):
    r = await client.post(
        "/api/v1/books/99999/book-summary",
        json={"preset_name": "executive_brief"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_book_summary_400_when_no_section_summaries(
    app, client: AsyncClient
):
    await _seed_book_no_summaries(app, book_id=11)
    r = await client.post(
        "/api/v1/books/11/book-summary",
        json={"preset_name": "executive_brief"},
    )
    assert r.status_code == 400
    assert "summarize sections first" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_post_book_summary_400_for_invalid_preset(
    app, client: AsyncClient
):
    await _seed_book_with_section_summaries(app, book_id=12)
    r = await client.post(
        "/api/v1/books/12/book-summary",
        json={"preset_name": "does_not_exist"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_post_book_summary_409_when_job_running(app, client: AsyncClient):
    await _seed_book_with_section_summaries(app, book_id=13)
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO processing_jobs (book_id, status, step, pid) "
                "VALUES (13, 'RUNNING', 'SUMMARIZE', :pid)"
            ),
            {"pid": os.getpid()},
        )
        await session.commit()
    r = await client.post(
        "/api/v1/books/13/book-summary",
        json={"preset_name": "executive_brief"},
    )
    assert r.status_code == 409
