"""Integration tests for the Concepts API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_concepts_empty(client: AsyncClient):
    resp = await client.get("/api/v1/concepts")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_concept_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/concepts/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_concept_not_found(client: AsyncClient):
    resp = await client.patch("/api/v1/concepts/99999", json={"definition": "new def"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reset_concept_not_found(client: AsyncClient):
    resp = await client.post("/api/v1/concepts/99999/reset")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_concept_not_found(client: AsyncClient):
    resp = await client.delete("/api/v1/concepts/99999")
    assert resp.status_code == 404
