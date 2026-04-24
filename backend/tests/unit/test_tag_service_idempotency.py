"""FR-E1.4 (normalization) + FR-E2.5 (idempotent add_tag) coverage."""

from __future__ import annotations

import pytest

from app.db.models import Book, BookStatus
from app.services.tag_service import TagError, TagService, normalize_tag_name


def test_normalize_strips_leading_trailing():
    assert normalize_tag_name("  strategy  ") == "strategy"


def test_normalize_collapses_internal_whitespace():
    assert normalize_tag_name("competitive  advantage") == "competitive advantage"


def test_normalize_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        normalize_tag_name("   ")


def test_normalize_rejects_none():
    with pytest.raises(ValueError, match="empty"):
        normalize_tag_name(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_add_tag_idempotent_returns_existing(db_session):
    book = Book(
        title="T",
        file_data=b"",
        file_hash="a" * 64,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)

    svc = TagService(db_session)
    tag1 = await svc.add_tag("book", book.id, "strategy")
    tag2 = await svc.add_tag("book", book.id, "strategy")
    assert tag1.id == tag2.id


@pytest.mark.asyncio
async def test_add_tag_normalizes_whitespace(db_session):
    book = Book(
        title="T",
        file_data=b"",
        file_hash="b" * 64,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)

    svc = TagService(db_session)
    t1 = await svc.add_tag("book", book.id, "  competitive  advantage  ")
    t2 = await svc.add_tag("book", book.id, "competitive advantage")
    assert t1.id == t2.id
    assert t1.name == "competitive advantage"


@pytest.mark.asyncio
async def test_add_tag_rejects_empty_name(db_session):
    book = Book(
        title="T",
        file_data=b"",
        file_hash="c" * 64,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)

    svc = TagService(db_session)
    with pytest.raises(TagError, match="empty"):
        await svc.add_tag("book", book.id, "   ")


@pytest.mark.asyncio
async def test_add_tag_nocase_dedup(db_session):
    """Strategy and STRATEGY collapse to the same row via NOCASE collation."""
    book = Book(
        title="T",
        file_data=b"",
        file_hash="d" * 64,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)

    svc = TagService(db_session)
    t1 = await svc.add_tag("book", book.id, "strategy")
    t2 = await svc.add_tag("book", book.id, "STRATEGY")
    assert t1.id == t2.id
