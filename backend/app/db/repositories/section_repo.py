"""BookSection repository — data access layer."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookSection, SummaryStatus


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

    async def update_summary(
        self,
        section_id: int,
        summary_md: str,
        summary_status: SummaryStatus,
        summary_model: str | None = None,
        summary_version: str | None = None,
    ) -> None:
        section = await self.get_by_id(section_id)
        if section:
            section.summary_md = summary_md
            section.summary_status = summary_status
            if summary_model:
                section.summary_model = summary_model
            if summary_version:
                section.summary_version = summary_version
            await self.session.flush()

    async def get_pending_sections(self, book_id: int) -> list[BookSection]:
        result = await self.session.execute(
            select(BookSection)
            .where(
                BookSection.book_id == book_id,
                BookSection.summary_status == SummaryStatus.PENDING,
            )
            .order_by(BookSection.order_index)
        )
        return list(result.scalars().all())
