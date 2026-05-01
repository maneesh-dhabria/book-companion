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


@pytest.mark.asyncio
async def test_section_brief_default_summary_carries_char_count(app, client: AsyncClient):
    """FR-31: SectionBriefResponse must embed default_summary.summary_char_count
    so the book-detail SectionListTable can compute the Compression column.
    """
    md = "x" * 1000
    await _seed(app, content_md=md)
    factory = app.state.session_factory
    async with factory() as session:
        # Insert a Summary row tied to section 1, then point default_summary_id at it.
        await session.execute(
            text(
                """
                INSERT INTO summaries
                  (id, content_type, content_id, book_id, model_used,
                   prompt_text_sent, summary_md, input_char_count,
                   summary_char_count, input_tokens, output_tokens, latency_ms,
                   facets_used)
                VALUES (42, 'SECTION', 1, 1, 'claude-sonnet-4-6',
                        'p', 'short summary', 1000, 200, 100, 50, 1000, '{}')
                """
            )
        )
        await session.execute(
            text("UPDATE book_sections SET default_summary_id = 42 WHERE id = 1")
        )
        await session.commit()

    r = await client.get("/api/v1/books/1")
    assert r.status_code == 200, r.text
    s = r.json()["sections"][0]
    assert s["has_summary"] is True
    assert s["default_summary"] is not None
    assert s["default_summary"]["id"] == 42
    assert s["default_summary"]["summary_char_count"] == 200


@pytest.mark.asyncio
async def test_section_brief_default_summary_null_when_no_summary(
    app, client: AsyncClient
):
    await _seed(app, content_md="abc")
    r = await client.get("/api/v1/books/1")
    s = r.json()["sections"][0]
    assert s["has_summary"] is False
    assert s["default_summary"] is None
