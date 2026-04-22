"""Tests for GET /api/v1/summarize/presets."""

from pathlib import Path

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_presets_returns_all_yaml_files(client: AsyncClient):
    resp = await client.get("/api/v1/summarize/presets")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["default_id"] == "practitioner_bullets"
    ids = {p["id"] for p in body["presets"]}
    # All five bundled system presets must be present.
    assert ids == {
        "academic_detailed",
        "executive_brief",
        "practitioner_bullets",
        "study_guide",
        "tweet_thread",
    }
    first = next(p for p in body["presets"] if p["id"] == "practitioner_bullets")
    assert first["label"] == "Practitioner Bullets"
    assert "facets" in first and isinstance(first["facets"], dict)
    assert first["system"] is True


@pytest.mark.asyncio
async def test_list_presets_skips_malformed_yaml_files(
    client: AsyncClient, monkeypatch, tmp_path
):
    """Drop a malformed YAML into the presets dir; endpoint should omit it."""
    from app.services import preset_service as ps

    real_presets_dir = ps.PRESETS_DIR
    staging = tmp_path / "presets"
    staging.mkdir()
    for yaml_file in real_presets_dir.glob("*.yaml"):
        (staging / yaml_file.name).write_text(yaml_file.read_text())
    (staging / "broken.yaml").write_text("not: valid: yaml: ::::\n")

    monkeypatch.setattr(ps, "PRESETS_DIR", staging)

    resp = await client.get("/api/v1/summarize/presets")
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()["presets"]}
    assert "broken" not in ids
    # Existing bundled presets still resolve.
    assert "practitioner_bullets" in ids


@pytest.mark.asyncio
async def test_list_presets_default_id_is_first_when_practitioner_absent(
    client: AsyncClient, monkeypatch, tmp_path
):
    from app.services import preset_service as ps

    staging = tmp_path / "presets_only_one"
    staging.mkdir()
    stem_only = Path(ps.PRESETS_DIR) / "executive_brief.yaml"
    (staging / "executive_brief.yaml").write_text(stem_only.read_text())
    monkeypatch.setattr(ps, "PRESETS_DIR", staging)

    resp = await client.get("/api/v1/summarize/presets")
    body = resp.json()
    assert body["default_id"] == "executive_brief"
