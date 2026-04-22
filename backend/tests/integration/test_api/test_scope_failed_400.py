"""FR-A5.2 — POST /summarize with scope=failed returns 400 when none failed."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed_book(app, book_id: int, with_failure: bool = False):
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (:id, 'T', x'00', :h, 'epub', 1, 'COMPLETED')
                """
            ),
            {"id": book_id, "h": f"h{book_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                "section_type, content_md, last_failure_type) VALUES "
                "(:sid, :bid, 'Ch', 0, 0, 'chapter', 'c', :ftype)"
            ),
            {
                "sid": book_id * 10,
                "bid": book_id,
                "ftype": "cli_timeout" if with_failure else None,
            },
        )
        await session.commit()


@pytest.mark.asyncio
async def test_scope_failed_returns_400_when_none_failed(app, client: AsyncClient):
    await _seed_book(app, book_id=50, with_failure=False)
    r = await client.post(
        "/api/v1/books/50/summarize", json={"scope": "failed"}
    )
    assert r.status_code == 400, r.text
    assert "no failed sections" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_scope_failed_accepted_when_section_has_failure(
    app, client: AsyncClient
):
    await _seed_book(app, book_id=51, with_failure=True)
    r = await client.post(
        "/api/v1/books/51/summarize", json={"scope": "failed"}
    )
    # Should not 400; 200/202/400-for-no-LLM are acceptable depending on env.
    assert r.status_code != 400 or "no failed sections" not in r.json()["detail"].lower()
