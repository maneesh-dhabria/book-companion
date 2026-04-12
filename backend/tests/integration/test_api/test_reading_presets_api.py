"""Integration tests for the Reading Presets API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_reading_presets(client: AsyncClient):
    resp = await client.get("/api/v1/reading-presets")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_active_preset(client: AsyncClient):
    resp = await client.get("/api/v1/reading-presets/active")
    # On a fresh DB, no active preset exists — 404 is acceptable
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "font_family" in data
        assert "font_size_px" in data


@pytest.mark.asyncio
async def test_create_user_preset(client: AsyncClient):
    resp = await client.post(
        "/api/v1/reading-presets",
        json={
            "name": "Test Preset T5",
            "font_family": "Merriweather",
            "font_size_px": 20,
            "line_spacing": 1.8,
            "content_width_px": 720,
            "theme": "sepia",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Preset T5"
    assert data["is_system"] is False
    preset_id = data["id"]
    # Cleanup
    await client.delete(f"/api/v1/reading-presets/{preset_id}")


@pytest.mark.asyncio
async def test_cannot_delete_system_preset(client: AsyncClient):
    resp = await client.get("/api/v1/reading-presets")
    system = next((p for p in resp.json() if p.get("is_system")), None)
    if system:
        del_resp = await client.delete(f"/api/v1/reading-presets/{system['id']}")
        assert del_resp.status_code == 400


@pytest.mark.asyncio
async def test_activate_preset(client: AsyncClient):
    resp = await client.get("/api/v1/reading-presets")
    presets = resp.json()
    if presets:
        act_resp = await client.post(f"/api/v1/reading-presets/{presets[0]['id']}/activate")
        assert act_resp.status_code == 200


@pytest.mark.asyncio
async def test_create_and_activate_preset(client: AsyncClient):
    r1 = await client.post(
        "/api/v1/reading-presets",
        json={
            "name": "Preset Alpha T5",
            "font_family": "Georgia",
            "font_size_px": 18,
            "line_spacing": 1.6,
            "content_width_px": 720,
            "theme": "light",
        },
    )
    r2 = await client.post(
        "/api/v1/reading-presets",
        json={
            "name": "Preset Beta T5",
            "font_family": "Inter",
            "font_size_px": 16,
            "line_spacing": 1.5,
            "content_width_px": 680,
            "theme": "dark",
        },
    )
    id1, id2 = r1.json()["id"], r2.json()["id"]

    await client.post(f"/api/v1/reading-presets/{id1}/activate")
    await client.post(f"/api/v1/reading-presets/{id2}/activate")

    all_presets = (await client.get("/api/v1/reading-presets")).json()
    active = [p for p in all_presets if p["is_active"]]
    assert len(active) == 1, f"Expected exactly 1 active preset, got {len(active)}"
    assert active[0]["id"] == id2

    # Cleanup
    await client.delete(f"/api/v1/reading-presets/{id1}")
    await client.delete(f"/api/v1/reading-presets/{id2}")


@pytest.mark.asyncio
async def test_update_user_preset(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/reading-presets",
        json={
            "name": "Update Test T5",
            "font_family": "Georgia",
            "font_size_px": 18,
            "line_spacing": 1.6,
            "content_width_px": 720,
            "theme": "light",
        },
    )
    preset_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/reading-presets/{preset_id}",
        json={"font_size_px": 22, "line_spacing": 2.0},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["font_size_px"] == 22
    assert data["line_spacing"] == 2.0
    assert data["font_family"] == "Georgia"

    # Cleanup
    await client.delete(f"/api/v1/reading-presets/{preset_id}")
