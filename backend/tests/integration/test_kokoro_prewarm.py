"""B6: Kokoro lifespan pre-warm with graceful degradation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.config import Settings, TTSConfig
from app.services.tts.prewarm import prewarm_kokoro


@pytest.mark.asyncio
async def test_prewarm_skipped_for_web_speech():
    settings = Settings(tts=TTSConfig(engine="web-speech"))
    assert (await prewarm_kokoro(settings)) is False


@pytest.mark.asyncio
async def test_prewarm_skipped_when_disabled():
    settings = Settings(tts=TTSConfig(engine="kokoro", prewarm_on_startup=False))
    assert (await prewarm_kokoro(settings)) is False


@pytest.mark.asyncio
async def test_prewarm_succeeds_when_loader_returns():
    settings = Settings(tts=TTSConfig(engine="kokoro", prewarm_on_startup=True))

    class FakeProvider:
        def _load(self):
            return None

    with patch("app.services.tts.create_tts_provider", return_value=FakeProvider()):
        ok = await prewarm_kokoro(settings)
        assert ok is True


@pytest.mark.asyncio
async def test_prewarm_failure_returns_false():
    settings = Settings(tts=TTSConfig(engine="kokoro", prewarm_on_startup=True))

    def boom(*a, **k):
        raise RuntimeError("model missing")

    with patch("app.services.tts.create_tts_provider", side_effect=boom):
        ok = await prewarm_kokoro(settings)
        assert ok is False
