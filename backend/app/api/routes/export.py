"""Export API endpoints — wraps ExportService for book and library export."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.deps import get_export_service
from app.services.export_service import ExportError, ExportService

router = APIRouter(prefix="/api/v1/export", tags=["export"])


@router.get("/book/{book_id}")
async def export_book(
    book_id: int,
    format: str = Query("json", pattern="^(json|markdown)$"),
    export_service: ExportService = Depends(get_export_service),
):
    """Export a single book as JSON or Markdown."""
    try:
        content = await export_service.export_book(book_id, fmt=format)
    except ExportError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    if format == "markdown":
        return PlainTextResponse(
            content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=book_{book_id}.md"},
        )
    return JSONResponse(
        content=json.loads(content),
        headers={"Content-Disposition": f"attachment; filename=book_{book_id}.json"},
    )


@router.get("/library")
async def export_library(
    format: str = Query("json", pattern="^(json|markdown)$"),
    export_service: ExportService = Depends(get_export_service),
):
    """Export the entire library as JSON or Markdown."""
    content = await export_service.export_library(fmt=format)

    if format == "markdown":
        return PlainTextResponse(
            content,
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=library_export.md"},
        )
    return JSONResponse(
        content=json.loads(content),
        headers={"Content-Disposition": "attachment; filename=library_export.json"},
    )
