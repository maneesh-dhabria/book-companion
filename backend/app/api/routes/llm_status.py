"""GET /api/v1/llm/status — LLM CLI availability probe.

Reports whether the first auto-detected CLI (``claude`` > ``codex``) is on
PATH, plus a best-effort version string. Consumers use this to gate the
upload wizard's Start button and the BookSummaryView's Generate button.
"""

from __future__ import annotations

import asyncio
import re
import shutil

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.summarizer import detect_llm_provider

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])

logger = structlog.get_logger()

_VERSION_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)?(?:[A-Za-z0-9.\-+]+)?)\b")
_VERSION_TIMEOUT_SECONDS = 3.0


class LLMStatusResponse(BaseModel):
    available: bool
    provider: str | None
    version: str | None


async def _probe_version(cli: str) -> str | None:
    binary = shutil.which(cli)
    if binary is None:
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, PermissionError):
        return None
    try:
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=_VERSION_TIMEOUT_SECONDS
        )
    except TimeoutError:
        proc.kill()
        return None
    if proc.returncode != 0:
        return None
    text = stdout.decode(errors="replace").strip()
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


@router.get("/status", response_model=LLMStatusResponse)
async def llm_status() -> LLMStatusResponse:
    provider = detect_llm_provider()
    if provider is None:
        return LLMStatusResponse(available=False, provider=None, version=None)
    version = await _probe_version(provider)
    return LLMStatusResponse(available=True, provider=provider, version=version)
