"""Summary repository — data access for append-only summary log."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Summary, SummaryContentType


class SummaryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, summary: Summary) -> Summary:
        self.session.add(summary)
        await self.session.flush()
        return summary

    async def get_by_id(self, summary_id: int) -> Summary | None:
        result = await self.session.execute(
            select(Summary).where(Summary.id == summary_id)
        )
        return result.scalar_one_or_none()

    async def list_by_book(self, book_id: int) -> list[Summary]:
        result = await self.session.execute(
            select(Summary)
            .where(Summary.book_id == book_id)
            .order_by(Summary.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_content(
        self, content_type: SummaryContentType, content_id: int
    ) -> list[Summary]:
        result = await self.session.execute(
            select(Summary)
            .where(
                Summary.content_type == content_type,
                Summary.content_id == content_id,
            )
            .order_by(Summary.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_book_level(self, book_id: int) -> list[Summary]:
        result = await self.session.execute(
            select(Summary)
            .where(
                Summary.book_id == book_id,
                Summary.content_type == SummaryContentType.BOOK,
            )
            .order_by(Summary.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_latest_by_content_and_facets(
        self,
        content_type: SummaryContentType,
        content_id: int,
        facets: dict,
    ) -> Summary | None:
        result = await self.session.execute(
            select(Summary)
            .where(
                Summary.content_type == content_type,
                Summary.content_id == content_id,
                Summary.facets_used == facets,
            )
            .order_by(Summary.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_for_book(self, book_id: int) -> Summary | None:
        result = await self.session.execute(
            select(Summary)
            .where(Summary.book_id == book_id)
            .order_by(Summary.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_by_content(
        self, content_type: SummaryContentType, content_id: int
    ) -> int:
        result = await self.session.execute(
            select(func.count(Summary.id)).where(
                Summary.content_type == content_type,
                Summary.content_id == content_id,
            )
        )
        return result.scalar_one()
