"""FR-A1.1 — SummarizerService rewrites image placeholders on summary save."""

from __future__ import annotations

import pytest

from app.db.models import Book, BookSection, BookStatus, Image


@pytest.mark.asyncio
async def test_image_map_for_section_returns_filename_to_id(db_session):
    book = Book(
        title="T",
        file_data=b"",
        file_hash="x" * 64,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.flush()
    section = BookSection(
        book_id=book.id, title="ch", order_index=0, depth=0, content_md="x"
    )
    db_session.add(section)
    await db_session.flush()
    image = Image(
        section_id=section.id, data=b"fake", mime_type="image/png", filename="pic.png"
    )
    db_session.add(image)
    await db_session.commit()
    await db_session.refresh(image)

    from unittest.mock import MagicMock

    from app.services.summarizer.summarizer_service import SummarizerService

    svc = SummarizerService.__new__(SummarizerService)
    svc.db = db_session
    svc.config = MagicMock()
    image_map = await svc._image_map_for_section(section.id)
    assert image_map == {"pic.png": image.id}


@pytest.mark.asyncio
async def test_image_map_for_book_aggregates_across_sections(db_session):
    book = Book(
        title="T",
        file_data=b"",
        file_hash="y" * 64,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.flush()
    s1 = BookSection(
        book_id=book.id, title="a", order_index=0, depth=0, content_md=""
    )
    s2 = BookSection(
        book_id=book.id, title="b", order_index=1, depth=0, content_md=""
    )
    db_session.add_all([s1, s2])
    await db_session.flush()
    i1 = Image(section_id=s1.id, data=b"", mime_type="image/png", filename="a.png")
    i2 = Image(section_id=s2.id, data=b"", mime_type="image/png", filename="b.png")
    db_session.add_all([i1, i2])
    await db_session.commit()
    await db_session.refresh(i1)
    await db_session.refresh(i2)

    from unittest.mock import MagicMock

    from app.services.summarizer.summarizer_service import SummarizerService

    svc = SummarizerService.__new__(SummarizerService)
    svc.db = db_session
    svc.config = MagicMock()
    image_map = await svc._image_map_for_book(book.id)
    assert image_map == {"a.png": i1.id, "b.png": i2.id}


def test_from_placeholder_strip_used_by_section_summary():
    # Pure-function smoke test on the rewrite behavior invoked by the
    # section summary save path.
    from app.services.parser.image_url_rewrite import from_placeholder

    md = "intro __IMG_PLACEHOLDER__:pic.png__ENDIMG__ done"
    out = from_placeholder(md, {"pic.png": 42}, on_missing="strip")
    assert "/api/v1/images/42" in out
    assert "__IMG_PLACEHOLDER__" not in out


def test_from_placeholder_strip_drops_missing_filenames():
    from app.services.parser.image_url_rewrite import from_placeholder

    md = "intro ![alt](__IMG_PLACEHOLDER__:deleted.png__ENDIMG__) outro"
    out = from_placeholder(md, {}, on_missing="strip")
    assert "__IMG_PLACEHOLDER__" not in out
    assert "deleted.png" not in out
    assert "intro" in out
    assert "outro" in out
