"""SearchIndex repository — data access layer for FTS5 + numpy cosine search."""

import numpy as np
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SearchIndex, SourceType
from app.services.embedding_service import deserialize_embedding


class SearchIndexRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_bulk(self, entries: list[SearchIndex]) -> list[SearchIndex]:
        self.session.add_all(entries)
        await self.session.flush()
        return entries

    async def bm25_search(
        self, query: str, book_id: int | None = None, limit: int = 20
    ) -> list[tuple[SearchIndex, float]]:
        """BM25 full-text search via FTS5."""
        # FTS5 MATCH query with bm25() ranking
        sql = """
            SELECT si.id, bm25(search_fts) as rank
            FROM search_index si
            JOIN search_fts ON si.id = search_fts.rowid
            WHERE search_fts MATCH :query
        """
        params: dict = {"query": query, "limit": limit}
        if book_id:
            sql += " AND si.book_id = :book_id"
            params["book_id"] = book_id
        sql += " ORDER BY rank LIMIT :limit"

        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()

        if not rows:
            return []

        # Load full ORM objects for matched IDs
        ids = [row[0] for row in rows]
        ranks = {row[0]: row[1] for row in rows}
        stmt = select(SearchIndex).where(SearchIndex.id.in_(ids))
        orm_result = await self.session.execute(stmt)
        entries = {e.id: e for e in orm_result.scalars().all()}

        return [(entries[id_], ranks[id_]) for id_ in ids if id_ in entries]

    async def semantic_search(
        self,
        embedding: list[float],
        book_id: int | None = None,
        limit: int = 20,
    ) -> list[tuple[SearchIndex, float]]:
        """Semantic search via in-Python cosine similarity."""
        # Load all embeddings in scope
        stmt = select(SearchIndex.id, SearchIndex.embedding).where(
            SearchIndex.embedding.isnot(None)
        )
        if book_id:
            stmt = stmt.where(SearchIndex.book_id == book_id)
        result = await self.session.execute(stmt)
        rows = result.fetchall()

        if not rows:
            return []

        # Compute cosine similarity in numpy
        query_vec = np.array(embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        scored = []
        for row_id, emb_blob in rows:
            if emb_blob is None:
                continue
            vec = np.array(deserialize_embedding(emb_blob), dtype=np.float32)
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0:
                continue
            similarity = float(np.dot(query_vec, vec) / (query_norm * vec_norm))
            scored.append((row_id, similarity))

        # Sort by similarity descending, take top N
        scored.sort(key=lambda x: x[1], reverse=True)
        top_ids = [s[0] for s in scored[:limit]]
        top_scores = {s[0]: s[1] for s in scored[:limit]}

        if not top_ids:
            return []

        # Load full ORM objects
        stmt = select(SearchIndex).where(SearchIndex.id.in_(top_ids))
        orm_result = await self.session.execute(stmt)
        entries = {e.id: e for e in orm_result.scalars().all()}

        return [(entries[id_], top_scores[id_]) for id_ in top_ids if id_ in entries]

    async def delete_by_book(self, book_id: int) -> int:
        result = await self.session.execute(
            delete(SearchIndex).where(SearchIndex.book_id == book_id)
        )
        await self.session.flush()
        return result.rowcount

    async def delete_by_source(self, source_type: SourceType, source_id: int) -> int:
        result = await self.session.execute(
            delete(SearchIndex).where(
                SearchIndex.source_type == source_type,
                SearchIndex.source_id == source_id,
            )
        )
        await self.session.flush()
        return result.rowcount
