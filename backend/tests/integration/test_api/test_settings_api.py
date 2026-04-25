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


# --- T2: strict pydantic validation on PATCH ---


@pytest.mark.asyncio
async def test_patch_unknown_key_returns_400(client):
    """FR-F1.4: unknown nested key → 400 with FastAPI-shape detail."""
    resp = await client.patch("/api/v1/settings", json={"llm": {"foo": "bar"}})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any("foo" in str(e["loc"]) for e in detail)


@pytest.mark.asyncio
async def test_patch_invalid_type_returns_400(client):
    resp = await client.patch("/api/v1/settings", json={"llm": {"timeout_seconds": "bad"}})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_patch_valid_returns_200_with_updated_value(client):
    resp = await client.patch("/api/v1/settings", json={"llm": {"cli_command": "claude-personal"}})
    assert resp.status_code == 200
    assert resp.json()["llm"]["cli_command"] == "claude-personal"


@pytest.mark.asyncio
async def test_patch_partial_validity_rejects_all(client):
    """D17: partial-bad PATCH must not change any field on disk or in memory."""
    # First, set a known good value
    r1 = await client.patch("/api/v1/settings", json={"llm": {"cli_command": "before"}})
    assert r1.status_code == 200
    # Now try a partial-bad PATCH
    resp = await client.patch(
        "/api/v1/settings",
        json={"llm": {"cli_command": "after", "timeout_seconds": "nope"}},
    )
    assert resp.status_code == 400
    # cli_command must NOT have been changed
    get_resp = await client.get("/api/v1/settings")
    assert get_resp.json()["llm"]["cli_command"] == "before"
