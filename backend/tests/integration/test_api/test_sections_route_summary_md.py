"""FR-19..FR-22: section response includes summary_md + is_summarizable."""

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed_book_with_section(
    app, *, section_type: str = "chapter", with_summary: bool = False,
    dangling_default: bool = False,
) -> tuple[int, int]:
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (1, 'Book', x'00', 'h1', 'epub', 1, 'COMPLETED')
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO book_sections (id, book_id, title, order_index, depth,
                                           section_type, content_md)
                VALUES (1, 1, 'Title', 0, 0, :st, 'content')
                """
            ),
            {"st": section_type},
        )
        if with_summary:
            await session.execute(
                text(
                    """
                    INSERT INTO summaries (
                      id, content_type, content_id, book_id, facets_used,
                      prompt_text_sent, model_used, input_char_count,
                      summary_char_count, summary_md, created_at
                    ) VALUES (
                      10, 'section', 1, 1, '{}', 'p', 'm', 100, 50,
                      'Pithy markdown summary.', :ts
                    )
                    """
                ),
                {"ts": datetime.utcnow()},
            )
            await session.execute(
                text("UPDATE book_sections SET default_summary_id = 10 WHERE id = 1")
            )
        elif dangling_default:
            await session.execute(
                text(
                    """
                    INSERT INTO summaries (
                      id, content_type, content_id, book_id, facets_used,
                      prompt_text_sent, model_used, input_char_count,
                      summary_char_count, summary_md, created_at
                    ) VALUES (
                      999, 'section', 1, 1, '{}', 'p', 'm', 10, 5, 's', :ts
                    )
                    """
                ),
                {"ts": datetime.utcnow()},
            )
            await session.execute(
                text("UPDATE book_sections SET default_summary_id = 999 WHERE id = 1")
            )
            await session.execute(text("DELETE FROM summaries WHERE id = 999"))
        await session.commit()
    return 1, 1


@pytest.mark.asyncio
async def test_section_response_includes_summary_md(app, client: AsyncClient):
    book_id, section_id = await _seed_book_with_section(
        app, section_type="chapter", with_summary=True
    )
    r = await client.get(
        f"/api/v1/books/{book_id}/sections/{section_id}?include_content=true"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["default_summary"] is not None
    assert body["default_summary"]["summary_md"] == "Pithy markdown summary."
    assert body["is_summarizable"] is True


@pytest.mark.asyncio
async def test_section_response_is_summarizable_false_for_copyright(
    app, client: AsyncClient
):
    book_id, section_id = await _seed_book_with_section(
        app, section_type="copyright"
    )
    r = await client.get(f"/api/v1/books/{book_id}/sections/{section_id}")
    assert r.status_code == 200
    assert r.json()["is_summarizable"] is False


@pytest.mark.asyncio
async def test_section_response_handles_dangling_default_summary_id(
    app, client: AsyncClient
):
    book_id, section_id = await _seed_book_with_section(
        app, section_type="chapter", dangling_default=True
    )
    r = await client.get(f"/api/v1/books/{book_id}/sections/{section_id}")
    assert r.status_code == 200
    assert r.json()["default_summary"] is None
