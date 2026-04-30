"""LLM provider interface."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0


class LLMProvider(ABC):
    """Base class for subprocess-based LLM CLI providers.

    Concrete subclasses inherit ``terminate()``; before each subprocess spawn
    they call ``self._track_active(proc)`` so cancel-RUNNING (FR-B15) can
    SIGTERM the in-flight call. Cleared in ``finally`` after each call so
    ``self._active_proc`` is None whenever the provider is idle.
    """

    _active_proc: asyncio.subprocess.Process | None = None

    def _track_active(self, proc: asyncio.subprocess.Process | None) -> None:
        self._active_proc = proc

    async def terminate(self) -> None:
        """SIGTERM the in-flight subprocess, if any.

        Best-effort: callers wrap in try/except. SIGKILL after 5 s is the
        responsibility of the caller (see ``cancel_processing`` route).
        """
        proc = self._active_proc
        if proc is None or proc.returncode is not None:
            return
        try:
            proc.terminate()
        except (ProcessLookupError, OSError):
            pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        json_schema: dict | None = None,
        timeout: int | None = None,
        context: dict | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def generate_with_image(
        self,
        prompt: str,
        image_path: Path,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> LLMResponse: ...
