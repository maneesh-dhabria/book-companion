"""Annotation API endpoints — CRUD, linking, and export."""

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_annotation_repo, get_db
from app.api.schemas import (
    AnnotationCreateRequest,
    AnnotationExportFormat,
    AnnotationLinkRequest,
    AnnotationResponse,
    AnnotationUpdateRequest,
)
from app.db.models import Annotation, AnnotationType, Book, BookSection, ContentType
from app.db.repositories.annotation_repo import AnnotationRepository


async def _enrich_with_context(
    db: AsyncSession,
    annotations: list[Annotation],
) -> list[dict]:
    """Return annotation dicts augmented with book + section titles.

    Resolves ``content_id`` → section → book for section-scoped annotations.
    Annotations against other content types keep their book/section fields
    as null (the frontend can still render the note itself).
    """
    from sqlalchemy import select

    section_ids = {
        a.content_id
        for a in annotations
        if a.content_type in (ContentType.SECTION_CONTENT, ContentType.SECTION_SUMMARY)
    }
    section_rows: dict[int, tuple[int, str, str]] = {}
    if section_ids:
        rows = (
            await db.execute(
                select(
                    BookSection.id,
                    BookSection.title,
                    BookSection.book_id,
                    Book.title,
                )
                .join(Book, Book.id == BookSection.book_id)
                .where(BookSection.id.in_(section_ids))
            )
        ).all()
        for sec_id, sec_title, book_id, book_title in rows:
            section_rows[sec_id] = (book_id, book_title, sec_title)

    items: list[dict] = []
    for a in annotations:
        payload = AnnotationResponse.model_validate(a).model_dump()
        if a.content_type in (ContentType.SECTION_CONTENT, ContentType.SECTION_SUMMARY):
            ctx = section_rows.get(a.content_id)
            if ctx is not None:
                book_id, book_title, section_title = ctx
                payload["book_id"] = book_id
                payload["book_title"] = book_title
                payload["section_id"] = a.content_id
                payload["section_title"] = section_title
        items.append(payload)
    return items

router = APIRouter(prefix="/api/v1/annotations", tags=["annotations"])


@router.get("/export")
async def export_annotations(
    format: AnnotationExportFormat = Query("markdown"),
    book_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    repo: AnnotationRepository = Depends(get_annotation_repo),
):
    """Export annotations as markdown, JSON, or CSV file download."""
    if book_id:
        annotations = await repo.list_by_book(book_id)
    else:
        # List all annotations
        from sqlalchemy import select

        result = await db.execute(select(Annotation).order_by(Annotation.created_at.desc()))
        annotations = list(result.scalars().all())

    if format == "markdown":
        lines = ["# Annotations Export", ""]
        for ann in annotations:
            lines.append(f"## {ann.type.value.title()}")
            if ann.selected_text:
                lines.append(f"> {ann.selected_text}")
                lines.append("")
            if ann.note:
                lines.append(ann.note)
                lines.append("")
            lines.append(f"*Type: {ann.type.value} | Created: {ann.created_at.isoformat()}*")
            lines.append("")
            lines.append("---")
            lines.append("")
        content = "\n".join(lines)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=annotations.md"},
        )
    elif format == "json":
        data = [
            {
                "id": ann.id,
                "content_type": ann.content_type.value,
                "content_id": ann.content_id,
                "type": ann.type.value,
                "selected_text": ann.selected_text,
                "note": ann.note,
                "text_start": ann.text_start,
                "text_end": ann.text_end,
                "created_at": ann.created_at.isoformat(),
            }
            for ann in annotations
        ]
        content = json.dumps(data, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=annotations.json"},
        )
    else:
        # CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["id", "content_type", "content_id", "type", "selected_text", "note", "created_at"]
        )
        for ann in annotations:
            writer.writerow(
                [
                    ann.id,
                    ann.content_type.value,
                    ann.content_id,
                    ann.type.value,
                    ann.selected_text,
                    ann.note,
                    ann.created_at.isoformat(),
                ]
            )
        content = output.getvalue()
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=annotations.csv"},
        )


