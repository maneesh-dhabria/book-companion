"""Integration tests for settings API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_settings(client):
    resp = await client.get("/api/v1/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "network" in data
    assert "llm" in data
    assert "web" in data
    assert "summarization" in data


@pytest.mark.asyncio
async def test_get_settings_masks_secrets(client):
    """Settings response must not leak raw access tokens."""
    resp = await client.get("/api/v1/settings")
    data = resp.json()
    token = data["network"].get("access_token")
    # Token should be None or masked
    assert token is None or token == "***"


@pytest.mark.asyncio
async def test_get_database_stats(client):
    resp = await client.get("/api/v1/settings/database-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "books" in data
    assert "book_sections" in data
    assert "summaries" in data
    assert isinstance(data["books"], int)


@pytest.mark.asyncio
async def test_get_migration_status(client):
    resp = await client.get("/api/v1/settings/migration-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "current" in data
    assert "is_behind" in data
