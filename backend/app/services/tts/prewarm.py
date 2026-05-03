"""Kokoro pre-warm — load model in worker thread; never raises on failure."""

from __future__ import annotations

import asyncio

import structlog

from app.config import Settings

log = structlog.get_logger(__name__)


async def prewarm_kokoro(settings: Settings) -> bool:
    """Load Kokoro into memory. Returns True on success, False on any failure.

    Caller stores the result on ``app.state.tts_warm`` for /settings/tts/status.
    """
    if settings.tts.engine != "kokoro" or not settings.tts.prewarm_on_startup:
        return False

    def _load() -> bool:
        from app.services.tts import create_tts_provider

        provider = create_tts_provider("kokoro", settings)
        if provider is None:
            raise RuntimeError("kokoro provider unavailable")
        if hasattr(provider, "_load"):
            provider._load()
        return True

    try:
        await asyncio.to_thread(_load)
        log.info("kokoro_prewarmed")
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("kokoro_prewarm_failed", error=str(e))
        return False
