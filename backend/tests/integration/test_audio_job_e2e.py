"""Audio job end-to-end via AudioGenService.run_job (no HTTP layer)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    Base,
    Book,
    BookSection,
    BookStatus,
    ContentType,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
)
from app.db.repositories.audio_file_repo import AudioFileRepository
from app.services.audio_gen_service import AudioGenService
from tests.integration.test_audio_gen_service import FakeTTSProvider


@pytest_asyncio.fixture
async def setup(tmp_path, monkeypatch):
    db = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db}")
    eng = create_async_engine(f"sqlite+aiosqlite:///{db}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(eng, expire_on_commit=False)

    async with sm() as session:
        book = Book(
            title="B",
            file_data=b"\x00",
            file_hash="h",
            file_format="epub",
            file_size_bytes=1,
            status=BookStatus.COMPLETED,
        )
        session.add(book)
        await session.flush()
        sections = [
            BookSection(
                book_id=book.id,
                title=f"S{i}",
                content_md="x",
                order_index=i,
            )
            for i in range(3)
        ]
        session.add_all(sections)
        await session.flush()
        job = ProcessingJob(
            book_id=book.id,
            step=ProcessingStep.AUDIO,
            status=ProcessingJobStatus.RUNNING,
            request_params={"voice": "af_sarah", "engine": "kokoro"},
        )
        session.add(job)
        await session.commit()
        repo = AudioFileRepository(session, tmp_path)
        provider = FakeTTSProvider()
        service = AudioGenService(
            session=session,
            audio_repo=repo,
            tts_provider=provider,
            data_dir=tmp_path,
        )
        yield service, session, job, sections, repo


@pytest.mark.asyncio
async def test_run_job_completes_with_per_unit_events(setup):
    service, session, job, sections, repo = setup
    events: list[tuple[str, dict]] = []

    async def collect(name, data):
        events.append((name, data))

    units = [
        (ContentType.SECTION_SUMMARY, s.id, f"Section {s.title} body. Here.")
        for s in sections
    ]
    await service.run_job(job=job, units=units, voice="af_sarah", on_event=collect)

    kinds = [e[0] for e in events]
    assert kinds.count("section_audio_started") == 3
    assert kinds.count("section_audio_completed") == 3
    assert kinds[0] == "processing_started"
    assert kinds[-1] == "processing_completed"
    assert job.status == ProcessingJobStatus.COMPLETED
    assert job.progress["completed"] == 3
    rows = await repo.list_by_book(job.book_id)
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_run_job_per_unit_failure_continues(setup):
    service, session, job, sections, repo = setup
    events: list[tuple[str, dict]] = []

    async def collect(name, data):
        events.append((name, data))

    units = [
        (ContentType.SECTION_SUMMARY, sections[0].id, "First sentence valid here."),
        # Empty md → EmptySanitizedTextError
        (ContentType.SECTION_SUMMARY, sections[1].id, "```\n```"),
        (ContentType.SECTION_SUMMARY, sections[2].id, "Third one valid."),
    ]
    await service.run_job(job=job, units=units, voice="af_sarah", on_event=collect)

    failed = [e for e in events if e[0] == "section_audio_failed"]
    assert len(failed) == 1
    assert failed[0][1]["reason"] == "empty_after_sanitize"
    assert job.status == ProcessingJobStatus.COMPLETED
    rows = await repo.list_by_book(job.book_id)
    assert len(rows) == 2
