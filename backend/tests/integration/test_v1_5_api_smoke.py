"""V4 smoke tests — every new v1.5 endpoint returns the expected shape."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.main import create_app
from app.db.models import Book, BookSection, BookStatus


@pytest_asyncio.fixture
async def smoke_client(engine, test_settings):
    app = create_app()
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.settings = test_settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def smoke_book(db_session):
    book = Book(
        title="Smoke", file_data=b"", file_hash="smoke" * 13,
        file_format="epub", file_size_bytes=0, status=BookStatus.COMPLETED,
        suggested_tags_json=["a", "b"],
    )
    db_session.add(book)
    await db_session.flush()
    section = BookSection(
        book_id=book.id, title="S", order_index=0, depth=0, content_md="content"
    )
    db_session.add(section)
    await db_session.commit()
    await db_session.refresh(book)
    await db_session.refresh(section)
    return book, section


@pytest.mark.asyncio
async def test_get_books_id_includes_new_v1_5_fields(smoke_client, smoke_book):
    book, _ = smoke_book
    r = await smoke_client.get(f"/api/v1/books/{book.id}")
    assert r.status_code == 200
    body = r.json()
    # v1.5 extensions on the book response.
    assert "suggested_tags" in body
    assert body["suggested_tags"] == ["a", "b"]
    assert "summary_progress" in body
    assert isinstance(body["summary_progress"]["summarizable"], int)
    assert "last_summary_failure" in body  # null when no failure, but key present


@pytest.mark.asyncio
async def test_config_models_shape(smoke_client):
    r = await smoke_client.get("/api/v1/config/models")
    assert r.status_code == 200
    body = r.json()
    assert "providers" in body
    assert "claude" in body["providers"]
    assert "codex" in body["providers"]
    # Each provider entry is a list of {id, label}.
    for prov_list in body["providers"].values():
        for entry in prov_list:
            assert "id" in entry
            assert "label" in entry


@pytest.mark.asyncio
async def test_tags_library_list_and_suggest(smoke_client, smoke_book):
    book, _ = smoke_book
    # Seed one tag via the idempotent add endpoint.
    r = await smoke_client.post(
        f"/api/v1/books/{book.id}/tags", json={"name": "alpha"}
    )
    assert r.status_code == 201

    # Library-wide list reports usage.
    r = await smoke_client.get("/api/v1/tags")
    assert r.status_code == 200
    assert any(t["name"] == "alpha" and t["usage_count"] >= 1 for t in r.json()["tags"])

    # Suggest with prefix.
    r = await smoke_client.get("/api/v1/tags/suggest?q=alp")
    assert r.status_code == 200
    assert any(s["name"] == "alpha" for s in r.json()["suggestions"])


@pytest.mark.asyncio
async def test_patch_suggested_tags_reject(smoke_client, smoke_book):
    book, _ = smoke_book
    r = await smoke_client.patch(
        f"/api/v1/books/{book.id}/suggested-tags", json={"reject": ["a"]}
    )
    assert r.status_code == 200
    assert r.json()["suggested_tags"] == ["b"]


@pytest.mark.asyncio
async def test_list_books_tag_filter_short_circuits(smoke_client, smoke_book):
    # No books carry this tag — expect zero results.
    r = await smoke_client.get("/api/v1/books?tag=does-not-exist")
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0
