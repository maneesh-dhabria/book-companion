"""Reading state repository — thin query builder for reading_state table."""

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import BookSection, ReadingState
from app.services.parser.section_classifier import FRONT_MATTER_TYPES


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

    async def get_for_device_and_book(self, user_agent: str, book_id: int) -> ReadingState | None:
        """Reading state for a specific device + book pair (P13, FR-C02 helper).

        Used by the Continue tile in OverviewDashboard to switch its label
        between "Continue reading" and "Start reading".
        """
        result = await self.session.execute(
            select(ReadingState)
            .options(selectinload(ReadingState.section))
            .where(ReadingState.user_agent == user_agent)
            .where(ReadingState.book_id == book_id)
        )
        return result.scalar_one_or_none()

    async def get_all_devices_for_book(
        self, book_id: int, *, since: datetime | None = None
    ) -> list[ReadingState]:
        """All reading-state rows for a book across every device, optionally
        windowed to rows updated at-or-after `since`. Ordered newest-first.

        Used by `GET /reading-state/by-book/{id}` (FR-17) to populate the Quiz
        tab's D31 default-scope hints from cross-device activity.
        """
        stmt = (
            select(ReadingState)
            .options(selectinload(ReadingState.section))
            .where(ReadingState.book_id == book_id)
        )
        if since is not None:
            stmt = stmt.where(ReadingState.updated_at >= since)
        stmt = stmt.order_by(ReadingState.updated_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_resume_banner_reading(self) -> ReadingState | None:
        """Get the most-recent reading_state across ALL browsers, skipping rows
        whose target section is front-matter.

        Used by `GET /reading-state/resume-banner` (FR-B05). Differs from
        `get_latest_other_device` in that it does NOT filter on user_agent —
        the home banner shows the most-recent action regardless of device.
        """
        result = await self.session.execute(
            select(ReadingState)
            .outerjoin(BookSection, BookSection.id == ReadingState.section_id)
            .options(selectinload(ReadingState.book), selectinload(ReadingState.section))
            .where(ReadingState.book_id.isnot(None))
            .where(
                or_(
                    ReadingState.section_id.is_(None),
                    BookSection.section_type.notin_(FRONT_MATTER_TYPES),
                )
            )
            .order_by(ReadingState.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_other_device(self, current_user_agent: str) -> ReadingState | None:
        """Get the most recent reading state from a different device.

        Skips rows whose target section is front-matter (copyright, cover, …) so
        the "Continue where you left off" banner never lands on a non-readable
        page (FR-B05a). Rows with `section_id IS NULL` (book-level resume) pass
        through.
        """
        result = await self.session.execute(
            select(ReadingState)
            .outerjoin(BookSection, BookSection.id == ReadingState.section_id)
            .options(selectinload(ReadingState.book), selectinload(ReadingState.section))
            .where(ReadingState.user_agent != current_user_agent)
            .where(ReadingState.book_id.isnot(None))
            .where(
                or_(
                    ReadingState.section_id.is_(None),
                    BookSection.section_type.notin_(FRONT_MATTER_TYPES),
                )
            )
            .order_by(ReadingState.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
