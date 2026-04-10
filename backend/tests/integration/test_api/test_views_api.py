"""Integration tests for library views API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_views(client):
    resp = await client.get("/api/v1/views")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_view(client):
    resp = await client.post(
        "/api/v1/views",
        json={
            "name": "Test View",
            "display_mode": "list",
            "sort_field": "title",
            "sort_direction": "asc",
            "filters": {"status": ["completed"]},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test View"
    assert data["display_mode"] == "list"

    # Cleanup: delete it
    view_id = data["id"]
    del_resp = await client.delete(f"/api/v1/views/{view_id}")
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_default_view_blocked(client):
    resp = await client.get("/api/v1/views")
    if resp.status_code == 200 and resp.json():
        default_view = next((v for v in resp.json() if v.get("is_default")), None)
        if default_view:
            del_resp = await client.delete(f"/api/v1/views/{default_view['id']}")
            assert del_resp.status_code == 400
