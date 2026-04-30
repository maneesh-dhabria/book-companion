"""Section CRUD, merge, split, reorder endpoints + edit-impact + split-preview.

Phase D additions (Section editing during/after summarization):

* ``GET /edit-impact`` — returns the set of summaries that would become
  stale if the given section IDs are mutated (FR-B18).
* ``GET /{section_id}/split-preview`` — 3-mode preview (heading / paragraph
  / char) without mutating (FR-B18a).
* All mutating routes (PATCH, DELETE, merge, split, reorder) now:
  1. 409 when an active processing_jobs row exists for the book (FR-B20)
  2. Auto-mark affected ``summaries.is_stale=True`` in the same transaction
     (FR-B19)
  3. Revert ``Book.default_summary_id=None`` and ``Book.status=PARSED``
     when the book-level summary's coverage is invalidated (FR-B21).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_section_edit_service
from app.api.schemas import (
    SectionMergeRequest,
    SectionReorderRequest,
    SectionResponse,
    SectionSplitRequest,
    SummaryBriefResponse,
)
from app.db.models import (
    Book,
    BookSection,
    BookStatus,
    ProcessingJob,
    ProcessingJobStatus,
    Summary,
)
from app.services.parser.section_classifier import SUMMARIZABLE_TYPES

router = APIRouter(prefix="/api/v1/books/{book_id}/sections", tags=["sections"])

MAX_TITLE_LEN = 500


async def _reject_if_active_job(book_id: int, db: AsyncSession) -> None:
    """409 if a PENDING/RUNNING processing_jobs row exists for the book.

    FR-B20: edits during a job would race the worker. Block at the API
    boundary.
    """
    active = (
        await db.execute(
            select(ProcessingJob.id).where(
                ProcessingJob.book_id == book_id,
                ProcessingJob.status.in_(
                    [ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING]
                ),
            )
        )
    ).scalar_one_or_none()
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "summarization_in_progress",
                "message": (
                    "Cannot edit sections while a summarization job is active. "
                    "Cancel the job or wait for it to finish."
                ),
            },
        )


async def _affected_summary_ids(
    db: AsyncSession, section_ids: list[int]
) -> list[int]:
    if not section_ids:
        return []
    rows = (
        await db.execute(
            select(Summary.id).where(
                Summary.content_type == "section",
                Summary.content_id.in_(section_ids),
                Summary.is_stale.is_(False),
            )
        )
    ).scalars().all()
    return list(rows)


async def _mark_summaries_stale_and_revert_book(
    db: AsyncSession, book: Book, section_ids: list[int]
) -> None:
    """Mark section-level summaries stale; revert book status if any non-stale
    section summary belongs to the affected set (FR-B19, FR-B21, P3, P4)."""
    if not section_ids:
        return
    affected = await _affected_summary_ids(db, section_ids)
    if not affected:
        return
    await db.execute(
        update(Summary)
        .where(Summary.id.in_(affected))
        .values(is_stale=True)
    )
    # Book summary invalidation: any structural change to a section that
    # contributed to the book summary invalidates the book-level conclusion.
    if book.default_summary_id is not None:
        book.default_summary_id = None
        if book.status == BookStatus.COMPLETED:
            book.status = BookStatus.PARSED


async def _get_book_or_404(book_id: int, db: AsyncSession) -> Book:
    result = await db.execute(
        select(Book).where(Book.id == book_id).options(selectinload(Book.sections))
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


async def _build_section_response(
    section: BookSection,
    db: AsyncSession,
    include_content: bool = False,
) -> dict:
    """Build section response dict, fetching summary data from DB."""
    has_summary = section.default_summary_id is not None
    default_summary = None

    if has_summary:
        result = await db.execute(select(Summary).where(Summary.id == section.default_summary_id))
        summary = result.scalar_one_or_none()
        if summary:
            default_summary = SummaryBriefResponse(
                id=summary.id,
                preset_name=summary.preset_name,
                model_used=summary.model_used,
                summary_char_count=summary.summary_char_count,
                created_at=summary.created_at,
                summary_md=summary.summary_md,
            ).model_dump()

    # Count all summaries for this section
    count_result = await db.execute(
        select(func.count(Summary.id)).where(
            Summary.content_id == section.id,
            Summary.content_type == "section",
        )
    )
    summary_count = count_result.scalar() or 0

    return {
        "id": section.id,
        "book_id": section.book_id,
        "title": section.title,
        "order_index": section.order_index,
        "section_type": section.section_type,
        "content_token_count": section.content_token_count,
        "content_md": section.content_md if include_content else None,
        "default_summary": default_summary,
        "summary_count": summary_count,
        "annotation_count": 0,
        "has_summary": has_summary,
        "is_summarizable": section.section_type in SUMMARIZABLE_TYPES,
    }


@router.get("")
async def list_sections(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all sections for a book."""
    book = await _get_book_or_404(book_id, db)
    results = []
    for s in sorted(book.sections, key=lambda s: s.order_index):
        results.append(SectionResponse(**await _build_section_response(s, db)))
    return results


