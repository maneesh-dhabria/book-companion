"""Integration tests for summaries API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_summaries_not_found(client):
    resp = await client.get("/api/v1/books/99999/summaries")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_summary_not_found(client):
    resp = await client.get("/api/v1/summaries/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_default_not_found(client):
    resp = await client.post("/api/v1/summaries/99999/set-default")
    assert resp.status_code == 404
