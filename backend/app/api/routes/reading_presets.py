"""Reading Presets API endpoints — CRUD and activation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import (
    ReadingPresetCreateRequest,
    ReadingPresetListResponse,
    ReadingPresetResponse,
    ReadingPresetUpdateRequest,
)
from app.db.models import ReadingPreset

router = APIRouter(prefix="/api/v1/reading-presets", tags=["reading-presets"])


@router.get("", response_model=ReadingPresetListResponse)
async def list_reading_presets(
    db: AsyncSession = Depends(get_db),
):
    """List all reading presets with the id of the active/default preset."""
    result = await db.execute(
        select(ReadingPreset).order_by(
            ReadingPreset.is_system.desc(), ReadingPreset.name.asc()
        )
    )
    items = list(result.scalars().all())
    default = next((p for p in items if p.is_active), None)
    return {"items": items, "default_id": default.id if default else None}


@router.post("", response_model=ReadingPresetResponse, status_code=201)
async def create_reading_preset(
    body: ReadingPresetCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a user reading preset."""
    # Check name uniqueness
    result = await db.execute(
        select(ReadingPreset).where(ReadingPreset.name == body.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Preset '{body.name}' already exists")

    preset = ReadingPreset(
        name=body.name,
        font_family=body.font_family,
        font_size_px=body.font_size_px,
        line_spacing=body.line_spacing,
        content_width_px=body.content_width_px,
        theme=body.theme,
        is_system=False,
        is_active=False,
    )
    db.add(preset)
    await db.commit()
    await db.refresh(preset)
    return preset


@router.patch("/{preset_id}", response_model=ReadingPresetResponse)
async def update_reading_preset(
    preset_id: int,
    body: ReadingPresetUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a user reading preset. System presets cannot be modified."""
    result = await db.execute(
        select(ReadingPreset).where(ReadingPreset.id == preset_id)
    )
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    if preset.is_system:
        raise HTTPException(status_code=400, detail="Cannot modify system presets")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(preset, key, value)

    await db.commit()
    await db.refresh(preset)
    return preset


@router.delete("/{preset_id}", status_code=204)
async def delete_reading_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a user reading preset. System presets cannot be deleted."""
    result = await db.execute(
        select(ReadingPreset).where(ReadingPreset.id == preset_id)
    )
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    if preset.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system presets")

    was_active = preset.is_active
    await db.delete(preset)

    if was_active:
        # Activate Comfortable fallback
        comfortable = await db.execute(
            select(ReadingPreset).where(
                ReadingPreset.name == "Comfortable", ReadingPreset.is_system.is_(True)
            )
        )
        fallback = comfortable.scalar_one_or_none()
        if fallback:
            fallback.is_active = True

    await db.commit()


@router.post("/{preset_id}/activate", response_model=ReadingPresetResponse)
async def activate_reading_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Activate a reading preset, deactivating all others."""
    result = await db.execute(
        select(ReadingPreset).where(ReadingPreset.id == preset_id)
    )
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    # Deactivate all presets
    await db.execute(
        update(ReadingPreset).values(is_active=False)
    )
    # Activate the target
    preset.is_active = True
    await db.commit()
    await db.refresh(preset)
    return preset
