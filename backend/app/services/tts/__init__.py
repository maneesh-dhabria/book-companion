"""TTS service package — providers, sanitizer, factory."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from app.config import Settings
from app.services.tts.provider import TTSProvider


def detect_tts_provider() -> str | None:
    """Return the first usable TTS provider name on this host, or ``None``."""
    has_ffmpeg = shutil.which("ffmpeg") is not None
    has_kokoro = importlib.util.find_spec("kokoro_onnx") is not None
    if has_ffmpeg and has_kokoro:
        return "kokoro"
    return None


def create_tts_provider(name: str | None, settings: Settings) -> TTSProvider | None:
    """Instantiate a provider by name; ``None``/``"auto"`` triggers detection."""
    if name in (None, "auto"):
        name = detect_tts_provider()
    if name == "kokoro":
        from app.services.tts.kokoro_provider import KokoroProvider

        model_dir = Path(settings.data.directory) / "models" / "tts"
        return KokoroProvider(model_dir=model_dir)
    return None
