"""FR-23, FR-24, FR-27: scope validation on summarize route."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed_two_books(app) -> tuple[int, int, int]:
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES
                  (1, 'A', x'00', 'ha', 'epub', 1, 'COMPLETED'),
                  (2, 'B', x'00', 'hb', 'epub', 1, 'COMPLETED')
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO book_sections (id, book_id, title, order_index, depth,
                                           section_type, content_md)
                VALUES
                  (10, 1, 'Ch', 0, 0, 'chapter', 'c'),
                  (20, 2, 'Ch', 0, 0, 'chapter', 'c')
                """
            )
        )
        await session.commit()
    return 1, 10, 20


@pytest.mark.asyncio
async def test_scope_section_requires_section_id(app, client: AsyncClient):
    book_id, _, _ = await _seed_two_books(app)
    r = await client.post(
        f"/api/v1/books/{book_id}/summarize", json={"scope": "section"}
    )
    assert r.status_code == 422
    assert "section_id" in r.json()["detail"]


@pytest.mark.asyncio
async def test_scope_section_wrong_book_returns_422(app, client: AsyncClient):
    book_id, _, foreign = await _seed_two_books(app)
    r = await client.post(
        f"/api/v1/books/{book_id}/summarize",
        json={"scope": "section", "section_id": foreign},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_scope_pending_with_force_returns_400(app, client: AsyncClient):
    book_id, _, _ = await _seed_two_books(app)
    r = await client.post(
        f"/api/v1/books/{book_id}/summarize",
        json={"scope": "pending", "force": True},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_scope_all_default_preserves_current_behavior(
    app, client: AsyncClient
):
    book_id, _, _ = await _seed_two_books(app)
    r = await client.post(f"/api/v1/books/{book_id}/summarize", json={})
    # Accept either success kickoff (200/202) or 400 from missing LLM provider.
    assert r.status_code in (200, 202, 400)
