"""FR-D4.1 / FR-D4.2 — GET /annotations returns book + section context."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed(app):
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO books (id, title, file_data, file_hash, file_format, "
                "file_size_bytes, status) VALUES "
                "(1, 'Competitive Strategy', x'00', 'h-por', 'epub', 1, 'COMPLETED')"
            )
        )
        await session.execute(
            text(
                "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                "section_type, content_md) VALUES "
                "(10, 1, 'Introduction', 0, 0, 'chapter', 'c')"
            )
        )
        await session.execute(
            text(
                "INSERT INTO annotations (id, content_type, content_id, type, "
                "selected_text, note) VALUES "
                "(100, 'SECTION_CONTENT', 10, 'HIGHLIGHT', 'five forces', 'key')"
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_annotations_list_includes_book_and_section_context(
    app, client: AsyncClient
):
    await _seed(app)
    r = await client.get("/api/v1/annotations")
    assert r.status_code == 200
    body = r.json()
    assert body["items"], r.text
    ann = body["items"][0]
    assert ann["book_id"] == 1
    assert ann["book_title"] == "Competitive Strategy"
    assert ann["section_id"] == 10
    assert ann["section_title"] == "Introduction"


@pytest.mark.asyncio
async def test_annotations_context_null_when_section_missing(
    app, client: AsyncClient
):
    # Seed an annotation whose content_id does not match any section.
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO annotations (id, content_type, content_id, type, "
                "selected_text, note) VALUES "
                "(200, 'SECTION_CONTENT', 9999, 'NOTE', 'orphan', 'NOTE')"
            )
        )
        await session.commit()
    r = await client.get("/api/v1/annotations")
    body = r.json()
    ann = next((a for a in body["items"] if a["id"] == 200), None)
    assert ann is not None
    assert ann["book_id"] is None
    assert ann["section_id"] is None
