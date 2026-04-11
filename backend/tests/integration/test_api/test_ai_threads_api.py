"""Integration tests for the AI Threads API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_threads_for_nonexistent_book(client: AsyncClient):
    resp = await client.get("/api/v1/books/99999/ai-threads")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_thread_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/ai-threads/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_thread_not_found(client: AsyncClient):
    resp = await client.delete("/api/v1/ai-threads/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_thread_and_verify_fields(client: AsyncClient):
    """Book 1 must exist in test fixtures."""
    resp = await client.post("/api/v1/books/1/ai-threads", json={"title": "Strategy Discussion"})
    if resp.status_code == 404:
        pytest.skip("Book 1 not available in test DB")
    assert resp.status_code == 201
    data = resp.json()
    assert data["book_id"] == 1
    assert data["title"] == "Strategy Discussion"
    assert "id" in data
    assert data["messages"] == []
    thread_id = data["id"]

    # Cleanup
    await client.delete(f"/api/v1/ai-threads/{thread_id}")


@pytest.mark.asyncio
async def test_list_threads_returns_created_thread(client: AsyncClient):
    create_resp = await client.post("/api/v1/books/1/ai-threads", json={"title": "My Discussion"})
    if create_resp.status_code == 404:
        pytest.skip("Book 1 not available in test DB")
    thread_id = create_resp.json()["id"]

    list_resp = await client.get("/api/v1/books/1/ai-threads")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert isinstance(items, list)
    thread_ids = [t["id"] for t in items]
    assert thread_id in thread_ids

    # Cleanup
    await client.delete(f"/api/v1/ai-threads/{thread_id}")


@pytest.mark.asyncio
async def test_get_thread_returns_correct_book_id(client: AsyncClient):
    create_resp = await client.post("/api/v1/books/1/ai-threads", json={"title": "Thread for get"})
    if create_resp.status_code == 404:
        pytest.skip("Book 1 not available in test DB")
    thread_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/ai-threads/{thread_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == thread_id
    assert data["book_id"] == 1
    assert data["title"] == "Thread for get"
    assert "messages" in data

    # Cleanup
    await client.delete(f"/api/v1/ai-threads/{thread_id}")


@pytest.mark.asyncio
async def test_update_thread_title(client: AsyncClient):
    create_resp = await client.post("/api/v1/books/1/ai-threads", json={"title": "Old Title"})
    if create_resp.status_code == 404:
        pytest.skip("Book 1 not available in test DB")
    thread_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/api/v1/ai-threads/{thread_id}", json={"title": "New Title"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "New Title"
    assert patch_resp.json()["id"] == thread_id

    # Cleanup
    await client.delete(f"/api/v1/ai-threads/{thread_id}")


@pytest.mark.asyncio
async def test_delete_thread_removes_from_list(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/books/1/ai-threads", json={"title": "Thread to delete"}
    )
    if create_resp.status_code == 404:
        pytest.skip("Book 1 not available in test DB")
    thread_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/ai-threads/{thread_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/ai-threads/{thread_id}")
    assert get_resp.status_code == 404
