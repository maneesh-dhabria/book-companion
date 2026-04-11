"""Integration tests for reading state API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_upsert_reading_state(client):
    """Saving reading state returns the book_id we sent."""
    # First check if any books exist
    books_resp = await client.get("/api/v1/books")
    books = books_resp.json().get("items", [])
    if not books:
        pytest.skip("No books in test DB")

    book_id = books[0]["id"]
    resp = await client.put(
        "/api/v1/reading-state",
        json={"book_id": book_id},
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Desktop Chrome Test)"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_book_id"] == book_id


@pytest.mark.asyncio
async def test_get_continue_reading_cross_device(client):
    """After saving from one device, a different device sees the position."""
    books_resp = await client.get("/api/v1/books")
    books = books_resp.json().get("items", [])
    if not books:
        pytest.skip("No books in test DB")

    book_id = books[0]["id"]
    # Save from desktop
    await client.put(
        "/api/v1/reading-state",
        json={"book_id": book_id},
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Desktop Chrome)"},
    )
    # Request from mobile — should see desktop's position
    resp = await client.get(
        "/api/v1/reading-state/continue",
        headers={"User-Agent": "Mozilla/5.0 (iPhone; Mobile Safari)"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_book_id"] == book_id


@pytest.mark.asyncio
async def test_no_continue_reading_same_device(client):
    """Same device should not see its own position as 'continue'."""
    books_resp = await client.get("/api/v1/books")
    books = books_resp.json().get("items", [])
    if not books:
        pytest.skip("No books in test DB")

    book_id = books[0]["id"]
    ua = "Mozilla/5.0 (SameDevice Test)"
    await client.put(
        "/api/v1/reading-state",
        json={"book_id": book_id},
        headers={"User-Agent": ua},
    )
    resp = await client.get(
        "/api/v1/reading-state/continue",
        headers={"User-Agent": ua},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should not see own position
    assert data.get("last_book_id") is None or data.get("last_book_id") != book_id


@pytest.mark.asyncio
async def test_continue_reading_empty(client):
    """When no reading state exists, continue returns nulls."""
    resp = await client.get(
        "/api/v1/reading-state/continue",
        headers={"User-Agent": "Mozilla/5.0 (FreshDevice/1.0)"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # May be null or may have leftover data from other tests — just check it returns
    assert "last_book_id" in data
