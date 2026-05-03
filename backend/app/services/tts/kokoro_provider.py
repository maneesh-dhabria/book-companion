"""KokoroProvider — local subprocess-free TTS via kokoro-onnx + ffmpeg.

The constructor lazy-loads the ONNX model (downloaded on first use) and the
voices binary. ``synthesize`` segments via the markdown-to-speech sanitizer
when handed raw markdown, or accepts pre-segmented sentences via
``synthesize_segmented``. PCM is concatenated then encoded to MP3 by piping
into a one-shot ffmpeg subprocess.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path
from typing import ClassVar

import structlog

from app.services.tts.markdown_to_speech import sanitize
from app.services.tts.provider import (
    EmptySanitizedTextError,
    FfmpegEncodeError,
    KokoroModelDownloadError,
    SynthesisResult,
    TooLargeError,
    TTSProvider,
    VoiceInfo,
)

MAX_SANITIZED_CHARS = 50_000

logger = structlog.get_logger(__name__)

ONNX_FILENAME = "kokoro-v1.0.onnx"
VOICES_FILENAME = "voices-v1.0.bin"

# GitHub Releases is the canonical distribution channel for the bundled
# kokoro-v1.0.onnx + voices-v1.0.bin pair (the upstream HF repo
# `onnx-community/Kokoro-82M-v1.0-ONNX` ships split shards that don't match
# what kokoro-onnx expects to load). Tag `model-files-v1.0`.
_GITHUB_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_MODEL_URLS: dict[str, str] = {
    ONNX_FILENAME: f"{_GITHUB_RELEASE}/{ONNX_FILENAME}",
    VOICES_FILENAME: f"{_GITHUB_RELEASE}/{VOICES_FILENAME}",
}

# Static voice catalog — matches the bundled voices-v1.0.bin shipped by
# onnx-community/Kokoro-82M-v1.0-ONNX. Kept in sync with upstream at install
# time. Used for /settings/tts PUT validation.
KOKORO_VOICES: set[str] = {
    "af_alloy",
    "af_aoede",
    "af_bella",
    "af_jessica",
    "af_kore",
    "af_nicole",
    "af_nova",
    "af_river",
    "af_sarah",
    "af_sky",
    "am_adam",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_michael",
    "am_onyx",
    "am_puck",
    "am_santa",
    "bf_alice",
    "bf_emma",
    "bf_isabella",
    "bf_lily",
    "bm_daniel",
    "bm_fable",
    "bm_george",
    "bm_lewis",
}
SAMPLE_RATE = 24000


class KokoroProvider(TTSProvider):
    name: ClassVar[str] = "kokoro"

    def __init__(self, model_dir: Path):
        self.model_dir = Path(model_dir)
        self._kokoro = None
        self._terminated = threading.Event()
        self._active_proc: subprocess.Popen | None = None

    # --- model lifecycle ----------------------------------------------------

    @staticmethod
    def _ensure_model_downloaded(model_dir: Path) -> None:
        """Download Kokoro model + voices binary from GitHub Releases if missing.

        Files come from the kokoro-onnx project's tagged release (~338 MB total).
        Downloads stream to a `.partial` sibling and atomic-rename on success
        so a half-finished file can't poison subsequent loads.
        """
        model_dir.mkdir(parents=True, exist_ok=True)
        onnx_path = model_dir / ONNX_FILENAME
        voices_path = model_dir / VOICES_FILENAME
        if onnx_path.exists() and voices_path.exists():
            return

        # Use httpx for streaming + redirect handling; already a project dep.
        try:
            import httpx
        except ImportError as e:  # pragma: no cover — httpx is required
            raise KokoroModelDownloadError(f"httpx missing: {e}") from e

        targets = [
            (onnx_path, KOKORO_MODEL_URLS[ONNX_FILENAME]),
            (voices_path, KOKORO_MODEL_URLS[VOICES_FILENAME]),
        ]
        for dest, url in targets:
            if dest.exists():
                continue
            partial = dest.with_suffix(dest.suffix + ".partial")
            try:
                with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as resp:
                    resp.raise_for_status()
                    with partial.open("wb") as fh:
                        for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                            fh.write(chunk)
                partial.rename(dest)
            except (httpx.HTTPError, OSError) as e:
                # Best-effort cleanup so a transient failure doesn't leave
                # zero-byte/half-written files that future loads accept.
                partial.unlink(missing_ok=True)
                raise KokoroModelDownloadError(f"download failed for {url}: {e}") from e

    def _load(self) -> None:
        if self._kokoro is not None:
            return
        self._ensure_model_downloaded(self.model_dir)
        try:
            from kokoro_onnx import Kokoro
        except ImportError as e:
            raise KokoroModelDownloadError(f"kokoro_onnx not installed: {e}") from e
        self._kokoro = Kokoro(
            str(self.model_dir / ONNX_FILENAME),
            str(self.model_dir / VOICES_FILENAME),
        )

    # --- public API ---------------------------------------------------------

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> SynthesisResult:
        sanitized = sanitize(text)
        if len(sanitized.text) > MAX_SANITIZED_CHARS:
            raise TooLargeError(
                f"post-sanitizer text {len(sanitized.text)} chars "
                f"exceeds cap of {MAX_SANITIZED_CHARS}"
            )
        sentences = self._split_by_offsets(sanitized.text, sanitized.sentence_offsets_chars)
        if not sentences:
            raise EmptySanitizedTextError("no sentences after sanitization")
        return self.synthesize_segmented(sentences, voice=voice, speed=speed)

    def synthesize_segmented(
        self, sentences: list[str], voice: str, speed: float = 1.0
    ) -> SynthesisResult:
        if shutil.which("ffmpeg") is None:
            raise FfmpegEncodeError("ffmpeg not on PATH; install via `brew install ffmpeg`")

        self._load()
        import numpy as np

        buffers: list = []
        offsets: list[float] = []
        cursor = 0.0
        for sent in sentences:
            if self._terminated.is_set():
                break
            offsets.append(cursor)
            pcm, sr = self._kokoro.create(sent, voice=voice, speed=speed)
            buffers.append(pcm)
            cursor += len(pcm) / float(sr)

        if not buffers:
            raise EmptySanitizedTextError("no audio produced")

        joined = np.concatenate(buffers).astype("float32")
        mp3_bytes = self._run_ffmpeg(joined.tobytes())
        return SynthesisResult(
            audio_bytes=mp3_bytes,
            sample_rate=SAMPLE_RATE,
            sentence_offsets=offsets,
            duration_seconds=cursor,
        )

    def list_voices(self) -> list[VoiceInfo]:
        self._load()
        names: list[str] = []
        try:
            voices = self._kokoro.list_voices() if hasattr(self._kokoro, "list_voices") else []
            names = list(voices)
        except Exception as e:  # pragma: no cover — provider variance
            logger.warning("kokoro_list_voices_failed", error=str(e))
        return [VoiceInfo(name=n, language="en") for n in names]

    def terminate(self) -> None:
        self._terminated.set()
        proc = self._active_proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:  # pragma: no cover
                pass

    # --- internals ----------------------------------------------------------

    def _run_ffmpeg(self, pcm_bytes: bytes) -> bytes:
        cmd = [
            "ffmpeg",
            "-f",
            "f32le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-i",
            "-",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "96k",
            "-f",
            "mp3",
            "-",
        ]
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self._active_proc = proc
        try:
            stdout, stderr = proc.communicate(input=pcm_bytes)
        except BrokenPipeError as e:
            raise FfmpegEncodeError("ffmpeg pipe broken", stderr_tail=str(e)) from e
        finally:
            self._active_proc = None
        if proc.returncode != 0:
            tail = stderr[-2048:].decode("utf-8", errors="replace") if stderr else ""
            raise FfmpegEncodeError(f"ffmpeg returncode={proc.returncode}", stderr_tail=tail)
        return stdout

    @staticmethod
    def _split_by_offsets(text: str, offsets: list[int]) -> list[str]:
        if not offsets:
            return []
        ends = list(offsets[1:]) + [len(text)]
        return [
            text[start:end].strip()
            for start, end in zip(offsets, ends, strict=True)
            if text[start:end].strip()
        ]
