"""Reading Presets API endpoints — read-only after v1.5.1.

FR-F4.3 / FR-F4.4 / D16: POST/PATCH/DELETE/activate are gone. The single
mutation surface is the v1_5_1 Alembic migration. Frontend reads via
``GET ""`` and consumes any captured legacy-active name via
``GET /legacy-active-hint`` (one-shot, deletes the sidecar on first read).
"""

import contextlib
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import ReadingPresetListResponse
from app.db.models import ReadingPreset

router = APIRouter(prefix="/api/v1/reading-presets", tags=["reading-presets"])


@router.get("", response_model=ReadingPresetListResponse)
async def list_reading_presets(
    db: AsyncSession = Depends(get_db),
):
    """List all (system) reading presets ordered by name."""
    result = await db.execute(select(ReadingPreset).order_by(ReadingPreset.name.asc()))
    items = list(result.scalars().all())
    return {"items": items}


@router.get("/legacy-active-hint")
async def get_legacy_active_hint(request: Request):
    """Return the legacy active preset name captured by the v1_5_1 migration.

    FR-F4.7c / P3: returns ``{"name": "<preset>"}`` on first call, deletes the
    sidecar file, then returns ``{"name": null}`` on every subsequent call.

    Reads ``app.state.settings`` (the per-app instance set by ``create_app``)
    so per-test data directories are honoured.
    """
    settings = request.app.state.settings
    path = Path(settings.data.directory) / "migration_v1_5_1_legacy_active.txt"
    if not path.exists():
        return {"name": None}
    name = path.read_text().strip()
    # If we can't delete it, the next read will return the same name —
    # acceptable degradation; data dir is single-user single-process.
    with contextlib.suppress(OSError):
        path.unlink()
    return {"name": name or None}
