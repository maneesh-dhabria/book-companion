"""Reading state API endpoints — cross-device reading position sync."""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_reading_state_repo
from app.api.schemas import ReadingStateResponse, ReadingStateUpsert, ResumeBannerResponse
from app.db.repositories.audio_position_repo import AudioPositionRepository
from app.db.repositories.reading_state_repo import ReadingStateRepository

router = APIRouter(prefix="/api/v1/reading-state", tags=["reading-state"])


@router.put("")
async def upsert_reading_state(
    body: ReadingStateUpsert,
    user_agent: str = Header(default="Unknown"),
    repo: ReadingStateRepository = Depends(get_reading_state_repo),
    db: AsyncSession = Depends(get_db),
):
    """Save or update reading position for the current device (identified by User-Agent)."""
    rs = await repo.upsert(
        user_agent=user_agent,
        book_id=body.book_id,
        section_id=body.section_id,
        scroll_position=body.scroll_position,
        content_mode=body.content_mode,
    )
    await db.commit()
    return ReadingStateResponse(
        last_book_id=rs.book_id,
        last_section_id=rs.section_id,
        last_viewed_at=rs.updated_at.isoformat() if rs.updated_at else None,
    )


@router.get("/continue")
async def get_continue_reading(
    user_agent: str = Header(default="Unknown"),
    repo: ReadingStateRepository = Depends(get_reading_state_repo),
):
    """Get reading position from a different device for 'Continue where you left off' banner."""
    rs = await repo.get_latest_other_device(user_agent)
    if not rs:
        return ReadingStateResponse()

    book_title = rs.book.title if rs.book else None
    section_title = rs.section.title if rs.section else None

    return ReadingStateResponse(
        last_book_id=rs.book_id,
        last_section_id=rs.section_id,
        last_viewed_at=rs.updated_at.isoformat() if rs.updated_at else None,
        book_title=book_title,
        section_title=section_title,
    )


@router.get("/by-book/{book_id}", response_model=ReadingStateResponse)
async def get_reading_state_by_book(
    book_id: int,
    user_agent: str = Header(default="Unknown"),
    repo: ReadingStateRepository = Depends(get_reading_state_repo),
):
    """Per-device + per-book reading state (FR-C02 helper, P13).

    Always 200; all-null fields when no row exists for this device+book pair.
    """
    rs = await repo.get_for_device_and_book(user_agent, book_id)
    if rs is None:
        return ReadingStateResponse()
    return ReadingStateResponse(
        last_book_id=rs.book_id,
        last_section_id=rs.section_id,
        last_viewed_at=rs.updated_at.isoformat() if rs.updated_at else None,
        section_title=rs.section.title if rs.section else None,
    )


@router.get("/resume-banner", response_model=ResumeBannerResponse)
async def get_resume_banner(
    repo: ReadingStateRepository = Depends(get_reading_state_repo),
    db: AsyncSession = Depends(get_db),
):
    """Most-recent reading + audio positions across ALL browsers (FR-B05, §9.1)."""
    rs = await repo.get_latest_resume_banner_reading()
    audio_repo = AudioPositionRepository(db)
    audio = await audio_repo.get_latest_resume_banner()

    payload = ResumeBannerResponse()
    if rs is not None:
        payload.last_book_id = rs.book_id
        payload.last_section_id = rs.section_id
        payload.last_book_title = rs.book.title if rs.book else None
        payload.last_section_title = rs.section.title if rs.section else None
        payload.last_viewed_at = rs.updated_at.isoformat() if rs.updated_at else None
    if audio is not None:
        payload.last_audio_content_type = audio.content_type
        payload.last_audio_content_id = audio.content_id
        payload.last_audio_book_id = audio.book_id
        payload.last_audio_book_title = audio.book_title
        payload.last_audio_section_title = audio.section_title
        payload.last_audio_at = audio.updated_at.isoformat() if audio.updated_at else None
        payload.last_audio_total_sentences = audio.total_sentences
    return payload
