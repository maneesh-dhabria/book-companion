"""Summary list, compare, and set-default endpoints."""

from __future__ import annotations

import contextlib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.api.deps import get_db, get_summary_service
from app.api.schemas import SummaryCompareResponse, SummaryResponse
from app.db.models import Book, BookSection, Summary

router = APIRouter(tags=["summaries"])


@router.get("/api/v1/books/{book_id}/summaries")
async def list_summaries(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all summaries for a book."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    result = await db.execute(
        select(Summary).where(Summary.book_id == book_id).order_by(Summary.created_at.desc())
    )
    summaries = result.scalars().all()
    return [SummaryResponse.model_validate(s) for s in summaries]


@router.get("/api/v1/summaries/{summary_id}")
async def get_summary(
    summary_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single summary."""
    result = await db.execute(select(Summary).where(Summary.id == summary_id))
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return SummaryResponse.model_validate(summary)


@router.get("/api/v1/summaries/compare")
async def compare_summaries(
    id1: int = Query(...),
    id2: int = Query(...),
    db: AsyncSession = Depends(get_db),
    summary_service=Depends(get_summary_service),
):
    """Compare two summaries with concept diff."""
    result1 = await db.execute(select(Summary).where(Summary.id == id1))
    s1 = result1.scalar_one_or_none()
    result2 = await db.execute(select(Summary).where(Summary.id == id2))
    s2 = result2.scalar_one_or_none()

    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="One or both summaries not found")

    concept_diff = None
    with contextlib.suppress(Exception):
        concept_diff = await summary_service.compare_summaries(id1, id2)

    return SummaryCompareResponse(
        summary_a=SummaryResponse.model_validate(s1),
        summary_b=SummaryResponse.model_validate(s2),
        concept_diff=concept_diff,
    )


@router.post("/api/v1/summaries/{summary_id}/set-default")
async def set_default(
    summary_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Set a summary as the default for its section/book."""
    result = await db.execute(select(Summary).where(Summary.id == summary_id))
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    content_type = summary.content_type
    if hasattr(content_type, "value"):
        content_type = content_type.value

    if content_type == "section":
        result = await db.execute(select(BookSection).where(BookSection.id == summary.content_id))
        section = result.scalar_one_or_none()
        if section:
            section.default_summary_id = summary.id
    elif content_type == "book":
        result = await db.execute(select(Book).where(Book.id == summary.content_id))
        book = result.scalar_one_or_none()
        if book:
            book.default_summary_id = summary.id

    await db.commit()
    return SummaryResponse.model_validate(summary)
