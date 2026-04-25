"""FR-F4.4 / D16: simplified GET shape + legacy-active-hint endpoint."""

from pathlib import Path

import pytest  # noqa: F401  -- pytest discovery via decorator namespace

_SEED_PRESETS = [
    ("Light", "light"),
    ("Sepia", "sepia"),
    ("Dark", "dark"),
    ("Night", "night"),
    ("Paper", "paper"),
    ("High Contrast", "contrast"),
]


async def _seed_system_presets(app):
    """Insert the 6 v1.5 system presets via the app's session factory."""
    from app.db.models import ReadingPreset

    factory = app.state.session_factory
    async with factory() as session:
        for name, theme in _SEED_PRESETS:
            session.add(
                ReadingPreset(
                    name=name,
                    font_family="Georgia",
                    font_size_px=16,
                    line_spacing=1.6,
                    content_width_px=720,
                    theme=theme,
                )
            )
        await session.commit()


@pytest.mark.asyncio
async def test_list_returns_simplified_shape(client, app):
    await _seed_system_presets(app)
    resp = await client.get("/api/v1/reading-presets")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and isinstance(body["items"], list)
    assert "default_id" not in body
    assert len(body["items"]) >= 6
    sample = body["items"][0]
    for forbidden in ("is_system", "is_active"):
        assert forbidden not in sample
    for required in (
        "id",
        "name",
        "font_family",
        "font_size_px",
        "line_spacing",
        "content_width_px",
        "theme",
        "created_at",
    ):
        assert required in sample
    names = {p["name"] for p in body["items"]}
    assert {"Light", "Sepia", "Dark", "Night", "Paper", "High Contrast"}.issubset(names)


@pytest.mark.asyncio
async def test_legacy_active_hint_endpoint_returns_null_when_absent(client):
    resp = await client.get("/api/v1/reading-presets/legacy-active-hint")
    assert resp.status_code == 200
    assert resp.json() == {"name": None}


@pytest.mark.asyncio
async def test_legacy_active_hint_consumes_once(client, app):
    """FR-F4.7c / P3: GET returns the captured name then deletes the file."""
    settings = app.state.settings
    hint = Path(settings.data.directory) / "migration_v1_5_1_legacy_active.txt"
    hint.parent.mkdir(parents=True, exist_ok=True)
    hint.write_text("Sepia")
    r1 = await client.get("/api/v1/reading-presets/legacy-active-hint")
    assert r1.status_code == 200
    assert r1.json() == {"name": "Sepia"}
    r2 = await client.get("/api/v1/reading-presets/legacy-active-hint")
    assert r2.status_code == 200
    assert r2.json() == {"name": None}
    assert not hint.exists()