@router.get("/edit-impact")
async def section_edit_impact(
    book_id: int,
    section_ids: str = Query(..., description="Comma-separated section IDs"),
    db: AsyncSession = Depends(get_db),
):
    """Compute summary-invalidation impact for a proposed edit (FR-B18 / T15).

    Used by the StructureEditor confirm dialog to surface "this will mark X
    summaries stale and revert the book summary" before the user commits.

    NOTE: Registered BEFORE the parameterized ``GET /{section_id}`` route so
    FastAPI doesn't try to coerce ``edit-impact`` into ``section_id: int``.
    """
    book = await _get_book_or_404(book_id, db)
    try:
        ids = [int(s) for s in section_ids.split(",") if s.strip()]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not ids:
        return {
            "summaries_to_invalidate": [],
            "invalidate_book_summary": False,
            "summarized_section_count": 0,
        }
    affected_summary_ids = await _affected_summary_ids(db, ids)
    summarized_section_count = (
        await db.execute(
            select(func.count(func.distinct(Summary.content_id))).where(
                Summary.content_type == "section",
                Summary.content_id.in_(ids),
                Summary.is_stale.is_(False),
            )
        )
    ).scalar() or 0
    invalidate_book_summary = (
        bool(affected_summary_ids) and book.default_summary_id is not None
    )
    return {
        "summaries_to_invalidate": affected_summary_ids,
        "invalidate_book_summary": invalidate_book_summary,
        "summarized_section_count": int(summarized_section_count),
    }


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
    return SectionResponse(**await _build_section_response(section, db, include_content=True))


@router.patch("/{section_id}")
async def update_section(
    book_id: int,
    section_id: int,
    payload: dict[str, Any] = Body(...),  # noqa: B008
    db: AsyncSession = Depends(get_db),
):
    """Update section title and/or type. FR-B19/B20/B21."""
    book = await _get_book_or_404(book_id, db)
    await _reject_if_active_job(book_id, db)

    result = await db.execute(
        select(BookSection).where(
            BookSection.id == section_id,
            BookSection.book_id == book_id,
        )
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    title = payload.get("title")
    section_type = payload.get("section_type")
    structural_change = False

    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise HTTPException(
                status_code=400,
                detail={"error": "title_required", "message": "Title cannot be empty"},
            )
        if len(cleaned) > MAX_TITLE_LEN:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "title_too_long",
                    "message": f"Title must be {MAX_TITLE_LEN} characters or less",
                },
            )
        # Title-only edits don't invalidate summaries (the summary is over the
        # CONTENT, not the title). Section-type edits DO change which sections
        # are summarizable, so they invalidate.
        section.title = cleaned

    if section_type is not None and section_type != section.section_type:
        section.section_type = section_type
        structural_change = True

    if structural_change:
        await _mark_summaries_stale_and_revert_book(db, book, [section_id])

    await db.commit()
    return SectionResponse(**await _build_section_response(section, db))


