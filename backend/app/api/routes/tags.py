"""Tag CRUD endpoints for books, sections, and library-wide list + suggest.

All write endpoints are idempotent (FR-E2.5); a duplicate POST returns
200 instead of 201. Normalisation + NOCASE collation is handled by
``TagService`` so the API layer stays thin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tag_service
from app.db.models import Book, BookSection, Tag, Taggable
from app.services.tag_service import TagError, TagService

router = APIRouter(prefix="/api/v1", tags=["tags"])


class TagCreateRequest(BaseModel):
    name: str
    color: str | None = None


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str | None = None


class TagListResponse(BaseModel):
    tags: list[TagResponse]


class TagWithUsage(BaseModel):
    id: int
    name: str
    color: str | None = None
    usage_count: int


class TagUsageListResponse(BaseModel):
    tags: list[TagWithUsage]


class TagSuggestion(BaseModel):
    id: int
    name: str


class TagSuggestResponse(BaseModel):
    suggestions: list[TagSuggestion]


async def _require_book(db: AsyncSession, book_id: int) -> None:
    result = await db.execute(select(Book.id).where(Book.id == book_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, f"Book {book_id} not found")


async def _require_section(db: AsyncSession, section_id: int) -> None:
    result = await db.execute(select(BookSection.id).where(BookSection.id == section_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, f"Section {section_id} not found")


async def _taggable_exists(
    db: AsyncSession, taggable_type: str, taggable_id: int, tag_id: int
) -> bool:
    result = await db.execute(
        select(Taggable).where(
            Taggable.tag_id == tag_id,
            Taggable.taggable_type == taggable_type,
            Taggable.taggable_id == taggable_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def _add_to_entity(
    entity: str,
    entity_id: int,
    body: TagCreateRequest,
    db: AsyncSession,
    svc: TagService,
) -> JSONResponse:
    if entity == "book":
        await _require_book(db, entity_id)
    elif entity == "section":
        await _require_section(db, entity_id)

    try:
        # Track whether association exists BEFORE add (for 200 vs 201).
        existing = await db.execute(
            select(Tag).where(func.lower(Tag.name) == func.lower(body.name.strip()))
        )
        existing_tag = existing.scalar_one_or_none()
        was_existing_assoc = False
        if existing_tag is not None:
            was_existing_assoc = await _taggable_exists(
                db, entity, entity_id, existing_tag.id
            )
        tag = await svc.add_tag(entity, entity_id, body.name, color=body.color)
    except TagError as e:
        raise HTTPException(400, str(e)) from e

    await db.commit()
    await db.refresh(tag)

    return JSONResponse(
        status_code=200 if was_existing_assoc else 201,
        content=TagResponse.model_validate(tag).model_dump(),
    )


@router.post("/books/{book_id}/tags")
async def add_book_tag(
    book_id: int,
    body: TagCreateRequest,
    db: AsyncSession = Depends(get_db),
    svc: TagService = Depends(get_tag_service),
):
    return await _add_to_entity("book", book_id, body, db, svc)


@router.post("/sections/{section_id}/tags")
async def add_section_tag(
    section_id: int,
    body: TagCreateRequest,
    db: AsyncSession = Depends(get_db),
    svc: TagService = Depends(get_tag_service),
):
    return await _add_to_entity("section", section_id, body, db, svc)


@router.get("/books/{book_id}/tags", response_model=TagListResponse)
async def list_book_tags(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    svc: TagService = Depends(get_tag_service),
):
    await _require_book(db, book_id)
    tags = await svc.list_tags_for_entity("book", book_id)
    return TagListResponse(tags=[TagResponse.model_validate(t) for t in tags])


@router.get("/sections/{section_id}/tags", response_model=TagListResponse)
async def list_section_tags(
    section_id: int,
    db: AsyncSession = Depends(get_db),
    svc: TagService = Depends(get_tag_service),
):
    await _require_section(db, section_id)
    tags = await svc.list_tags_for_entity("section", section_id)
    return TagListResponse(tags=[TagResponse.model_validate(t) for t in tags])


@router.delete("/books/{book_id}/tags/{tag_id}", status_code=204)
async def remove_book_tag(
    book_id: int,
    tag_id: int,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text(
            "DELETE FROM taggables "
            "WHERE tag_id=:tag_id AND taggable_type='book' AND taggable_id=:book_id"
        ),
        {"tag_id": tag_id, "book_id": book_id},
    )
    await db.commit()
    return None


@router.delete("/sections/{section_id}/tags/{tag_id}", status_code=204)
async def remove_section_tag(
    section_id: int,
    tag_id: int,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text(
            "DELETE FROM taggables "
            "WHERE tag_id=:tag_id AND taggable_type='section' AND taggable_id=:sid"
        ),
        {"tag_id": tag_id, "sid": section_id},
    )
    await db.commit()
    return None


# --- Library list + autocomplete (T15) ---


@router.get("/tags", response_model=TagUsageListResponse)
async def list_tags_with_usage(db: AsyncSession = Depends(get_db)):
    """All tags with their taggable count across the library."""
    stmt = (
        select(Tag.id, Tag.name, Tag.color, func.count(Taggable.tag_id).label("usage_count"))
        .outerjoin(Taggable, Taggable.tag_id == Tag.id)
        .group_by(Tag.id, Tag.name, Tag.color)
        .order_by(Tag.name)
    )
    rows = (await db.execute(stmt)).all()
    return TagUsageListResponse(
        tags=[
            TagWithUsage(id=r.id, name=r.name, color=r.color, usage_count=r.usage_count)
            for r in rows
        ]
    )


@router.get("/tags/suggest", response_model=TagSuggestResponse)
async def suggest_tags(
    q: str = Query("", description="Prefix query"),
    db: AsyncSession = Depends(get_db),
):
    q = (q or "").strip()
    if not q:
        return TagSuggestResponse(suggestions=[])
    # NOCASE collation is enabled on Tag.name (v1_5d); plain LIKE + lower() is
    # used here for portability against other DBs; COLLATE NOCASE also works.
    stmt = (
        select(Tag.id, Tag.name)
        .where(func.lower(Tag.name).like(func.lower(q) + "%"))
        .order_by(Tag.name)
        .limit(10)
    )
    rows = (await db.execute(stmt)).all()
    return TagSuggestResponse(
        suggestions=[TagSuggestion(id=r.id, name=r.name) for r in rows]
    )
