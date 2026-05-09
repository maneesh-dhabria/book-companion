"""T20 — re-import quiz cleanup (FR-64, FR-82, E16).

Verifies that BookService._re_import_book performs the 5-step cleanup atomically:
1. All quiz_questions for the book → is_stale=True (FR-64)
2. quiz_dedup_state reset (themes_summary=None, last_rollup_question_count=0) (FR-64)
3. Open quiz_sessions → status=abandoned (E16)
4. Book.pre_drafted_q1_id → NULL (FR-82)
5. New QUIZ_PREGEN_Q1 job enqueued (FR-82) iff none active
"""

import json

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
    QuizSession,
)
from app.services.book_service import BookService

# A minimal stub epub bytestream — the parser is mocked below so the actual
# parse never runs against this; we only need a .epub-shaped value to thread
# through.
_STUB_EPUB = b"PK\x03\x04stub"


@pytest.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / "reimport_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


class _StubParser:
    """Returns a parsed-book object with a single section so the re-import
    flow has something to work with. The point of these tests is the quiz
    cleanup, not parser fidelity."""

    async def parse(self, file_path):
        from types import SimpleNamespace

        return SimpleNamespace(
            title="Stub",
            authors=[],
            sections=[
                SimpleNamespace(
                    order_index=0,
                    title="Ch1",
                    depth=0,
                    content_md="Updated content.",
                    section_type="chapter",
                    images=[],
                )
            ],
        )


@pytest.fixture
def patched_book_service(session_factory, monkeypatch, tmp_path):
    """BookService whose parser + image-substitution + audio-orphan paths
    are stubbed so the test exercises ONLY the quiz-cleanup block."""

    async def _make(session):
        # data dir override
        s = Settings()
        s.data.directory = str(tmp_path)
        svc = BookService(db=session, config=s)

        monkeypatch.setattr(BookService, "_get_parser", lambda self, fmt: _StubParser())

        async def _noop_substitute(self, book_id):
            return None

        monkeypatch.setattr(BookService, "_substitute_image_urls", _noop_substitute)

        # Patch out audio-orphan deletion (it expects a real file system tree)
        from app.db.repositories import audio_file_repo

        async def _zero_orphans(self, book_id, surviving):
            return 0

        monkeypatch.setattr(audio_file_repo.AudioFileRepository, "delete_orphans", _zero_orphans)
        # Skip structure detection signature
        from app.services.parser.structure_detector import StructureDetector

        monkeypatch.setattr(
            StructureDetector,
            "validate_structure",
            lambda self, sections: sections,
        )
        return svc

    return _make


async def _seed_book_with_quiz_history(session_factory) -> int:
    async with session_factory() as session:
        b = Book(
            title="t",
            file_data=b"old",
            file_hash="hh",
            file_format="epub",
            file_size_bytes=3,
            status=BookStatus.PARSED,
        )
        session.add(b)
        await session.flush()
        # Two quiz_questions
        for i in range(2):
            session.add(
                QuizQuestion(
                    book_id=b.id,
                    session_id=None,
                    shape="open",
                    bloom_level="apply",
                    stem=f"Old stem {i}",
                    concept_label=f"c{i}",
                    citation_json=json.dumps(
                        {"section_id": 1, "section_title": "Ch", "snippet": "..."}
                    ),
                )
            )
        # Dedup state with summary
        session.add(
            QuizDedupState(
                book_id=b.id,
                themes_summary="Old themes summary",
                last_rollup_question_count=60,
            )
        )
        # In-progress session
        session.add(QuizSession(book_id=b.id, scope_mode="all_summaries", status="in_progress"))
        await session.commit()
        return b.id


