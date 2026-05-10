"""FR-01: 502 mapping for SubprocessNonZeroExitError on quiz routes.

Uses dependency_overrides on `get_quiz_service` to inject a stub raising
SubprocessNonZeroExitError; verifies the route returns 502 with
{detail, llm_stderr_tail} payload shape.
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.api import deps
from app.api.main import create_app
from app.config import Settings
from app.db.models import Base
from app.db.session import create_session_factory
from app.exceptions import SubprocessNonZeroExitError


# ---- fixtures (kept self-contained to avoid cross-suite coupling) ----------


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "quiz502.db"
    os.environ["BOOKCOMPANION_DATA__DIRECTORY"] = str(tmp_path)
    os.environ["BOOKCOMPANION_DATABASE__URL"] = f"sqlite+aiosqlite:///{db_path}"
    from app.services import settings_service as ss

    monkeypatch.setattr(ss, "DEFAULT_CONFIG_PATH", tmp_path / "settings.yaml")
    monkeypatch.setattr(ss, "default_user_settings_path", lambda: tmp_path / "settings.yaml")

    application = create_app()
    settings = Settings()
    application.state.settings = settings
    application.state.session_factory = create_session_factory(settings)

    import asyncio

    async def _init_schema():
        eng = create_async_engine(settings.database.url, connect_args={"check_same_thread": False})
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                        chunk_text, content=search_index, content_rowid=id,
                        tokenize='porter unicode61'
                    )
                    """
                )
            )
        await eng.dispose()

    asyncio.run(_init_schema())
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_book(app, *, book_id: int = 1) -> None:
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (:id, 'B', x'00', :hash, 'epub', 1, 'COMPLETED')
                """
            ),
            {"id": book_id, "hash": f"h{book_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                "section_type, content_md) VALUES (:sid, :bid, 'Ch1', 0, 0, 'chapter', 'c')"
            ),
            {"sid": book_id * 100 + 1, "bid": book_id},
        )
        await session.commit()


async def _seed_session(app, *, book_id: int) -> int:
    factory = app.state.session_factory
    async with factory() as session:
        from app.db.models import QuizSession

        qs = QuizSession(book_id=book_id, scope_mode="all_summaries", status="in_progress")
        session.add(qs)
        await session.flush()
        sid = qs.id
        await session.commit()
    return sid


async def _seed_question(app, *, book_id: int, session_id: int) -> int:
    import json as _json

    factory = app.state.session_factory
    async with factory() as session:
        from app.db.models import QuizQuestion

        q = QuizQuestion(
            book_id=book_id,
            session_id=session_id,
            shape="open",
            bloom_level="apply",
            stem="Q?",
            concept_label="x",
            citation_json=_json.dumps(
                {"section_id": 101, "section_title": "Ch", "snippet": "..."}
            ),
            explain_history_json="[]",
        )
        session.add(q)
        await session.flush()
        qid = q.id
        await session.commit()
    return qid


# ---- T1: start_session ------------------------------------------------------


class _StubQuizStart:
    async def start_session(self, **_):
        raise SubprocessNonZeroExitError(
            returncode=1, stderr_truncated="boom-tail", stderr_full="boom-tail"
        )


@pytest.mark.asyncio
async def test_start_session_502_on_subprocess_nonzero(app, client):
    await _seed_book(app, book_id=1)
    app.dependency_overrides[deps.get_quiz_service] = lambda: _StubQuizStart()
    try:
        r = await client.post(
            "/api/v1/books/1/quiz-sessions",
            json={"scope": {"mode": "all_summaries"}},
        )
        assert r.status_code == 502, r.text
        body = r.json()
        assert body["detail"]["detail"].startswith("LLM provider error: ")
        assert body["detail"]["llm_stderr_tail"] == "boom-tail"
    finally:
        app.dependency_overrides.pop(deps.get_quiz_service, None)


# ---- T2: next_question -----------------------------------------------------


class _StubQuizNext:
    async def generate_question(self, **_):
        raise SubprocessNonZeroExitError(
            returncode=1, stderr_truncated="next-tail", stderr_full="next-tail"
        )


@pytest.mark.asyncio
async def test_next_question_502(app, client):
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    app.dependency_overrides[deps.get_quiz_service] = lambda: _StubQuizNext()
    try:
        r = await client.post(f"/api/v1/quiz-sessions/{sid}/next-question")
        assert r.status_code == 502, r.text
        body = r.json()
        assert body["detail"]["detail"].startswith("LLM provider error: ")
        assert body["detail"]["llm_stderr_tail"] == "next-tail"
    finally:
        app.dependency_overrides.pop(deps.get_quiz_service, None)


# ---- T3: explain_question --------------------------------------------------


class _StubQuizExplain:
    async def explain_question(self, **_):
        raise SubprocessNonZeroExitError(
            returncode=1, stderr_truncated="explain-tail", stderr_full="explain-tail"
        )


@pytest.mark.asyncio
async def test_explain_question_502(app, client):
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    qid = await _seed_question(app, book_id=1, session_id=sid)
    app.dependency_overrides[deps.get_quiz_service] = lambda: _StubQuizExplain()
    try:
        r = await client.post(
            f"/api/v1/quiz-sessions/{sid}/questions/{qid}/explain"
        )
        assert r.status_code == 502, r.text
        body = r.json()
        assert body["detail"]["detail"].startswith("LLM provider error: ")
        assert body["detail"]["llm_stderr_tail"] == "explain-tail"
    finally:
        app.dependency_overrides.pop(deps.get_quiz_service, None)
