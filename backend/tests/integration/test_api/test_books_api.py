"""Integration tests for books API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_books(client):
    resp = await client.get("/api/v1/books")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["items"], list)
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert "pages" in data


@pytest.mark.asyncio
async def test_list_books_with_pagination(client):
    resp = await client.get("/api/v1/books?page=1&per_page=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["per_page"] == 5


@pytest.mark.asyncio
async def test_get_book_not_found(client):
    resp = await client.get("/api/v1/books/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_book_not_found(client):
    resp = await client.delete("/api/v1/books/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_check_duplicate_no_match(client):
    resp = await client.post(
        "/api/v1/books/check-duplicate",
        json={"file_hash": "sha256:nonexistent"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_duplicate"] is False
    assert data["existing_book_id"] is None


@pytest.mark.asyncio
async def test_get_cover_not_found(client):
    resp = await client.get("/api/v1/books/99999/cover")
    assert resp.status_code == 404
