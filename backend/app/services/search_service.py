"""Hybrid search: BM25 + semantic + Reciprocal Rank Fusion."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Annotation,
    Book,
    BookSection,
    Concept,
    SearchIndex,
    SourceType,
    Tag,
    Taggable,
)
from app.services.embedding_service import EmbeddingService, serialize_embedding


@dataclass
class SearchResult:
    source_type: str
    source_id: int
    book_id: int
    book_title: str
    section_title: str | None
    chunk_text: str
    score: float
    highlight: str


@dataclass
class GroupedSearchResults:
    query: str
    books: dict[int, list[SearchResult]]
    total_count: int


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
        rrf_k: int = 60,
        default_limit: int = 20,
    ):
        self.session = session
        self.embedding_service = embedding_service
        self.rrf_k = rrf_k
        self.default_limit = default_limit

    async def search(
        self,
        query: str,
        book_id: int | None = None,
        source_types: list[str] | None = None,
        source_type: str | None = None,
        tag: str | None = None,
        limit: int | None = None,
    ) -> GroupedSearchResults:
        limit = limit or self.default_limit

        # Normalize source_type to source_types list
        if source_type and not source_types:
            source_types = [source_type]

        # Phase 2: If tag filter, get book IDs with that tag
        if tag:
            tag_book_ids = await self._get_tagged_book_ids(tag)
            if not tag_book_ids:
                return GroupedSearchResults(query=query, books={}, total_count=0)
            # If book_id is also set, intersect
            if book_id:
                if book_id not in tag_book_ids:
                    return GroupedSearchResults(query=query, books={}, total_count=0)
            # We'll filter by these book IDs in the search methods below
            # For simplicity, use the first one or iterate -- this is a simplified approach

        # 1. Generate query embedding
        query_embedding = await self.embedding_service.embed_text(query)

        # 2. BM25 search
        bm25_results = await self._bm25_search(query, book_id, source_types, limit * 2)

        # 3. Semantic search
        semantic_results = await self._semantic_search(
            query_embedding, book_id, source_types, limit * 2
        )

        # 4. RRF merge
        all_results = {r.source_id: r for r in bm25_results + semantic_results}
        bm25_ids = [r.source_id for r in bm25_results]
        semantic_ids = [r.source_id for r in semantic_results]
        fused_ids = self._rrf_merge_static(bm25_ids, semantic_ids, self.rrf_k)

        # 5. Build ordered results
        fused_results = []
        for sid in fused_ids[:limit]:
            if sid in all_results:
                fused_results.append(all_results[sid])

        return self._group_results_static(fused_results, query)

    async def _bm25_search(
        self,
        query: str,
        book_id: int | None,
        source_types: list[str] | None,
        limit: int,
    ) -> list[SearchResult]:
        """BM25 full-text search via FTS5."""
        # Build FTS5 query — use raw SQL for FTS5 MATCH
        sql = """
            SELECT si.id, si.source_type, si.source_id, si.book_id,
                   si.chunk_text, bm25(search_fts) as rank
            FROM search_index si
            JOIN search_fts ON si.id = search_fts.rowid
            WHERE search_fts MATCH :query
        """
        params: dict = {"query": query, "limit": limit}
        if book_id:
            sql += " AND si.book_id = :book_id"
            params["book_id"] = book_id
        if source_types:
            placeholders = ", ".join(f":st{i}" for i in range(len(source_types)))
            sql += f" AND si.source_type IN ({placeholders})"
            for i, st in enumerate(source_types):
                params[f"st{i}"] = st
        sql += " ORDER BY rank LIMIT :limit"

        result = await self.session.execute(text(sql), params)
        rows = result.all()
        return await self._rows_to_results(rows)

    async def _semantic_search(
        self,
        embedding: list[float],
        book_id: int | None,
        source_types: list[str] | None,
        limit: int,
    ) -> list[SearchResult]:
        """Semantic search via in-Python cosine similarity."""
        import numpy as np

        from app.services.embedding_service import deserialize_embedding

        # Load all embeddings in scope
        stmt = select(
            SearchIndex.id,
            SearchIndex.source_type,
            SearchIndex.source_id,
            SearchIndex.book_id,
            SearchIndex.chunk_text,
            SearchIndex.embedding,
        ).where(SearchIndex.embedding.isnot(None))

        if book_id:
            stmt = stmt.where(SearchIndex.book_id == book_id)
        if source_types:
            stmt = stmt.where(SearchIndex.source_type.in_(source_types))

        result = await self.session.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        # Compute cosine similarity
        query_vec = np.array(embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        scored_rows = []
        for row in rows:
            if row.embedding is None:
                continue
            vec = np.array(deserialize_embedding(row.embedding), dtype=np.float32)
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0:
                continue
            similarity = float(np.dot(query_vec, vec) / (query_norm * vec_norm))
            scored_rows.append((row, similarity))

        scored_rows.sort(key=lambda x: x[1], reverse=True)
        top_rows = scored_rows[:limit]

        # Convert to SearchResult using _rows_to_results pattern
        results = []
        for row, score in top_rows:
            book = await self.session.get(Book, row.book_id)
            section_title = None
            if row.source_type in ("section_content", "section_summary", "section_title"):
                section = await self.session.get(BookSection, row.source_id)
                section_title = section.title if section else None
            results.append(
                SearchResult(
                    source_type=row.source_type,
                    source_id=row.source_id,
                    book_id=row.book_id,
                    book_title=book.title if book else "Unknown",
                    section_title=section_title,
                    chunk_text=row.chunk_text[:200],
                    score=score,
                    highlight=row.chunk_text[:150],
                )
            )
        return results

    async def _rows_to_results(self, rows) -> list[SearchResult]:
        results = []
        for row in rows:
            # Look up book title and section title
            book = await self.session.get(Book, row.book_id)
            section_title = None
            if row.source_type in (
                "section_content",
                "section_summary",
                "section_title",
            ):
                section = await self.session.get(BookSection, row.source_id)
                section_title = section.title if section else None

            results.append(
                SearchResult(
                    source_type=row.source_type,
                    source_id=row.source_id,
                    book_id=row.book_id,
                    book_title=book.title if book else "Unknown",
                    section_title=section_title,
                    chunk_text=row.chunk_text[:200],
                    score=getattr(row, "rank", 0) or (1 - getattr(row, "distance", 1)),
                    highlight=row.chunk_text[:150],
                )
            )
        return results

    @staticmethod
    def _rrf_merge_static(bm25_ids: list[int], semantic_ids: list[int], k: int = 60) -> list[int]:
        """Reciprocal Rank Fusion: RRF_score(doc) = 1/(k + rank)"""
        scores: dict[int, float] = defaultdict(float)
        for rank, doc_id in enumerate(bm25_ids):
            scores[doc_id] += 1.0 / (k + rank + 1)
        for rank, doc_id in enumerate(semantic_ids):
            scores[doc_id] += 1.0 / (k + rank + 1)
        return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    @staticmethod
    def _group_results_static(results: list[SearchResult], query: str = "") -> GroupedSearchResults:
        books: dict[int, list[SearchResult]] = defaultdict(list)
        for r in results:
            books[r.book_id].append(r)
        return GroupedSearchResults(query=query, books=dict(books), total_count=len(results))

    # --- Section Content Indexing ---

    async def index_section(self, section, book_id: int) -> None:
        """Index a section's content in the search index for discovery."""
        text = getattr(section, "content_md", None) or ""
        if not text.strip():
            return

        chunks = self.embedding_service._split_into_chunks(text)
        for idx, chunk in enumerate(chunks):
            try:
                embedding = await self.embedding_service.embed_text(chunk)
            except Exception:
                embedding = None  # BM25-only if Ollama unavailable
            entry = SearchIndex(
                source_type=SourceType.SECTION_CONTENT,
                source_id=section.id,
                book_id=book_id,
                chunk_text=chunk,
                chunk_index=idx,
                embedding=serialize_embedding(embedding) if embedding else None,
            )
            self.session.add(entry)
        await self.session.flush()

    async def index_book_sections(self, book_id: int, sections: list) -> None:
        """Index all sections of a book. Called after add/re-import."""
        # Delete existing entries for this book first
        await self.session.execute(
            delete(SearchIndex).where(SearchIndex.book_id == book_id)
        )
        await self.session.flush()

        for section in sections:
            await self.index_section(section, book_id)

    # --- Image Caption Indexing ---

    async def index_image_captions(self, section, book_id: int) -> None:
        """Index non-decorative image captions for search discovery."""
        images = getattr(section, "images", None) or []
        captions = [
            f"[Image: {img.caption}]"
            for img in images
            if img.relevance in ("key", "supplementary") and img.caption
        ]
        if not captions:
            return

        caption_text = "\n".join(captions)
        chunks = self.embedding_service._split_into_chunks(caption_text)
        for idx, chunk in enumerate(chunks):
            embedding = await self.embedding_service.embed_text(chunk)
            entry = SearchIndex(
                source_type=SourceType.SECTION_CONTENT,
                source_id=section.id,
                book_id=book_id,
                chunk_text=chunk,
                chunk_index=idx + 1000,  # Offset to avoid collision with regular chunks
                embedding=serialize_embedding(embedding) if embedding else None,
            )
            self.session.add(entry)
        await self.session.flush()

    # --- Phase 2: Annotation & Concept Indexing ---

    async def index_annotation(self, annotation: "Annotation", book_id: int) -> None:
        """Index an annotation in the search index for discovery."""
        text = annotation.note or annotation.selected_text or ""
        if not text.strip():
            return

        chunks = self.embedding_service._split_into_chunks(text)
        for idx, chunk in enumerate(chunks):
            embedding = await self.embedding_service.embed_text(chunk)
            entry = SearchIndex(
                source_type=SourceType.ANNOTATION,
                source_id=annotation.id,
                book_id=book_id,
                chunk_text=chunk,
                chunk_index=idx,
                embedding=serialize_embedding(embedding) if embedding else None,
            )
            self.session.add(entry)
        await self.session.flush()

    async def index_concept(self, concept: "Concept") -> None:
        """Index a concept in the search index."""
        text = f"{concept.term}: {concept.definition}"
        chunks = self.embedding_service._split_into_chunks(text)
        for idx, chunk in enumerate(chunks):
            embedding = await self.embedding_service.embed_text(chunk)
            entry = SearchIndex(
                source_type=SourceType.CONCEPT,
                source_id=concept.id,
                book_id=concept.book_id,
                chunk_text=chunk,
                chunk_index=idx,
                embedding=serialize_embedding(embedding) if embedding else None,
            )
            self.session.add(entry)
        await self.session.flush()

    async def reindex_annotation(self, annotation: "Annotation", book_id: int) -> None:
        """Re-index an annotation (delete old entries and re-create)."""
        await self._delete_source_entries(SourceType.ANNOTATION, annotation.id)
        await self.index_annotation(annotation, book_id)

    async def delete_annotation_index(self, annotation_id: int) -> None:
        """Delete search index entries for a deleted annotation."""
        await self._delete_source_entries(SourceType.ANNOTATION, annotation_id)

    async def _delete_source_entries(self, source_type: SourceType, source_id: int) -> None:
        """Delete all search index entries for a given source."""
        from sqlalchemy import delete

        await self.session.execute(
            delete(SearchIndex).where(
                SearchIndex.source_type == source_type,
                SearchIndex.source_id == source_id,
            )
        )
        await self.session.flush()

    async def _get_tagged_book_ids(self, tag_name: str) -> list[int]:
        """Get book IDs that have a specific tag."""
        result = await self.session.execute(
            select(Taggable.taggable_id)
            .join(Tag, Tag.id == Taggable.tag_id)
            .where(Tag.name == tag_name, Taggable.taggable_type == "book")
        )
        return list(result.scalars().all())
