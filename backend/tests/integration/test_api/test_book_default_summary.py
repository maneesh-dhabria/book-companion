"""T5: GET /api/v1/books/{id} embeds default_summary with summary_md (FR-02, SD22)."""

import pytest
from httpx import AsyncClient

from app.db.models import Book, BookStatus, Summary, SummaryContentType


async def _seed_book(app, *, with_summary: bool) -> int:
    factory = app.state.session_factory
    async with factory() as session:
        book = Book(
            title="DS Test",
            file_data=b"",
            file_hash=("ds-with" if with_summary else "ds-without"),
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.COMPLETED,
        )
        session.add(book)
        await session.commit()
        if with_summary:
            s = Summary(
                content_type=SummaryContentType.BOOK,
                content_id=book.id,
                book_id=book.id,
                facets_used={},
                prompt_text_sent="p",
                model_used="sonnet",
                input_char_count=10,
                summary_char_count=42,
                summary_md="# Book Summary\n\nKey takeaways.",
            )
            session.add(s)
            await session.flush()
            book.default_summary_id = s.id
            await session.commit()
        return book.id


@pytest.mark.asyncio
async def test_get_book_includes_default_summary_when_present(client: AsyncClient, app):
    book_id = await _seed_book(app, with_summary=True)
    r = await client.get(f"/api/v1/books/{book_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    summary = body.get("default_summary")
    assert summary is not None
    assert "summary_md" in summary
    assert isinstance(summary["summary_md"], str) and len(summary["summary_md"]) > 0


@pytest.mark.asyncio
async def test_get_book_default_summary_is_null_when_absent(client: AsyncClient, app):
    book_id = await _seed_book(app, with_summary=False)
    r = await client.get(f"/api/v1/books/{book_id}")
    assert r.status_code == 200, r.text
    assert r.json().get("default_summary") is None
