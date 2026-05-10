"""FR-03: split listen_wpm (TTS) + reading_wpm (Reading) settings.

Backend config namespace check: `tts` and `reading` are top-level Settings
keys (matching the existing `tts:` block at config.py:178). The plan's
sketch references `audio.tts.*`; we use the live root-level shape since the
codebase has no `audio` wrapper.
"""

import pytest


@pytest.mark.asyncio
async def test_patch_listen_wpm_persists(client):
    r = await client.patch("/api/v1/settings", json={"tts": {"listen_wpm": 225}})
    assert r.status_code == 200, r.text
    body = (await client.get("/api/v1/settings")).json()
    assert body["tts"]["listen_wpm"] == 225


@pytest.mark.asyncio
async def test_patch_listen_wpm_below_min_400(client):
    r = await client.patch("/api/v1/settings", json={"tts": {"listen_wpm": 95}})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_listen_wpm_above_max_400(client):
    r = await client.patch("/api/v1/settings", json={"tts": {"listen_wpm": 425}})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_reading_wpm_persists(client):
    r = await client.patch("/api/v1/settings", json={"reading": {"reading_wpm": 275}})
    assert r.status_code == 200, r.text
    body = (await client.get("/api/v1/settings")).json()
    assert body["reading"]["reading_wpm"] == 275


@pytest.mark.asyncio
async def test_patch_preserves_unrelated_keys(client):
    """R4 mitigation: PATCH listen_wpm must not clobber other tts keys."""
    initial = (await client.get("/api/v1/settings")).json()
    initial_engine = initial["tts"]["engine"]
    initial_voice = initial["tts"]["voice"]
    initial_speed = initial["tts"]["default_speed"]
    initial_auto_advance = initial["tts"]["auto_advance"]

    r = await client.patch("/api/v1/settings", json={"tts": {"listen_wpm": 250}})
    assert r.status_code == 200, r.text

    after = (await client.get("/api/v1/settings")).json()
    assert after["tts"]["listen_wpm"] == 250
    assert after["tts"]["engine"] == initial_engine
    assert after["tts"]["voice"] == initial_voice
    assert after["tts"]["default_speed"] == initial_speed
    assert after["tts"]["auto_advance"] == initial_auto_advance
