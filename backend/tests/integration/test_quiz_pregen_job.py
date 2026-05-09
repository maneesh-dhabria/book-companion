"""T17 — QUIZ_PREGEN_Q1 worker handler tests (FR-80, FR-81, FR-83, S3).

Drives the worker through `worker.tick()` deterministically. We monkeypatch
`detect_llm_provider` + `create_llm_provider` in the handler's import path so
the worker uses our `FakeLLMProvider` instead of dispatching to a real CLI.
"""

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.models import (
    Base,
    Book,
    BookSection,
    BookStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
    QuizQuestion,
    Summary,
    SummaryContentType,
)
from app.services.job_queue_worker import JobQueueWorker
from tests.unit.conftest import FakeLLMProvider


@pytest.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / "pregen_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def book_with_summary(session_factory):
    async with session_factory() as session:
        b = Book(
            title="t",
            file_data=b"",
            file_hash="h-pregen",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.PARSED,
        )
        session.add(b)
        await session.flush()
        sec = BookSection(
            book_id=b.id,
            title="Ch1",
            order_index=0,
            depth=0,
            section_type="chapter",
            content_md="The chapter content.",
        )
        session.add(sec)
        await session.flush()
        s = Summary(
            book_id=b.id,
            content_type=SummaryContentType.SECTION,
            content_id=sec.id,
            facets_used={},
            prompt_text_sent="p",
            model_used="fake",
            input_char_count=10,
            summary_char_count=12,
            summary_md="Summary text",
        )
        session.add(s)
        await session.flush()
        sec.default_summary_id = s.id
        await session.commit()
        return b.id


@pytest.fixture
def event_bus():
    bus = AsyncMock()
    bus.publish = AsyncMock()
    bus.close = AsyncMock()
    return bus


def _patch_provider(monkeypatch, provider):
    """Make worker `_run_quiz_pregen_q1` resolve to the given provider."""
    import app.services.summarizer as _sum

    monkeypatch.setattr(_sum, "detect_llm_provider", lambda: "fake")
    monkeypatch.setattr(_sum, "create_llm_provider", lambda *a, **k: provider)


async def _enqueue(session_factory, *, book_id: int, step=ProcessingStep.QUIZ_PREGEN_Q1) -> int:
    async with session_factory() as session:
        j = ProcessingJob(book_id=book_id, step=step, status=ProcessingJobStatus.PENDING)
        session.add(j)
        await session.commit()
        return j.id


def _well_formed_question() -> dict:
    return {
        "stem": "What is loss aversion?",
        "concept_label": "loss aversion",
        "citation": {"section_id": 1, "section_title": "Ch 1", "snippet": "..."},
        "shape": "open",
        "bloom_level": "apply",
    }


# ---- tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_pregen_handler_populates_slot(
    session_factory, book_with_summary, event_bus, monkeypatch
):
    fake = FakeLLMProvider([_well_formed_question()])
    _patch_provider(monkeypatch, fake)
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    await _enqueue(session_factory, book_id=book_with_summary)
    promoted = await worker.tick()
    assert promoted is True
    async with session_factory() as session:
        b = await session.get(Book, book_with_summary)
        assert b.pre_drafted_q1_id is not None
        q = await session.get(QuizQuestion, b.pre_drafted_q1_id)
        assert q is not None
        assert q.is_pregen is True
        assert q.session_id is None
        # The job row is now COMPLETED.
        row = (
            await session.execute(
                select(ProcessingJob).where(ProcessingJob.book_id == book_with_summary)
            )
        ).scalar_one()
        assert row.status == ProcessingJobStatus.COMPLETED


@pytest.mark.asyncio
async def test_pregen_handler_noops_when_slot_populated(
    session_factory, book_with_summary, event_bus, monkeypatch
):
    """FR-81a: a second pregen job is a noop when the slot already holds a
    non-stale question. The FakeLLMProvider is given NO scripted responses so
    any LLM call would raise — the test passing proves no call was made."""
    fake = FakeLLMProvider([])
    _patch_provider(monkeypatch, fake)
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    # Pre-populate the slot.
    async with session_factory() as session:
        existing_q = QuizQuestion(
            book_id=book_with_summary,
            session_id=None,
            shape="open",
            bloom_level="apply",
            stem="pre-existing",
            concept_label="x",
            citation_json=json.dumps({"section_id": 1, "section_title": "Ch", "snippet": "..."}),
            is_pregen=True,
        )
        session.add(existing_q)
        await session.flush()
        b = await session.get(Book, book_with_summary)
        b.pre_drafted_q1_id = existing_q.id
        await session.commit()
        existing_qid = existing_q.id

    await _enqueue(session_factory, book_id=book_with_summary)
    await worker.tick()
    async with session_factory() as session:
        b = await session.get(Book, book_with_summary)
        assert b.pre_drafted_q1_id == existing_qid  # unchanged
        row = (
            await session.execute(
                select(ProcessingJob).where(ProcessingJob.book_id == book_with_summary)
            )
        ).scalar_one()
        assert row.status == ProcessingJobStatus.COMPLETED
    assert fake.calls == []  # FR-81a — no LLM call


