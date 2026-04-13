"""Integration test for BookService._substitute_image_urls.

Builds a Book + Section (content_md with placeholders) + Image directly, then
calls the substitution pass. Verifies placeholders become /api/v1/images/{id}.
"""

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.models import Book, BookSection, BookStatus, Image
from app.services.book_service import BookService


@pytest.mark.asyncio
async def test_substitute_image_urls_replaces_placeholders(db_session):
    book = Book(
        title="t",
        file_data=b"x",
        file_hash="h",
        file_format="epub",
        file_size_bytes=1,
        status=BookStatus.PARSED,
    )
    db_session.add(book)
    await db_session.flush()

    section = BookSection(
        book_id=book.id,
        title="s",
        order_index=0,
        depth=1,
        content_md="before ![a](__IMG_PLACEHOLDER__:cover.png__) after",
    )
    db_session.add(section)
    await db_session.flush()

    image = Image(
        section_id=section.id,
        data=b"\x89PNG\r\n\x1a\n",
        mime_type="image/png",
        filename="OEBPS/cover.png",
    )
    db_session.add(image)
    await db_session.flush()

    service = BookService(db_session, Settings())
    await service._substitute_image_urls(book.id)

    refreshed = (
        await db_session.execute(select(BookSection).where(BookSection.id == section.id))
    ).scalar_one()
    assert f"/api/v1/images/{image.id}" in refreshed.content_md
    assert "__IMG_PLACEHOLDER__" not in refreshed.content_md


@pytest.mark.asyncio
async def test_substitute_image_urls_leaves_unknown(db_session):
    book = Book(
        title="t",
        file_data=b"x",
        file_hash="h2",
        file_format="epub",
        file_size_bytes=1,
        status=BookStatus.PARSED,
    )
    db_session.add(book)
    await db_session.flush()
    section = BookSection(
        book_id=book.id,
        title="s",
        order_index=0,
        depth=1,
        content_md="![](__IMG_PLACEHOLDER__:missing.png__)",
    )
    db_session.add(section)
    await db_session.flush()

    service = BookService(db_session, Settings())
    await service._substitute_image_urls(book.id)

    refreshed = (
        await db_session.execute(select(BookSection).where(BookSection.id == section.id))
    ).scalar_one()
    assert "__IMG_PLACEHOLDER__:missing.png__" in refreshed.content_md
