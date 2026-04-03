"""BookSection repository — data access layer."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookSection


class SectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_bulk(self, sections: list[BookSection]) -> list[BookSection]:
        self.session.add_all(sections)
        await self.session.flush()
        return sections

    async def create(self, section: BookSection) -> BookSection:
        self.session.add(section)
        await self.session.flush()
        return section

    async def get_by_book_id(self, book_id: int) -> list[BookSection]:
        result = await self.session.execute(
            select(BookSection)
            .where(BookSection.book_id == book_id)
            .order_by(BookSection.order_index)
        )
        return list(result.scalars().all())

    async def get_by_id(self, section_id: int) -> BookSection | None:
        result = await self.session.execute(select(BookSection).where(BookSection.id == section_id))
        return result.scalar_one_or_none()

    async def get_by_ids(self, section_ids: list[int]) -> list[BookSection]:
        if not section_ids:
            return []
        result = await self.session.execute(
            select(BookSection)
            .where(BookSection.id.in_(section_ids))
            .order_by(BookSection.order_index)
        )
        return list(result.scalars().all())

    async def delete_by_ids(self, section_ids: list[int]) -> int:
        if not section_ids:
            return 0
        result = await self.session.execute(
            delete(BookSection).where(BookSection.id.in_(section_ids))
        )
        await self.session.flush()
        return result.rowcount

    async def reindex_order(self, book_id: int) -> None:
        """Re-number order_index values 0-based for all sections in a book."""
        sections = await self.get_by_book_id(book_id)
        for idx, section in enumerate(sections):
            section.order_index = idx
        await self.session.flush()

    async def update_default_summary(self, section_id: int, summary_id: int | None) -> None:
        section = await self.get_by_id(section_id)
        if section:
            section.default_summary_id = summary_id
            await self.session.flush()

    async def count_by_book(self, book_id: int) -> int:
        result = await self.session.execute(
            select(func.count(BookSection.id)).where(BookSection.book_id == book_id)
        )
        return result.scalar_one()
