"""Unit tests for search service."""

from app.services.search_service import SearchService, SearchResult, GroupedSearchResults


def test_rrf_merge():
    """RRF fusion should combine rankings correctly."""
    bm25_ids = [1, 3, 5, 7]  # Ranked by BM25
    semantic_ids = [3, 1, 9, 5]  # Ranked by semantic

    fused = SearchService._rrf_merge_static(bm25_ids, semantic_ids, k=60)
    # ID 3 ranks #2 in BM25, #1 in semantic -> should score highest
    # ID 1 ranks #1 in BM25, #2 in semantic -> close second
    assert fused[0] in (1, 3)  # Top result is ID 1 or 3
    assert len(fused) == 5  # Union of all unique IDs


def test_result_grouping():
    """Results should group by book_id."""
    results = [
        SearchResult(
            source_type="section_content",
            source_id=1,
            book_id=1,
            book_title="Book A",
            section_title="Ch1",
            chunk_text="text",
            score=0.9,
            highlight="text",
        ),
        SearchResult(
            source_type="section_content",
            source_id=2,
            book_id=2,
            book_title="Book B",
            section_title="Ch1",
            chunk_text="text",
            score=0.8,
            highlight="text",
        ),
        SearchResult(
            source_type="section_summary",
            source_id=3,
            book_id=1,
            book_title="Book A",
            section_title="Ch2",
            chunk_text="text",
            score=0.7,
            highlight="text",
        ),
    ]
    grouped = SearchService._group_results_static(results)
    assert len(grouped.books) == 2
    assert len(grouped.books[1]) == 2  # Book A has 2 results
    assert grouped.total_count == 3
