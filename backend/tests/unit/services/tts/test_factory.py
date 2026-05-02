"""TTS factory + auto-detect tests."""

import importlib.util as _iu

import pytest

from app.config import Settings
from app.services.tts import create_tts_provider, detect_tts_provider


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    return Settings()


def test_detect_returns_none_when_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr("app.services.tts.shutil.which", lambda c: None)
    assert detect_tts_provider() is None


def test_detect_returns_none_when_kokoro_not_installed(monkeypatch):
    monkeypatch.setattr("app.services.tts.shutil.which", lambda c: "/usr/bin/ffmpeg")
    monkeypatch.setattr("app.services.tts.importlib.util.find_spec", lambda n: None)
    assert detect_tts_provider() is None


def test_detect_returns_kokoro_when_both_present(monkeypatch):
    monkeypatch.setattr("app.services.tts.shutil.which", lambda c: "/opt/homebrew/bin/ffmpeg")
    monkeypatch.setattr("app.services.tts.importlib.util.find_spec", lambda n: object())
    assert detect_tts_provider() == "kokoro"


def test_create_kokoro_returns_instance(monkeypatch, settings):
    monkeypatch.setattr(
        "app.services.tts.kokoro_provider.KokoroProvider._ensure_model_downloaded",
        lambda _d: None,
    )
    p = create_tts_provider("kokoro", settings)
    assert p is not None
    assert p.name == "kokoro"


def test_create_unknown_returns_none(settings):
    assert create_tts_provider("bogus", settings) is None


def test_create_auto_falls_back_to_detect(monkeypatch, settings):
    monkeypatch.setattr("app.services.tts.shutil.which", lambda c: None)
    assert create_tts_provider("auto", settings) is None
