"""SearchIndex repository — data access layer."""

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SearchIndex, SourceType


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
        ts_query = func.plainto_tsquery("english", query)
        rank = func.ts_rank(SearchIndex.tsvector, ts_query)
        stmt = (
            select(SearchIndex, rank.label("rank"))
            .where(SearchIndex.tsvector.op("@@")(ts_query))
            .order_by(rank.desc())
            .limit(limit)
        )
        if book_id:
            stmt = stmt.where(SearchIndex.book_id == book_id)
        result = await self.session.execute(stmt)
        return list(result.all())

    async def semantic_search(
        self,
        embedding: list[float],
        book_id: int | None = None,
        limit: int = 20,
    ) -> list[tuple[SearchIndex, float]]:
        distance = SearchIndex.embedding.cosine_distance(embedding)
        stmt = (
            select(SearchIndex, distance.label("distance"))
            .where(SearchIndex.embedding.isnot(None))
            .order_by(distance)
            .limit(limit)
        )
        if book_id:
            stmt = stmt.where(SearchIndex.book_id == book_id)
        result = await self.session.execute(stmt)
        return list(result.all())

    async def delete_by_book(self, book_id: int) -> int:
        result = await self.session.execute(
            delete(SearchIndex).where(SearchIndex.book_id == book_id)
        )
        await self.session.flush()
        return result.rowcount

    async def delete_by_source(
        self, source_type: SourceType, source_id: int
    ) -> int:
        result = await self.session.execute(
            delete(SearchIndex).where(
                SearchIndex.source_type == source_type,
                SearchIndex.source_id == source_id,
            )
        )
        await self.session.flush()
        return result.rowcount
