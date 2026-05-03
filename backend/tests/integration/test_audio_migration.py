"""Integration tests for the audiobook-mode migration."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = Path(__file__).parent.parent.parent / "app" / "migrations" / "alembic.ini"
PRE_REV = "9a67312a27a7"
HEAD_REV = "2026_05_02_audiobook"


def _setup_db(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
    cfg = Config(str(ALEMBIC_INI))
    return cfg, db_path


def _sync_engine(db_path: Path) -> sa.Engine:
    return sa.create_engine(f"sqlite:///{db_path}")


def test_audio_tables_created(tmp_path, monkeypatch):
    cfg, db_path = _setup_db(tmp_path, monkeypatch)
    upgrade(cfg, "head")
    eng = _sync_engine(db_path)
    insp = sa.inspect(eng)
    tables = set(insp.get_table_names())
    assert "audio_files" in tables
    assert "audio_positions" in tables


def test_audio_files_unique_unit_index(tmp_path, monkeypatch):
    cfg, db_path = _setup_db(tmp_path, monkeypatch)
    upgrade(cfg, "head")
    eng = _sync_engine(db_path)
    insp = sa.inspect(eng)
    uniques = insp.get_unique_constraints("audio_files")
    names = {u["name"]: u["column_names"] for u in uniques}
    assert names.get("ux_audio_files_unit") == ["book_id", "content_type", "content_id", "voice"]


def test_processing_jobs_index_swap(tmp_path, monkeypatch):
    cfg, db_path = _setup_db(tmp_path, monkeypatch)
    upgrade(cfg, "head")
    eng = _sync_engine(db_path)
    insp = sa.inspect(eng)
    names = {i["name"] for i in insp.get_indexes("processing_jobs")}
    assert "ix_processing_jobs_one_active_per_book_step" in names
    assert "ix_processing_jobs_one_active_per_book" not in names


def test_concurrent_audio_and_summarize_per_book(tmp_path, monkeypatch):
    """New (book_id, step) index lets AUDIO + SUMMARIZE jobs coexist for one book."""
    cfg, db_path = _setup_db(tmp_path, monkeypatch)
    upgrade(cfg, "head")
    eng = _sync_engine(db_path)
    with eng.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO books "
                "(title, status, file_data, file_hash, file_size_bytes, file_format) "
                "VALUES ('B1', 'completed', X'00', 'h', 1, 'epub')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO processing_jobs (book_id, step, status) "
                "VALUES (1, 'SUMMARIZE', 'RUNNING'), (1, 'AUDIO', 'RUNNING')"
            )
        )
        count = conn.execute(sa.text("SELECT COUNT(*) FROM processing_jobs")).scalar()
    assert count == 2


def test_duplicate_same_step_same_book_rejected(tmp_path, monkeypatch):
    cfg, db_path = _setup_db(tmp_path, monkeypatch)
    upgrade(cfg, "head")
    eng = _sync_engine(db_path)
    with eng.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO books "
                "(title, status, file_data, file_hash, file_size_bytes, file_format) "
                "VALUES ('B1', 'completed', X'00', 'h', 1, 'epub')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO processing_jobs (book_id, step, status) VALUES (1, 'AUDIO', 'RUNNING')"
            )
        )
    with pytest.raises(sa.exc.IntegrityError), eng.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO processing_jobs (book_id, step, status) VALUES (1, 'AUDIO', 'PENDING')"
            )
        )


def test_downgrade_round_trip(tmp_path, monkeypatch):
    cfg, db_path = _setup_db(tmp_path, monkeypatch)
    upgrade(cfg, "head")
    downgrade(cfg, "-1")
    eng = _sync_engine(db_path)
    insp = sa.inspect(eng)
    tables = set(insp.get_table_names())
    assert "audio_files" not in tables
    assert "audio_positions" not in tables
    names = {i["name"] for i in insp.get_indexes("processing_jobs")}
    assert "ix_processing_jobs_one_active_per_book" in names
    assert "ix_processing_jobs_one_active_per_book_step" not in names
    upgrade(cfg, "head")
