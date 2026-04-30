"""T15 / FR-B18: GET /api/v1/books/{id}/sections/edit-impact."""

import pytest

from app.db.models import (
    Book,
    BookSection,
    BookStatus,
    Summary,
    SummaryContentType,
)


async def _seed_book_with_summaries(app, *, summaries_for_sections: int) -> dict:
    """Insert a book with 4 sections; the first ``summaries_for_sections``
    have a non-stale Summary; the book has a default_summary_id."""
    factory = app.state.session_factory
    async with factory() as session:
        book = Book(
            title="Edit Impact",
            file_data=b"",
            file_hash="impact-1",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.COMPLETED,
        )
        session.add(book)
        await session.commit()
        # Sections
        section_ids: list[int] = []
        for i in range(4):
            sec = BookSection(
                book_id=book.id,
                order_index=i,
                title=f"Sec {i}",
                content_md=f"Body of section {i}",
                section_type="chapter",
                content_token_count=10,
            )
            session.add(sec)
            await session.flush()
            section_ids.append(sec.id)
        # Section-level summaries for the first N
        section_summary_ids: list[int] = []
        for sid in section_ids[:summaries_for_sections]:
            s = Summary(
                content_type=SummaryContentType.SECTION,
                content_id=sid,
                book_id=book.id,
                facets_used={},
                prompt_text_sent="prompt",
                model_used="sonnet",
                input_char_count=100,
                summary_char_count=20,
                summary_md="summary text",
            )
            session.add(s)
            await session.flush()
            section_summary_ids.append(s.id)
        # Book-level default summary
        book_summary = Summary(
            content_type=SummaryContentType.BOOK,
            content_id=book.id,
            book_id=book.id,
            facets_used={},
            prompt_text_sent="prompt",
            model_used="sonnet",
            input_char_count=400,
            summary_char_count=50,
            summary_md="book summary",
        )
        session.add(book_summary)
        await session.flush()
        book.default_summary_id = book_summary.id
        await session.commit()
        return {
            "book_id": book.id,
            "section_ids": section_ids,
            "section_summary_ids": section_summary_ids,
            "book_summary_id": book_summary.id,
        }


@pytest.mark.asyncio
async def test_edit_impact_with_summarized_sections(app, client):
    seed = await _seed_book_with_summaries(app, summaries_for_sections=2)
    target_section_ids = seed["section_ids"][:2]
    r = await client.get(
        f"/api/v1/books/{seed['book_id']}/sections/edit-impact",
        params={"section_ids": ",".join(str(i) for i in target_section_ids)},
    )
    assert r.status_code == 200
    body = r.json()
    assert sorted(body["summaries_to_invalidate"]) == sorted(seed["section_summary_ids"])
    assert body["invalidate_book_summary"] is True
    assert body["summarized_section_count"] == 2


@pytest.mark.asyncio
async def test_edit_impact_no_summaries(app, client):
    seed = await _seed_book_with_summaries(app, summaries_for_sections=0)
    # Drop the book-level default since the test seeds it; invalidation bool
    # depends on default_summary_id being set, but no section-level summaries
    # exist so nothing is affected anyway.
    target_ids = seed["section_ids"][:2]
    r = await client.get(
        f"/api/v1/books/{seed['book_id']}/sections/edit-impact",
        params={"section_ids": ",".join(str(i) for i in target_ids)},
    )
    body = r.json()
    assert body["summarized_section_count"] == 0
    assert body["invalidate_book_summary"] is False
    assert body["summaries_to_invalidate"] == []


@pytest.mark.asyncio
async def test_edit_impact_unaffected_sections(app, client):
    """Editing sections that have no summary should report zero impact even
    when other sections in the book are summarized."""
    seed = await _seed_book_with_summaries(app, summaries_for_sections=2)
    untouched_ids = seed["section_ids"][2:]  # sections without summaries
    r = await client.get(
        f"/api/v1/books/{seed['book_id']}/sections/edit-impact",
        params={"section_ids": ",".join(str(i) for i in untouched_ids)},
    )
    body = r.json()
    assert body["summarized_section_count"] == 0
    assert body["invalidate_book_summary"] is False
    assert body["summaries_to_invalidate"] == []


@pytest.mark.asyncio
async def test_edit_impact_book_404(client):
    r = await client.get(
        "/api/v1/books/999999/sections/edit-impact",
        params={"section_ids": "1,2"},
    )
    assert r.status_code == 404
