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
from app.db.models import Book, BookSection
from app.services.parser.section_classifier import SUMMARIZABLE_TYPES

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

    # FR-F3.1 / §9.1 extended response fields: tags, suggested_tags,
    # summary_progress snapshot, last_summary_failure block. Tags come from
    # the relationship that lazily loads; they're expected to be pre-loaded
    # via ``selectinload`` by the repo, falling back to an empty list if
    # the caller didn't bother.
    try:
        from app.services.parser.section_classifier import SUMMARIZABLE_TYPES

        summarizable = [
            s for s in (book.sections or []) if s.section_type in SUMMARIZABLE_TYPES
        ]
        summarized_count = sum(
            1 for s in summarizable if s.default_summary_id is not None
        )
        failed_count = sum(
            1
            for s in summarizable
            if s.default_summary_id is None
            and getattr(s, "last_failure_type", None) is not None
        )
    except Exception:
        summarizable = []
        summarized_count = 0
        failed_count = 0

    summary_progress = {
        "summarizable": len(summarizable),
        "summarized": summarized_count,
        "failed_and_pending": failed_count,
        "pending": max(0, len(summarizable) - summarized_count - failed_count),
    }

    last_summary_failure = None
    if book.last_summary_failure_code:
        last_summary_failure = {
            "code": book.last_summary_failure_code,
            "stderr": book.last_summary_failure_stderr,
            "at": book.last_summary_failure_at,
        }

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
        "suggested_tags": list(book.suggested_tags_json or []),
        "summary_progress": summary_progress,
        "last_summary_failure": last_summary_failure,
        "created_at": book.created_at,
        "updated_at": book.updated_at,
    }


ALLOWED_SORT_FIELDS = {"title", "created_at", "updated_at", "file_size_bytes", "status"}


@router.get("")
async def list_books(
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    file_format: str | None = None,
    sort_field: str = "updated_at",
    sort_direction: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    """List books with pagination, filtering, and sorting."""
    # Build filter conditions
    conditions = []
    if status:
        conditions.append(Book.status == status)
    if file_format:
        conditions.append(Book.file_format == file_format)

    # Count total (without eager loading)
    count_query = select(func.count(Book.id))
    for cond in conditions:
        count_query = count_query.where(cond)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Sorting — whitelist allowed fields
    if sort_field not in ALLOWED_SORT_FIELDS:
        sort_field = "updated_at"
    sort_col = getattr(Book, sort_field)
    order = sort_col.asc() if sort_direction == "asc" else sort_col.desc()

    # Main query with eager loading
    query = (
        select(Book)
        .options(selectinload(Book.authors), selectinload(Book.sections))
        .order_by(order)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    for cond in conditions:
        query = query.where(cond)

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


async def _summary_progress(db: AsyncSession, book_id: int) -> dict[str, int]:
    summarizable_list = list(SUMMARIZABLE_TYPES)
    total = (
        await db.execute(
            select(func.count(BookSection.id))
            .where(BookSection.book_id == book_id)
            .where(BookSection.section_type.in_(summarizable_list))
        )
    ).scalar() or 0
    summarized = (
        await db.execute(
            select(func.count(BookSection.id))
            .where(BookSection.book_id == book_id)
            .where(BookSection.section_type.in_(summarizable_list))
            .where(BookSection.default_summary_id.isnot(None))
        )
    ).scalar() or 0
    return {"summarized": summarized, "total": total}


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
    book_dict = _book_to_response(book)
    book_dict["summary_progress"] = await _summary_progress(db, book_id)

    # Resolve the book-level Summary (if any) so the frontend can render
    # the body directly from /books/:id without a second fetch.
    if book.default_summary_id:
        from app.db.models import Summary

        default_summary = (
            await db.execute(
                select(Summary).where(Summary.id == book.default_summary_id)
            )
        ).scalar_one_or_none()
        if default_summary is not None:
            book_dict["default_summary"] = {
                "id": default_summary.id,
                "preset_name": default_summary.preset_name,
                "model_used": default_summary.model_used,
                "summary_char_count": default_summary.summary_char_count,
                "created_at": default_summary.created_at,
                "summary_md": default_summary.summary_md,
            }

    # Expose the most-recent preset used on any section for Generate-modal
    # preselection. Section summaries win over the book-level summary when
    # available — users usually want "re-run the same preset I just used".
    from app.db.models import BookSection as _BS

    latest_preset = (
        await db.execute(
            select(_BS.last_preset_used)
            .where(_BS.book_id == book_id)
            .where(_BS.last_preset_used.is_not(None))
            .where(_BS.last_attempted_at.is_not(None))
            .order_by(_BS.last_attempted_at.desc())
            .limit(1)
        )
    ).scalar()
    if latest_preset:
        book_dict["last_used_preset"] = latest_preset
    elif (
        book_dict.get("default_summary")
        and book_dict["default_summary"].get("preset_name")
    ):
        book_dict["last_used_preset"] = book_dict["default_summary"]["preset_name"]

    return BookResponse(**book_dict)


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

        # Index sections for search
        try:
            from app.services.embedding_service import EmbeddingService
            from app.services.search_service import SearchService

            embedding_service = EmbeddingService()
            search_service = SearchService(session=db, embedding_service=embedding_service)
            if book.sections:
                await search_service.index_book_sections(book.id, list(book.sections))
                await db.commit()
        except Exception:
            pass  # Search indexing failure should not block upload

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


@router.patch("/{book_id}/suggested-tags")
async def patch_suggested_tags(
    book_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """FR-E4.4 — dismiss or replace the LLM-proposed tag list.

    Accepts either ``{"reject": ["a", "b"]}`` (remove matching entries) or
    ``{"set": [...]}`` (replace wholesale). Returns ``{suggested_tags: [...]}``.
    Reject silently ignores names that aren't in the current list.
    """
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")

    current = list(book.suggested_tags_json or [])
    if "set" in body:
        current = [str(x) for x in (body.get("set") or []) if isinstance(x, str)]
    elif "reject" in body:
        reject = {r.lower() for r in (body.get("reject") or []) if isinstance(r, str)}
        current = [c for c in current if c.lower() not in reject]
    else:
        raise HTTPException(status_code=400, detail="Provide 'set' or 'reject'")

    book.suggested_tags_json = current
    await db.commit()
    return {"suggested_tags": current}
