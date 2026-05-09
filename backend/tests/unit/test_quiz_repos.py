"""Unit tests for quiz repositories."""

import pytest
import pytest_asyncio

from app.db.models import (
    Book,
    BookStatus,
    QuizDedupState,
    QuizQuestion,
    QuizSession,
)
from app.db.repositories.quiz_dedup_state_repo import QuizDedupStateRepository
from app.db.repositories.quiz_question_repo import QuizQuestionRepository
from app.db.repositories.quiz_session_repo import QuizSessionRepository


@pytest_asyncio.fixture
async def book_factory(db_session):
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
        b = Book(**defaults)
        db_session.add(b)
        await db_session.flush()
        return b

    return _make


@pytest_asyncio.fixture
async def question_factory(db_session):
    async def _make(**overrides):
        defaults = dict(
            shape="open",
            bloom_level="apply",
            stem="?",
            concept_label="x",
            citation_json="{}",
        )
        defaults.update(overrides)
        q = QuizQuestion(**defaults)
        db_session.add(q)
        await db_session.flush()
        return q

    return _make


# ---- QuizSessionRepository ---------------------------------------------------


@pytest.mark.asyncio
async def test_session_create_and_get_by_id(db_session, book_factory):
    book = await book_factory()
    repo = QuizSessionRepository(db_session)
    qs = await repo.create(
        book_id=book.id, scope_mode="all_summaries", scope_section_ids=None, theme=None
    )
    assert qs.id is not None
    fetched = await repo.get_by_id(qs.id)
    assert fetched is not None
    assert fetched.book_id == book.id
    # selectinload on questions
    assert fetched.questions == []


@pytest.mark.asyncio
async def test_session_list_by_book_orders_desc(db_session, book_factory):
    book = await book_factory()
    repo = QuizSessionRepository(db_session)
    s1 = await repo.create(book_id=book.id, scope_mode="all_summaries")
    s2 = await repo.create(book_id=book.id, scope_mode="all_summaries")
    sessions = await repo.list_by_book(book.id)
    assert [s.id for s in sessions] == [s2.id, s1.id]


@pytest.mark.asyncio
async def test_session_get_in_progress_for_book(db_session, book_factory):
    book = await book_factory()
    repo = QuizSessionRepository(db_session)
    s = await repo.create(book_id=book.id, scope_mode="all_summaries")
    found = await repo.get_in_progress_for_book(book.id)
    assert found is not None and found.id == s.id
    await repo.update_status(s.id, "completed", ended_at=None)
    assert await repo.get_in_progress_for_book(book.id) is None


# ---- QuizQuestionRepository --------------------------------------------------


@pytest.mark.asyncio
async def test_question_recent_stems_filters_stale_discarded_skipped(
    db_session, book_factory, question_factory
):
    book = await book_factory()
    await question_factory(book_id=book.id, stem="ok")
    await question_factory(book_id=book.id, stem="stale", is_stale=True)
    await question_factory(book_id=book.id, stem="discarded", discarded=True)
    await question_factory(book_id=book.id, stem="skipped", skip_count=3)
    await question_factory(book_id=book.id, stem="warmup_unanswered", warm_up=True)
    await question_factory(
        book_id=book.id,
        stem="warmup_answered",
        warm_up=True,
        self_assessment="got_it",
    )
    repo = QuizQuestionRepository(db_session)
    stems = await repo.recent_stems(book.id, limit=50)
    assert set(stems) == {"ok", "warmup_answered"}


@pytest.mark.asyncio
async def test_increment_skip_for_stem_updates_all_matching_rows(
    db_session, book_factory, question_factory
):
    book = await book_factory()
    q1 = await question_factory(book_id=book.id, stem="What is X?")
    q2 = await question_factory(book_id=book.id, stem="What is X?")
    q3 = await question_factory(book_id=book.id, stem="What is Y?")
    repo = QuizQuestionRepository(db_session)
    n = await repo.increment_skip_for_stem(book.id, "What is X?")
    assert n == 2
    await db_session.refresh(q1)
    await db_session.refresh(q2)
    await db_session.refresh(q3)
    assert q1.skip_count == 1
    assert q2.skip_count == 1
    assert q3.skip_count == 0


@pytest.mark.asyncio
async def test_concepts_with_skip_threshold(db_session, book_factory, question_factory):
    book = await book_factory()
    await question_factory(book_id=book.id, concept_label="alpha", skip_count=3)
    await question_factory(book_id=book.id, concept_label="alpha", skip_count=3)
    await question_factory(book_id=book.id, concept_label="beta", skip_count=2)
    repo = QuizQuestionRepository(db_session)
    concepts = await repo.concepts_with_skip_threshold(book.id, threshold=3)
    assert "alpha" in concepts
    assert "beta" not in concepts


@pytest.mark.asyncio
async def test_mark_stale_for_book(db_session, book_factory, question_factory):
    book = await book_factory()
    q1 = await question_factory(book_id=book.id, stem="a")
    q2 = await question_factory(book_id=book.id, stem="b")
    repo = QuizQuestionRepository(db_session)
    n = await repo.mark_stale_for_book(book.id)
    assert n == 2
    await db_session.refresh(q1)
    await db_session.refresh(q2)
    assert q1.is_stale is True
    assert q2.is_stale is True


@pytest.mark.asyncio
async def test_discard_sets_flag(db_session, book_factory, question_factory):
    book = await book_factory()
    q = await question_factory(book_id=book.id)
    repo = QuizQuestionRepository(db_session)
    await repo.discard(q.id)
    await db_session.refresh(q)
    assert q.discarded is True


@pytest.mark.asyncio
async def test_discarded_stems_for_session(db_session, book_factory, question_factory):
    book = await book_factory()
    sess = QuizSession(book_id=book.id, scope_mode="all_summaries", status="in_progress")
    db_session.add(sess)
    await db_session.flush()
    await question_factory(book_id=book.id, session_id=sess.id, stem="kept")
    await question_factory(
        book_id=book.id, session_id=sess.id, stem="dropped", discarded=True
    )
    repo = QuizQuestionRepository(db_session)
    stems = await repo.discarded_stems_for_session(sess.id)
    assert stems == ["dropped"]


# ---- QuizDedupStateRepository -----------------------------------------------


@pytest.mark.asyncio
async def test_dedup_state_upsert_and_reset(db_session, book_factory):
    book = await book_factory()
    repo = QuizDedupStateRepository(db_session)
    assert await repo.get(book.id) is None
    state = await repo.upsert(
        book_id=book.id, themes_summary="prose", last_rollup_question_count=42
    )
    assert state.themes_summary == "prose"
    assert state.last_rollup_question_count == 42
    # upsert updates existing
    state2 = await repo.upsert(
        book_id=book.id, themes_summary="prose-v2", last_rollup_question_count=80
    )
    assert state2.book_id == state.book_id
    assert state2.themes_summary == "prose-v2"
    # reset
    await repo.reset(book.id)
    refreshed = await repo.get(book.id)
    assert refreshed.themes_summary is None
    assert refreshed.last_rollup_question_count == 0
