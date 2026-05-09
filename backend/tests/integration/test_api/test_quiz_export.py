"""T34 — Quiz session export integration tests.

Covers:
- ExportService.export_quiz_session (Markdown render path)
- Image-URL sanitization in citation snippets / feedback.actual
- Abandoned-session refusal
- CLI subcommand `export quiz-session <id> -o file.md`
- GET /api/v1/quiz-sessions/{sid}/export?fmt=markdown route
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient


# ---- helpers ---------------------------------------------------------------


async def _seed_book_for_export(app, *, book_id: int = 1, title: str = "Art of War") -> None:
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (:id, :title, x'00', :hash, 'epub', 1, 'COMPLETED')
                """
            ),
            {"id": book_id, "title": title, "hash": f"h{book_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                "section_type, content_md) VALUES (:sid, :bid, 'Ch1', 0, 0, 'chapter', 'c')"
            ),
            {"sid": book_id * 100 + 1, "bid": book_id},
        )
        await session.commit()


async def _seed_session(
    app,
    *,
    book_id: int,
    status: str = "completed",
    scope_mode: str = "all_summaries",
) -> int:
    factory = app.state.session_factory
    async with factory() as session:
        from app.db.models import QuizSession

        qs = QuizSession(book_id=book_id, scope_mode=scope_mode, status=status)
        session.add(qs)
        await session.flush()
        sid = qs.id
        await session.commit()
    return sid


async def _seed_question(
    app,
    *,
    book_id: int,
    session_id: int,
    stem: str,
    user_answer: str | None = None,
    feedback_actual: str | None = None,
    self_assessment: str | None = None,
    citation_snippet: str = "An important snippet.",
) -> int:
    factory = app.state.session_factory
    async with factory() as session:
        from app.db.models import QuizQuestion

        feedback_json = None
        if feedback_actual is not None:
            feedback_json = json.dumps(
                {
                    "correct": "the correct point",
                    "missing": "the missing nuance",
                    "actual": feedback_actual,
                    "agent_verdict": "partial",
                }
            )
        q = QuizQuestion(
            book_id=book_id,
            session_id=session_id,
            shape="open",
            bloom_level="apply",
            stem=stem,
            concept_label="x",
            citation_json=json.dumps(
                {
                    "section_id": book_id * 100 + 1,
                    "section_title": "Ch1",
                    "snippet": citation_snippet,
                }
            ),
            user_answer=user_answer,
            feedback_json=feedback_json,
            self_assessment=self_assessment,
        )
        session.add(q)
        await session.flush()
        qid = q.id
        await session.commit()
    return qid


# ---- service-layer tests ---------------------------------------------------


@pytest.mark.asyncio
async def test_export_quiz_session_markdown_includes_each_turn(app):
    await _seed_book_for_export(app, book_id=1)
    sid = await _seed_session(app, book_id=1, status="completed")
    await _seed_question(
        app,
        book_id=1,
        session_id=sid,
        stem="What is loss aversion?",
        user_answer="Feeling losses ~2x more than gains.",
        feedback_actual="Per Ch 1, this is correct; the canonical 2x figure dates to Kahneman.",
        self_assessment="got_it",
    )
    await _seed_question(
        app,
        book_id=1,
        session_id=sid,
        stem="Define anchoring.",
        user_answer="Latching on to the first number you see.",
        feedback_actual="Reasonable definition.",
        self_assessment="partial",
    )

    factory = app.state.session_factory
    async with factory() as session:
        from app.services.export_service import ExportService

        svc = ExportService(session=session)
        md = await svc.export_quiz_session(session_id=sid, fmt="markdown")

    assert "Quiz Session" in md
    assert "What is loss aversion?" in md
    assert "Define anchoring." in md
    assert "Per Ch 1" in md
    assert "Reasonable definition." in md
    assert "got_it" in md
    assert "partial" in md


@pytest.mark.asyncio
async def test_export_quiz_session_sanitizes_image_urls(app):
    await _seed_book_for_export(app, book_id=2)
    sid = await _seed_session(app, book_id=2, status="completed")
    await _seed_question(
        app,
        book_id=2,
        session_id=sid,
        stem="Image-bearing question.",
        user_answer="An answer.",
        feedback_actual=(
            "See ![diagram](/api/v1/images/42) — that's the chart you wanted."
        ),
        self_assessment="got_it",
        citation_snippet=(
            'Inline <img src="/api/v1/images/99" alt="cover"> art reference.'
        ),
    )

    factory = app.state.session_factory
    async with factory() as session:
        from app.services.export_service import ExportService

        svc = ExportService(session=session)
        md = await svc.export_quiz_session(session_id=sid, fmt="markdown")

    assert "/api/v1/images/" not in md
    assert "image://" not in md
    # Sanitized placeholder survives.
    assert "[Image:" in md or "[Image]" in md


