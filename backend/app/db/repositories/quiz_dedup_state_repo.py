"""QuizDedupState repository — data access layer."""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QuizDedupState


class QuizDedupStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, book_id: int) -> QuizDedupState | None:
        return await self.session.get(QuizDedupState, book_id)

    async def upsert(
        self,
        *,
        book_id: int,
        themes_summary: str | None,
        last_rollup_question_count: int,
    ) -> QuizDedupState:
        existing = await self.get(book_id)
        now = datetime.now(timezone.utc)
        if existing is None:
            state = QuizDedupState(
                book_id=book_id,
                themes_summary=themes_summary,
                themes_summary_computed_at=now if themes_summary else None,
                last_rollup_question_count=last_rollup_question_count,
            )
            self.session.add(state)
            await self.session.flush()
            return state
        existing.themes_summary = themes_summary
        existing.themes_summary_computed_at = now if themes_summary else None
        existing.last_rollup_question_count = last_rollup_question_count
        await self.session.flush()
        return existing

    async def reset(self, book_id: int) -> None:
        """FR-64: re-import wipes the cached themed-summary."""
        await self.session.execute(
            update(QuizDedupState)
            .where(QuizDedupState.book_id == book_id)
            .values(
                themes_summary=None,
                themes_summary_computed_at=None,
                last_rollup_question_count=0,
            )
        )
