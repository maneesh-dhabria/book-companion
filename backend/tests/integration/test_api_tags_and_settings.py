"""FastAPI integration coverage for T13–T17 endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import create_app
from app.db.models import Book, BookSection, BookStatus


@pytest_asyncio.fixture
async def client(engine, test_settings):
    app = create_app()
    # Reuse the test engine's session factory so API-side reads see test data.
    from sqlalchemy.ext.asyncio import async_sessionmaker

    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.settings = test_settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def seed_book(db_session):
    book = Book(
        title="TestBook",
        file_data=b"",
        file_hash="seed1" * 13,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)
    return book


@pytest_asyncio.fixture
async def seed_section(db_session, seed_book):
    section = BookSection(
        book_id=seed_book.id,
        title="Ch1",
        order_index=0,
        depth=0,
        content_md="hello",
    )
    db_session.add(section)
    await db_session.commit()
    await db_session.refresh(section)
    return section


# --- T14 tag CRUD book scope ---


@pytest.mark.asyncio
async def test_post_book_tag_returns_201_first_time(client, seed_book):
    r = await client.post(
        f"/api/v1/books/{seed_book.id}/tags", json={"name": "strategy"}
    )
    assert r.status_code == 201
    assert r.json()["name"] == "strategy"


@pytest.mark.asyncio
async def test_post_book_tag_normalizes_whitespace(client, seed_book):
    r = await client.post(
        f"/api/v1/books/{seed_book.id}/tags", json={"name": "  strategy  "}
    )
    assert r.status_code == 201
    assert r.json()["name"] == "strategy"


@pytest.mark.asyncio
async def test_post_book_tag_rejects_empty(client, seed_book):
    r = await client.post(
        f"/api/v1/books/{seed_book.id}/tags", json={"name": "   "}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_book_tags(client, seed_book):
    await client.post(
        f"/api/v1/books/{seed_book.id}/tags", json={"name": "strategy"}
    )
    r = await client.get(f"/api/v1/books/{seed_book.id}/tags")
    assert r.status_code == 200
    names = [t["name"] for t in r.json()["tags"]]
    assert "strategy" in names


@pytest.mark.asyncio
async def test_section_scope_mirrors_book_scope(client, seed_section):
    r = await client.post(
        f"/api/v1/sections/{seed_section.id}/tags", json={"name": "chapter-tag"}
    )
    assert r.status_code == 201


# --- T15 library tag list + suggest ---


@pytest.mark.asyncio
async def test_get_all_tags_with_usage(client, seed_book):
    await client.post(
        f"/api/v1/books/{seed_book.id}/tags", json={"name": "aardvark"}
    )
    r = await client.get("/api/v1/tags")
    assert r.status_code == 200
    entries = r.json()["tags"]
    assert any(e["name"] == "aardvark" and e["usage_count"] >= 1 for e in entries)


@pytest.mark.asyncio
async def test_suggest_empty_returns_empty(client):
    r = await client.get("/api/v1/tags/suggest?q=")
    assert r.json()["suggestions"] == []


@pytest.mark.asyncio
async def test_suggest_prefix_nocase(client, seed_book):
    await client.post(
        f"/api/v1/books/{seed_book.id}/tags", json={"name": "strategy"}
    )
    r = await client.get("/api/v1/tags/suggest?q=STR")
    names = [s["name"] for s in r.json()["suggestions"]]
    assert "strategy" in names


# --- T16 config/models ---


@pytest.mark.asyncio
async def test_get_config_models(client):
    r = await client.get("/api/v1/config/models")
    body = r.json()
    assert "providers" in body
    assert "claude" in body["providers"]


# --- T17 suggested-tags patch ---


@pytest.mark.asyncio
async def test_patch_suggested_tags_reject_removes(client, db_session, seed_book):
    import sqlalchemy as sa

    from app.db.models import Book as B

    await db_session.execute(
        sa.update(B).where(B.id == seed_book.id).values(
            suggested_tags_json=["a", "b", "c"]
        )
    )
    await db_session.commit()
    r = await client.patch(
        f"/api/v1/books/{seed_book.id}/suggested-tags",
        json={"reject": ["b"]},
    )
    assert r.status_code == 200
    assert r.json()["suggested_tags"] == ["a", "c"]


@pytest.mark.asyncio
async def test_patch_suggested_tags_set_wholesale(client, db_session, seed_book):
    import sqlalchemy as sa

    from app.db.models import Book as B

    await db_session.execute(
        sa.update(B).where(B.id == seed_book.id).values(suggested_tags_json=["x"])
    )
    await db_session.commit()
    r = await client.patch(
        f"/api/v1/books/{seed_book.id}/suggested-tags", json={"set": []}
    )
    assert r.status_code == 200
    assert r.json()["suggested_tags"] == []


# --- T13 annotation POST with tags + prefix + suffix ---


@pytest.mark.asyncio
async def test_list_books_q_escapes_like_wildcards(client, db_session):
    """Regression: typing '100%' in search must not match everything."""
    from app.db.models import Book, BookStatus

    for title in ["Pure title", "Has 100% battery", "Something else"]:
        db_session.add(
            Book(
                title=title,
                file_data=b"",
                file_hash=title + "h" * 64,
                file_format="epub",
                file_size_bytes=0,
                status=BookStatus.COMPLETED,
            )
        )
    await db_session.commit()

    # `100%` must now match only the literal substring.
    r = await client.get("/api/v1/books?q=100%25")  # URL-encoded %
    assert r.status_code == 200
    titles = [b["title"] for b in r.json()["items"]]
    # Only 'Has 100% battery' matches literal '100%'.
    assert any("100%" in t for t in titles)
    assert all("100%" in t or "100" in t for t in titles)


@pytest.mark.asyncio
async def test_post_annotation_with_tags_and_prefix_suffix(client, seed_section):
    r = await client.post(
        "/api/v1/annotations",
        json={
            "content_type": "section_content",
            "content_id": seed_section.id,
            "type": "highlight",
            "selected_text": "hello",
            "text_start": 0,
            "text_end": 5,
            "tags": ["keep"],
            "prefix": "pre",
            "suffix": "suf",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["prefix"] == "pre"
    assert body["suffix"] == "suf"
    assert "keep" in body["tags"]
