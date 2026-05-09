"""Unit tests for quiz schema additions: ProcessingStep extension + 3 ORM models + Book.pre_drafted_q1_id."""

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Book,
    BookStatus,
    ProcessingStep,
    QuizDedupState,
    QuizQuestion,
    QuizSession,
)


def test_processing_step_includes_quiz_values():
    assert ProcessingStep.QUIZ_PREGEN_Q1.value == "quiz_pregen_q1"
    assert ProcessingStep.QUIZ_ROLLUP.value == "quiz_rollup"


@pytest_asyncio.fixture
async def book_factory(db_session):
    """Create persisted Book rows on demand."""
    counter = {"i": 0}

    async def _make(**overrides):
        counter["i"] += 1
        defaults = dict(
            title=f"Book {counter['i']}",
            file_data=b"data",
            file_hash=f"hash-{counter['i']}",
            file_format="epub",
            file_size_bytes=1,
            status=BookStatus.PARSED,
        )
        defaults.update(overrides)
        book = Book(**defaults)
        db_session.add(book)
        await db_session.flush()
        return book

    return _make


@pytest.mark.asyncio
async def test_quiz_session_round_trip(db_session, book_factory):
    book = await book_factory()
    qs = QuizSession(book_id=book.id, scope_mode="all_summaries", status="in_progress")
    db_session.add(qs)
    await db_session.commit()
    assert qs.id is not None
    assert qs.created_at is not None
    assert qs.updated_at is not None


@pytest.mark.asyncio
async def test_quiz_session_scope_mode_check_rejects_bad_value(db_session, book_factory):
    book = await book_factory()
    qs = QuizSession(book_id=book.id, scope_mode="invalid_mode", status="in_progress")
    db_session.add(qs)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_quiz_question_shape_check_mcq_requires_options(db_session, book_factory):
    book = await book_factory()
    qq = QuizQuestion(
        session_id=None,
        book_id=book.id,
        shape="mcq",
        bloom_level="apply",
        stem="?",
        concept_label="x",
        citation_json="{}",
        mcq_options_json=None,  # MISSING — should fail CHECK
    )
    db_session.add(qq)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_quiz_question_open_round_trip_with_create_bloom(db_session, book_factory):
    book = await book_factory()
    qq = QuizQuestion(
        session_id=None,
        book_id=book.id,
        shape="open",
        bloom_level="create",
        stem="?",
        concept_label="x",
        citation_json="{}",
    )
    db_session.add(qq)
    await db_session.commit()
    assert qq.id is not None
    assert qq.bloom_level == "create"
    # Defaults
    assert qq.skip_count == 0
    assert qq.discarded is False
    assert qq.warm_up is False
    assert qq.is_pregen is False
    assert qq.is_stale is False
    assert qq.explain_history_json == "[]"


@pytest.mark.asyncio
async def test_quiz_question_spot_error_requires_intended_error(db_session, book_factory):
    book = await book_factory()
    qq = QuizQuestion(
        session_id=None,
        book_id=book.id,
        shape="spot_error",
        bloom_level="analyze",
        stem="?",
        concept_label="x",
        citation_json="{}",
        intended_error=None,  # MISSING — should fail CHECK
        error_explanation=None,
    )
    db_session.add(qq)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_quiz_dedup_state_round_trip(db_session, book_factory):
    book = await book_factory()
    state = QuizDedupState(book_id=book.id)
    db_session.add(state)
    await db_session.commit()
    assert state.book_id == book.id
    assert state.themes_summary is None
    assert state.last_rollup_question_count == 0


@pytest.mark.asyncio
async def test_book_pre_drafted_q1_id_nullable_default(db_session, book_factory):
    book = await book_factory()
    assert book.pre_drafted_q1_id is None
