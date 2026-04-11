"""Concepts API endpoints — list, detail, update, reset, delete."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_concept_repo, get_db
from app.api.schemas import (
    ConceptDetailResponse,
    ConceptResponse,
    ConceptUpdateRequest,
    SectionBriefResponse,
)
from app.db.models import BookSection, Concept
from app.db.repositories.concept_repo import ConceptRepository

router = APIRouter(prefix="/api/v1/concepts", tags=["concepts"])


@router.get("", response_model=dict)
async def list_concepts(
    book_id: int | None = Query(None),
    user_edited: bool | None = Query(None),
    sort: str = Query("term"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    repo: ConceptRepository = Depends(get_concept_repo),
):
    """List concepts with optional filters."""
    if book_id:
        concepts = await repo.get_by_book(book_id)
    else:
        result = await db.execute(select(Concept).order_by(Concept.term))
        concepts = list(result.scalars().all())

    # Apply user_edited filter
    if user_edited is not None:
        concepts = [c for c in concepts if c.user_edited == user_edited]

    # Sort
    if sort == "updated_at":
        concepts.sort(key=lambda c: c.updated_at, reverse=True)
    else:
        concepts.sort(key=lambda c: c.term.lower())

    total = len(concepts)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = concepts[start:end]

    return {
        "items": [ConceptResponse.model_validate(c).model_dump() for c in page_items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }


@router.get("/{concept_id}", response_model=ConceptDetailResponse)
async def get_concept(
    concept_id: int,
    db: AsyncSession = Depends(get_db),
    repo: ConceptRepository = Depends(get_concept_repo),
):
    """Get concept detail with section appearances and related concepts."""
    concept = await repo.get_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    # Fetch section appearances
    section_ids = await repo.get_sections_for_concept(concept_id)
    section_appearances = []
    if section_ids:
        result = await db.execute(
            select(BookSection).where(BookSection.id.in_(section_ids))
        )
        sections = list(result.scalars().all())
        section_appearances = [
            SectionBriefResponse(
                id=s.id,
                title=s.title,
                order_index=s.order_index,
                section_type=(
                    s.section_type.value
                    if hasattr(s.section_type, "value")
                    else str(s.section_type)
                ),
                content_token_count=s.content_token_count,
                has_summary=s.default_summary_id is not None,
            )
            for s in sections
        ]

    # Fetch related concepts (same book, limit 10)
    same_book_concepts = await repo.get_by_book(concept.book_id)
    related = [
        ConceptResponse.model_validate(c)
        for c in same_book_concepts
        if c.id != concept_id
    ][:10]

    # Get book title
    from app.db.models import Book

    book_result = await db.execute(select(Book).where(Book.id == concept.book_id))
    book = book_result.scalar_one_or_none()
    book_title = book.title if book else ""

    return ConceptDetailResponse(
        id=concept.id,
        book_id=concept.book_id,
        term=concept.term,
        definition=concept.definition,
        user_edited=concept.user_edited,
        created_at=concept.created_at,
        updated_at=concept.updated_at,
        section_appearances=section_appearances,
        related_concepts=related,
        book_title=book_title,
    )


@router.patch("/{concept_id}", response_model=ConceptResponse)
async def update_concept(
    concept_id: int,
    body: ConceptUpdateRequest,
    db: AsyncSession = Depends(get_db),
    repo: ConceptRepository = Depends(get_concept_repo),
):
    """Update concept definition or term."""
    concept = await repo.get_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    if body.definition is not None:
        concept = await repo.update_definition(concept_id, body.definition, user_edited=True)
    if body.term is not None:
        concept = await repo.update(concept_id, term=body.term)

    await db.commit()
    await db.refresh(concept)
    return ConceptResponse.model_validate(concept)


@router.post("/{concept_id}/reset", response_model=ConceptResponse)
async def reset_concept(
    concept_id: int,
    db: AsyncSession = Depends(get_db),
    repo: ConceptRepository = Depends(get_concept_repo),
):
    """Reset concept user_edited flag to False."""
    concept = await repo.get_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    concept = await repo.update(concept_id, user_edited=False)
    await db.commit()
    await db.refresh(concept)
    return ConceptResponse.model_validate(concept)


@router.delete("/{concept_id}", status_code=204)
async def delete_concept(
    concept_id: int,
    db: AsyncSession = Depends(get_db),
    repo: ConceptRepository = Depends(get_concept_repo),
):
    """Delete a concept."""
    concept = await repo.get_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    await db.execute(delete(Concept).where(Concept.id == concept_id))
    await db.commit()