@pytest.mark.asyncio
async def test_export_quiz_session_abandoned_raises(app):
    await _seed_book_for_export(app, book_id=3)
    sid = await _seed_session(app, book_id=3, status="abandoned")

    factory = app.state.session_factory
    async with factory() as session:
        from app.services.export_service import ExportService, QuizExportError

        svc = ExportService(session=session)
        with pytest.raises(QuizExportError):
            await svc.export_quiz_session(session_id=sid, fmt="markdown")


@pytest.mark.asyncio
async def test_export_quiz_session_unknown_session_raises(app):
    factory = app.state.session_factory
    async with factory() as session:
        from app.services.export_service import ExportError, ExportService

        svc = ExportService(session=session)
        with pytest.raises(ExportError):
            await svc.export_quiz_session(session_id=99999, fmt="markdown")


# ---- route tests -----------------------------------------------------------


@pytest.mark.asyncio
async def test_route_export_returns_markdown(app, client: AsyncClient):
    await _seed_book_for_export(app, book_id=4)
    sid = await _seed_session(app, book_id=4, status="completed")
    await _seed_question(
        app,
        book_id=4,
        session_id=sid,
        stem="Q1?",
        user_answer="A1",
        feedback_actual="OK.",
        self_assessment="got_it",
    )
    r = await client.get(f"/api/v1/quiz-sessions/{sid}/export?fmt=markdown")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    assert "Q1?" in r.text
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert f"_quiz_session_{sid}.md" in cd


@pytest.mark.asyncio
async def test_route_export_404_for_abandoned(app, client: AsyncClient):
    await _seed_book_for_export(app, book_id=5)
    sid = await _seed_session(app, book_id=5, status="abandoned")
    r = await client.get(f"/api/v1/quiz-sessions/{sid}/export?fmt=markdown")
    assert r.status_code == 404
    assert "abandoned" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_route_export_404_for_unknown_session(client: AsyncClient):
    r = await client.get("/api/v1/quiz-sessions/99999/export?fmt=markdown")
    assert r.status_code == 404


# ---- CLI test --------------------------------------------------------------


def test_cli_export_quiz_session_writes_file(tmp_path, monkeypatch):
    """CLI smoke: `export quiz-session <id> -o out.md` writes a Markdown file."""
    import asyncio
    import os

    from sqlalchemy import text
    from typer.testing import CliRunner

    db_path = tmp_path / "cli_test.db"
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")

    # Bust the module-level Settings cache so the CLI's get_services()
    # picks up our monkeypatched env vars instead of an earlier test's.
    from app.cli import deps as cli_deps

    monkeypatch.setattr(cli_deps, "_settings", None)

    from app.config import Settings
    from app.db.models import Base, QuizQuestion, QuizSession
    from app.db.session import create_session_factory

    settings = Settings()
    factory = create_session_factory(settings)

    async def _seed():
        from sqlalchemy.ext.asyncio import create_async_engine

        eng = create_async_engine(settings.database.url, connect_args={"check_same_thread": False})
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

        async with factory() as s:
            await s.execute(
                text(
                    """
                    INSERT INTO books (id, title, file_data, file_hash, file_format,
                                       file_size_bytes, status)
                    VALUES (1, 'Cli Book', x'00', 'h', 'epub', 1, 'COMPLETED')
                    """
                )
            )
            await s.execute(
                text(
                    "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                    "section_type, content_md) VALUES (101, 1, 'Ch1', 0, 0, 'chapter', 'c')"
                )
            )
            qs = QuizSession(book_id=1, scope_mode="all_summaries", status="completed")
            s.add(qs)
            await s.flush()
            q = QuizQuestion(
                book_id=1,
                session_id=qs.id,
                shape="open",
                bloom_level="apply",
                stem="Cli Q?",
                concept_label="x",
                citation_json='{"section_id": 101, "section_title": "Ch1", "snippet": "snip"}',
                user_answer="cli answer",
                feedback_json='{"correct":"a","missing":"b","actual":"c","agent_verdict":"partial"}',
                self_assessment="partial",
            )
            s.add(q)
            await s.flush()
            sid = qs.id
            await s.commit()
            return sid

    sid = asyncio.run(_seed())

    from app.cli.main import app as cli_app

    runner = CliRunner()
    out_path = tmp_path / "out.md"
    result = runner.invoke(
        cli_app, ["export", "quiz-session", str(sid), "-o", str(out_path)]
    )
    assert result.exit_code == 0, f"stderr: {result.stderr or result.output}"
    assert out_path.exists()
    body = out_path.read_text(encoding="utf-8")
    assert "Cli Q?" in body
    assert "/api/v1/images/" not in body

    # cleanup env so other tests' Settings() picks up their tmp paths
    if "BOOKCOMPANION_DATA__DIRECTORY" in os.environ:
        del os.environ["BOOKCOMPANION_DATA__DIRECTORY"]
    if "BOOKCOMPANION_DATABASE__URL" in os.environ:
        del os.environ["BOOKCOMPANION_DATABASE__URL"]
