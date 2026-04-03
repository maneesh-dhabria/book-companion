"""Integration tests for database operations."""

import pytest
from sqlalchemy import select

from app.db.models import Author, Book, BookSection, BookStatus


@pytest.mark.asyncio
async def test_create_book_with_author(db_session):
    author = Author(name="Sun Tzu")
    db_session.add(author)
    await db_session.flush()

    book = Book(
        title="The Art of War",
        file_data=b"fake epub content",
        file_hash="abc123def456",
        file_format="epub",
        file_size_bytes=1024,
        status=BookStatus.PARSED,
    )
    book.authors.append(author)
    db_session.add(book)
    await db_session.flush()

    result = await db_session.execute(select(Book).where(Book.id == book.id))
    fetched = result.scalar_one()
    assert fetched.title == "The Art of War"
    assert fetched.status == BookStatus.PARSED


@pytest.mark.asyncio
async def test_create_book_sections(db_session):
    book = Book(
        title="Test Book",
        file_data=b"test",
        file_hash="unique_hash_001",
        file_format="epub",
        file_size_bytes=100,
    )
    db_session.add(book)
    await db_session.flush()

    sections = [
        BookSection(
            book_id=book.id,
            title=f"Chapter {i}",
            order_index=i,
            depth=1,
            content_md=f"Content for chapter {i}",
            content_token_count=100,
        )
        for i in range(3)
    ]
    db_session.add_all(sections)
    await db_session.flush()

    result = await db_session.execute(
        select(BookSection)
        .where(BookSection.book_id == book.id)
        .order_by(BookSection.order_index)
    )
    fetched = result.scalars().all()
    assert len(fetched) == 3
    assert fetched[0].title == "Chapter 0"


@pytest.mark.asyncio
async def test_cascade_delete_book(db_session):
    book = Book(
        title="Delete Me",
        file_data=b"delete",
        file_hash="delete_hash_001",
        file_format="pdf",
        file_size_bytes=50,
    )
    db_session.add(book)
    await db_session.flush()

    section = BookSection(
        book_id=book.id, title="Ch1", order_index=0, depth=0
    )
    db_session.add(section)
    await db_session.flush()

    await db_session.delete(book)
    await db_session.flush()

    result = await db_session.execute(
        select(BookSection).where(BookSection.book_id == book.id)
    )
    assert result.scalars().all() == []
