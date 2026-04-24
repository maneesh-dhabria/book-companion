"""FR-E4.1/2/3 — AI tag suggestions injected via book-summary JSON schema."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa

from app.db.models import Book, BookStatus, Tag, Taggable
from app.services.summarizer.summarizer_service import SummarizerService


class _FakeResponse:
    def __init__(self, structured):
        self.structured_output = structured
        self.content = ""
        self.input_tokens = 0
        self.output_tokens = 0


@pytest.mark.asyncio
async def test_existing_book_tags_returns_names(db_session):
    book = Book(
        title="T", file_data=b"", file_hash="1" * 64, file_format="epub",
        file_size_bytes=0, status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.flush()
    tag = Tag(name="strategy")
    db_session.add(tag)
    await db_session.flush()
    db_session.add(Taggable(tag_id=tag.id, taggable_type="book", taggable_id=book.id))
    await db_session.commit()
    await db_session.refresh(book)

    svc = SummarizerService.__new__(SummarizerService)
    svc.db = db_session
    names = await svc._existing_book_tags(book.id)
    assert names == ["strategy"]


def test_extract_suggested_tags_from_structured_output():
    svc = SummarizerService.__new__(SummarizerService)
    svc.config = MagicMock()
    resp = _FakeResponse({"suggested_tags": ["strategy", "porter"]})
    assert svc._extract_suggested_tags(resp) == ["strategy", "porter"]


def test_extract_suggested_tags_filters_non_strings():
    svc = SummarizerService.__new__(SummarizerService)
    resp = _FakeResponse({"suggested_tags": ["a", 123, None, "b"]})
    assert svc._extract_suggested_tags(resp) == ["a", "b"]


def test_extract_suggested_tags_fallback_to_json_body():
    svc = SummarizerService.__new__(SummarizerService)
    resp = _FakeResponse(None)
    resp.content = '{"summary_md": "x", "suggested_tags": ["a"]}'
    assert svc._extract_suggested_tags(resp) == ["a"]


def test_extract_suggested_tags_returns_empty_on_missing():
    svc = SummarizerService.__new__(SummarizerService)
    resp = _FakeResponse({"summary_md": "x"})
    assert svc._extract_suggested_tags(resp) == []


def test_extract_summary_text_prefers_structured_output():
    svc = SummarizerService.__new__(SummarizerService)
    resp = _FakeResponse({"summary_md": "Structured!"})
    resp.content = "something else"
    assert svc._extract_summary_text(resp) == "Structured!"


@pytest.mark.asyncio
async def test_book_suggested_tags_column_updates(db_session):
    """Verify we can write to suggested_tags_json as the update will do."""
    book = Book(
        title="T", file_data=b"", file_hash="2" * 64, file_format="epub",
        file_size_bytes=0, status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)
    await db_session.execute(
        sa.update(Book).where(Book.id == book.id).values(
            suggested_tags_json=["porter", "value-chain"]
        )
    )
    await db_session.commit()
    await db_session.refresh(book)
    assert book.suggested_tags_json == ["porter", "value-chain"]
