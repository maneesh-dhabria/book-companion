"""QuizService — orchestrates question generation, grading, explain, override.

T9 added the skeleton; T10 fills in `generate_question`. Subsequent tasks fill
the remaining stubs.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import jsonschema
from sqlalchemy import select

from app.db.models import BookSection, QuizQuestion, Summary, SummaryContentType
from app.db.repositories.quiz_dedup_state_repo import QuizDedupStateRepository
from app.db.repositories.quiz_question_repo import QuizQuestionRepository
from app.db.repositories.quiz_session_repo import QuizSessionRepository
from app.exceptions import QuizGenerationError
from app.services.quiz.normalize import normalize_concept_label
from app.services.quiz.prompt_builder import QuizPromptBuilder
from app.services.quiz.schemas import QUESTION_SCHEMA

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.config import Settings
    from app.services.summarizer.llm_provider import LLMProvider


# FR-33: deliberate-flip lexicon. The spot_error validator requires the stem
# to differ from the citation snippet by ≥1 negation/quantitative-flip token.
_FLIP_TOKENS = frozenset(
    [
        "not",
        "no",
        "never",
        "none",
        "neither",
        "without",
        "always",
        "all",
        "every",
        "everyone",
        "everywhere",
        "more",
        "less",
        "fewer",
        "greater",
        "smaller",
        "increase",
        "decrease",
        "increased",
        "decreased",
        "rises",
        "falls",
        "positive",
        "negative",
        "before",
        "after",
        "above",
        "below",
        "first",
        "last",
        "cause",
        "effect",
        "true",
        "false",
        "majority",
        "minority",
        "most",
        "least",
        "high",
        "low",
        "rarely",
        "often",
        "seldom",
        "frequent",
        "infrequent",
    ]
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class SpotErrorValidationError(QuizGenerationError):
    """FR-33: stem failed the deliberate-flip heuristic."""


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

    # ---- public surface --------------------------------------------------

    async def generate_question(
        self,
        *,
        book_id: int,
        session_id: int | None,
        scope: dict | None = None,
        scope_content: str | None = None,
        theme: str | None = None,
        warm_up: bool = False,
    ) -> QuizQuestion:
        """FR-30/32/33/34/35.

        Either `scope_content` is provided directly (start_session passes it
        in after fetching), or `scope` is given and we resolve it via
        `_fetch_scope_content`. Tests pass `scope_content` directly to skip
        DB fetch fixtures.
        """
        if scope_content is None:
            scope_content = await self._fetch_scope_content(book_id, scope or {})

        recent_stems = await self.question_repo.recent_stems(
            book_id, limit=self.settings.quiz.dedup_verbatim_cap
        )
        dedup_state = await self.dedup_repo.get(book_id)
        themed_summary = dedup_state.themes_summary if dedup_state else None
        shape_hist = await self._compute_shape_histogram(session_id)
        skipped = await self.question_repo.concepts_with_skip_threshold(
            book_id, threshold=self.settings.quiz.skip_dedup_threshold
        )

        validator_error: str | None = None
        data: dict[str, Any] | None = None
        last_exc: Exception | None = None
        for attempt in (0, 1):
            prompt = self.builder.build_generation_prompt(
                scope_content=scope_content,
                recent_stems=recent_stems,
                themed_summary=themed_summary,
                theme=theme,
                shape_histogram=shape_hist,
                skipped_concepts=skipped,
                validator_error=validator_error,
            )
            try:
                resp = await self.llm.generate(prompt, json_schema=QUESTION_SCHEMA)
                data = json.loads(resp.content)
                jsonschema.validate(data, QUESTION_SCHEMA)
                if data["shape"] == "spot_error":
                    self._validate_spot_error(data)
                break
            except (
                json.JSONDecodeError,
                jsonschema.ValidationError,
                SpotErrorValidationError,
            ) as e:
                last_exc = e
                validator_error = self._format_validator_error(e)
                data = None
                if attempt == 1:
                    raise QuizGenerationError(f"Question generation failed after retry: {e}") from e

        assert data is not None  # defensive — break would have set data  # noqa: S101
        # FR-34: normalize before persistence so the D29 JOIN finds the row.
        data["concept_label"] = normalize_concept_label(data["concept_label"])

        qq = QuizQuestion(
            book_id=book_id,
            session_id=session_id,
            shape=data["shape"],
            bloom_level=data["bloom_level"],
            stem=data["stem"],
            concept_label=data["concept_label"],
            citation_json=json.dumps(data["citation"]),
            mcq_options_json=(
                json.dumps(
                    {
                        "options": data["mcq_options"],
                        "correct_index": data.get("mcq_correct_index", 0),
                    }
                )
                if data["shape"] == "mcq"
                else None
            ),
            intended_error=data.get("intended_error") if data["shape"] == "spot_error" else None,
            error_explanation=(
                data.get("error_explanation") if data["shape"] == "spot_error" else None
            ),
            warm_up=warm_up,
        )
        self.session.add(qq)
        await self.session.flush()
        # Silence unused last_exc in static analyzers; kept for potential
        # future telemetry without changing the raise path.
        _ = last_exc
        return qq

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

    # ---- helpers ---------------------------------------------------------

    async def _fetch_scope_content(self, book_id: int, scope: dict) -> str:
        """Build the scope-content blob fed into the generation prompt.

        - `mode='all_summaries'`: concatenate default section summaries (and
          fall back to section titles when no summary exists).
        - `mode='specific_chapters'`: concatenate `content_md` for the given
          section IDs in order.
        - empty scope: returns empty string (caller must provide
          `scope_content` directly in that case).
        """
        mode = scope.get("mode")
        if mode == "specific_chapters":
            section_ids = scope.get("section_ids") or []
            rows = await self.session.execute(
                select(BookSection)
                .where(BookSection.book_id == book_id, BookSection.id.in_(section_ids))
                .order_by(BookSection.order_index)
            )
            sections = list(rows.scalars().all())
            return "\n\n".join(f"## {s.title}\n\n{s.content_md or ''}" for s in sections)
        if mode == "all_summaries":
            rows = await self.session.execute(
                select(Summary, BookSection)
                .join(BookSection, BookSection.id == Summary.content_id)
                .where(
                    BookSection.book_id == book_id,
                    Summary.content_type == SummaryContentType.SECTION,
                    Summary.is_stale.is_(False),
                )
                .order_by(BookSection.order_index)
            )
            chunks: list[str] = []
            for summary, section in rows.all():
                if summary.id == section.default_summary_id:
                    chunks.append(f"## {section.title}\n\n{summary.summary_md or ''}")
            return "\n\n".join(chunks)
        return ""

    async def _compute_shape_histogram(self, session_id: int | None) -> dict[str, int]:
        hist = {"mcq": 0, "open": 0, "spot_error": 0}
        if session_id is None:
            return hist
        rows = await self.session.execute(
            select(QuizQuestion.shape)
            .where(QuizQuestion.session_id == session_id)
            .order_by(QuizQuestion.created_at.desc(), QuizQuestion.id.desc())
            .limit(5)
        )
        for (shape,) in rows.all():
            if shape in hist:
                hist[shape] += 1
        return hist

    def _validate_spot_error(self, data: dict) -> None:
        """FR-33: the stem must encode a deliberate flip vs. the citation snippet.

        Heuristic: tokens in the stem MUST contain at least one
        negation/quantitative-flip token NOT present in the citation snippet.
        Reject when the snippet already contains every flip-token in the stem
        (treat as a "correct restatement").
        """
        intended = (data.get("intended_error") or "").strip()
        if not intended:
            raise SpotErrorValidationError("spot_error response missing non-empty intended_error")
        stem = (data.get("stem") or "").lower()
        snippet = (data.get("citation", {}).get("snippet") or "").lower()
        stem_tokens = set(_TOKEN_RE.findall(stem))
        snippet_tokens = set(_TOKEN_RE.findall(snippet))
        deliberate_flips = (stem_tokens - snippet_tokens) & _FLIP_TOKENS
        if not deliberate_flips:
            raise SpotErrorValidationError(
                "spot_error stem does not introduce a deliberate negation or "
                "quantitative flip beyond the citation snippet — refusing as a "
                "correct restatement (FR-33)."
            )

    @staticmethod
    def _format_validator_error(exc: Exception) -> str:
        if isinstance(exc, jsonschema.ValidationError):
            path = "/".join(str(p) for p in exc.absolute_path) or "<root>"
            return f"JSON-schema validation failed at {path}: {exc.message}"
        return f"{type(exc).__name__}: {exc}"
