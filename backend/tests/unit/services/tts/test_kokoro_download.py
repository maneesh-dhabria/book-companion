"""Mocked Kokoro model-download tests (no real HF call)."""

import sys
import types

import pytest

from app.services.tts.kokoro_provider import KokoroProvider
from app.services.tts.provider import KokoroModelDownloadError


def _install_fake_hf(monkeypatch, *, raises: type[BaseException] | None = None):
    errors_mod = types.ModuleType("huggingface_hub.errors")

    class HfHubHTTPError(Exception):
        pass

    errors_mod.HfHubHTTPError = HfHubHTTPError

    hub_mod = types.ModuleType("huggingface_hub")
    called = {}

    def fake_dl(*, repo_id, filename, local_dir):
        called[filename] = True
        from pathlib import Path

        p = Path(local_dir) / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        if raises is not None:
            raise raises("boom")
        p.write_bytes(b"FAKE")
        return str(p)

    hub_mod.hf_hub_download = fake_dl
    hub_mod.errors = errors_mod
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub_mod)
    monkeypatch.setitem(sys.modules, "huggingface_hub.errors", errors_mod)
    return called, HfHubHTTPError


def test_download_succeeds(tmp_path, monkeypatch):
    called, _ = _install_fake_hf(monkeypatch)
    KokoroProvider._ensure_model_downloaded(tmp_path / "models" / "tts")
    assert called.get("kokoro-v1.0.onnx") is True
    assert called.get("voices-v1.0.bin") is True


def test_download_connection_error_raises(tmp_path, monkeypatch):
    _install_fake_hf(monkeypatch, raises=ConnectionError)
    with pytest.raises(KokoroModelDownloadError):
        KokoroProvider._ensure_model_downloaded(tmp_path / "models" / "tts")


def test_download_skipped_when_files_present(tmp_path, monkeypatch):
    model_dir = tmp_path / "models" / "tts"
    model_dir.mkdir(parents=True)
    (model_dir / "kokoro-v1.0.onnx").write_bytes(b"x")
    (model_dir / "voices-v1.0.bin").write_bytes(b"y")
    called, _ = _install_fake_hf(monkeypatch)
    KokoroProvider._ensure_model_downloaded(model_dir)
    assert called == {}
