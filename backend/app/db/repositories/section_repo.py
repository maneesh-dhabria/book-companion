"""BookSection repository — data access layer."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookSection


class SectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_bulk(self, sections: list[BookSection]) -> list[BookSection]:
        self.session.add_all(sections)
        await self.session.flush()
        return sections

    async def get_by_book_id(self, book_id: int) -> list[BookSection]:
        result = await self.session.execute(
            select(BookSection)
            .where(BookSection.book_id == book_id)
            .order_by(BookSection.order_index)
        )
        return list(result.scalars().all())

    async def get_by_id(self, section_id: int) -> BookSection | None:
        result = await self.session.execute(
            select(BookSection).where(BookSection.id == section_id)
        )
        return result.scalar_one_or_none()
