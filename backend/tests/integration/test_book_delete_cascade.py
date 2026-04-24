"""FR-E1.3: BookService.delete_book cascades book + section taggables."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.config import Settings
from app.db.models import Book, BookSection, BookStatus
from app.services.book_service import BookService
from app.services.tag_service import TagService


@pytest.mark.asyncio
async def test_delete_book_cascades_section_and_book_tags(db_session):
    book = Book(
        title="Test",
        file_data=b"",
        file_hash="deadbeef" * 8,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.flush()
    section1 = BookSection(
        book_id=book.id, title="Ch1", order_index=0, depth=0,
        content_md="content1", section_type="chapter",
    )
    section2 = BookSection(
        book_id=book.id, title="Ch2", order_index=1, depth=0,
        content_md="content2", section_type="chapter",
    )
    db_session.add_all([section1, section2])
    await db_session.commit()
    await db_session.refresh(book)
    await db_session.refresh(section1)
    await db_session.refresh(section2)
    section_ids = [section1.id, section2.id]

    tag_service = TagService(db_session)
    book_service = BookService(db=db_session, config=Settings())

    await tag_service.add_tag("book", book.id, "strategy")
    for sid in section_ids:
        await tag_service.add_tag("section", sid, "chapter-tag")
    await db_session.commit()

    res = await db_session.execute(text("SELECT COUNT(*) FROM taggables"))
    assert res.scalar() == 3

    await book_service.delete_book(book.id)

    res = await db_session.execute(
        text(
            "SELECT COUNT(*) FROM taggables WHERE "
            "(taggable_type='book' AND taggable_id=:bid) "
            "OR (taggable_type='section' AND taggable_id IN (:s1, :s2))"
        ),
        {"bid": book.id, "s1": section_ids[0], "s2": section_ids[1]},
    )
    assert res.scalar() == 0

    # Orphan Tag rows may remain — app-level cascade doesn't reap them.
    # A doctor --orphan-tags CLI will do that in T36.
    res = await db_session.execute(text("SELECT COUNT(*) FROM tags"))
    assert res.scalar() >= 2
