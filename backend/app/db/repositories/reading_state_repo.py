"""Reading state repository — thin query builder for reading_state table."""

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ReadingState


class ReadingStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        user_agent: str,
        book_id: int,
        section_id: int | None = None,
        scroll_position: float | None = None,
        content_mode: str = "summary",
    ) -> ReadingState:
        """Insert or update reading state by user_agent using ON CONFLICT."""
        stmt = sqlite_insert(ReadingState).values(
            user_agent=user_agent,
            book_id=book_id,
            section_id=section_id,
            scroll_position=scroll_position,
            content_mode=content_mode,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_agent"],
            set_={
                "book_id": stmt.excluded.book_id,
                "section_id": stmt.excluded.section_id,
                "scroll_position": stmt.excluded.scroll_position,
                "content_mode": stmt.excluded.content_mode,
            },
        ).returning(ReadingState)
        result = await self.session.execute(stmt)
        row = result.scalar_one()
        await self.session.flush()
        return row

    async def get_by_user_agent(self, user_agent: str) -> ReadingState | None:
        """Get reading state for a specific device."""
        result = await self.session.execute(
            select(ReadingState)
            .options(selectinload(ReadingState.book), selectinload(ReadingState.section))
            .where(ReadingState.user_agent == user_agent)
        )
        return result.scalar_one_or_none()

    async def get_latest_other_device(self, current_user_agent: str) -> ReadingState | None:
        """Get the most recent reading state from a different device."""
        result = await self.session.execute(
            select(ReadingState)
            .options(selectinload(ReadingState.book), selectinload(ReadingState.section))
            .where(ReadingState.user_agent != current_user_agent)
            .where(ReadingState.book_id.isnot(None))
            .order_by(ReadingState.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
