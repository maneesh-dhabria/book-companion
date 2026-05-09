"""QuizQuestion repository — data access layer."""

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QuizQuestion, QuizSession


class QuizQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **fields) -> QuizQuestion:
        q = QuizQuestion(**fields)
        self.session.add(q)
        await self.session.flush()
        return q

    async def get_by_id(self, question_id: int) -> QuizQuestion | None:
        return await self.session.get(QuizQuestion, question_id)

    async def recent_stems(self, book_id: int, limit: int = 50) -> list[str]:
        """FR-60: recent verbatim stems for dedup payload.

        Excludes stale, discarded, skipped (>=3) rows; warm-up rows count only
        once they've been answered (self_assessment IS NOT NULL).
        """
        q = (
            select(QuizQuestion.stem)
            .where(
                QuizQuestion.book_id == book_id,
                QuizQuestion.is_stale.is_(False),
                QuizQuestion.discarded.is_(False),
                QuizQuestion.skip_count < 3,
                or_(
                    QuizQuestion.warm_up.is_(False),
                    QuizQuestion.self_assessment.isnot(None),
                ),
            )
            .order_by(QuizQuestion.created_at.desc(), QuizQuestion.id.desc())
            .limit(limit)
        )
        return [row[0] for row in (await self.session.execute(q)).all()]

    async def concepts_with_skip_threshold(
        self, book_id: int, threshold: int
    ) -> list[str]:
        """FR-44: concepts that have been skipped >= threshold times across all
        questions for this book."""
        q = (
            select(QuizQuestion.concept_label)
            .where(
                QuizQuestion.book_id == book_id,
                QuizQuestion.is_stale.is_(False),
                QuizQuestion.skip_count >= threshold,
            )
            .group_by(QuizQuestion.concept_label)
        )
        return [row[0] for row in (await self.session.execute(q)).all()]

    async def warm_up_candidates(
        self, book_id: int, lookback_sessions: int = 3
    ) -> list[tuple[str, dict]]:
        """FR-70: stems from the last N sessions that the user marked as
        partial/missed and that have not yet been retried."""
        recent_sessions_q = (
            select(QuizSession.id)
            .where(QuizSession.book_id == book_id)
            .order_by(QuizSession.created_at.desc(), QuizSession.id.desc())
            .limit(lookback_sessions)
        )
        recent_session_ids = [
            row[0] for row in (await self.session.execute(recent_sessions_q)).all()
        ]
        if not recent_session_ids:
            return []
        q = (
            select(QuizQuestion)
            .where(
                QuizQuestion.book_id == book_id,
                QuizQuestion.session_id.in_(recent_session_ids),
                QuizQuestion.self_assessment.in_(["partial", "missed"]),
                QuizQuestion.is_stale.is_(False),
                QuizQuestion.discarded.is_(False),
            )
            .order_by(QuizQuestion.created_at.desc())
        )
        rows = list((await self.session.execute(q)).scalars().all())
        return [
            (
                row.stem,
                {
                    "concept_label": row.concept_label,
                    "shape": row.shape,
                    "bloom_level": row.bloom_level,
                    "self_assessment": row.self_assessment,
                    "session_id": row.session_id,
                },
            )
            for row in rows
        ]

    async def mark_stale_for_book(self, book_id: int) -> int:
        """FR-64: re-import flips is_stale=True on all questions for the book.
        Returns affected rowcount."""
        result = await self.session.execute(
            update(QuizQuestion)
            .where(QuizQuestion.book_id == book_id, QuizQuestion.is_stale.is_(False))
            .values(is_stale=True)
        )
        return result.rowcount or 0

    async def increment_skip_for_stem(self, book_id: int, stem: str) -> int:
        """FR-43: when the user skips a question, every persisted row with the
        same stem (across sessions) gets skip_count += 1. Returns rowcount.
        """
        result = await self.session.execute(
            update(QuizQuestion)
            .where(QuizQuestion.book_id == book_id, QuizQuestion.stem == stem)
            .values(skip_count=QuizQuestion.skip_count + 1)
        )
        return result.rowcount or 0

    async def discard(self, question_id: int) -> None:
        """G4: 'Already asked' link consumed → flip discarded=True."""
        await self.session.execute(
            update(QuizQuestion)
            .where(QuizQuestion.id == question_id)
            .values(discarded=True)
        )

    async def discarded_stems_for_session(self, session_id: int) -> list[str]:
        """FR-47/G4: stems the user discarded inside this session — fed to the
        next-question prompt as a 'do not repeat' list."""
        q = (
            select(QuizQuestion.stem)
            .where(
                QuizQuestion.session_id == session_id,
                QuizQuestion.discarded.is_(True),
            )
            .order_by(QuizQuestion.created_at)
        )
        return [row[0] for row in (await self.session.execute(q)).all()]
