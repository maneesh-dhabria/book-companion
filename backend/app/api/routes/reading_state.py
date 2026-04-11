"""Reading state API endpoints — cross-device reading position sync."""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_reading_state_repo
from app.api.schemas import ReadingStateResponse, ReadingStateUpsert
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