@router.get("", response_model=dict)
async def list_annotations(
    content_type: str | None = Query(None),
    content_id: int | None = Query(None),
    book_id: int | None = Query(None),
    type: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    repo: AnnotationRepository = Depends(get_annotation_repo),
):
    """List annotations with optional filters."""
    annotation_type = None
    if type:
        try:
            annotation_type = AnnotationType(type)
        except ValueError as err:
            raise HTTPException(
                status_code=422, detail=f"Invalid annotation type: {type}"
            ) from err

    if content_type and content_id:
        try:
            ct = ContentType(content_type)
        except ValueError as err:
            raise HTTPException(
                status_code=422, detail=f"Invalid content type: {content_type}"
            ) from err
        annotations = await repo.list_by_content(ct, content_id, annotation_type)
    elif book_id:
        annotations = await repo.list_by_book(book_id, annotation_type)
    else:
        # List all — use repo session directly
        from sqlalchemy import select

        query = select(Annotation).order_by(Annotation.created_at.desc())
        if annotation_type:
            query = query.where(Annotation.type == annotation_type)
        result = await repo.session.execute(query)
        annotations = list(result.scalars().all())

    total = len(annotations)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = annotations[start:end]

    enriched = await _enrich_with_context(repo.session, page_items)
    return {
        "items": enriched,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }


@router.get("/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(
    annotation_id: int,
    repo: AnnotationRepository = Depends(get_annotation_repo),
):
    """Get a single annotation by ID."""
    annotation = await repo.get_by_id(annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return AnnotationResponse.model_validate(annotation)


@router.post("", response_model=AnnotationResponse, status_code=201)
async def create_annotation(
    body: AnnotationCreateRequest,
    db: AsyncSession = Depends(get_db),
    repo: AnnotationRepository = Depends(get_annotation_repo),
):
    """Create a new annotation."""
    # Validate note length
    if body.note and len(body.note) > 10_000:
        raise HTTPException(status_code=422, detail="Note exceeds 10,000 character limit")

    # Validate content reference exists
    try:
        ct = ContentType(body.content_type)
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail=f"Invalid content type: {body.content_type}"
        ) from err

    if ct in (ContentType.SECTION_CONTENT, ContentType.SECTION_SUMMARY):
        from sqlalchemy import select

        result = await db.execute(select(BookSection).where(BookSection.id == body.content_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Section {body.content_id} not found")

    annotation = Annotation(
        content_type=ct,
        content_id=body.content_id,
        type=AnnotationType(body.type.value),
        selected_text=body.selected_text,
        text_start=body.text_start,
        text_end=body.text_end,
        note=body.note,
    )
    annotation = await repo.create(annotation)
    await db.commit()
    await db.refresh(annotation)
    return AnnotationResponse.model_validate(annotation)


@router.patch("/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    annotation_id: int,
    body: AnnotationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    repo: AnnotationRepository = Depends(get_annotation_repo),
):
    """Update an annotation's note or type."""
    annotation = await repo.get_by_id(annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    if body.note is not None:
        if len(body.note) > 10_000:
            raise HTTPException(status_code=422, detail="Note exceeds 10,000 character limit")
        annotation.note = body.note
    if body.type is not None:
        annotation.type = AnnotationType(body.type.value)

    await repo.update(annotation)
    await db.commit()
    await db.refresh(annotation)
    return AnnotationResponse.model_validate(annotation)


@router.delete("/{annotation_id}", status_code=204)
async def delete_annotation(
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
    repo: AnnotationRepository = Depends(get_annotation_repo),
):
    """Delete an annotation."""
    deleted = await repo.delete(annotation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Annotation not found")
    await db.commit()


@router.post("/{annotation_id}/link", response_model=AnnotationResponse)
async def link_annotation(
    annotation_id: int,
    body: AnnotationLinkRequest,
    db: AsyncSession = Depends(get_db),
    repo: AnnotationRepository = Depends(get_annotation_repo),
):
    """Link this annotation to another."""
    annotation = await repo.get_by_id(annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    target = await repo.get_by_id(body.target_annotation_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target annotation not found")

    annotation = await repo.link_annotations(annotation_id, body.target_annotation_id)
    await db.commit()
    await db.refresh(annotation)
    return AnnotationResponse.model_validate(annotation)


@router.delete("/{annotation_id}/link", response_model=AnnotationResponse)
async def unlink_annotation(
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
    repo: AnnotationRepository = Depends(get_annotation_repo),
):
    """Remove the link from this annotation."""
    annotation = await repo.get_by_id(annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    annotation.linked_annotation_id = None
    await repo.update(annotation)
    await db.commit()
    await db.refresh(annotation)
    return AnnotationResponse.model_validate(annotation)
