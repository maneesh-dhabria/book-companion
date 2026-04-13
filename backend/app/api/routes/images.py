"""Image serving — looks up Image by id and returns the binary."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.api.deps import get_db
from app.db.models import Image

router = APIRouter(prefix="/api/v1/images", tags=["images"])


@router.get("/{image_id}")
async def get_image(image_id: int, db: AsyncSession = Depends(get_db)):
    # `Image.data` is a deferred column — undefer so it loads eagerly.
    result = await db.execute(
        select(Image).where(Image.id == image_id).options(undefer(Image.data))
    )
    image = result.scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(
        content=image.data,
        media_type=image.mime_type or "image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
