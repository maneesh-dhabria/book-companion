"""Audio resume-position routes — GET/PUT /api/v1/audio_position."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import ContentType
from app.db.repositories.audio_position_repo import AudioPositionRepository

router = APIRouter()


class PositionPut(BaseModel):
    content_type: str
    content_id: int
    browser_id: str = Field(..., min_length=1)
    sentence_index: int


@router.get("/api/v1/audio_position")
async def get_position(
    content_type: str,
    content_id: int,
    browser_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        ct = ContentType(content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="unknown content_type") from e
    repo = AudioPositionRepository(db)
    hint = await repo.get_with_hint(ct, content_id, browser_id)
    if hint is None:
        raise HTTPException(status_code=404, detail="no position recorded")
    return {
        "sentence_index": hint.sentence_index,
        "updated_at": hint.updated_at.isoformat() if hint.updated_at else None,
        "has_other_browser": hint.has_other_browser,
        "other_browser_updated_at": hint.other_browser_updated_at.isoformat()
        if hint.other_browser_updated_at
        else None,
    }


@router.put("/api/v1/audio_position")
async def put_position(
    body: PositionPut,
    db: AsyncSession = Depends(get_db),
):
    try:
        ct = ContentType(body.content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="unknown content_type") from e
    repo = AudioPositionRepository(db)
    landed = await repo.upsert(ct, body.content_id, body.browser_id, body.sentence_index)
    await db.commit()
    return {"landed": landed}
