"""FR-29: book response summary_progress counts only summarizable types."""

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed_book(app, sections: list[tuple[str, bool]]) -> int:
    """Seed one book with (section_type, has_summary) tuples."""
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (1, 'B', x'00', 'h1', 'epub', 1, 'COMPLETED')
                """
            )
        )
        next_sum_id = 100
        for i, (st, has_sum) in enumerate(sections, start=1):
            await session.execute(
                text(
                    """
                    INSERT INTO book_sections (id, book_id, title, order_index,
                                               depth, section_type, content_md)
                    VALUES (:id, 1, :t, :idx, 0, :st, 'c')
                    """
                ),
                {"id": i, "t": f"S{i}", "idx": i - 1, "st": st},
            )
            if has_sum:
                await session.execute(
                    text(
                        """
                        INSERT INTO summaries (
                          id, content_type, content_id, book_id, facets_used,
                          prompt_text_sent, model_used, input_char_count,
                          summary_char_count, summary_md, created_at
                        ) VALUES (:id, 'section', :cid, 1, '{}', 'p', 'm',
                                  10, 5, 's', :ts)
                        """
                    ),
                    {
                        "id": next_sum_id,
                        "cid": i,
                        "ts": datetime.utcnow(),
                    },
                )
                await session.execute(
                    text(
                        "UPDATE book_sections SET default_summary_id = :sid WHERE id = :id"
                    ),
                    {"sid": next_sum_id, "id": i},
                )
                next_sum_id += 1
        await session.commit()
    return 1


@pytest.mark.asyncio
async def test_summary_progress_counts_only_summarizable_types(
    app, client: AsyncClient
):
    book_id = await _seed_book(
        app,
        [
            ("copyright", False),
            ("part_header", False),
            ("chapter", True),
            ("chapter", False),
            ("chapter", False),
        ],
    )
    r = await client.get(f"/api/v1/books/{book_id}")
    assert r.status_code == 200
    # v1.5 enriched the payload with pending / summarizable / failed_and_pending
    # while preserving the legacy summarized / total keys. Assert superset.
    progress = r.json()["summary_progress"]
    assert progress["summarized"] == 1
    assert progress["total"] == 3


@pytest.mark.asyncio
async def test_summary_progress_zero_when_no_summarizable_sections(
    app, client: AsyncClient
):
    book_id = await _seed_book(app, [("glossary", False)])
    r = await client.get(f"/api/v1/books/{book_id}")
    assert r.status_code == 200
    progress = r.json()["summary_progress"]
    assert progress["summarized"] == 0
    assert progress["total"] == 0
