"""T21 — structured logging + outcome metrics (NFR-10, NFR-10a)."""

import pytest
import structlog
from structlog.testing import capture_logs

from app.config import Settings
from app.services.quiz.quiz_service import QuizService
from tests.unit.conftest import FakeLLMProvider


@pytest.fixture
def configured_structlog():
    """Pin a known structlog config so capture_logs() works regardless of the
    process-wide config installed by pytest plugins."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )
    yield


def _well_formed_question_payload() -> dict:
    return {
        "stem": "What is loss aversion?",
        "concept_label": "loss aversion",
        "citation": {"section_id": 1, "section_title": "Ch 1", "snippet": "..."},
        "shape": "open",
        "bloom_level": "apply",
    }


@pytest.mark.asyncio
async def test_generate_emits_started_and_completed(db_session, book_factory, configured_structlog):
    """NFR-10: every LLM invocation emits .started and .completed events
    with latency_ms."""
    book = await book_factory()
    fake = FakeLLMProvider([_well_formed_question_payload()])
    svc = QuizService(db_session, fake, Settings())
    with capture_logs() as logs:
        await svc.generate_question(
            book_id=book.id,
            session_id=None,
            scope_content="some content",
            warm_up=False,
        )
    events = [e["event"] for e in logs]
    assert "quiz.generate.started" in events
    assert "quiz.generate.completed" in events
    completed = next(e for e in logs if e["event"] == "quiz.generate.completed")
    assert "latency_ms" in completed
    assert completed["book_id"] == book.id


@pytest.mark.asyncio
async def test_generate_emits_failed_on_schema_error(
    db_session, book_factory, configured_structlog
):
    """NFR-10: schema-validation failure emits .failed."""
    book = await book_factory()
    # Both attempts emit invalid payloads → after retry, raises QuizGenerationError.
    fake = FakeLLMProvider([{"foo": "bar"}, {"foo": "bar"}])
    svc = QuizService(db_session, fake, Settings())
    with capture_logs() as logs:
        from app.exceptions import QuizGenerationError

        with pytest.raises(QuizGenerationError):
            await svc.generate_question(
                book_id=book.id,
                session_id=None,
                scope_content="x",
                warm_up=False,
            )
    failed = [e for e in logs if e["event"] == "quiz.generate.failed"]
    assert len(failed) == 2  # one per attempt
    assert all("error" in e for e in failed)
