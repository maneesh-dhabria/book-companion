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


# ---------------------------------------------------------------------------
# M2 — data backfill tests
# ---------------------------------------------------------------------------

M1_ONLY_REV = "d4e5f6a7b8c9"


def _seed_book_and_section(conn, *, section_id: int = 1, book_id: int = 1):
    conn.execute(
        sa.text(
            "INSERT INTO books (id, title, file_data, file_hash, file_format, "
            "file_size_bytes, status) "
            "VALUES (:b, 'T', x'00', :h, 'epub', 1, 'COMPLETED')"
        ),
        {"b": book_id, "h": f"h{book_id}"},
    )
    conn.execute(
        sa.text(
            "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
            "section_type, content_md) "
            "VALUES (:s, :b, 'Chap', 0, 0, 'chapter', 'body')"
        ),
        {"s": section_id, "b": book_id},
    )


def _seed_summary(conn, *, sid: int, content_id: int, book_id: int, md: str, offset: int = 0):
    from datetime import datetime, timedelta

    ts = (datetime.utcnow() + timedelta(seconds=offset)).isoformat(sep=" ")
    conn.execute(
        sa.text(
            "INSERT INTO summaries (id, content_type, content_id, book_id, "
            "facets_used, prompt_text_sent, model_used, "
            "input_char_count, summary_char_count, summary_md, created_at) "
            "VALUES (:id, 'section', :cid, :bid, '{}', 'p', 'm', "
            "10, :chars, :md, :ts)"
        ),
        {
            "id": sid,
            "cid": content_id,
            "bid": book_id,
            "chars": len(md),
            "md": md,
            "ts": ts,
        },
    )


def test_m2_deletes_empty_summaries_and_stamps_empty_output(
    tmp_path, monkeypatch
):
    cfg, engine = _setup_db(tmp_path, monkeypatch)
    # Downgrade to M1 so we can seed state, then re-run M2 alone.
    downgrade(cfg, M1_ONLY_REV)

    with engine.begin() as conn:
        _seed_book_and_section(conn, section_id=1, book_id=1)
        _seed_summary(conn, sid=100, content_id=1, book_id=1, md="")
        _seed_summary(conn, sid=101, content_id=1, book_id=1, md="real summary", offset=1)
        conn.execute(sa.text("UPDATE book_sections SET default_summary_id = 100 WHERE id = 1"))

    upgrade(cfg, "head")

    with engine.begin() as conn:
        # Empty summary row is gone.
        count = conn.execute(sa.text("SELECT COUNT(*) FROM summaries WHERE id=100")).scalar()
        assert count == 0
        # default_summary_id switched from the deleted empty row to the real one.
        row = conn.execute(
            sa.text("SELECT default_summary_id, last_failure_type FROM book_sections WHERE id=1")
        ).first()
        assert row.default_summary_id == 101
        assert row.last_failure_type == "empty_output"


def test_m2_preserves_newer_typed_failure(tmp_path, monkeypatch):
    """P-3 guard — never overwrite a typed failure with empty_output."""
    cfg, engine = _setup_db(tmp_path, monkeypatch)
    downgrade(cfg, M1_ONLY_REV)

    with engine.begin() as conn:
        _seed_book_and_section(conn, section_id=1, book_id=1)
        # Prior diagnostic state from a real v1.4 run.
        conn.execute(
            sa.text(
                "UPDATE book_sections SET last_failure_type='cli_timeout', "
                "last_failure_message='Timed out' WHERE id=1"
            )
        )
        # Legacy buggy empty summary row.
        _seed_summary(conn, sid=200, content_id=1, book_id=1, md="")

    upgrade(cfg, "head")

    with engine.begin() as conn:
        count = conn.execute(sa.text("SELECT COUNT(*) FROM summaries WHERE id=200")).scalar()
        row = conn.execute(
            sa.text("SELECT last_failure_type, last_failure_message FROM book_sections WHERE id=1")
        ).first()
    assert count == 0
    # Typed failure preserved, not overwritten.
    assert row.last_failure_type == "cli_timeout"
    assert row.last_failure_message == "Timed out"


def test_m2_backfills_default_summary_id(tmp_path, monkeypatch):
    cfg, engine = _setup_db(tmp_path, monkeypatch)
    downgrade(cfg, M1_ONLY_REV)

    with engine.begin() as conn:
        _seed_book_and_section(conn, section_id=1, book_id=1)
        _seed_summary(conn, sid=300, content_id=1, book_id=1, md="older", offset=0)
        _seed_summary(conn, sid=301, content_id=1, book_id=1, md="newer", offset=10)
        # default_summary_id is NULL (no UPDATE).

    upgrade(cfg, "head")

    with engine.begin() as conn:
        row = conn.execute(
            sa.text("SELECT default_summary_id FROM book_sections WHERE id=1")
        ).first()
    assert row.default_summary_id == 301


def test_m2_creates_backup_file(tmp_path, monkeypatch):
    cfg, engine = _setup_db(tmp_path, monkeypatch)
    # Re-running the data migration creates a fresh backup each time, so pop
    # back to M1 and upgrade once.
    downgrade(cfg, M1_ONLY_REV)
    # Clear any pre-existing backup files (none expected on fresh tmp_path).
    for f in tmp_path.glob("library.db.pre-v1-4-*.bak"):
        f.unlink()

    upgrade(cfg, "head")

    backups = list(tmp_path.glob("library.db.pre-v1-4-*.bak"))
    assert len(backups) == 1, [str(b) for b in backups]


def test_m2_is_idempotent(tmp_path, monkeypatch):
    cfg, engine = _setup_db(tmp_path, monkeypatch)
    downgrade(cfg, M1_ONLY_REV)
    with engine.begin() as conn:
        _seed_book_and_section(conn, section_id=1, book_id=1)
        _seed_summary(conn, sid=400, content_id=1, book_id=1, md="", offset=0)
        _seed_summary(conn, sid=401, content_id=1, book_id=1, md="real", offset=1)

    upgrade(cfg, "head")
    with engine.begin() as conn:
        initial_counts = conn.execute(
            sa.text("SELECT COUNT(*) FROM summaries")
        ).scalar()

    # Second up-down-up should no-op.
    downgrade(cfg, M1_ONLY_REV)
    upgrade(cfg, "head")
    with engine.begin() as conn:
        final_counts = conn.execute(
            sa.text("SELECT COUNT(*) FROM summaries")
        ).scalar()
    assert initial_counts == final_counts


def test_m2_aborts_on_backup_failure(tmp_path, monkeypatch):
    """If the pre-backup raises, Alembic must stop at v1_4a (not v1_4b)."""
    cfg, engine = _setup_db(tmp_path, monkeypatch)
    downgrade(cfg, M1_ONLY_REV)

    # Patch shutil.copy2 directly — the migration's module is imported fresh
    # by Alembic, so patching the module-level helper may not stick; the
    # copy2 call at the underlying syscall level is a stable seam.
    import shutil as _shutil

    real_copy2 = _shutil.copy2

    def _boom(src, dst, *a, **kw):  # noqa: ARG001
        raise RuntimeError("simulated disk full")

    monkeypatch.setattr(_shutil, "copy2", _boom)

    with pytest.raises(RuntimeError, match="simulated disk full"):
        upgrade(cfg, "head")

    monkeypatch.setattr(_shutil, "copy2", real_copy2)

    with engine.begin() as conn:
        rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    assert rev == M1_ONLY_REV
