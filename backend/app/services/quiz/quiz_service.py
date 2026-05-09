"""QuizService — orchestrates question generation, grading, explain, override.

Skeleton in T9; methods are filled in by T10 (generate_question), T11
(start_session), T12 (warm_up_candidates), T13 (grade/skip/explain/discard).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.db.repositories.quiz_dedup_state_repo import QuizDedupStateRepository
from app.db.repositories.quiz_question_repo import QuizQuestionRepository
from app.db.repositories.quiz_session_repo import QuizSessionRepository
from app.services.quiz.prompt_builder import QuizPromptBuilder

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.config import Settings
    from app.services.summarizer.llm_provider import LLMProvider


class QuizService:
    def __init__(
        self,
        session: AsyncSession,
        llm: LLMProvider,
        settings: Settings,
    ):
        self.session = session
        self.llm = llm
        self.settings = settings
        self.session_repo = QuizSessionRepository(session)
        self.question_repo = QuizQuestionRepository(session)
        self.dedup_repo = QuizDedupStateRepository(session)
        self.builder = QuizPromptBuilder(settings)

    async def generate_question(self, **kwargs):  # noqa: D401 — implemented in T10
        raise NotImplementedError("Filled in by T10")

    async def start_session(self, **kwargs):
        raise NotImplementedError("Filled in by T11")

    async def warm_up_candidates(self, *, book_id: int):
        raise NotImplementedError("Filled in by T12")

    async def grade_answer(self, **kwargs):
        raise NotImplementedError("Filled in by T13")

    async def skip_question(self, **kwargs):
        raise NotImplementedError("Filled in by T13")

    async def explain_question(self, **kwargs):
        raise NotImplementedError("Filled in by T13")

    async def override_verdict(self, **kwargs):
        raise NotImplementedError("Filled in by T13")

    async def discard_question(self, **kwargs):
        raise NotImplementedError("Filled in by T13")
