"""Settings API endpoints — read/write config, DB stats, migration status."""

import asyncio

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_settings
from app.config import Settings
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
# Separate router so the shipped models.yaml surfaces as /api/v1/config/models.
config_router = APIRouter(prefix="/api/v1/config", tags=["config"])


def _get_settings_service(
    settings: Settings = Depends(get_settings),
) -> SettingsService:
    return SettingsService(settings=settings)


@router.get("")
async def get_settings_endpoint(
    svc: SettingsService = Depends(_get_settings_service),
):
    """Return application settings with sensitive values masked."""
    return svc.get_safe_settings()


@router.patch("")
async def patch_settings(
    updates: dict = Body(...),
    svc: SettingsService = Depends(_get_settings_service),
):
    """Partially update application settings. Writes to YAML config.

    Strict validation (FR-F1.4 / D17): unknown nested keys, type mismatches,
    or any failure in any field → 400 with a FastAPI-shape ``detail`` array;
    the on-disk YAML and in-memory state are unchanged.
    """
    try:
        return svc.update_settings(updates)
    except ValidationError as e:
        # ValidationError.errors() returns dicts that may contain ctx values
        # carrying non-JSON-serialisable objects (e.g. ValueError instances).
        # Strip them so FastAPI can JSON-encode the response cleanly.
        cleaned = []
        for err in e.errors():
            cleaned.append(
                {
                    "type": err.get("type"),
                    "loc": list(err.get("loc", ())),
                    "msg": err.get("msg"),
                    "input": err.get("input"),
                }
            )
        raise HTTPException(status_code=400, detail=cleaned) from e


# --- TTS (B16) ---------------------------------------------------------------


@router.get("/tts")
async def get_tts_settings(settings: Settings = Depends(get_settings)):
    return {
        "engine": settings.tts.engine,
        "voice": settings.tts.voice,
        "default_speed": settings.tts.default_speed,
        "auto_advance": settings.tts.auto_advance,
        "prewarm_on_startup": settings.tts.prewarm_on_startup,
    }


@router.put("/tts")
async def put_tts_settings(
    body: dict = Body(...),
    svc: SettingsService = Depends(_get_settings_service),
    settings: Settings = Depends(get_settings),
):
    if body.get("engine") == "kokoro" and body.get("voice"):
        from app.services.tts.kokoro_provider import KOKORO_VOICES

        if body["voice"] not in KOKORO_VOICES:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "unknown_voice",
                    "available": sorted(KOKORO_VOICES),
                },
            )
    try:
        return svc.update_settings({"tts": body})
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/tts/status")
async def get_tts_status(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    """Return the engine warm-up state for the UI status chip."""
    if settings.tts.engine != "kokoro":
        return {"status": "n/a"}

    from pathlib import Path as _Path

    md = _Path(settings.data.directory) / "models" / "tts"
    onnx = md / "kokoro-v1.0.onnx"
    bin_ = md / "voices-v1.0.bin"
    if not onnx.exists() or not bin_.exists():
        return {"status": "not_downloaded"}

    warm = bool(getattr(request.app.state, "tts_warm", False))
    return {"status": "warm" if warm else "cold"}


@router.get("/database-stats")
async def get_database_stats(
    db: AsyncSession = Depends(get_db),
    svc: SettingsService = Depends(_get_settings_service),
):
    """Return row counts for each database table."""
    return await svc.get_database_stats(db)


@router.get("/migration-status")
async def get_migration_status(
    svc: SettingsService = Depends(_get_settings_service),
):
    """Return current and latest Alembic migration revision."""
    return await svc.get_migration_status()


@router.post("/run-migrations")
async def run_migrations():
    """Run alembic upgrade head as a subprocess."""
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "alembic",
        "upgrade",
        "head",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {stderr.decode().strip()}",
        )
    return {"status": "ok", "output": stdout.decode().strip()}


# --- T16: /config/models surface ---


@config_router.get("/models")
async def get_config_models(
    svc: SettingsService = Depends(_get_settings_service),
    settings: Settings = Depends(get_settings),
):
    """Return the shipped models.yaml candidate list + the auto-detected
    provider so the Settings UI can pre-select a default dropdown value."""
    from app.services.summarizer import detect_llm_provider

    data = svc.load_models()
    detected = detect_llm_provider() if settings.llm.provider == "auto" else None
    return {**data, "detected_provider": detected, "current_model": settings.llm.model}
