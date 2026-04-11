"""AI Threads API endpoints — CRUD and message sending."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_settings
from app.api.schemas import (
    AIMessageCreateRequest,
    AIMessageResponse,
    AIThreadCreateRequest,
    AIThreadListItem,
    AIThreadResponse,
    AIThreadUpdateRequest,
)
from app.config import Settings
from app.db.models import AIMessage, AIThread, Book

router = APIRouter(tags=["ai-threads"])


@router.get("/api/v1/books/{book_id}/ai-threads", response_model=list[AIThreadListItem])
async def list_threads(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List AI threads for a book, ordered by updated_at DESC."""
    # Verify book exists
    book_result = await db.execute(select(Book).where(Book.id == book_id))
    if not book_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Book not found")

    result = await db.execute(
        select(AIThread)
        .options(selectinload(AIThread.messages))
        .where(AIThread.book_id == book_id)
        .order_by(AIThread.updated_at.desc())
    )
    threads = list(result.scalars().all())

    return [
        AIThreadListItem(
            id=t.id,
            book_id=t.book_id,
            title=t.title,
            message_count=len(t.messages),
            last_message_preview=t.messages[-1].content[:100] if t.messages else None,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in threads
    ]


@router.post(
    "/api/v1/books/{book_id}/ai-threads",
    response_model=AIThreadResponse,
    status_code=201,
)
async def create_thread(
    book_id: int,
    body: AIThreadCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new AI thread for a book."""
    book_result = await db.execute(select(Book).where(Book.id == book_id))
    if not book_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Book not found")

    thread = AIThread(
        book_id=book_id,
        title=body.title,
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)

    return AIThreadResponse(
        id=thread.id,
        book_id=thread.book_id,
        title=thread.title,
        messages=[],
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@router.get("/api/v1/ai-threads/{thread_id}", response_model=AIThreadResponse)
async def get_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a thread with all messages."""
    result = await db.execute(
        select(AIThread)
        .options(selectinload(AIThread.messages))
        .where(AIThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.patch("/api/v1/ai-threads/{thread_id}", response_model=AIThreadResponse)
async def update_thread(
    thread_id: int,
    body: AIThreadUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a thread's title."""
    result = await db.execute(
        select(AIThread)
        .options(selectinload(AIThread.messages))
        .where(AIThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread.title = body.title
    await db.commit()
    await db.refresh(thread)

    # Re-fetch with messages
    result = await db.execute(
        select(AIThread)
        .options(selectinload(AIThread.messages))
        .where(AIThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    return thread


@router.delete("/api/v1/ai-threads/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a thread and all its messages."""
    result = await db.execute(
        select(AIThread).where(AIThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await db.delete(thread)
    await db.commit()


@router.post(
    "/api/v1/ai-threads/{thread_id}/messages",
    response_model=AIMessageResponse,
    status_code=201,
)
async def send_message(
    thread_id: int,
    body: AIMessageCreateRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Send a message in a thread — invokes LLM and returns assistant response."""
    from app.services.ai_thread_service import AIThreadService
    from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider

    llm = ClaudeCodeCLIProvider(
        cli_command=settings.llm.cli_command,
        default_model=settings.llm.model,
        default_timeout=settings.llm.timeout_seconds,
        max_budget_usd=settings.llm.max_budget_usd,
    )
    service = AIThreadService(session=db, llm_provider=llm, settings=settings)

    try:
        assistant_msg = await service.send_message(
            thread_id=thread_id,
            content=body.content,
            context_section_id=body.context_section_id,
            selected_text=body.selected_text,
        )
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    return assistant_msg


@router.get(
    "/api/v1/ai-threads/{thread_id}/messages",
    response_model=list[AIMessageResponse],
)
async def list_messages(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List messages in a thread."""
    result = await db.execute(
        select(AIThread).where(AIThread.id == thread_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Thread not found")

    result = await db.execute(
        select(AIMessage)
        .where(AIMessage.thread_id == thread_id)
        .order_by(AIMessage.created_at.asc())
    )
    return list(result.scalars().all())
