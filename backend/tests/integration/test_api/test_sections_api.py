"""Integration tests for sections API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_sections_for_nonexistent_book(client):
    resp = await client.get("/api/v1/books/99999/sections")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_section_not_found(client):
    resp = await client.get("/api/v1/books/99999/sections/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_merge_requires_sections(client):
    resp = await client.post(
        "/api/v1/books/99999/sections/merge",
        json={"section_ids": [], "title": "X"},
    )
    # Either 404 (book) or 400 (bad request)
    assert resp.status_code in (400, 404)
