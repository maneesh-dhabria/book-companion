"""Unit-test fixtures: factories + FakeLLMProvider for QuizService tests."""

from __future__ import annotations

import json

import pytest_asyncio

from app.db.models import Book, BookSection, BookStatus
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse


class FakeLLMProvider(LLMProvider):
    """Test double — returns scripted JSON dicts (or raises) per generate() call.

    Pass `responses=[{...dict...}, RuntimeError(...), ...]`. Each call pops the
    head; dicts are JSON-encoded into LLMResponse.content; Exceptions are
    raised. Inspect `.calls` for prompt + json_schema captured per call.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def generate(  # noqa: D401
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        json_schema: dict | None = None,
        timeout: int | None = None,
        context: dict | None = None,
    ) -> LLMResponse:
        self.calls.append({"prompt": prompt, "schema": json_schema})
        if not self._responses:
            raise RuntimeError("FakeLLMProvider exhausted — no scripted response")
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return LLMResponse(content=json.dumps(r), model="fake")

    async def generate_with_image(self, *args, **kwargs):
        raise NotImplementedError("FakeLLMProvider does not support images")


@pytest_asyncio.fixture
async def book_factory(db_session):
    """Persist a Book row with sensible defaults; overrides via kwargs."""
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
async def section_factory(db_session):
    """Persist a BookSection row attached to a given Book."""
    counter = {"i": 0}

    async def _make(*, book, **overrides):
        counter["i"] += 1
        defaults = dict(
            book_id=book.id,
            title=f"Section {counter['i']}",
            order_index=counter["i"],
            content_md="Default section content.",
        )
        defaults.update(overrides)
        s = BookSection(**defaults)
        db_session.add(s)
        await db_session.flush()
        return s

    return _make
