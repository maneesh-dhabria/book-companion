"""LLM preflight service.

Single source of truth for "is the LLM CLI usable right now?". Used by:
- ``GET /api/v1/llm/status`` (Settings page banner)
- The processing-queue worker before promoting a PENDING job to RUNNING
- The summarize route, as a 400-gate before queueing

Cache: 60 s TTL, in-process, keyed by resolved provider. Invalidated by
``SettingsService.update_settings()`` after every successful PATCH so a
config change picks up on the next read instead of waiting out the TTL.

Spec refs: FR-B08, FR-B08a, NFR-01.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import time

import structlog
from pydantic import BaseModel

from app.services.summarizer import detect_llm_provider

log = structlog.get_logger(__name__)

VERSION_FLOORS: dict[str, tuple[int, int, int]] = {
    "claude": (2, 1, 0),
    "codex": (0, 118, 0),
}

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class PreflightResult(BaseModel):
    """Result of a preflight check.

    ``ok`` reflects whether summarization can proceed at all (i.e. binary
    resolved). Version-floor failures are ``ok=True, version_ok=False`` —
    a non-blocking warning surfaced to the UI banner.
    """

    ok: bool
    provider: str | None
    binary: str | None
    binary_resolved: bool
    version: str | None
    version_ok: bool
    reason: str | None


class LLMPreflightService:
    def __init__(self, ttl_seconds: float = 60.0) -> None:
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, PreflightResult]] = {}

    def invalidate_cache(self, provider: str | None = None) -> None:
        if provider is None:
            self._cache.clear()
        else:
            self._cache.pop(provider, None)

    async def check(self, provider: str) -> PreflightResult:
        cached = self._cache.get(provider)
        if cached is not None:
            ts, result = cached
            if time.monotonic() - ts < self._ttl:
                return result

        result = await self._probe(provider)
        self._cache[provider] = (time.monotonic(), result)
        return result

    async def _probe(self, provider: str) -> PreflightResult:
        resolved_provider = provider
        if provider == "auto":
            detected = detect_llm_provider()
            if detected is None:
                return PreflightResult(
                    ok=False,
                    provider=None,
                    binary=None,
                    binary_resolved=False,
                    version=None,
                    version_ok=False,
                    reason="No LLM CLI found on PATH (tried claude, codex). "
                    "Install Claude Code CLI or Codex CLI.",
                )
            resolved_provider = detected

        binary = resolved_provider
        which = shutil.which(binary)
        if which is None:
            return PreflightResult(
                ok=False,
                provider=resolved_provider,
                binary=binary,
                binary_resolved=False,
                version=None,
                version_ok=False,
                reason=f"{binary!r} not found on PATH. Install it or add it to PATH.",
            )

        version, version_ok = await self._probe_version(binary)
        if version is None:
            return PreflightResult(
                ok=True,  # binary works; version probe is best-effort
                provider=resolved_provider,
                binary=binary,
                binary_resolved=True,
                version=None,
                version_ok=False,
                reason=f"Could not determine {binary!r} version.",
            )

        floor = VERSION_FLOORS.get(binary)
        if floor and not version_ok:
            return PreflightResult(
                ok=True,  # non-blocking warning
                provider=resolved_provider,
                binary=binary,
                binary_resolved=True,
                version=version,
                version_ok=False,
                reason=(
                    f"{binary} {version} is below the recommended floor "
                    f"({floor[0]}.{floor[1]}.{floor[2]}). Some features may not work."
                ),
            )

        return PreflightResult(
            ok=True,
            provider=resolved_provider,
            binary=binary,
            binary_resolved=True,
            version=version,
            version_ok=True,
            reason=None,
        )

    async def _probe_version(self, binary: str) -> tuple[str | None, bool]:
        try:
            proc = await asyncio.create_subprocess_exec(
                binary,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return None, False

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except TimeoutError:
            proc.kill()
            return None, False

        text = (stdout or b"").decode(errors="replace") + (stderr or b"").decode(
            errors="replace"
        )
        match = _VERSION_RE.search(text)
        if match is None:
            return None, False

        version_tuple = tuple(int(x) for x in match.groups())
        version_str = ".".join(str(x) for x in version_tuple)
        floor = VERSION_FLOORS.get(binary)
        version_ok = floor is None or version_tuple >= floor
        return version_str, version_ok


_preflight_singleton: LLMPreflightService | None = None


def get_preflight_service() -> LLMPreflightService:
    global _preflight_singleton
    if _preflight_singleton is None:
        _preflight_singleton = LLMPreflightService()
    return _preflight_singleton