@pytest.mark.asyncio
async def test_reimport_quiz_cleanup_runs_all_five_steps(
    session_factory, patched_book_service, tmp_path
):
    book_id = await _seed_book_with_quiz_history(session_factory)
    # Seed a pre-drafted Q1
    async with session_factory() as session:
        b = await session.get(Book, book_id)
        pregen = QuizQuestion(
            book_id=book_id,
            session_id=None,
            shape="open",
            bloom_level="apply",
            stem="pregen",
            concept_label="pq",
            citation_json=json.dumps({"section_id": 1, "section_title": "Ch", "snippet": "..."}),
            is_pregen=True,
        )
        session.add(pregen)
        await session.flush()
        b.pre_drafted_q1_id = pregen.id
        # Add an old section so re-import has something to update in-place
        from app.db.models import BookSection

        sec = BookSection(
            book_id=book_id,
            title="Old Ch1",
            order_index=0,
            depth=0,
            section_type="chapter",
            content_md="Old content.",
        )
        session.add(sec)
        await session.commit()

    fake_path = tmp_path / "fake.epub"
    fake_path.write_bytes(_STUB_EPUB)

    async with session_factory() as session:
        svc = await patched_book_service(session)
        b = await session.get(Book, book_id)
        await svc._re_import_book(b, _STUB_EPUB, fake_path, "epub")

    # Verify all 5 steps.
    async with session_factory() as session:
        # 1. All questions stale.
        qs = (
            (await session.execute(select(QuizQuestion).where(QuizQuestion.book_id == book_id)))
            .scalars()
            .all()
        )
        assert all(q.is_stale for q in qs)
        # 2. Dedup state reset.
        state = await session.get(QuizDedupState, book_id)
        assert state is not None
        assert state.themes_summary is None
        assert state.last_rollup_question_count == 0
        assert state.themes_summary_computed_at is None
        # 3. In-progress session abandoned.
        sessions = (
            (await session.execute(select(QuizSession).where(QuizSession.book_id == book_id)))
            .scalars()
            .all()
        )
        assert all(s.status != "in_progress" for s in sessions)
        assert any(s.status == "abandoned" for s in sessions)
        # 4. pre_drafted_q1_id cleared.
        b = await session.get(Book, book_id)
        assert b.pre_drafted_q1_id is None
        # 5. Fresh pregen job enqueued.
        jobs = (
            (
                await session.execute(
                    select(ProcessingJob).where(
                        ProcessingJob.book_id == book_id,
                        ProcessingJob.step == ProcessingStep.QUIZ_PREGEN_Q1,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(list(jobs)) >= 1
        assert any(j.status == ProcessingJobStatus.PENDING for j in jobs)


@pytest.mark.asyncio
async def test_reimport_skips_pregen_enqueue_when_one_already_active(
    session_factory, patched_book_service, tmp_path
):
    """The partial UNIQUE INDEX would reject a second PENDING pregen for the
    same book; we pre-check to avoid rolling back the whole re-import."""
    book_id = await _seed_book_with_quiz_history(session_factory)
    async with session_factory() as session:
        # Pre-existing pregen job
        session.add(
            ProcessingJob(
                book_id=book_id,
                step=ProcessingStep.QUIZ_PREGEN_Q1,
                status=ProcessingJobStatus.PENDING,
            )
        )
        # Add an old section so re-import has something to do
        from app.db.models import BookSection

        session.add(
            BookSection(
                book_id=book_id,
                title="Old Ch1",
                order_index=0,
                depth=0,
                section_type="chapter",
                content_md="Old.",
            )
        )
        await session.commit()
    fake_path = tmp_path / "fake.epub"
    fake_path.write_bytes(_STUB_EPUB)
    async with session_factory() as session:
        svc = await patched_book_service(session)
        b = await session.get(Book, book_id)
        await svc._re_import_book(b, _STUB_EPUB, fake_path, "epub")
    async with session_factory() as session:
        jobs = (
            (
                await session.execute(
                    select(ProcessingJob).where(
                        ProcessingJob.book_id == book_id,
                        ProcessingJob.step == ProcessingStep.QUIZ_PREGEN_Q1,
                    )
                )
            )
            .scalars()
            .all()
        )
        # Still exactly one pregen job (the pre-existing one).
        assert len(list(jobs)) == 1
        # The cleanup steps still ran:
        b = await session.get(Book, book_id)
        assert b.pre_drafted_q1_id is None
