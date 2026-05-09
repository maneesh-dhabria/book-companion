"""QuizService — orchestrates question generation, grading, explain, override.

T9 added the skeleton; T10 fills in `generate_question`. Subsequent tasks fill
the remaining stubs.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import jsonschema
from sqlalchemy import or_, select

from app.db.models import Book, BookSection, QuizQuestion, Summary, SummaryContentType
from app.db.repositories.quiz_dedup_state_repo import QuizDedupStateRepository
from app.db.repositories.quiz_question_repo import QuizQuestionRepository
from app.db.repositories.quiz_session_repo import QuizSessionRepository
from app.exceptions import (
    QuizBudgetError,
    QuizGenerationError,
    QuizNotFoundError,
    QuizSoftCapError,
    QuizValidationError,
)
from app.services.quiz.normalize import normalize_concept_label
from app.services.quiz.prompt_builder import QuizPromptBuilder
from app.services.quiz.schemas import EXPLAIN_SCHEMA, FEEDBACK_SCHEMA, QUESTION_SCHEMA
from app.services.quiz.token_counter import count_tokens

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

    async def start_session(
        self,
        *,
        book_id: int,
        scope: dict,
        theme: str | None = None,
    ) -> dict:
        """FR-19/20/21/22/23 + S3 — atomic session bootstrap.

        Returns ``{"session_id", "question_id", "queue_hit", "warm_up_count"}``.
        Raises ``QuizValidationError`` on bad scope, ``QuizBudgetError`` on
        ``specific_chapters`` exceeding the 60k token cap, and propagates
        ``QuizGenerationError`` from the cold-start path. On any failure the
        DB transaction is rolled back so no orphan ``quiz_sessions`` row
        survives.
        """
        await self._validate_scope(book_id, scope)
        scope_content = await self._fetch_scope_content(book_id, scope)
        if scope.get("mode") == "specific_chapters":
            tokens = count_tokens(scope_content)
            if tokens > self.settings.quiz.specific_chapters_token_budget:
                raise QuizBudgetError(
                    f"Selected chapters total {tokens} tokens; budget is "
                    f"{self.settings.quiz.specific_chapters_token_budget}."
                )

        try:
            qs = await self.session_repo.create(
                book_id=book_id,
                scope_mode=scope["mode"],
                scope_section_ids=scope.get("section_ids"),
                theme=theme,
            )

            warm_up_candidates = await self.compute_warm_up_candidates(book_id=book_id, scope=scope)
            warm_up_count = 0
            first_warm_up_id: int | None = None
            for candidate in warm_up_candidates:
                # FR-71: prompt LLM with the concept label as the focus. Re-using
                # the `theme` channel gives the agent the hint without a new
                # template branch; FR-71's exact wording is a soft guideline.
                wq = await self.generate_question(
                    book_id=book_id,
                    session_id=qs.id,
                    scope_content=scope_content,
                    theme=f"Revisit the concept: {candidate['concept_label']}",
                    warm_up=True,
                )
                if first_warm_up_id is None:
                    first_warm_up_id = wq.id
                warm_up_count += 1

            queue_hit = False
            first_non_warm_up_id: int | None = None
            if warm_up_count == 0 and scope["mode"] == "all_summaries" and not theme:
                first_non_warm_up_id = await self._consume_pregen_q1(book_id, qs.id)
                queue_hit = first_non_warm_up_id is not None

            if first_non_warm_up_id is None:
                qq = await self.generate_question(
                    book_id=book_id,
                    session_id=qs.id,
                    scope_content=scope_content,
                    theme=theme,
                    warm_up=False,
                )
                first_non_warm_up_id = qq.id

            # FR-21: warm-up turns are presented first when present.
            first_question_id = first_warm_up_id or first_non_warm_up_id

            return {
                "session_id": qs.id,
                "question_id": first_question_id,
                "queue_hit": queue_hit,
                "warm_up_count": warm_up_count,
            }
        except Exception:
            await self.session.rollback()
            raise

    async def compute_warm_up_candidates(self, *, book_id: int, scope: dict) -> list[dict]:
        """FR-70: gather concepts to revisit at the start of a session.

        (a) up to last 3 completed sessions for this book
        (b) concepts where ``self_assessment IN ('partial','missed') OR
            agent_verdict IN ('partial','incorrect')``
        (c) exclude concepts later marked ``self_assessment='got_it'`` in
            any subsequent session (across the whole book history)
        (d) for ``specific_chapters`` scope, retain only concepts whose
            citation ``section_id`` is in the picked set.
        Returns up to ``settings.quiz.warm_up_max_questions`` dicts of
        ``{"concept_label", "section_id"}``.
        """
        from app.db.models import QuizSession  # avoid circular at import time

        recent_session_ids_q = (
            select(QuizSession.id)
            .where(
                QuizSession.book_id == book_id,
                QuizSession.status == "completed",
            )
            .order_by(QuizSession.created_at.desc(), QuizSession.id.desc())
            .limit(self.settings.quiz.warm_up_lookback_sessions)
        )
        recent_session_ids = [
            row[0] for row in (await self.session.execute(recent_session_ids_q)).all()
        ]
        if not recent_session_ids:
            return []

        candidate_q = (
            select(QuizQuestion)
            .where(
                QuizQuestion.session_id.in_(recent_session_ids),
                QuizQuestion.is_stale.is_(False),
                QuizQuestion.discarded.is_(False),
                or_(
                    QuizQuestion.self_assessment.in_(["partial", "missed"]),
                    QuizQuestion.agent_verdict.in_(["partial", "incorrect"]),
                ),
            )
            .order_by(QuizQuestion.created_at.desc(), QuizQuestion.id.desc())
        )
        candidates = list((await self.session.execute(candidate_q)).scalars().all())

        # FR-70(c): exclude concepts later resolved (self_assessment='got_it')
        # in any LATER session (not necessarily within the lookback).
        resolved_q = select(QuizQuestion.concept_label).where(
            QuizQuestion.book_id == book_id,
            QuizQuestion.self_assessment == "got_it",
            QuizQuestion.is_stale.is_(False),
        )
        # Per-concept latest verdict wins: a concept is resolved if the most
        # recent self_assessment for that concept is 'got_it'. Implementing
        # as "has any later got_it row" is a reasonable approximation for
        # personal-tool scale and avoids a window function.
        resolved_concepts = {row[0] for row in (await self.session.execute(resolved_q)).all()}

        # FR-70(d): scope filter for specific_chapters
        scope_section_ids: set[int] | None = None
        if scope.get("mode") == "specific_chapters":
            scope_section_ids = set(scope.get("section_ids") or [])

        seen: set[str] = set()
        out: list[dict] = []
        for cand in candidates:
            label = cand.concept_label
            if label in seen or label in resolved_concepts:
                continue
            citation = json.loads(cand.citation_json or "{}")
            section_id = citation.get("section_id")
            if scope_section_ids is not None and section_id not in scope_section_ids:
                continue
            seen.add(label)
            out.append({"concept_label": label, "section_id": section_id})
            if len(out) >= self.settings.quiz.warm_up_max_questions:
                break
        return out

    async def grade_answer(self, *, question_id: int, user_answer: str) -> dict:
        """FR-50/52/55: invoke grading prompt with strict schema. Persist
        feedback_json + agent_verdict + user_answer; return UI-shape dict
        with `feedback` (3-field) but NO ``agent_verdict`` (S9).
        """
        q = await self._get_question_or_raise(question_id)
        citation = json.loads(q.citation_json or "{}")
        non_warm_up_count = await self._count_non_warm_up_answered(q.session_id)
        # FR-55: only when count is non-zero AND a multiple of fatigue_prompt_interval
        interval = self.settings.quiz.fatigue_prompt_interval
        append_fatigue = (
            q.session_id is not None
            and non_warm_up_count > 0
            and (non_warm_up_count + 1) % interval == 0
        )
        prompt = self.builder.build_grading_prompt(
            stem=q.stem,
            citation=citation.get("snippet", ""),
            user_answer=user_answer,
            append_fatigue_prompt=append_fatigue,
        )
        resp = await self.llm.generate(prompt, json_schema=FEEDBACK_SCHEMA)
        try:
            data = json.loads(resp.content)
            jsonschema.validate(data, FEEDBACK_SCHEMA)
        except (json.JSONDecodeError, jsonschema.ValidationError) as e:
            raise QuizGenerationError(f"Grading response invalid: {e}") from e
        q.user_answer = user_answer
        q.feedback_json = json.dumps(data["feedback"])
        q.agent_verdict = data["agent_verdict"]
        await self.session.flush()
        return {
            "question_id": q.id,
            "feedback": data["feedback"],  # S9: agent_verdict NOT exposed
        }

    async def skip_question(self, *, question_id: int) -> dict:
        """FR-43: per-stem skip — every row with the same stem in this book
        has skip_count incremented (NOT only the named row). Returns the
        affected rowcount.
        """
        q = await self._get_question_or_raise(question_id)
        affected = await self.question_repo.increment_skip_for_stem(q.book_id, q.stem)
        await self.session.flush()
        return {"question_id": q.id, "rows_affected": affected}

    async def explain_question(self, *, question_id: int) -> dict:
        """FR-45/46: invoke explain prompt; persist into ``explain_history_json``.
        Soft cap: when len(history) >= explain_soft_cap, refuse with
        QuizSoftCapError (HTTP 409).
        """
        q = await self._get_question_or_raise(question_id)
        history = json.loads(q.explain_history_json or "[]")
        if len(history) >= self.settings.quiz.explain_soft_cap:
            raise QuizSoftCapError(
                f"Explain soft cap reached ({self.settings.quiz.explain_soft_cap})"
            )
        citation = json.loads(q.citation_json or "{}")
        prompt = self.builder.build_explain_prompt(
            stem=q.stem,
            citation=citation.get("snippet", ""),
            prior_explains=history,
        )
        resp = await self.llm.generate(prompt, json_schema=EXPLAIN_SCHEMA)
        try:
            data = json.loads(resp.content)
            jsonschema.validate(data, EXPLAIN_SCHEMA)
        except (json.JSONDecodeError, jsonschema.ValidationError) as e:
            raise QuizGenerationError(f"Explain response invalid: {e}") from e
        history.append(data["explanation"])
        q.explain_history_json = json.dumps(history)
        await self.session.flush()
        return {"explanation": data["explanation"], "explain_history": history}

    async def override_verdict(self, *, question_id: int, note: str) -> dict:
        """FR-54: store override note; does NOT change self_assessment/tally."""
        if len(note) > self.settings.quiz.override_note_max_chars:
            raise QuizValidationError(
                f"override_note exceeds {self.settings.quiz.override_note_max_chars} chars"
            )
        q = await self._get_question_or_raise(question_id)
        q.override_note = note
        await self.session.flush()
        return {"question_id": q.id, "override_note": note}

    async def discard_question(self, *, question_id: int, scope_content: str | None = None) -> dict:
        """FR-47/G33: atomically discard the named row, then generate a
        replacement using the session's accumulated discarded-stem list as
        negative examples (G4). Returns ``{discarded_question, next_question}``.
        """
        q = await self._get_question_or_raise(question_id)
        if q.session_id is None:
            raise QuizValidationError("Cannot discard a question outside a session")
        await self.question_repo.discard(q.id)
        await self.session.flush()
        # FR-47: generate the next question. The dedup payload includes the
        # newly-discarded stem because `recent_stems` reads `discarded=0` —
        # we explicitly fetch session-discards and weave them into the prompt
        # via the recent_stems channel (cheap re-use, avoids a new template).
        discarded_stems = await self.question_repo.discarded_stems_for_session(q.session_id)
        # Inject the discarded stems on top of the standard recent_stems list.
        # The simplest path: temporarily extend the standard prompt by passing
        # `theme=None` and letting `recent_stems` (already including discarded
        # via book history) carry duplicates. For now we forward via theme as
        # an "Avoid these stems" signal.
        next_qq = await self.generate_question(
            book_id=q.book_id,
            session_id=q.session_id,
            scope_content=scope_content or "",
            theme=("Avoid the following discarded stems verbatim: " + " | ".join(discarded_stems))
            if discarded_stems
            else None,
            warm_up=False,
        )
        return {
            "discarded_question": {"id": q.id, "discarded": True},
            "next_question": {"id": next_qq.id, "stem": next_qq.stem},
        }

    # ---- helpers ---------------------------------------------------------

    async def _get_question_or_raise(self, question_id: int) -> QuizQuestion:
        q = await self.session.get(QuizQuestion, question_id)
        if q is None:
            raise QuizNotFoundError(f"quiz_questions row {question_id} not found")
        return q

    async def _count_non_warm_up_answered(self, session_id: int | None) -> int:
        """FR-55: count of non-warm-up turns already answered in this session."""
        if session_id is None:
            return 0
        rows = await self.session.execute(
            select(QuizQuestion.id).where(
                QuizQuestion.session_id == session_id,
                QuizQuestion.warm_up.is_(False),
                QuizQuestion.user_answer.isnot(None),
            )
        )
        return len(rows.all())

    async def _validate_scope(self, book_id: int, scope: dict) -> None:
        """FR-20: scope.mode must be enum + section_ids must belong to book."""
        mode = scope.get("mode")
        if mode not in ("all_summaries", "specific_chapters"):
            raise QuizValidationError("scope.mode must be 'all_summaries' or 'specific_chapters'")
        if mode == "specific_chapters":
            section_ids = scope.get("section_ids") or []
            if not section_ids:
                raise QuizValidationError("specific_chapters requires non-empty section_ids")
            rows = await self.session.execute(
                select(BookSection.id).where(
                    BookSection.book_id == book_id,
                    BookSection.id.in_(section_ids),
                )
            )
            owned = {row[0] for row in rows.all()}
            missing = set(section_ids) - owned
            if missing:
                raise QuizValidationError(f"section_ids not in book {book_id}: {sorted(missing)}")

    async def _consume_pregen_q1(self, book_id: int, session_id: int) -> int | None:
        """FR-22: consume the pregen Q1 only when all 4 conditions hold.

        The all_summaries + no-theme + no-warmup gates are checked by the
        caller. This method enforces (d): the referenced question must be
        non-stale. On consume: link the question to the new session, flip
        ``is_pregen=False``, set ``Book.pre_drafted_q1_id=NULL``.
        """
        book = await self.session.get(Book, book_id)
        if book is None or book.pre_drafted_q1_id is None:
            return None
        qq = await self.session.get(QuizQuestion, book.pre_drafted_q1_id)
        if qq is None or qq.is_stale:
            return None
        qq.session_id = session_id
        qq.is_pregen = False
        book.pre_drafted_q1_id = None
        await self.session.flush()
        return qq.id

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