@pytest.mark.asyncio
async def test_pregen_handler_graceful_degrade_no_llm(
    session_factory, book_with_summary, event_bus, monkeypatch
):
    """FR-83: when no LLM provider exists, the handler marks the job
    COMPLETED and leaves the slot empty (graceful degrade)."""
    import app.services.summarizer as _sum

    monkeypatch.setattr(_sum, "detect_llm_provider", lambda: None)
    monkeypatch.setattr(_sum, "create_llm_provider", lambda *a, **k: None)
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    await _enqueue(session_factory, book_id=book_with_summary)
    await worker.tick()
    async with session_factory() as session:
        b = await session.get(Book, book_with_summary)
        assert b.pre_drafted_q1_id is None
        row = (
            await session.execute(
                select(ProcessingJob).where(ProcessingJob.book_id == book_with_summary)
            )
        ).scalar_one()
        assert row.status == ProcessingJobStatus.COMPLETED
        assert row.error_message is None


@pytest.mark.asyncio
async def test_pregen_handler_marks_failed_on_generation_error(
    session_factory, book_with_summary, event_bus, monkeypatch
):
    """LLM emits invalid JSON twice → QuizGenerationError → job FAILED with
    error_message preserved. Slot stays empty."""
    fake = FakeLLMProvider([{"foo": "bar"}, {"foo": "bar"}])
    _patch_provider(monkeypatch, fake)
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    await _enqueue(session_factory, book_id=book_with_summary)
    await worker.tick()
    async with session_factory() as session:
        b = await session.get(Book, book_with_summary)
        assert b.pre_drafted_q1_id is None
        row = (
            await session.execute(
                select(ProcessingJob).where(ProcessingJob.book_id == book_with_summary)
            )
        ).scalar_one()
        assert row.status == ProcessingJobStatus.FAILED
        assert row.error_message


# ---- T19: post-summarize enqueue helper -----------------------------------


@pytest.mark.asyncio
async def test_maybe_enqueue_pregen_q1_when_slot_empty(
    session_factory, book_with_summary, event_bus
):
    """FR-80: slot empty → helper enqueues exactly one PENDING job."""
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    async with session_factory() as session:
        added = await worker._maybe_enqueue_pregen_q1(session, book_with_summary)
        await session.commit()
    assert added is True
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(ProcessingJob).where(
                        ProcessingJob.book_id == book_with_summary,
                        ProcessingJob.step == ProcessingStep.QUIZ_PREGEN_Q1,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(list(rows)) == 1


@pytest.mark.asyncio
async def test_maybe_enqueue_pregen_q1_skips_when_slot_populated(
    session_factory, book_with_summary, event_bus
):
    """FR-80 idempotency: slot populated by non-stale question → no enqueue."""
    async with session_factory() as session:
        existing = QuizQuestion(
            book_id=book_with_summary,
            session_id=None,
            shape="open",
            bloom_level="apply",
            stem="x",
            concept_label="x",
            citation_json=json.dumps({"section_id": 1, "section_title": "Ch", "snippet": "..."}),
            is_pregen=True,
        )
        session.add(existing)
        await session.flush()
        b = await session.get(Book, book_with_summary)
        b.pre_drafted_q1_id = existing.id
        await session.commit()
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    async with session_factory() as session:
        added = await worker._maybe_enqueue_pregen_q1(session, book_with_summary)
        await session.commit()
    assert added is False


@pytest.mark.asyncio
async def test_maybe_enqueue_pregen_q1_when_slot_stale(
    session_factory, book_with_summary, event_bus
):
    """FR-80 + FR-82: slot points at a stale question → re-enqueue."""
    async with session_factory() as session:
        stale_q = QuizQuestion(
            book_id=book_with_summary,
            session_id=None,
            shape="open",
            bloom_level="apply",
            stem="x",
            concept_label="x",
            citation_json=json.dumps({"section_id": 1, "section_title": "Ch", "snippet": "..."}),
            is_pregen=True,
            is_stale=True,
        )
        session.add(stale_q)
        await session.flush()
        b = await session.get(Book, book_with_summary)
        b.pre_drafted_q1_id = stale_q.id
        await session.commit()
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    async with session_factory() as session:
        added = await worker._maybe_enqueue_pregen_q1(session, book_with_summary)
        await session.commit()
    assert added is True


@pytest.mark.asyncio
async def test_maybe_enqueue_pregen_q1_swallows_integrity_when_active_exists(
    session_factory, book_with_summary, event_bus
):
    """When a PENDING pregen job already exists for the book, the partial
    UNIQUE INDEX rejects the new INSERT. Helper returns False, no crash."""
    async with session_factory() as session:
        session.add(
            ProcessingJob(
                book_id=book_with_summary,
                step=ProcessingStep.QUIZ_PREGEN_Q1,
                status=ProcessingJobStatus.PENDING,
            )
        )
        await session.commit()
    worker = JobQueueWorker(
        session_factory=session_factory, event_bus=event_bus, settings=Settings()
    )
    async with session_factory() as session:
        added = await worker._maybe_enqueue_pregen_q1(session, book_with_summary)
        await session.commit()
    assert added is False
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(ProcessingJob).where(
                        ProcessingJob.book_id == book_with_summary,
                        ProcessingJob.step == ProcessingStep.QUIZ_PREGEN_Q1,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(list(rows)) == 1  # only the pre-existing one
