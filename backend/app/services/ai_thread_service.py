"""AI Thread Service — context building, LLM invocation, and DB persistence."""

import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.models import AIMessage, AIThread, Book, BookSection, Summary
from app.services.summarizer.llm_provider import LLMProvider

_TITLE_MAX = 40
_DEFAULT_TITLES = {"", "new thread", "untitled", "new chat"}


def _is_default_thread_title(title: str | None) -> bool:
    """True when ``title`` is a placeholder worth replacing with first-message text."""
    if title is None:
        return True
    t = title.strip().lower()
    return t in _DEFAULT_TITLES


def _derive_thread_title(content: str) -> str:
    """Trim ``content`` to ≤40 chars on a word boundary for the sidebar."""
    text = " ".join(content.strip().split())
    if len(text) <= _TITLE_MAX:
        return text
    cut = text[:_TITLE_MAX]
    last_space = cut.rfind(" ")
    if last_space >= 20:
        cut = cut[:last_space]
    return cut.rstrip() + "…"


class AIThreadService:
    def __init__(self, session: AsyncSession, llm_provider: LLMProvider, settings: Settings):
        self.session = session
        self.llm = llm_provider
        self.settings = settings

    def build_context_prompt(
        self,
        book_title: str,
        book_summary: str | None,
        section_title: str | None,
        section_content: str | None,
        thread_history: list[dict],
        user_message: str,
        selected_text: str | None,
    ) -> str:
        """Build structured prompt with book context for LLM."""
        parts = []
        parts.append(f"# Book: {book_title}")

        if book_summary:
            parts.append(f"\n## Book Summary\n{book_summary}")

        if section_title:
            parts.append(f"\n## Current Section: {section_title}")

        if section_content:
            parts.append(f"\n### Section Content\n{section_content}")

        if selected_text:
            parts.append(f"\n## Selected Passage\n> {selected_text}")

        if thread_history:
            parts.append("\n## Conversation History")
            for msg in thread_history:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                parts.append(f"\n**{role_label}:** {msg['content']}")

        parts.append(f"\n## Current Question\n{user_message}")

        return "\n".join(parts)

    async def _fetch_thread(self, thread_id: int) -> AIThread | None:
        result = await self.session.execute(
            select(AIThread)
            .options(selectinload(AIThread.messages))
            .where(AIThread.id == thread_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_book(self, book_id: int) -> Book | None:
        result = await self.session.execute(
            select(Book).where(Book.id == book_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_section(self, section_id: int) -> BookSection | None:
        result = await self.session.execute(
            select(BookSection).where(BookSection.id == section_id)
        )
        return result.scalar_one_or_none()

    async def send_message(
        self,
        thread_id: int,
        content: str,
        context_section_id: int | None = None,
        selected_text: str | None = None,
    ) -> AIMessage:
        """Send a user message, invoke LLM, and store both messages."""
        thread = await self._fetch_thread(thread_id)
        if not thread:
            raise ValueError(f"Thread {thread_id} not found")

        book = await self._fetch_book(thread.book_id)
        if not book:
            raise ValueError(f"Book {thread.book_id} not found")

        # Fetch section content if specified
        section_title = None
        section_content = None
        if context_section_id:
            section = await self._fetch_section(context_section_id)
            if section:
                section_title = section.title
                section_content = section.content_md

        # Get book summary if available
        book_summary = None
        if book.default_summary_id:
            result = await self.session.execute(
                select(Summary).where(Summary.id == book.default_summary_id)
            )
            summary = result.scalar_one_or_none()
            if summary:
                book_summary = summary.summary_md

        # Build conversation history
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in thread.messages
        ]

        # Build prompt
        prompt = self.build_context_prompt(
            book_title=book.title,
            book_summary=book_summary,
            section_title=section_title,
            section_content=section_content,
            thread_history=history,
            user_message=content,
            selected_text=selected_text,
        )

        # Store user message
        user_msg = AIMessage(
            thread_id=thread_id,
            role="user",
            content=content,
        )
        self.session.add(user_msg)

        # FR-D1.4 — auto-derive thread title from the first user message
        # when the thread still holds a default/placeholder label. Trim on
        # word boundary, cap at 40 characters so sidebar lists stay scannable.
        if len(thread.messages) == 0 and _is_default_thread_title(thread.title):
            thread.title = _derive_thread_title(content)

        # Invoke LLM
        start_time = time.monotonic()
        try:
            response = await self.llm.generate(prompt)
            response_text = response.content
        except Exception:
            response_text = "I'm sorry, I encountered an error processing your request."
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Store assistant message
        assistant_msg = AIMessage(
            thread_id=thread_id,
            role="assistant",
            content=response_text,
        )
        # Attach latency_ms as a transient attribute for callers
        assistant_msg.latency_ms = elapsed_ms
        self.session.add(assistant_msg)

        await self.session.flush()
        await self.session.commit()

        return assistant_msg