@router.delete("/{section_id}", status_code=204)
async def delete_section(
    book_id: int,
    section_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a section. FR-B19/B20/B21."""
    book = await _get_book_or_404(book_id, db)
    await _reject_if_active_job(book_id, db)
    result = await db.execute(
        select(BookSection).where(
            BookSection.id == section_id,
            BookSection.book_id == book_id,
        )
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    await _mark_summaries_stale_and_revert_book(db, book, [section_id])
    await db.delete(section)
    await db.commit()


@router.post("/merge")
async def merge_sections(
    book_id: int,
    body: SectionMergeRequest,
    db: AsyncSession = Depends(get_db),
    section_edit_service=Depends(get_section_edit_service),
):
    """Merge adjacent sections. FR-B19/B20/B21."""
    book = await _get_book_or_404(book_id, db)
    await _reject_if_active_job(book_id, db)
    if len(body.section_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 sections to merge")
    try:
        await _mark_summaries_stale_and_revert_book(db, book, list(body.section_ids))
        merged = await section_edit_service.merge_sections(book_id, body.section_ids, body.title)
        await db.commit()
        return SectionResponse(**await _build_section_response(merged, db))
    except HTTPException:
        raise
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
    """Split a section. FR-B19/B20/B21."""
    book = await _get_book_or_404(book_id, db)
    await _reject_if_active_job(book_id, db)
    try:
        await _mark_summaries_stale_and_revert_book(db, book, [section_id])
        new_sections = await section_edit_service.split_section(
            book_id, section_id, body.mode, body.positions
        )
        await db.commit()
        results = []
        for s in new_sections:
            results.append(SectionResponse(**await _build_section_response(s, db)))
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/{section_id}/split-preview")
async def split_preview(
    book_id: int,
    section_id: int,
    mode: str = Query(..., pattern="^(heading|paragraph|char)$"),
    position: int | None = Query(None, ge=0),
    db: AsyncSession = Depends(get_db),
    section_edit_service=Depends(get_section_edit_service),
):
    """Compute split candidates without mutating (FR-B18a / T16).

    Modes:
    * ``heading`` — every Markdown heading detected in the content becomes a
      candidate boundary.
    * ``paragraph`` — every blank-line boundary becomes a candidate.
    * ``char`` — single boundary at ``position``; preview shows the two halves.
    """
    await _get_book_or_404(book_id, db)
    section = (
        await db.execute(
            select(BookSection).where(
                BookSection.id == section_id,
                BookSection.book_id == book_id,
            )
        )
    ).scalar_one_or_none()
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    content = section.content_md or ""
    candidates: list[dict] = []

    if mode == "heading":
        boundaries: list[tuple[str, int]] = []
        for i, line in enumerate(content.splitlines(keepends=True)):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                boundaries.append((line.strip().lstrip("# ").strip(), _line_offset(content, i)))
        if not boundaries:
            return {"candidates": [], "mode": mode}
        # Build candidates as (title, start, end)
        for idx, (title, start) in enumerate(boundaries):
            end = boundaries[idx + 1][1] if idx + 1 < len(boundaries) else len(content)
            chunk = content[start:end]
            first_line = next(
                (line for line in chunk.splitlines() if line.strip() and not line.lstrip().startswith("#")),
                "",
            )
            candidates.append(
                {
                    "title": title or f"Part {idx + 1}",
                    "char_count": len(chunk),
                    "first_line": first_line[:200],
                    "start": start,
                    "end": end,
                }
            )

    elif mode == "paragraph":
        # Boundaries between paragraphs (blank-line separated). Skip
        # zero-length pieces.
        pieces: list[tuple[int, int]] = []
        cursor = 0
        for chunk in content.split("\n\n"):
            if not chunk.strip():
                cursor += len(chunk) + 2
                continue
            start = cursor
            end = cursor + len(chunk)
            pieces.append((start, end))
            cursor = end + 2
        for idx, (start, end) in enumerate(pieces):
            chunk = content[start:end]
            first_line = next((line for line in chunk.splitlines() if line.strip()), "")
            candidates.append(
                {
                    "title": f"Paragraph {idx + 1}",
                    "char_count": len(chunk),
                    "first_line": first_line[:200],
                    "start": start,
                    "end": end,
                }
            )

    elif mode == "char":
        if position is None or position <= 0 or position >= len(content):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_position",
                    "message": (
                        f"position must be 1..{max(0, len(content) - 1)}; "
                        f"got {position}"
                    ),
                },
            )
        # Snap to nearest non-whitespace boundary
        if content[position].isspace():
            # walk forward to non-whitespace
            snap = position
            while snap < len(content) and content[snap].isspace():
                snap += 1
            position = snap
        for idx, (start, end) in enumerate([(0, position), (position, len(content))]):
            chunk = content[start:end]
            first_line = next((line for line in chunk.splitlines() if line.strip()), "")
            candidates.append(
                {
                    "title": f"Part {idx + 1}",
                    "char_count": len(chunk),
                    "first_line": first_line[:200],
                    "start": start,
                    "end": end,
                }
            )

    return {"candidates": candidates, "mode": mode}


def _line_offset(content: str, line_index: int) -> int:
    """Char offset where the given line starts. Cheap O(line_index)."""
    if line_index == 0:
        return 0
    offset = 0
    for i, line in enumerate(content.splitlines(keepends=True)):
        if i == line_index:
            return offset
        offset += len(line)
    return offset


@router.post("/reorder")
async def reorder_sections(
    book_id: int,
    body: SectionReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reorder sections by providing the new order of section IDs.

    Reorder is structural enough that the book-level summary's narrative
    ordering is no longer trustworthy; mark stale + revert (FR-B19/B21).
    Per-section summaries are NOT marked stale — the content didn't change.
    """
    book = await _get_book_or_404(book_id, db)
    await _reject_if_active_job(book_id, db)
    section_map = {s.id: s for s in book.sections}
    for idx, sid in enumerate(body.section_ids):
        if sid in section_map:
            section_map[sid].order_index = idx
    if book.default_summary_id is not None:
        book.default_summary_id = None
        if book.status == BookStatus.COMPLETED:
            book.status = BookStatus.PARSED
    await db.commit()
    results = []
    for s in sorted(book.sections, key=lambda s: s.order_index):
        results.append(SectionResponse(**await _build_section_response(s, db)))
    return results
