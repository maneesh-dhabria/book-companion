"""Round-trip integration test for v1_7a quiz tables migration."""

import os
import sqlite3
import subprocess

import pytest


@pytest.mark.integration
def test_quiz_migration_round_trip(tmp_path):
    env = os.environ.copy()
    db_path = tmp_path / "lib.db"
    env["BOOKCOMPANION_DATABASE__URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["BOOKCOMPANION_DATA__DIRECTORY"] = str(tmp_path)
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cmd = ["uv", "run", "alembic", "-c", "app/migrations/alembic.ini"]

    # up → head
    r1 = subprocess.run([*cmd, "upgrade", "head"], env=env, cwd=cwd, capture_output=True)
    assert r1.returncode == 0, r1.stderr.decode()

    # down -1 (drops quiz)
    r2 = subprocess.run([*cmd, "downgrade", "-1"], env=env, cwd=cwd, capture_output=True)
    assert r2.returncode == 0, r2.stderr.decode()

    # up → head again (idempotent re-create)
    r3 = subprocess.run([*cmd, "upgrade", "head"], env=env, cwd=cwd, capture_output=True)
    assert r3.returncode == 0, r3.stderr.decode()

    con = sqlite3.connect(db_path)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"quiz_sessions", "quiz_questions", "quiz_dedup_state"}.issubset(tables), tables

        cols = {r[1] for r in con.execute("PRAGMA table_info(books)")}
        assert "pre_drafted_q1_id" in cols, cols

        indexes = {
            r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        # Spot-check key indexes from spec §10.3
        for ix in (
            "ix_quiz_questions_book_dedup",
            "ix_quiz_questions_concept",
            "ix_quiz_sessions_book_status",
            "ix_books_pre_drafted_q1",
        ):
            assert ix in indexes, (ix, indexes)
    finally:
        con.close()
