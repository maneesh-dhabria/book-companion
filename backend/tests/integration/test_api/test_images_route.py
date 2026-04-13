"""Integration tests for GET /api/v1/images/{image_id}."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def _insert_image(db_url: str) -> int:
    """Insert book + section + image directly via SQL; return image id."""
    eng = create_async_engine(db_url, connect_args={"check_same_thread": False})
    factory = async_sessionmaker(eng, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO books (title, file_data, file_hash, file_format, "
                "file_size_bytes, status) VALUES ('t', x'78', 'h', 'epub', 1, 'PARSED')"
            )
        )
        book_id = (await session.execute(text("SELECT last_insert_rowid()"))).scalar()
        await session.execute(
            text(
                "INSERT INTO book_sections (book_id, title, order_index, depth, "
                "content_md) VALUES (:bid, 's', 0, 1, 'x')"
            ),
            {"bid": book_id},
        )
        section_id = (await session.execute(text("SELECT last_insert_rowid()"))).scalar()
        await session.execute(
            text(
                "INSERT INTO images (section_id, data, mime_type, filename) "
                "VALUES (:sid, x'89504E470D0A1A0A', 'image/png', 'cover.png')"
            ),
            {"sid": section_id},
        )
        image_id = (await session.execute(text("SELECT last_insert_rowid()"))).scalar()
        await session.commit()
    await eng.dispose()
    return image_id


@pytest.mark.asyncio
async def test_get_image_returns_bytes(client: AsyncClient, app):
    db_url = app.state.settings.database.url
    image_id = await _insert_image(db_url)

    r = await client.get(f"/api/v1/images/{image_id}")
    assert r.status_code == 200
    assert r.content == b"\x89PNG\r\n\x1a\n"
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.asyncio
async def test_get_image_404_when_missing(client: AsyncClient):
    r = await client.get("/api/v1/images/99999")
    assert r.status_code == 404
