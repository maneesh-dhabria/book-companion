"""QuizSession repository — data access layer."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import QuizSession


class QuizSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        book_id: int,
        scope_mode: str,
        scope_section_ids: list[int] | None = None,
        theme: str | None = None,
    ) -> QuizSession:
        qs = QuizSession(
            book_id=book_id,
            scope_mode=scope_mode,
            scope_section_ids=scope_section_ids,
            theme=theme,
            status="in_progress",
        )
        self.session.add(qs)
        await self.session.flush()
        return qs

    async def get_by_id(self, session_id: int) -> QuizSession | None:
        q = (
            select(QuizSession)
            .where(QuizSession.id == session_id)
            .options(selectinload(QuizSession.questions))
        )
        return (await self.session.execute(q)).scalar_one_or_none()

    async def list_by_book(self, book_id: int) -> list[QuizSession]:
        q = (
            select(QuizSession)
            .where(QuizSession.book_id == book_id)
            .order_by(QuizSession.created_at.desc(), QuizSession.id.desc())
            .options(selectinload(QuizSession.questions))
        )
        return list((await self.session.execute(q)).scalars().all())

    async def get_in_progress_for_book(self, book_id: int) -> QuizSession | None:
        q = (
            select(QuizSession)
            .where(QuizSession.book_id == book_id, QuizSession.status == "in_progress")
            .options(selectinload(QuizSession.questions))
        )
        return (await self.session.execute(q)).scalars().first()

    async def update_status(
        self, session_id: int, status: str, ended_at: datetime | None = None
    ) -> None:
        await self.session.execute(
            update(QuizSession)
            .where(QuizSession.id == session_id)
            .values(status=status, ended_at=ended_at)
        )
