"""Settings API endpoints — read/write config, DB stats, migration status."""

import asyncio

from fastapi import APIRouter, Body, Depends, HTTPException
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
