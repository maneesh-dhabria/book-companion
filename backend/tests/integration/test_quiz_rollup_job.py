"""T18 — QUIZ_ROLLUP worker handler tests (FR-61, FR-62, FR-64, S7, G18, P8)."""

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.models import (
    Base,
    Book,
    BookStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
    QuizDedupState,
    QuizQuestion,
)
from app.services.job_queue_worker import JobQueueWorker
from tests.unit.conftest import FakeLLMProvider


@pytest.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / "rollup_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def book_id(session_factory):
    async with session_factory() as session:
        b = Book(
            title="t",
            file_data=b"",
            file_hash="h-rollup",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.PARSED,
        )
        session.add(b)
        await session.commit()
        return b.id


@pytest.fixture
def event_bus():
    bus = AsyncMock()
    bus.publish = AsyncMock()
    bus.close = AsyncMock()
    return bus


def _patch_provider(monkeypatch, provider):
    import app.services.summarizer as _sum

    monkeypatch.setattr(_sum, "detect_llm_provider", lambda: "fake")
    monkeypatch.setattr(_sum, "create_llm_provider", lambda *a, **k: provider)


async def _seed_questions(
    session_factory,
    *,
    book_id: int,
    count: int,
    is_stale: bool = False,
    discarded: bool = False,
) -> None:
    async with session_factory() as session:
        for i in range(count):
            session.add(
                QuizQuestion(
                    book_id=book_id,
                    session_id=None,
                    shape="open",
                    bloom_level="apply",
                    stem=f"Stem {i}",
                    concept_label=f"c{i}",
                    citation_json=json.dumps(
                        {"section_id": 1, "section_title": "Ch", "snippet": "..."}
                    ),
                    is_stale=is_stale,
                    discarded=discarded,
                )
            )
        await session.commit()


async def _enqueue(session_factory, *, book_id: int) -> int:
    async with session_factory() as session:
        j = ProcessingJob(
            book_id=book_id,
            step=ProcessingStep.QUIZ_ROLLUP,
            status=ProcessingJobStatus.PENDING,
        )
        session.add(j)
        await session.commit()
        return j.id


# ---- tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollup_noops_below_verbatim_cap(session_factory, book_id, event_bus, monkeypatch):
    """FR-61 below threshold: 30 stems < 50 cap → no themes_summary written."""
    fake = FakeLLMProvider([])  # exhausted: any LLM call would fail
    _patch_provider(monkeypatch, fake)
    await _seed_questions(session_factory, book_id=book_id, count=30)
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    await _enqueue(session_factory, book_id=book_id)
    await worker.tick()
    async with session_factory() as session:
        state = await session.get(QuizDedupState, book_id)
        # State may be lazily created with summary still None.
        assert state is None or state.themes_summary is None
    assert fake.calls == []


@pytest.mark.asyncio
async def test_rollup_runs_above_threshold(session_factory, book_id, event_bus, monkeypatch):
    """60 stems > 50 cap AND delta=60-0 >= 10 → LLM called, summary stored."""
    fake = FakeLLMProvider(
        [{"themes_summary": "Prospect theory and decision-making under risk dominate."}]
    )
    _patch_provider(monkeypatch, fake)
    await _seed_questions(session_factory, book_id=book_id, count=60)
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    await _enqueue(session_factory, book_id=book_id)
    await worker.tick()
    async with session_factory() as session:
        state = await session.get(QuizDedupState, book_id)
        assert state is not None
        assert state.themes_summary == "Prospect theory and decision-making under risk dominate."
        assert state.last_rollup_question_count == 60
        assert state.themes_summary_computed_at is not None


@pytest.mark.asyncio
async def test_rollup_delta_gate_skips_re_run(session_factory, book_id, event_bus, monkeypatch):
    """Already rolled up at 60; +5 more (delta < 10) → noop, no LLM call."""
    fake = FakeLLMProvider([])  # any call would fail
    _patch_provider(monkeypatch, fake)
    await _seed_questions(session_factory, book_id=book_id, count=65)
    async with session_factory() as session:
        session.add(
            QuizDedupState(
                book_id=book_id,
                themes_summary="prior summary",
                last_rollup_question_count=60,
            )
        )
        await session.commit()
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    await _enqueue(session_factory, book_id=book_id)
    await worker.tick()
    async with session_factory() as session:
        state = await session.get(QuizDedupState, book_id)
        assert state.themes_summary == "prior summary"  # unchanged
        assert state.last_rollup_question_count == 60  # unchanged
    assert fake.calls == []


@pytest.mark.asyncio
async def test_rollup_excludes_stale_stems_from_count(
    session_factory, book_id, event_bus, monkeypatch
):
    """FR-64: is_stale=1 rows are excluded from the threshold count.
    With 30 stale + 20 fresh, non_stale_count=20 < 50 → noop."""
    fake = FakeLLMProvider([])
    _patch_provider(monkeypatch, fake)
    await _seed_questions(session_factory, book_id=book_id, count=30, is_stale=True)
    await _seed_questions(session_factory, book_id=book_id, count=20)
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    await _enqueue(session_factory, book_id=book_id)
    await worker.tick()
    async with session_factory() as session:
        state = await session.get(QuizDedupState, book_id)
        assert state is None or state.themes_summary is None
    assert fake.calls == []


@pytest.mark.asyncio
async def test_rollup_truncates_to_200_stems_at_oversize(
    session_factory, book_id, event_bus, monkeypatch
):
    """P8: 250 stems → only the first 200 reach the LLM prompt."""
    fake = FakeLLMProvider([{"themes_summary": "ok"}])
    _patch_provider(monkeypatch, fake)
    await _seed_questions(session_factory, book_id=book_id, count=250)
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    await _enqueue(session_factory, book_id=book_id)
    await worker.tick()
    # The handler took the most-recent 200 stems. The newest stems are
    # `Stem 249, Stem 248, ..., Stem 50` — `Stem 49` should be the first
    # truncated one.
    sent_prompt = fake.calls[0]["prompt"]
    assert "Stem 249" in sent_prompt
    assert "Stem 50" in sent_prompt
    assert "Stem 49" not in sent_prompt


@pytest.mark.asyncio
async def test_rollup_graceful_degrade_no_llm(session_factory, book_id, event_bus, monkeypatch):
    """No LLM provider → handler completes, themes_summary stays None."""
    import app.services.summarizer as _sum

    monkeypatch.setattr(_sum, "detect_llm_provider", lambda: None)
    monkeypatch.setattr(_sum, "create_llm_provider", lambda *a, **k: None)
    await _seed_questions(session_factory, book_id=book_id, count=60)
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    await _enqueue(session_factory, book_id=book_id)
    await worker.tick()
    async with session_factory() as session:
        state = await session.get(QuizDedupState, book_id)
        assert state is None or state.themes_summary is None
        row = (
            await session.execute(select(ProcessingJob).where(ProcessingJob.book_id == book_id))
        ).scalar_one()
        assert row.status == ProcessingJobStatus.COMPLETED
