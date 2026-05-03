"""Mocked Kokoro model-download tests (no real network call).

Phase F /verify pivot: KokoroProvider._ensure_model_downloaded now streams
from GitHub Releases via httpx (was huggingface_hub). These tests pin that
behavior — fake httpx.stream + assert each release URL is fetched.
"""

from contextlib import contextmanager
from pathlib import Path

import pytest

from app.services.tts.kokoro_provider import (
    KOKORO_MODEL_URLS,
    ONNX_FILENAME,
    VOICES_FILENAME,
    KokoroProvider,
)
from app.services.tts.provider import KokoroModelDownloadError


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self, chunk_size: int = 1024 * 1024):
        yield self._payload


def _install_fake_httpx(monkeypatch, *, raises: type[BaseException] | None = None):
    """Patch ``app.services.tts.kokoro_provider``'s lazy ``httpx`` import."""
    import sys
    import types

    seen_urls: list[str] = []

    fake = types.ModuleType("httpx")

    class HTTPError(Exception):
        pass

    fake.HTTPError = HTTPError

    @contextmanager
    def fake_stream(method: str, url: str, **kwargs):
        seen_urls.append(url)
        if raises is not None:
            raise raises("boom")
        yield _FakeResponse(b"FAKE-BYTES")

    fake.stream = fake_stream
    monkeypatch.setitem(sys.modules, "httpx", fake)
    return seen_urls


def test_download_succeeds(tmp_path, monkeypatch):
    seen = _install_fake_httpx(monkeypatch)
    target = tmp_path / "models" / "tts"
    KokoroProvider._ensure_model_downloaded(target)
    assert (target / ONNX_FILENAME).exists()
    assert (target / VOICES_FILENAME).exists()
    # Both GitHub-Release URLs were fetched, in order.
    assert KOKORO_MODEL_URLS[ONNX_FILENAME] in seen
    assert KOKORO_MODEL_URLS[VOICES_FILENAME] in seen


def test_download_connection_error_raises(tmp_path, monkeypatch):
    # ConnectionError is an OSError subclass — caught by the kokoro provider's
    # (httpx.HTTPError, OSError) tuple and rewrapped as KokoroModelDownloadError.
    _install_fake_httpx(monkeypatch, raises=ConnectionError)
    with pytest.raises(KokoroModelDownloadError):
        KokoroProvider._ensure_model_downloaded(tmp_path / "models" / "tts")


def test_download_skipped_when_files_present(tmp_path, monkeypatch):
    model_dir = tmp_path / "models" / "tts"
    model_dir.mkdir(parents=True)
    (model_dir / ONNX_FILENAME).write_bytes(b"x")
    (model_dir / VOICES_FILENAME).write_bytes(b"y")
    seen = _install_fake_httpx(monkeypatch)
    KokoroProvider._ensure_model_downloaded(model_dir)
    assert seen == []


def test_partial_download_cleaned_up_on_error(tmp_path, monkeypatch):
    """A failed download must not leave a poisoned `.partial` sibling that
    later runs would mistake for a real model file."""
    _install_fake_httpx(monkeypatch, raises=ConnectionError)
    target = tmp_path / "models" / "tts"
    with pytest.raises(KokoroModelDownloadError):
        KokoroProvider._ensure_model_downloaded(target)
    assert not (target / f"{ONNX_FILENAME}.partial").exists()
    assert not (target / ONNX_FILENAME).exists()


def test_resumes_when_only_one_file_present(tmp_path, monkeypatch):
    """If onnx is on disk but voices isn't, only voices should be fetched."""
    target = tmp_path / "models" / "tts"
    target.mkdir(parents=True)
    Path(target / ONNX_FILENAME).write_bytes(b"already-here")
    seen = _install_fake_httpx(monkeypatch)
    KokoroProvider._ensure_model_downloaded(target)
    assert KOKORO_MODEL_URLS[VOICES_FILENAME] in seen
    assert KOKORO_MODEL_URLS[ONNX_FILENAME] not in seen
