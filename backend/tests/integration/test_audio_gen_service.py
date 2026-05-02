"""Integration tests for AudioGenService — generate_unit + lookup stale detection."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base, Book, BookSection, BookStatus, ContentType
from app.db.repositories.audio_file_repo import AudioFileRepository
from app.services.audio_gen_service import AudioGenService
from app.services.tts.markdown_to_speech import sanitize
from app.services.tts.provider import (
    EmptySanitizedTextError,
    SynthesisResult,
    TTSProvider,
    VoiceInfo,
)


class FakeTTSProvider(TTSProvider):
    name = "fake"

    def __init__(self, mp3: bytes = b"ID3\x04\x00\x00\x00\x00\x00\x00fake"):
        self.mp3 = mp3
        self.calls: list = []

    def synthesize(self, text, voice, speed=1.0):  # noqa: D401
        return SynthesisResult(self.mp3, 24000, [0.0], duration_seconds=1.0)

    def synthesize_segmented(self, sentences, voice, speed=1.0):
        self.calls.append((tuple(sentences), voice, speed))
        offsets = [float(i) for i in range(len(sentences))]
        return SynthesisResult(
            audio_bytes=self.mp3,
            sample_rate=24000,
            sentence_offsets=offsets,
            duration_seconds=float(len(sentences)),
        )

    def list_voices(self):
        return [VoiceInfo(name="af_sarah", language="en")]


@pytest_asyncio.fixture
async def session_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(eng, expire_on_commit=False)
    return sm, tmp_path


@pytest_asyncio.fixture
async def svc(session_factory):
    sm, tmp_path = session_factory
    async with sm() as session:
        book = Book(
            title="Test Book",
            file_data=b"\x00",
            file_hash="h1",
            file_format="epub",
            file_size_bytes=1,
            status=BookStatus.COMPLETED,
        )
        session.add(book)
        await session.flush()
        section = BookSection(
            book_id=book.id, title="Ch1", content_md="x", order_index=0
        )
        session.add(section)
        await session.commit()
        repo = AudioFileRepository(session, tmp_path)
        provider = FakeTTSProvider()
        service = AudioGenService(
            session=session,
            audio_repo=repo,
            tts_provider=provider,
            data_dir=tmp_path,
        )
        yield service, session, tmp_path, provider, book.id, section.id


@pytest.mark.asyncio
async def test_generate_unit_creates_audio_file_row_and_writes_mp3(svc):
    service, session, tmp_path, provider, book_id, section_id = svc
    af = await service.generate_unit(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=section_id,
        voice="af_sarah",
        source_md="Hello world. Second sentence.",
        job_id=None,
    )
    mp3 = (tmp_path / af.file_path).read_bytes()
    assert mp3.startswith(b"ID3")
    assert af.sentence_count == 2
    sanitized = sanitize("Hello world. Second sentence.")
    expected_hash = hashlib.sha256(sanitized.text.encode()).hexdigest()
    assert af.source_hash == expected_hash
    assert af.sanitizer_version == "1.0"
    assert af.engine == "fake"


@pytest.mark.asyncio
async def test_generate_unit_skips_on_empty_sanitizer(svc):
    service, *_ = svc
    with pytest.raises(EmptySanitizedTextError):
        await service.generate_unit(
            book_id=1,
            content_type=ContentType.SECTION_SUMMARY,
            content_id=42,
            voice="af_sarah",
            source_md="```\n```",
            job_id=None,
        )


@pytest.mark.asyncio
async def test_lookup_returns_stale_on_source_change(svc):
    service, session, tmp_path, provider, book_id, section_id = svc
    await service.generate_unit(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=section_id,
        voice="af_sarah",
        source_md="Original text here.",
        job_id=None,
    )
    result = await service.lookup(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=section_id,
        voice="af_sarah",
        current_source_md="Edited text now.",
    )
    assert result.pregenerated is True
    assert result.stale is True
    assert result.stale_reason == "source_changed"


@pytest.mark.asyncio
async def test_lookup_returns_stale_on_sanitizer_version_bump(svc, monkeypatch):
    service, session, tmp_path, provider, book_id, section_id = svc
    await service.generate_unit(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=section_id,
        voice="af_sarah",
        source_md="X is here.",
        job_id=None,
    )
    monkeypatch.setattr(
        "app.services.audio_gen_service.SANITIZER_VERSION", "1.1"
    )
    result = await service.lookup(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=section_id,
        voice="af_sarah",
        current_source_md="X is here.",
    )
    assert result.stale is True
    assert result.stale_reason == "sanitizer_upgraded"


@pytest.mark.asyncio
async def test_lookup_fresh_when_unchanged(svc):
    service, session, tmp_path, provider, book_id, section_id = svc
    await service.generate_unit(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=section_id,
        voice="af_sarah",
        source_md="Same content. Two sentences.",
        job_id=None,
    )
    result = await service.lookup(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=section_id,
        voice="af_sarah",
        current_source_md="Same content. Two sentences.",
    )
    assert result.pregenerated is True
    assert result.stale is False
    assert result.stale_reason is None
    assert result.url is not None and result.url.endswith(".mp3")
    assert result.duration_seconds is not None
