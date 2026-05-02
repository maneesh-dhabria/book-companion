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
    TTSProvider,
    VoiceInfo,
)

logger = structlog.get_logger(__name__)

KOKORO_REPO = "onnx-community/Kokoro-82M-v1.0-ONNX"
ONNX_FILENAME = "kokoro-v1.0.onnx"
VOICES_FILENAME = "voices-v1.0.bin"
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
        model_dir.mkdir(parents=True, exist_ok=True)
        onnx_path = model_dir / ONNX_FILENAME
        voices_path = model_dir / VOICES_FILENAME
        if onnx_path.exists() and voices_path.exists():
            return

        try:
            from huggingface_hub import hf_hub_download
            from huggingface_hub.errors import HfHubHTTPError
        except ImportError as e:
            raise KokoroModelDownloadError(f"huggingface_hub missing: {e}") from e

        try:
            for fn in (ONNX_FILENAME, VOICES_FILENAME):
                hf_hub_download(
                    repo_id=KOKORO_REPO,
                    filename=fn,
                    local_dir=str(model_dir),
                )
        except (HfHubHTTPError, ConnectionError, OSError) as e:
            raise KokoroModelDownloadError(f"download failed: {e}") from e

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
        return SynthesisResult(audio_bytes=mp3_bytes, sample_rate=SAMPLE_RATE, sentence_offsets=offsets)

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
            "-f", "f32le",
            "-ar", str(SAMPLE_RATE),
            "-ac", "1",
            "-i", "-",
            "-codec:a", "libmp3lame",
            "-b:a", "96k",
            "-f", "mp3",
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
        return [text[start:end].strip() for start, end in zip(offsets, ends, strict=True) if text[start:end].strip()]
