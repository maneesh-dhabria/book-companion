"""Settings API endpoints — read/write config, DB stats, migration status."""

import asyncio

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_settings
from app.config import Settings
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


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
    """Partially update application settings. Writes to YAML config."""
    return svc.update_settings(updates)


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
