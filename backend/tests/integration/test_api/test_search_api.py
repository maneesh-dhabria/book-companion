"""Integration tests for the Search API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_quick_search_empty_query(client: AsyncClient):
    resp = await client.get("/api/v1/search/quick?q=")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_quick_search_returns_grouped_results(client: AsyncClient):
    resp = await client.get("/api/v1/search/quick?q=test&limit=12")
    assert resp.status_code == 200
    data = resp.json()
    assert "query" in data
    assert "results" in data
    results = data["results"]
    assert "books" in results
    assert "sections" in results
    assert "concepts" in results
    assert "annotations" in results


@pytest.mark.asyncio
async def test_quick_search_query_echoed_in_response(client: AsyncClient):
    resp = await client.get("/api/v1/search/quick?q=deception")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "deception"


@pytest.mark.asyncio
async def test_quick_search_groups_by_type_and_caps_at_three(client: AsyncClient):
    resp = await client.get("/api/v1/search/quick?q=strategy&limit=12")
    assert resp.status_code == 200
    data = resp.json()
    results = data["results"]
    for group_name, group_items in results.items():
        assert len(group_items) <= 3, (
            f"Group '{group_name}' has {len(group_items)} items, max is 3"
        )


@pytest.mark.asyncio
async def test_full_search_paginated(client: AsyncClient):
    resp = await client.get("/api/v1/search?q=test&page=1&per_page=20")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_full_search_pagination_fields_correct(client: AsyncClient):
    resp = await client.get("/api/v1/search?q=war&page=1&per_page=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert data["per_page"] == 5


@pytest.mark.asyncio
async def test_recent_searches(client: AsyncClient):
    resp = await client.get("/api/v1/search/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_quick_search_stores_in_recent_searches(client: AsyncClient):
    unique_query = "xyzzy_test_query_unique_9871"
    await client.get(f"/api/v1/search/quick?q={unique_query}")
    recent_resp = await client.get("/api/v1/search/recent")
    assert recent_resp.status_code == 200
    recent_queries = [r["query"] for r in recent_resp.json()]
    assert unique_query in recent_queries
    # Cleanup
    await client.delete("/api/v1/search/recent")


@pytest.mark.asyncio
async def test_clear_recent_searches(client: AsyncClient):
    await client.get("/api/v1/search/quick?q=unique_query_to_clear")
    clear_resp = await client.delete("/api/v1/search/recent")
    assert clear_resp.status_code == 204
    recent_resp = await client.get("/api/v1/search/recent")
    assert recent_resp.json() == []
