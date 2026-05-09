"""T15 — Quiz API integration tests (spec §9.1–9.10).

Wiring + error-path coverage. The LLM-driven happy paths are exercised at
the unit level (`tests/unit/test_quiz_service_*.py`); these tests inject
FakeLLMProvider via the `get_quiz_service` dependency override to keep
integration tests deterministic and fast.
"""

import json

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.api import deps
from app.config import Settings
from app.services.quiz.quiz_service import QuizService
from tests.unit.conftest import FakeLLMProvider

# ---- helpers ---------------------------------------------------------------


async def _seed_book(app, *, book_id: int = 1, with_section: bool = True) -> None:
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (:id, 'B', x'00', :hash, 'epub', 1, 'COMPLETED')
                """
            ),
            {"id": book_id, "hash": f"h{book_id}"},
        )
        if with_section:
            await session.execute(
                text(
                    "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                    "section_type, content_md) VALUES (:sid, :bid, 'Ch1', 0, 0, 'chapter', 'c')"
                ),
                {"sid": book_id * 100 + 1, "bid": book_id},
            )
        await session.commit()


async def _seed_summary_for_section(app, *, book_id: int, section_id: int) -> None:
    factory = app.state.session_factory
    async with factory() as session:
        from app.db.models import Summary, SummaryContentType

        s = Summary(
            book_id=book_id,
            content_type=SummaryContentType.SECTION,
            content_id=section_id,
            facets_used={},
            prompt_text_sent="prompt",
            model_used="fake",
            input_char_count=10,
            summary_char_count=14,
            summary_md="Summary content",
        )
        session.add(s)
        await session.flush()
        await session.execute(
            text("UPDATE book_sections SET default_summary_id = :sid WHERE id = :sec"),
            {"sid": s.id, "sec": section_id},
        )
        await session.commit()


async def _seed_question(
    app,
    *,
    book_id: int,
    session_id: int | None = None,
    stem: str = "What is X?",
    self_assessment: str | None = None,
    user_answer: str | None = None,
    discarded: bool = False,
    skip_count: int = 0,
    explain_history_json: str = "[]",
    is_pregen: bool = False,
) -> int:
    """Insert a quiz_questions row directly; returns its id."""
    factory = app.state.session_factory
    async with factory() as session:
        from app.db.models import QuizQuestion

        q = QuizQuestion(
            book_id=book_id,
            session_id=session_id,
            shape="open",
            bloom_level="apply",
            stem=stem,
            concept_label="x",
            citation_json=json.dumps({"section_id": 1, "section_title": "Ch", "snippet": "..."}),
            self_assessment=self_assessment,
            user_answer=user_answer,
            discarded=discarded,
            skip_count=skip_count,
            explain_history_json=explain_history_json,
            is_pregen=is_pregen,
        )
        session.add(q)
        await session.flush()
        qid = q.id
        await session.commit()
    return qid


async def _seed_session(app, *, book_id: int, scope_mode: str = "all_summaries") -> int:
    factory = app.state.session_factory
    async with factory() as session:
        from app.db.models import QuizSession

        qs = QuizSession(book_id=book_id, scope_mode=scope_mode, status="in_progress")
        session.add(qs)
        await session.flush()
        sid = qs.id
        await session.commit()
    return sid


# ---- fixtures --------------------------------------------------------------


def _install_fake_llm(app, responses: list) -> FakeLLMProvider:
    """Override get_quiz_service to inject a FakeLLMProvider with scripted responses.

    Returns the FakeLLMProvider instance so tests can inspect `.calls`.
    """
    fake = FakeLLMProvider(responses)

    def _override(db=None, settings=None):  # FastAPI calls with deps; we ignore them
        # The real dep signature uses Depends(get_db) + Depends(get_settings).
        # FastAPI will inject the resolved AsyncSession when the override has
        # a matching Depends parameter, so we re-declare it via Depends below.
        raise RuntimeError("override should not be called directly")

    async def _impl(db, settings):
        return QuizService(session=db, llm=fake, settings=settings)

    from fastapi import Depends

    async def _route_dep(
        db=Depends(deps.get_db),  # noqa: B008
        settings=Depends(deps.get_settings),  # noqa: B008
    ):
        return await _impl(db, settings)

    app.dependency_overrides[deps.get_quiz_service] = _route_dep
    return fake


@pytest_asyncio.fixture
async def fake_llm(app):
    """Yields a controller object with `set(responses)` to script the next call."""

    class _Controller:
        provider: FakeLLMProvider | None = None

        def set(self, responses: list) -> FakeLLMProvider:
            self.provider = _install_fake_llm(app, responses)
            return self.provider

    ctl = _Controller()
    yield ctl
    app.dependency_overrides.pop(deps.get_quiz_service, None)


def _override_no_llm(app) -> None:
    """Inject a None quiz service to simulate `quiz disabled OR no LLM provider`."""
    app.dependency_overrides[deps.get_quiz_service] = lambda: None


def _well_formed_question_payload(stem: str = "What is loss aversion?") -> dict:
    return {
        "stem": stem,
        "concept_label": "loss aversion",
        "citation": {"section_id": 1, "section_title": "Ch 1", "snippet": "Important"},
        "shape": "open",
        "bloom_level": "apply",
    }


# ---- tests: list / lifetime ------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_empty(app, client: AsyncClient):
    await _seed_book(app, book_id=1)
    r = await client.get("/api/v1/books/1/quiz-sessions")
    assert r.status_code == 200
    body = r.json()
    assert body["sessions"] == []
    assert body["lifetime_tally"]["total_questions"] == 0
    assert body["lifetime_tally"]["session_count"] == 0


@pytest.mark.asyncio
async def test_list_sessions_404_book_not_found(app, client: AsyncClient):
    r = await client.get("/api/v1/books/999/quiz-sessions")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_lifetime_tally_includes_themes_summary(app, client: AsyncClient):
    await _seed_book(app, book_id=1)
    factory = app.state.session_factory
    async with factory() as session:
        from app.db.models import QuizDedupState

        session.add(
            QuizDedupState(
                book_id=1,
                themes_summary="Prospect theory dominates.",
                last_rollup_question_count=51,
            )
        )
        await session.commit()
    r = await client.get("/api/v1/books/1/quiz-sessions/lifetime-tally")
    assert r.status_code == 200
    assert r.json()["themes_summary"] == "Prospect theory dominates."


# ---- tests: start_session error paths --------------------------------------


@pytest.mark.asyncio
async def test_start_session_400_invalid_scope_mode(app, client: AsyncClient, fake_llm):
    """Pydantic validation rejects bogus scope.mode → 422 from FastAPI before the
    service-layer 400 ever runs. This is fine — both communicate "client error"."""
    fake_llm.set([])
    await _seed_book(app, book_id=1)
    r = await client.post(
        "/api/v1/books/1/quiz-sessions",
        json={"scope": {"mode": "bogus"}},
    )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_next_question_502_on_persistent_schema_failure(app, client: AsyncClient, fake_llm):
    """LLM emits invalid JSON twice → QuizGenerationError → 502."""
    # Script 2 responses both missing required schema fields — service does
    # one retry, then raises after the second failure.
    fake_llm.set([{"foo": "bar"}, {"foo": "bar"}])
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    r = await client.post(f"/api/v1/quiz-sessions/{sid}/next-question")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_start_session_503_no_llm(app, client: AsyncClient):
    _override_no_llm(app)
    try:
        await _seed_book(app, book_id=1)
        r = await client.post(
            "/api/v1/books/1/quiz-sessions",
            json={"scope": {"mode": "all_summaries"}},
        )
        assert r.status_code == 503
    finally:
        app.dependency_overrides.pop(deps.get_quiz_service, None)


@pytest.mark.asyncio
async def test_start_session_201_with_fake_provider(app, client: AsyncClient, fake_llm):
    """Happy path: FakeLLM returns a valid question → 201 with session + question."""
    await _seed_book(app, book_id=1)
    await _seed_summary_for_section(app, book_id=1, section_id=101)
    fake_llm.set([_well_formed_question_payload()])
    r = await client.post(
        "/api/v1/books/1/quiz-sessions",
        json={"scope": {"mode": "all_summaries"}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["session"]["status"] == "in_progress"
    assert body["first_question"]["stem"] == "What is loss aversion?"
    # S9: agent_verdict must NOT be in the response.
    assert "agent_verdict" not in body["first_question"]


@pytest.mark.asyncio
async def test_start_session_422_budget_exceeded(app, client: AsyncClient, fake_llm):
    """specific_chapters with an over-budget content blob → 422.

    Force this with a tiny budget via a custom Settings override so we don't
    have to seed 60k tokens of content.
    """
    fake_llm.set([])
    await _seed_book(app, book_id=1)
    await _seed_summary_for_section(app, book_id=1, section_id=101)

    settings = Settings()
    settings.quiz.specific_chapters_token_budget = 1

    async def _override(db, settings_=settings):
        return QuizService(session=db, llm=FakeLLMProvider([]), settings=settings_)

    from fastapi import Depends

    async def _route_dep(db=Depends(deps.get_db)):  # noqa: B008
        return await _override(db)

    app.dependency_overrides[deps.get_quiz_service] = _route_dep
    try:
        r = await client.post(
            "/api/v1/books/1/quiz-sessions",
            json={"scope": {"mode": "specific_chapters", "section_ids": [101]}},
        )
        assert r.status_code == 422, r.text
    finally:
        app.dependency_overrides.pop(deps.get_quiz_service, None)


# ---- tests: self_assessment race-safe --------------------------------------


@pytest.mark.asyncio
async def test_self_assessment_201_then_409(app, client: AsyncClient):
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    qid = await _seed_question(app, book_id=1, session_id=sid)
    # First PATCH lands.
    r1 = await client.patch(
        f"/api/v1/quiz-sessions/{sid}/questions/{qid}",
        json={"self_assessment": "got_it"},
    )
    assert r1.status_code == 200
    # Second PATCH on the same question → 409.
    r2 = await client.patch(
        f"/api/v1/quiz-sessions/{sid}/questions/{qid}",
        json={"self_assessment": "partial"},
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_self_assessment_404_unknown_question(app, client: AsyncClient):
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    r = await client.patch(
        f"/api/v1/quiz-sessions/{sid}/questions/9999",
        json={"self_assessment": "got_it"},
    )
    assert r.status_code == 404


# ---- tests: skip / explain / override / discard ----------------------------


@pytest.mark.asyncio
async def test_skip_increments_per_stem(app, client: AsyncClient, fake_llm):
    fake_llm.set([])  # skip path doesn't hit LLM
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    qid = await _seed_question(app, book_id=1, session_id=sid, stem="STEM A")
    qid2 = await _seed_question(app, book_id=1, session_id=sid, stem="STEM A")
    qid_other = await _seed_question(app, book_id=1, session_id=sid, stem="STEM B")
    r = await client.post(
        f"/api/v1/quiz-sessions/{sid}/questions/{qid}/skip",
    )
    assert r.status_code == 200
    # Both STEM A rows should have skip_count == 1; STEM B unchanged.
    factory = app.state.session_factory
    async with factory() as session:
        from app.db.models import QuizQuestion

        rows = (
            (
                await session.execute(
                    # noqa
                    __import__("sqlalchemy")
                    .select(QuizQuestion)
                    .where(QuizQuestion.id.in_([qid, qid2, qid_other]))
                )
            )
            .scalars()
            .all()
        )
        by_id = {q.id: q for q in rows}
        assert by_id[qid].skip_count == 1
        assert by_id[qid2].skip_count == 1
        assert by_id[qid_other].skip_count == 0


@pytest.mark.asyncio
async def test_explain_appends_history(app, client: AsyncClient, fake_llm):
    fake_llm.set([{"explanation": "Because it clarifies X."}])
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    qid = await _seed_question(app, book_id=1, session_id=sid)
    r = await client.post(
        f"/api/v1/quiz-sessions/{sid}/questions/{qid}/explain",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["explanation"] == "Because it clarifies X."
    assert body["question"]["explain_history"] == ["Because it clarifies X."]


@pytest.mark.asyncio
async def test_explain_409_soft_cap(app, client: AsyncClient, fake_llm):
    fake_llm.set([])  # no LLM call expected because the cap blocks first
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    qid = await _seed_question(
        app,
        book_id=1,
        session_id=sid,
        explain_history_json=json.dumps(["e1", "e2"]),
    )
    r = await client.post(
        f"/api/v1/quiz-sessions/{sid}/questions/{qid}/explain",
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_override_400_too_long(app, client: AsyncClient, fake_llm):
    fake_llm.set([])
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    qid = await _seed_question(app, book_id=1, session_id=sid)
    r = await client.post(
        f"/api/v1/quiz-sessions/{sid}/questions/{qid}/override",
        json={"note": "x" * 501},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_override_200_stores_note(app, client: AsyncClient, fake_llm):
    fake_llm.set([])
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    qid = await _seed_question(app, book_id=1, session_id=sid)
    r = await client.post(
        f"/api/v1/quiz-sessions/{sid}/questions/{qid}/override",
        json={"note": "Actually, the book says Y."},
    )
    assert r.status_code == 200
    assert r.json()["override_note"] == "Actually, the book says Y."


# ---- tests: stop session ---------------------------------------------------


@pytest.mark.asyncio
async def test_stop_session_flips_status(app, client: AsyncClient):
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    r = await client.post(f"/api/v1/quiz-sessions/{sid}/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
