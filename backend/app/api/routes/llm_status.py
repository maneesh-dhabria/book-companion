"""LLM preflight + recheck routes.

``GET /api/v1/llm/status`` reads from the in-process preflight cache (60 s
TTL) so polling is cheap. ``POST /api/v1/llm/recheck`` invalidates the
cache and re-probes — used by the Settings page "Re-detect" button after
the user installs/upgrades a CLI without changing config.

Spec refs: FR-B09, FR-B08, FR-B08a, §8.1, §8.1a.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_settings
from app.config import Settings
from app.services.llm_preflight import PreflightResult, get_preflight_service
from app.services.summarizer import detect_llm_provider

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])


def _resolve_provider(settings: Settings) -> str | None:
    """Return the binary the system would actually invoke right now.

    For ``provider="auto"``, this resolves via ``detect_llm_provider()`` so
    the UI can render "auto (→ claude 2.1.123)" instead of just "auto".
    """
    if settings.llm.provider == "auto":
        return detect_llm_provider()
    return settings.llm.provider


def _build_response(settings: Settings, result: PreflightResult) -> dict:
    resolved = _resolve_provider(settings)
    return {
        # configured value, e.g. "auto" / "claude" / "codex"
        "configured_provider": settings.llm.provider,
        # resolved binary; None if auto-detection found nothing
        "provider": resolved or settings.llm.provider,
        "preflight": result.model_dump(),
    }


@router.get("/status")
async def llm_status(settings: Settings = Depends(get_settings)) -> dict:
    svc = get_preflight_service()
    result = await svc.check(settings.llm.provider)
    return _build_response(settings, result)


@router.post("/recheck")
async def llm_recheck(settings: Settings = Depends(get_settings)) -> dict:
    svc = get_preflight_service()
    svc.invalidate_cache()
    result = await svc.check(settings.llm.provider)
    return _build_response(settings, result)
