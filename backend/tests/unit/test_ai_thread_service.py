"""Tests for AIThreadService — context building and message sending."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_thread_service import AIThreadService
from app.services.summarizer.llm_provider import LLMResponse


class TestBuildContextPrompt:
    def setup_method(self):
        self.svc = AIThreadService.__new__(AIThreadService)

    def test_build_context_prompt_includes_book_title_and_user_message(self):
        result = self.svc.build_context_prompt(
            book_title="Thinking, Fast and Slow",
            book_summary=None,
            section_title=None,
            section_content=None,
            thread_history=[],
            user_message="What is System 1?",
            selected_text=None,
        )
        assert "# Book: Thinking, Fast and Slow" in result
        assert "What is System 1?" in result

    def test_build_context_prompt_with_selected_text(self):
        result = self.svc.build_context_prompt(
            book_title="Test Book",
            book_summary=None,
            section_title=None,
            section_content=None,
            thread_history=[],
            user_message="Explain this",
            selected_text="The anchoring effect biases judgment.",
        )
        assert "## Selected Passage" in result
        assert "> The anchoring effect biases judgment." in result

    def test_build_context_prompt_includes_all_required_sections(self):
        result = self.svc.build_context_prompt(
            book_title="Deep Work",
            book_summary="A book about focused work.",
            section_title="Chapter 1",
            section_content="Content of chapter 1.",
            thread_history=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ],
            user_message="Tell me more",
            selected_text="Focus is key.",
        )
        assert "# Book: Deep Work" in result
        assert "## Book Summary" in result
        assert "A book about focused work." in result
        assert "## Current Section: Chapter 1" in result
        assert "### Section Content" in result
        assert "Content of chapter 1." in result
        assert "## Selected Passage" in result
        assert "> Focus is key." in result
        assert "## Conversation History" in result
        assert "**User:** Hello" in result
        assert "**Assistant:** Hi there" in result
        assert "## Current Question" in result
        assert "Tell me more" in result

    def test_build_context_prompt_selected_text_appears_before_user_message(self):
        result = self.svc.build_context_prompt(
            book_title="Test",
            book_summary=None,
            section_title=None,
            section_content=None,
            thread_history=[],
            user_message="Explain this passage",
            selected_text="Important passage here",
        )
        selected_pos = result.index("## Selected Passage")
        question_pos = result.index("## Current Question")
        assert selected_pos < question_pos

    def test_build_context_prompt_empty_history_produces_no_history_block(self):
        result = self.svc.build_context_prompt(
            book_title="Test",
            book_summary=None,
            section_title=None,
            section_content=None,
            thread_history=[],
            user_message="First question",
            selected_text=None,
        )
        assert "## Conversation History" not in result

    def test_build_context_prompt_omits_none_sections(self):
        """When book_summary, section_title, section_content, and selected_text are None,
        their sections should not appear."""
        result = self.svc.build_context_prompt(
            book_title="Minimal",
            book_summary=None,
            section_title=None,
            section_content=None,
            thread_history=[],
            user_message="Hi",
            selected_text=None,
        )
        assert "## Book Summary" not in result
        assert "## Current Section" not in result
        assert "### Section Content" not in result
        assert "## Selected Passage" not in result


class TestSendMessage:
    def _make_service(self):
        session = AsyncMock()
        llm = AsyncMock()
        settings = MagicMock()
        svc = AIThreadService(session=session, llm_provider=llm, settings=settings)
        return svc, session, llm

    def _make_thread(self, book_id=1, messages=None):
        thread = MagicMock()
        thread.id = 10
        thread.book_id = book_id
        thread.messages = messages or []
        return thread

    def _make_book(self, title="Test Book", default_summary_id=None):
        book = MagicMock()
        book.title = title
        book.default_summary_id = default_summary_id
        return book

    @pytest.mark.asyncio
    async def test_send_message_stores_both_user_and_assistant_messages(self):
        svc, session, llm = self._make_service()
        thread = self._make_thread()
        book = self._make_book()

        svc._fetch_thread = AsyncMock(return_value=thread)
        svc._fetch_book = AsyncMock(return_value=book)
        svc._fetch_section = AsyncMock(return_value=None)

        llm.generate = AsyncMock(
            return_value=LLMResponse(content="LLM says hello", model="test-model")
        )

        result = await svc.send_message(thread_id=10, content="Hello")

        # Should have added two messages (user + assistant)
        assert session.add.call_count == 2
        user_msg = session.add.call_args_list[0][0][0]
        assistant_msg = session.add.call_args_list[1][0][0]

        assert user_msg.role == "user"
        assert user_msg.content == "Hello"
        assert assistant_msg.role == "assistant"
        assert assistant_msg.content == "LLM says hello"

        # Should have flushed and committed
        session.flush.assert_awaited_once()
        session.commit.assert_awaited_once()

        # Return value is the assistant message
        assert result is assistant_msg

    @pytest.mark.asyncio
    async def test_send_message_records_latency(self):
        svc, session, llm = self._make_service()
        thread = self._make_thread()
        book = self._make_book()

        svc._fetch_thread = AsyncMock(return_value=thread)
        svc._fetch_book = AsyncMock(return_value=book)

        llm.generate = AsyncMock(return_value=LLMResponse(content="Response", model="test-model"))

        result = await svc.send_message(thread_id=10, content="Question")

        # latency_ms should be set as a transient attribute (>= 0)
        assert hasattr(result, "latency_ms")
        assert isinstance(result.latency_ms, int)
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_send_message_thread_not_found_raises(self):
        svc, session, llm = self._make_service()
        svc._fetch_thread = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Thread 99 not found"):
            await svc.send_message(thread_id=99, content="Hello")

    @pytest.mark.asyncio
    async def test_send_message_book_not_found_raises(self):
        svc, session, llm = self._make_service()
        thread = self._make_thread(book_id=42)
        svc._fetch_thread = AsyncMock(return_value=thread)
        svc._fetch_book = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Book 42 not found"):
            await svc.send_message(thread_id=10, content="Hello")

    @pytest.mark.asyncio
    async def test_send_message_llm_error_returns_error_message(self):
        svc, session, llm = self._make_service()
        thread = self._make_thread()
        book = self._make_book()

        svc._fetch_thread = AsyncMock(return_value=thread)
        svc._fetch_book = AsyncMock(return_value=book)

        llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))

        result = await svc.send_message(thread_id=10, content="Hello")

        assert result.content == "I'm sorry, I encountered an error processing your request."
        # Should still commit (error is gracefully handled)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_with_section_context(self):
        svc, session, llm = self._make_service()
        thread = self._make_thread()
        book = self._make_book()

        section = MagicMock()
        section.title = "Chapter 3"
        section.content_md = "Chapter 3 content here."

        svc._fetch_thread = AsyncMock(return_value=thread)
        svc._fetch_book = AsyncMock(return_value=book)
        svc._fetch_section = AsyncMock(return_value=section)

        llm.generate = AsyncMock(
            return_value=LLMResponse(content="About chapter 3", model="test-model")
        )

        with patch.object(svc, "build_context_prompt", wraps=svc.build_context_prompt) as spy:
            await svc.send_message(thread_id=10, content="Tell me about this", context_section_id=3)
            spy.assert_called_once()
            call_kwargs = spy.call_args
            assert call_kwargs.kwargs["section_title"] == "Chapter 3"
            assert call_kwargs.kwargs["section_content"] == "Chapter 3 content here."

    @pytest.mark.asyncio
    async def test_send_message_passes_history_to_prompt(self):
        svc, session, llm = self._make_service()

        existing_msg1 = MagicMock()
        existing_msg1.role = "user"
        existing_msg1.content = "Previous question"
        existing_msg2 = MagicMock()
        existing_msg2.role = "assistant"
        existing_msg2.content = "Previous answer"

        thread = self._make_thread(messages=[existing_msg1, existing_msg2])
        book = self._make_book()

        svc._fetch_thread = AsyncMock(return_value=thread)
        svc._fetch_book = AsyncMock(return_value=book)

        llm.generate = AsyncMock(
            return_value=LLMResponse(content="Follow-up answer", model="test-model")
        )

        with patch.object(svc, "build_context_prompt", wraps=svc.build_context_prompt) as spy:
            await svc.send_message(thread_id=10, content="Follow-up")
            call_kwargs = spy.call_args
            history = call_kwargs.kwargs["thread_history"]
            assert len(history) == 2
            assert history[0] == {"role": "user", "content": "Previous question"}
            assert history[1] == {"role": "assistant", "content": "Previous answer"}
