"""Integration tests for preset CRUD + template endpoints."""

from pathlib import Path

import pytest
from httpx import AsyncClient


@pytest.fixture
def tmp_presets_dir(app, tmp_path):
    """Override preset service to write to a tmp dir; copy in one system preset."""
    presets_dir = tmp_path / "presets"
    presets_dir.mkdir()

    # Seed a system preset so collision/system-readonly tests have a target.
    (presets_dir / "practitioner_bullets.yaml").write_text(
        "name: Practitioner Bullets\n"
        "description: System preset\n"
        "system: true\n"
        "facets:\n"
        "  style: bullet_points\n"
        "  audience: practitioner\n"
        "  compression: standard\n"
        "  content_focus: frameworks_examples\n"
    )

    from app.api.routes.summarize_presets import get_preset_service
    from app.services.preset_service import PresetService

    app.dependency_overrides[get_preset_service] = lambda: PresetService(presets_dir=presets_dir)
    yield presets_dir
    app.dependency_overrides.pop(get_preset_service, None)


@pytest.mark.asyncio
async def test_preset_crud_lifecycle(client: AsyncClient, tmp_presets_dir: Path):
    # Create
    r = await client.post(
        "/api/v1/summarize/presets",
        json={
            "name": "test_user_foo",
            "label": "Test Foo",
            "description": "ephemeral",
            "facets": {
                "style": "bullet_points",
                "audience": "practitioner",
                "compression": "standard",
                "content_focus": "frameworks_examples",
            },
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == "test_user_foo"

    # Update
    r = await client.put(
        "/api/v1/summarize/presets/test_user_foo",
        json={
            "name": "test_user_foo",
            "label": "Test Foo Updated",
            "description": "updated",
            "facets": {
                "style": "narrative",
                "audience": "practitioner",
                "compression": "brief",
                "content_focus": "frameworks_examples",
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["facets"]["style"] == "narrative"

    # Template
    r = await client.get("/api/v1/summarize/presets/test_user_foo/template")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "test_user_foo"
    assert body["is_system"] is False
    assert "source" in body["base_template"]
    assert len(body["fragments"]) == 4

    # Template not found
    r = await client.get("/api/v1/summarize/presets/nonexistent/template")
    assert r.status_code == 404

    # Delete
    r = await client.delete("/api/v1/summarize/presets/test_user_foo")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_preset_create_collision_returns_409(client: AsyncClient, tmp_presets_dir: Path):
    r = await client.post(
        "/api/v1/summarize/presets",
        json={
            "name": "practitioner_bullets",
            "label": "Dup",
            "description": "x",
            "facets": {
                "style": "bullet_points",
                "audience": "practitioner",
                "compression": "standard",
                "content_focus": "frameworks_examples",
            },
        },
    )
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preset_delete_system_returns_403(client: AsyncClient, tmp_presets_dir: Path):
    r = await client.delete("/api/v1/summarize/presets/practitioner_bullets")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_preset_invalid_facet_returns_422(client: AsyncClient, tmp_presets_dir: Path):
    r = await client.post(
        "/api/v1/summarize/presets",
        json={
            "name": "test_bad",
            "label": "Bad",
            "description": "x",
            "facets": {
                "style": "NONEXISTENT_VALUE",
                "audience": "practitioner",
                "compression": "standard",
                "content_focus": "frameworks_examples",
            },
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_preset_list_includes_warnings(client: AsyncClient, tmp_presets_dir: Path):
    # Drop a malformed file alongside the seed.
    (tmp_presets_dir / "broken.yaml").write_text("not: valid: yaml: ::: [\n")
    r = await client.get("/api/v1/summarize/presets")
    assert r.status_code == 200
    body = r.json()
    assert "warnings" in body
    assert any(w["file"] == "broken.yaml" for w in body["warnings"])
