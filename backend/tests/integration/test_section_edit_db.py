"""Integration tests for post-save section editing."""

import pytest
import pytest_asyncio

from app.db.models import Book, BookSection, BookStatus
from app.services.section_edit_service import SectionEditService


@pytest_asyncio.fixture
async def book_with_sections(db_session):
    book = Book(
        title="Edit Test",
        file_data=b"test",
        file_hash="edit_test_hash_v11",
        file_format="epub",
        file_size_bytes=100,
        status=BookStatus.PARSED,
    )
    db_session.add(book)
    await db_session.flush()

    for i in range(5):
        s = BookSection(
            book_id=book.id,
            title=f"Section {i + 1}",
            order_index=i,
            depth=0,
            content_md=f"Content for section {i + 1}. " * 100,
        )
        db_session.add(s)
    await db_session.flush()
    return book


@pytest.mark.asyncio
async def test_db_merge(db_session, book_with_sections):
    book = book_with_sections
    svc = SectionEditService(db_session)
    sections = await svc._repo.get_by_book_id(book.id)
    ids = [sections[1].id, sections[2].id]

    result = await svc.db_merge(book.id, ids, "Merged 2+3")
    await db_session.flush()

    updated = await svc._repo.get_by_book_id(book.id)
    assert len(updated) == 4
    merged = next(s for s in updated if s.title == "Merged 2+3")
    assert merged.derived_from == ids


@pytest.mark.asyncio
async def test_db_split(db_session, book_with_sections):
    book = book_with_sections
    svc = SectionEditService(db_session)
    sections = await svc._repo.get_by_book_id(book.id)

    results = await svc.db_split_at_char(book.id, sections[0].id, 500)
    await db_session.flush()

    updated = await svc._repo.get_by_book_id(book.id)
    assert len(updated) == 6


@pytest.mark.asyncio
async def test_db_delete_validates_minimum(db_session, book_with_sections):
    book = book_with_sections
    svc = SectionEditService(db_session)
    sections = await svc._repo.get_by_book_id(book.id)
    all_ids = [s.id for s in sections]

    from app.exceptions import SectionEditError

    with pytest.raises(SectionEditError, match="Cannot delete all"):
        await svc.db_delete(book.id, all_ids)


@pytest.mark.asyncio
async def test_db_delete_partial(db_session, book_with_sections):
    book = book_with_sections
    svc = SectionEditService(db_session)
    sections = await svc._repo.get_by_book_id(book.id)

    count = await svc.db_delete(book.id, [sections[4].id])
    await db_session.flush()
    assert count == 1

    updated = await svc._repo.get_by_book_id(book.id)
    assert len(updated) == 4
