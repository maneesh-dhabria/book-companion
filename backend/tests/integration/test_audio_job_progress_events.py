"""B3+B4: last_event_at stamping, monotonicity, progress shape, already-stale event."""

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
            BookSection(book_id=book.id, title=f"S{i}", content_md="x", order_index=i)
            for i in range(2)
        ]
        session.add_all(sections)
        await session.flush()
        job = ProcessingJob(
            book_id=book.id,
            step=ProcessingStep.AUDIO,
            status=ProcessingJobStatus.RUNNING,
            request_params={"voice": "af_sarah"},
        )
        session.add(job)
        await session.commit()
        repo = AudioFileRepository(session, tmp_path)
        provider = FakeTTSProvider()
        service = AudioGenService(
            session=session, audio_repo=repo, tts_provider=provider, data_dir=tmp_path
        )
        yield service, session, job, sections, repo


@pytest.mark.asyncio
async def test_every_event_has_last_event_at(setup):
    service, _, job, sections, _ = setup
    events = []

    async def collect(name, data):
        events.append((name, data))

    units = [
        (ContentType.SECTION_SUMMARY, s.id, "Body text here. Two sentences.")
        for s in sections
    ]
    await service.run_job(job=job, units=units, voice="af_sarah", on_event=collect)
    for name, data in events:
        assert "last_event_at" in data, f"{name} missing last_event_at"
        assert isinstance(data["last_event_at"], int)


@pytest.mark.asyncio
async def test_last_event_at_monotonic(setup):
    service, _, job, sections, _ = setup
    events = []

    async def collect(name, data):
        events.append((name, data))

    units = [
        (ContentType.SECTION_SUMMARY, s.id, "Hi there. More.")
        for s in sections
    ]
    await service.run_job(job=job, units=units, voice="af_sarah", on_event=collect)
    timestamps = [d["last_event_at"] for _, d in events]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_progress_dict_shape(setup):
    service, _, job, sections, _ = setup
    events = []

    async def collect(name, data):
        events.append((name, data))

    units = [
        (ContentType.SECTION_SUMMARY, s.id, "Hello. World.")
        for s in sections
    ]
    await service.run_job(job=job, units=units, voice="af_sarah", on_event=collect)
    assert set(job.progress.keys()) >= {
        "completed",
        "total",
        "current_kind",
        "current_ref",
        "last_event_at",
        "already_stale",
    }
    assert job.progress["completed"] == 2
    assert job.progress["total"] == 2


@pytest.mark.asyncio
async def test_already_stale_event_when_source_changed(setup):
    service, session, job, sections, repo = setup
    # First gen with original source
    await service.generate_unit(
        book_id=job.book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=sections[0].id,
        voice="af_sarah",
        source_md="Original content here.",
        job_id=None,
    )

    events = []

    async def collect(name, data):
        events.append((name, data))

    # Now run job with edited source for the same unit
    units = [
        (ContentType.SECTION_SUMMARY, sections[0].id, "Edited content now."),
    ]
    await service.run_job(job=job, units=units, voice="af_sarah", on_event=collect)

    stale_events = [e for e in events if e[0] == "section_audio_already_stale"]
    assert len(stale_events) == 1
    assert stale_events[0][1]["section_id"] == sections[0].id
    assert job.progress["already_stale"] == 1
