"""Book CRUD + upload + duplicate detection endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import selectinload

from app.api.deps import get_book_service, get_db
from app.api.schemas import (
    BookListItem,
    BookResponse,
    BookUpdateRequest,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    PaginatedResponse,
    SectionBriefResponse,
)
from app.db.models import Book

router = APIRouter(prefix="/api/v1/books", tags=["books"])


def _book_to_list_item(book: Book) -> dict:
    """Convert a Book ORM instance to BookListItem dict."""
    authors = []
    for ba in getattr(book, "_authors_with_role", []):
        authors.append({"id": ba.author_id, "name": ba.name, "role": ba.role})
    if not authors:
        authors = [{"id": a.id, "name": a.name, "role": "author"} for a in (book.authors or [])]

    section_count = len(book.sections) if book.sections else 0

    has_summary = book.default_summary_id is not None

    eval_passed = None
    eval_total = None

    return {
        "id": book.id,
        "title": book.title,
        "status": book.status.value if hasattr(book.status, "value") else str(book.status),
        "file_format": book.file_format,
        "file_size_bytes": book.file_size_bytes,
        "authors": authors,
        "section_count": section_count,
        "cover_url": f"/api/v1/books/{book.id}/cover" if book.cover_image else None,
        "has_summary": has_summary,
        "eval_passed": eval_passed,
        "eval_total": eval_total,
        "created_at": book.created_at,
        "updated_at": book.updated_at,
    }


def _book_to_response(book: Book) -> dict:
    """Convert a Book ORM instance to BookResponse dict."""
    authors = [{"id": a.id, "name": a.name, "role": "author"} for a in (book.authors or [])]
    sections = [
        SectionBriefResponse(
            id=s.id,
            title=s.title,
            order_index=s.order_index,
            section_type=s.section_type,
            content_token_count=s.content_token_count,
            has_summary=s.default_summary_id is not None,
        )
        for s in (book.sections or [])
    ]

    return {
        "id": book.id,
        "title": book.title,
        "status": book.status.value if hasattr(book.status, "value") else str(book.status),
        "file_format": book.file_format,
        "file_size_bytes": book.file_size_bytes,
        "file_hash": book.file_hash,
        "authors": authors,
        "sections": sections,
        "section_count": len(sections),
        "cover_url": f"/api/v1/books/{book.id}/cover" if book.cover_image else None,
        "created_at": book.created_at,
        "updated_at": book.updated_at,
    }


@router.get("")
async def list_books(
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    format: str | None = None,
    sort_field: str = "updated_at",
    sort_direction: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    """List books with pagination, filtering, and sorting."""
    query = select(Book).options(selectinload(Book.authors), selectinload(Book.sections))

    if status:
        query = query.where(Book.status == status)
    if format:
        query = query.where(Book.file_format == format)

    # Sorting
    sort_col = getattr(Book, sort_field, Book.updated_at)
    if sort_direction == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    books = result.scalars().unique().all()

    pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    return PaginatedResponse(
        items=[BookListItem(**_book_to_list_item(b)) for b in books],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{book_id}")
async def get_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single book with sections."""
    result = await db.execute(
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.authors), selectinload(Book.sections))
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return BookResponse(**_book_to_response(book))


@router.post("/upload", status_code=201)
async def upload_book(
    file: UploadFile,
    book_service=Depends(get_book_service),
):
    """Upload and parse a book file."""
    content = await file.read()

    suffix = Path(file.filename or "book.epub").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        book = await book_service.add_book(tmp_path)
        # Re-fetch with relationships loaded
        db = book_service.db
        result = await db.execute(
            select(Book)
            .where(Book.id == book.id)
            .options(selectinload(Book.authors), selectinload(Book.sections))
        )
        book = result.scalar_one()
        return BookResponse(**_book_to_response(book))
    finally:
        tmp_path.unlink(missing_ok=True)


@router.patch("/{book_id}")
async def update_book(
    book_id: int,
    body: BookUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update book metadata."""
    result = await db.execute(
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.authors), selectinload(Book.sections))
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if body.title is not None:
        book.title = body.title
    await db.commit()

    return BookResponse(**_book_to_response(book))


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a book."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    await db.delete(book)
    await db.commit()
    return Response(status_code=204)


@router.post("/check-duplicate")
async def check_duplicate(
    body: DuplicateCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """Check if a book with this file hash already exists."""
    result = await db.execute(select(Book).where(Book.file_hash == body.file_hash))
    existing = result.scalar_one_or_none()
    return DuplicateCheckResponse(
        is_duplicate=existing is not None,
        existing_book_id=existing.id if existing else None,
    )


@router.get("/{book_id}/cover")
async def get_cover(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Return cover image binary."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book or not book.cover_image:
        raise HTTPException(status_code=404, detail="Cover not found")
    return Response(content=book.cover_image, media_type="image/jpeg")


@router.put("/{book_id}/cover", status_code=204)
async def upload_cover(
    book_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """Upload a cover image."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book.cover_image = await file.read()
    await db.commit()
    return Response(status_code=204)
