"""Library view CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.api.deps import get_db
from app.api.schemas import (
    LibraryViewCreateRequest,
    LibraryViewResponse,
    LibraryViewUpdateRequest,
)
from app.db.models import LibraryView

router = APIRouter(prefix="/api/v1/views", tags=["views"])


@router.get("")
async def list_views(
    db: AsyncSession = Depends(get_db),
):
    """List all library views ordered by position."""
    result = await db.execute(select(LibraryView).order_by(LibraryView.position))
    views = result.scalars().all()
    return [LibraryViewResponse.model_validate(v) for v in views]


@router.post("", status_code=201)
async def create_view(
    body: LibraryViewCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new library view."""
    # Get max position
    result = await db.execute(select(LibraryView).order_by(LibraryView.position.desc()))
    existing = result.scalars().first()
    next_position = (existing.position + 1) if existing else 0

    view = LibraryView(
        name=body.name,
        display_mode=body.display_mode,
        sort_field=body.sort_field,
        sort_direction=body.sort_direction,
        filters=body.filters,
        table_columns=body.table_columns,
        position=next_position,
    )
    db.add(view)
    await db.commit()
    await db.refresh(view)
    return LibraryViewResponse.model_validate(view)


@router.patch("/{view_id}")
async def update_view(
    view_id: int,
    body: LibraryViewUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a library view."""
    result = await db.execute(select(LibraryView).where(LibraryView.id == view_id))
    view = result.scalar_one_or_none()
    if not view:
        raise HTTPException(status_code=404, detail="View not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(view, field, value)
    await db.commit()
    await db.refresh(view)
    return LibraryViewResponse.model_validate(view)


@router.delete("/{view_id}", status_code=204)
async def delete_view(
    view_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a library view (cannot delete default)."""
    result = await db.execute(select(LibraryView).where(LibraryView.id == view_id))
    view = result.scalar_one_or_none()
    if not view:
        raise HTTPException(status_code=404, detail="View not found")
    if view.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default view")

    await db.delete(view)
    await db.commit()


class ViewReorderRequest(BaseModel):
    view_ids: list[int]


@router.post("/reorder")
async def reorder_views(
    body: ViewReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reorder views by providing new order of view IDs."""
    result = await db.execute(select(LibraryView))
    views = {v.id: v for v in result.scalars().all()}

    for idx, vid in enumerate(body.view_ids):
        if vid in views:
            views[vid].position = idx
    await db.commit()

    result = await db.execute(select(LibraryView).order_by(LibraryView.position))
    return [LibraryViewResponse.model_validate(v) for v in result.scalars().all()]
