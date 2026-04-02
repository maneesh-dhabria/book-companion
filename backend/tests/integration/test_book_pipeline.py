"""Integration tests for the full book pipeline (parse -> store -> verify).

These tests commit to the real test DB. Each test cleans up after itself."""

import pytest
from sqlalchemy import select, text

from app.db.models import Book, BookSection, BookStatus


async def _cleanup_all_books(db_session):
    """Remove all books from test DB."""
    await db_session.execute(text("DELETE FROM search_index"))
    await db_session.execute(text("DELETE FROM concept_sections"))
    await db_session.execute(text("DELETE FROM concepts"))
    await db_session.execute(text("DELETE FROM eval_traces"))
    await db_session.execute(text("DELETE FROM images"))
    await db_session.execute(text("DELETE FROM book_sections"))
    await db_session.execute(text("DELETE FROM processing_jobs"))
    await db_session.execute(text("DELETE FROM external_references"))
    await db_session.execute(text("DELETE FROM book_authors"))
    await db_session.execute(text("DELETE FROM books"))
    await db_session.execute(text("DELETE FROM authors"))
    await db_session.commit()


@pytest.fixture(autouse=True)
async def clean_db(db_session):
    """Clean DB before and after each test."""
    await _cleanup_all_books(db_session)
    yield
    await _cleanup_all_books(db_session)


@pytest.mark.asyncio
async def test_full_epub_pipeline(db_session, sample_epub_path, test_settings):
    from app.services.book_service import BookService

    service = BookService(db=db_session, config=test_settings)
    book = await service.add_book(str(sample_epub_path))

    assert book.id is not None
    assert book.status == BookStatus.PARSED
    assert book.title
    result = await db_session.execute(
        select(BookSection).where(BookSection.book_id == book.id)
    )
    sections = result.scalars().all()
    assert len(sections) >= 5  # Art of War has 13+ sections


@pytest.mark.asyncio
async def test_full_pdf_pipeline(db_session, sample_pdf_path, test_settings):
    from app.services.book_service import BookService

    service = BookService(db=db_session, config=test_settings)
    book = await service.add_book(str(sample_pdf_path))
    assert book.status == BookStatus.PARSED


@pytest.mark.asyncio
async def test_duplicate_detection(db_session, sample_epub_path, test_settings):
    from app.services.book_service import BookService

    service = BookService(db=db_session, config=test_settings)
    await service.add_book(str(sample_epub_path))
    with pytest.raises(Exception, match="already exists"):
        await service.add_book(str(sample_epub_path))


@pytest.mark.asyncio
async def test_re_import_with_force(db_session, sample_epub_path, test_settings):
    from app.services.book_service import BookService

    service = BookService(db=db_session, config=test_settings)
    book1 = await service.add_book(str(sample_epub_path))
    book2 = await service.add_book(str(sample_epub_path), force=True)
    assert book2.id == book1.id  # Same book, re-imported


@pytest.mark.asyncio
async def test_delete_cascades_all_data(db_session, sample_epub_path, test_settings):
    from app.services.book_service import BookService

    service = BookService(db=db_session, config=test_settings)
    book = await service.add_book(str(sample_epub_path))
    book_id = book.id
    await service.delete_book(book_id)
    result = await db_session.execute(
        select(BookSection).where(BookSection.book_id == book_id)
    )
    assert result.scalars().all() == []
