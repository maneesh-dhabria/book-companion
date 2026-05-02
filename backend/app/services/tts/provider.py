"""TTSProvider ABC + value types + exception taxonomy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from app.exceptions import BookCompanionError


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    sample_rate: int
    sentence_offsets: list[float] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class VoiceInfo:
    name: str
    language: str
    gender: str | None = None


class TTSProviderError(BookCompanionError):
    """Base for TTS subsystem errors."""


class KokoroModelDownloadError(TTSProviderError):
    def __init__(
        self, message: str = "kokoro model download failed", retry_after_seconds: int | None = None
    ):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class FfmpegEncodeError(TTSProviderError):
    def __init__(self, message: str = "ffmpeg encode failed", stderr_tail: str | None = None):
        super().__init__(message)
        self.stderr_tail = stderr_tail


class EmptySanitizedTextError(TTSProviderError):
    """Raised when sanitization produces no synthesizable text.

    Re-exported here so boundary handlers can import it from one location.
    """


class TTSProvider(ABC):
    name: ClassVar[str] = ""

    @abstractmethod
    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> SynthesisResult:
        """Synthesize ``text`` into MP3 bytes; returns audio + sentence offsets in seconds."""

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        """Return the available voices for this provider."""

    def terminate(self) -> None:
        """Best-effort cancellation of any in-flight synthesis (no-op default)."""
