"""Search API endpoints — quick search (command palette) and full search."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_search_service
from app.api.schemas import (
    FullSearchResponse,
    QuickSearchResponse,
    QuickSearchResults,
    RecentSearchResponse,
    SearchResultItem,
)
from app.db.models import RecentSearch

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/recent", response_model=list[RecentSearchResponse])
async def get_recent_searches(
    db: AsyncSession = Depends(get_db),
):
    """Return last 5 recent searches."""
    result = await db.execute(
        select(RecentSearch).order_by(RecentSearch.created_at.desc()).limit(5)
    )
    return list(result.scalars().all())


@router.delete("/recent", status_code=204)
async def clear_recent_searches(
    db: AsyncSession = Depends(get_db),
):
    """Clear all recent searches."""
    await db.execute(delete(RecentSearch))
    await db.commit()


@router.get("/quick", response_model=QuickSearchResponse)
async def quick_search(
    q: str = Query("", min_length=0),
    limit: int = Query(12, ge=1, le=50),
    book_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    search_service=Depends(get_search_service),
):
    """Quick search for command palette — grouped results, max 3 per type."""
    if not q.strip():
        return QuickSearchResponse(query=q, results=QuickSearchResults())

    try:
        grouped = await search_service.search(
            query=q, book_id=book_id, limit=limit
        )
    except Exception:
        # Graceful degradation if Ollama/embeddings unavailable
        grouped = None

    # Build grouped results
    books_hits: list[dict] = []
    sections_hits: list[dict] = []
    concepts_hits: list[dict] = []
    annotations_hits: list[dict] = []

    if grouped:
        for book_results in grouped.books.values():
            for r in book_results:
                hit = {
                    "id": r.source_id,
                    "book_id": r.book_id,
                    "book_title": r.book_title,
                    "snippet": r.chunk_text[:200] if r.chunk_text else "",
                    "score": r.score,
                }
                st = r.source_type
                if hasattr(st, "value"):
                    st = st.value
                if st in ("section_content", "section_title", "section_summary"):
                    sections_hits.append({
                        **hit,
                        "title": r.section_title or "",
                        "section_title": r.section_title,
                    })
                elif st == "concept":
                    concepts_hits.append({
                        **hit,
                        "term": r.section_title or r.chunk_text[:50],
                    })
                elif st == "annotation":
                    annotations_hits.append({
                        **hit,
                        "note_snippet": r.chunk_text[:100] if r.chunk_text else None,
                        "selected_text": None,
                    })
                elif st in ("book_title", "book_summary"):
                    books_hits.append({
                        **hit,
                        "title": r.book_title,
                    })
                else:
                    # Default: treat as section
                    sections_hits.append({
                        **hit,
                        "title": r.section_title or "",
                        "section_title": r.section_title,
                    })

    # Cap at 3 per type
    results = QuickSearchResults(
        books=books_hits[:3],
        sections=sections_hits[:3],
        concepts=concepts_hits[:3],
        annotations=annotations_hits[:3],
    )

    # Store in recent searches
    total = len(books_hits) + len(sections_hits) + len(concepts_hits) + len(annotations_hits)
    recent = RecentSearch(query=q, result_count=total)
    db.add(recent)
    await db.commit()

    return QuickSearchResponse(query=q, results=results)


@router.get("", response_model=FullSearchResponse)
async def full_search(
    q: str = Query("", min_length=0),
    source_type: str | None = Query(None),
    book_id: int | None = Query(None),
    tag: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search_service=Depends(get_search_service),
):
    """Full paginated search for search results page."""
    if not q.strip():
        return FullSearchResponse(items=[], total=0, page=page, per_page=per_page)

    try:
        grouped = await search_service.search(
            query=q,
            book_id=book_id,
            source_type=source_type,
            tag=tag,
            limit=per_page * page,  # fetch enough to paginate
        )
    except Exception:
        return FullSearchResponse(items=[], total=0, page=page, per_page=per_page)

    # Flatten results
    all_results = []
    for book_results in grouped.books.values():
        for r in book_results:
            all_results.append(SearchResultItem(
                source_type=r.source_type,
                source_id=r.source_id,
                book_id=r.book_id,
                book_title=r.book_title,
                section_title=r.section_title,
                snippet=r.chunk_text[:300] if r.chunk_text else "",
                score=r.score,
                highlight=r.highlight or "",
            ))

    # Sort by score descending
    all_results.sort(key=lambda x: x.score, reverse=True)

    total = len(all_results)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = all_results[start:end]

    return FullSearchResponse(
        items=page_items,
        total=total,
        page=page,
        per_page=per_page,
    )
