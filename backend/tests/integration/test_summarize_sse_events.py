"""FR-28, FR-28a, FR-28b: summarizer callbacks emit section_id + new events.

These tests verify callback signatures (the wire that feeds SSE events in
processing.py). Exercising the full SSE loop would require a live LLM
provider; these tests isolate the contract that processing.py relies on.
"""

import pytest
import pytest_asyncio

from app.db.models import Book, BookSection, BookStatus
from app.services.summarizer.summarizer_service import SummarizerService

_FACETS = {
    "style": "bullet_points",
    "audience": "practitioner",
    "compression": "standard",
    "content_focus": "key_concepts",
}


class _Response:
    def __init__(self, content: str):
        self.content = content
        self.input_tokens = 10
        self.output_tokens = 10


class StubLLM:
    def __init__(self):
        self.call_count = 0

    async def generate(self, prompt, model=None, **kw):
        self.call_count += 1
        return _Response("stub summary bullet point. " * 10)


@pytest_asyncio.fixture
async def two_chapter_book(db_session):
    import uuid

    book = Book(
        title="T",
        file_data=b"x",
        file_hash=f"h-{uuid.uuid4()}",
        file_format="epub",
        file_size_bytes=1,
        status=BookStatus.PARSED,
    )
    db_session.add(book)
    await db_session.flush()
    ids: list[int] = []
    for i in range(2):
        s = BookSection(
            book_id=book.id,
            title=f"Chapter {i + 1}",
            order_index=i,
            depth=1,
            section_type="chapter",
            content_md=("Section content " * 200),
        )
        db_session.add(s)
        await db_session.flush()
        ids.append(s.id)
    await db_session.commit()
    return book.id, ids


@pytest.mark.asyncio
async def test_callbacks_receive_section_id_as_first_positional(
    db_session, test_settings, two_chapter_book
):
    book_id, section_ids = two_chapter_book
    started: list[tuple] = []
    completed: list[tuple] = []

    def on_start(section_id, index, total, title):
        started.append((section_id, index, total, title))

    def on_complete(section_id, index, total, title, elapsed=None, comp=None):
        completed.append((section_id, index, total, title))

    service = SummarizerService(db_session, StubLLM(), test_settings)
    result = await service.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        on_section_start=on_start,
        on_section_complete=on_complete,
    )
    assert result["completed"] == 2
    # Each section fires exactly one started + one completed event
    assert [s[0] for s in started] == section_ids
    assert [c[0] for c in completed] == section_ids
    # Index/total/title plumbing still works
    assert started[0][1] == 1 and started[0][2] == 2
    assert completed[1][1] == 2 and completed[1][2] == 2


@pytest.mark.asyncio
async def test_on_section_start_fires_before_complete(
    db_session, test_settings, two_chapter_book
):
    book_id, _ = two_chapter_book
    order: list[str] = []

    def on_start(*args):
        order.append("start")

    def on_complete(*args, **kw):
        order.append("complete")

    service = SummarizerService(db_session, StubLLM(), test_settings)
    await service.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        on_section_start=on_start,
        on_section_complete=on_complete,
    )
    # First event must be a start, then a complete, then the next start…
    assert order == ["start", "complete", "start", "complete"]


@pytest.mark.asyncio
async def test_on_section_skip_includes_section_id(
    db_session, test_settings, two_chapter_book
):
    book_id, section_ids = two_chapter_book
    # Summarize first to populate, second run will trigger skip
    svc = SummarizerService(db_session, StubLLM(), test_settings)
    await svc.summarize_book(book_id=book_id, facets=_FACETS, skip_eval=True)

    skips: list[tuple] = []

    def on_skip(section_id, index, total, title, reason):
        skips.append((section_id, title, reason))

    svc2 = SummarizerService(db_session, StubLLM(), test_settings)
    await svc2.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        on_section_skip=on_skip,
    )
    assert [s[0] for s in skips] == section_ids
