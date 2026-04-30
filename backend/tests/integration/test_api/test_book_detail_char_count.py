"""B7 — SectionBriefResponse.content_char_count (FR-25)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed(app, *, content_md: str | None = "hello world"):
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (1, 'T', x'00', 'h1', 'epub', 1, 'COMPLETED')
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO book_sections
                  (id, book_id, title, order_index, depth, section_type, content_md)
                VALUES (1, 1, 'Ch1', 0, 0, 'chapter', :md)
                """
            ),
            {"md": content_md},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_section_brief_includes_content_char_count(app, client: AsyncClient):
    md = "hello world"  # 11 chars
    await _seed(app, content_md=md)

    r = await client.get("/api/v1/books/1")
    assert r.status_code == 200, r.text
    body = r.json()
    sections = body["sections"]
    assert len(sections) == 1
    s = sections[0]
    assert "content_char_count" in s
    assert s["content_char_count"] == len(md)


@pytest.mark.asyncio
async def test_section_with_null_content_md_has_zero_char_count(app, client: AsyncClient):
    await _seed(app, content_md=None)
    r = await client.get("/api/v1/books/1")
    assert r.status_code == 200, r.text
    s = r.json()["sections"][0]
    assert s["content_char_count"] == 0
