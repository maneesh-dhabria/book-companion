"""Export API endpoints — wraps ExportService for book and library export."""

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select

from app.api.deps import get_export_service
from app.db.models import BookSection
from app.services.export_service import ExportError, ExportSelection, ExportService
from app.services.slug import filename_slug

router = APIRouter(prefix="/api/v1/export", tags=["export"])


@router.get("/book/{book_id}")
async def export_book(
    book_id: int,
    format: str = Query("json", pattern="^(json|markdown)$"),
    include_book_summary: bool = Query(True),
    include_toc: bool = Query(True),
    include_annotations: bool = Query(True),
    exclude_section: list[int] = Query(default_factory=list),
    export_service: ExportService = Depends(get_export_service),
):
    """Export a single book as JSON or summaries-focused Markdown.

    Selection params (`include_*`, `exclude_section`) are honored only by
    `format=markdown`; JSON exports remain full-fidelity.
    """
    try:
        book = await export_service.book_repo.get_by_id(book_id)
        if not book:
            raise HTTPException(status_code=404, detail=f"Book {book_id} not found.")

        if format == "json":
            content = await export_service.export_book(book_id, fmt="json")
            return JSONResponse(
                content=json.loads(content),
                headers={"Content-Disposition": f'attachment; filename="book_{book_id}.json"'},
            )

        # Markdown path
        if exclude_section:
            result = await export_service.session.execute(
                select(BookSection.id).where(BookSection.book_id == book_id)
            )
            valid_ids = {row[0] for row in result.all()}
            invalid = [sid for sid in exclude_section if sid not in valid_ids]
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"section {invalid[0]} does not belong to book {book_id}",
                )

        selection = ExportSelection(
            include_book_summary=include_book_summary,
            include_toc=include_toc,
            include_annotations=include_annotations,
            exclude_section_ids=frozenset(exclude_section),
        )
        body, is_empty = await export_service.export_book_markdown(book_id, selection)

        slug = filename_slug(book.title) or f"book-{book_id}"
        today = date.today().strftime("%Y%m%d")
        filename = f"{slug}-summary-{today}.md"

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, max-age=0",
            "X-Empty-Export": "true" if is_empty else "false",
        }
        return PlainTextResponse(body, media_type="text/markdown", headers=headers)
    except ExportError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.get("/library")
async def export_library(
    format: str = Query("json", pattern="^(json|markdown)$"),
    export_service: ExportService = Depends(get_export_service),
):
    """Export the entire library as JSON. Markdown was removed in v1.6."""
    if format == "markdown":
        raise HTTPException(
            status_code=410,
            detail=(
                "Library Markdown export was removed in v1.6 -- use format=json "
                "for full-library backups, or use /api/v1/export/book/{id}"
                "?format=markdown per book."
            ),
        )
    content = await export_service.export_library(fmt="json")
    return JSONResponse(
        content=json.loads(content),
        headers={"Content-Disposition": "attachment; filename=library_export.json"},
    )
