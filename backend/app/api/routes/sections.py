"""Section CRUD, merge, split, and reorder endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_section_edit_service
from app.api.schemas import (
    SectionMergeRequest,
    SectionReorderRequest,
    SectionResponse,
    SectionSplitRequest,
)
from app.db.models import Book, BookSection

router = APIRouter(prefix="/api/v1/books/{book_id}/sections", tags=["sections"])


async def _get_book_or_404(book_id: int, db: AsyncSession) -> Book:
    result = await db.execute(
        select(Book).where(Book.id == book_id).options(selectinload(Book.sections))
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


def _section_to_response(section: BookSection) -> dict:
    default_summary = None
    summary_count = 0
    has_summary = section.default_summary_id is not None

    return {
        "id": section.id,
        "book_id": section.book_id,
        "title": section.title,
        "order_index": section.order_index,
        "section_type": section.section_type,
        "content_token_count": section.content_token_count,
        "content_md": section.content_md,
        "default_summary": default_summary,
        "summary_count": summary_count,
        "annotation_count": 0,
        "has_summary": has_summary,
    }


@router.get("")
async def list_sections(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all sections for a book."""
    book = await _get_book_or_404(book_id, db)
    return [
        SectionResponse(**_section_to_response(s))
        for s in sorted(book.sections, key=lambda s: s.order_index)
    ]


@router.get("/{section_id}")
async def get_section(
    book_id: int,
    section_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single section with content."""
    await _get_book_or_404(book_id, db)
    result = await db.execute(
        select(BookSection).where(
            BookSection.id == section_id,
            BookSection.book_id == book_id,
        )
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return SectionResponse(**_section_to_response(section))


@router.patch("/{section_id}")
async def update_section(
    book_id: int,
    section_id: int,
    title: str | None = None,
    section_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Update section title or type."""
    await _get_book_or_404(book_id, db)
    result = await db.execute(
        select(BookSection).where(
            BookSection.id == section_id,
            BookSection.book_id == book_id,
        )
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    if title is not None:
        section.title = title
    if section_type is not None:
        section.section_type = section_type
    await db.commit()
    return SectionResponse(**_section_to_response(section))


@router.delete("/{section_id}", status_code=204)
async def delete_section(
    book_id: int,
    section_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a section."""
    await _get_book_or_404(book_id, db)
    result = await db.execute(
        select(BookSection).where(
            BookSection.id == section_id,
            BookSection.book_id == book_id,
        )
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    await db.delete(section)
    await db.commit()


@router.post("/merge")
async def merge_sections(
    book_id: int,
    body: SectionMergeRequest,
    db: AsyncSession = Depends(get_db),
    section_edit_service=Depends(get_section_edit_service),
):
    """Merge adjacent sections."""
    await _get_book_or_404(book_id, db)
    if len(body.section_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 sections to merge")
    try:
        merged = await section_edit_service.merge_sections(
            book_id, body.section_ids, body.title
        )
        await db.commit()
        return SectionResponse(**_section_to_response(merged))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/{section_id}/split")
async def split_section(
    book_id: int,
    section_id: int,
    body: SectionSplitRequest,
    db: AsyncSession = Depends(get_db),
    section_edit_service=Depends(get_section_edit_service),
):
    """Split a section."""
    await _get_book_or_404(book_id, db)
    try:
        new_sections = await section_edit_service.split_section(
            book_id, section_id, body.mode, body.positions
        )
        await db.commit()
        return [SectionResponse(**_section_to_response(s)) for s in new_sections]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/reorder")
async def reorder_sections(
    book_id: int,
    body: SectionReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reorder sections by providing the new order of section IDs."""
    book = await _get_book_or_404(book_id, db)
    section_map = {s.id: s for s in book.sections}
    for idx, sid in enumerate(body.section_ids):
        if sid in section_map:
            section_map[sid].order_index = idx
    await db.commit()
    return [
        SectionResponse(**_section_to_response(s))
        for s in sorted(book.sections, key=lambda s: s.order_index)
    ]
