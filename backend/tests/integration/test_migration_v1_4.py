"""Integration tests for v1.4 migrations (M1 schema + M2 data backfill)."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

ALEMBIC_INI = (
    Path(__file__).parent.parent.parent / "app" / "migrations" / "alembic.ini"
)

M1_REV = "d4e5f6a7b8c9"
PRE_M1_REV = "c3d4e5f6a7b8"


def _column_names(conn, table: str) -> set[str]:
    insp = sa.inspect(conn)
    return {c["name"] for c in insp.get_columns(table)}


def _setup_db(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv(
        "BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}"
    )
    cfg = Config(str(ALEMBIC_INI))
    upgrade(cfg, "head")
    engine = sa.create_engine(f"sqlite:///{db_path}")
    return cfg, engine


def test_m1_adds_book_section_failure_cols(tmp_path, monkeypatch):
    _, engine = _setup_db(tmp_path, monkeypatch)
    with engine.begin() as conn:
        cols = _column_names(conn, "book_sections")
    assert {
        "last_failure_type",
        "last_failure_message",
        "last_attempted_at",
        "attempt_count",
        "last_preset_used",
    } <= cols


def test_m1_partial_unique_rejects_second_running_job(tmp_path, monkeypatch):
    _, engine = _setup_db(tmp_path, monkeypatch)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
            INSERT INTO books (id, title, file_data, file_hash, file_format,
                               file_size_bytes, status)
            VALUES (1, 'T', x'00', 'h1', 'epub', 1, 'COMPLETED')
            """
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO processing_jobs (book_id, status, step) "
                "VALUES (1, 'RUNNING', 'SUMMARIZE')"
            )
        )

    # Second RUNNING row for same book should trip the partial UNIQUE.
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO processing_jobs (book_id, status, step) "
                "VALUES (1, 'RUNNING', 'SUMMARIZE')"
            )
        )

    # But a COMPLETED row is fine — the index only covers active statuses.
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO processing_jobs (book_id, status, step) "
                "VALUES (1, 'COMPLETED', 'SUMMARIZE')"
            )
        )


def test_m1_downgrades_cleanly(tmp_path, monkeypatch):
    cfg, engine = _setup_db(tmp_path, monkeypatch)
    downgrade(cfg, PRE_M1_REV)
    with engine.begin() as conn:
        cols = _column_names(conn, "book_sections")
        idx_names = {idx["name"] for idx in sa.inspect(conn).get_indexes("processing_jobs")}
    assert "last_failure_type" not in cols
    assert "attempt_count" not in cols
    assert "ix_processing_jobs_one_active_per_book" not in idx_names

    # Round-trip back up must succeed too.
    upgrade(cfg, "head")
    with engine.begin() as conn:
        cols = _column_names(conn, "book_sections")
    assert "last_failure_type" in cols


def test_m1_processing_jobs_pid_column_present(tmp_path, monkeypatch):
    _, engine = _setup_db(tmp_path, monkeypatch)
    with engine.begin() as conn:
        cols = _column_names(conn, "processing_jobs")
    assert "pid" in cols
