import pytest
from sqlalchemy import create_engine, inspect

from app.cli.commands.init_cmd import _run_migrations


def test_run_migrations_creates_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    # env.py reads Settings() which reads BOOKCOMPANION_DATABASE__URL — that's the
    # knob we turn, not Config.set_main_option (env.py ignores the Config URL).
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")

    _run_migrations()

    sync_engine = create_engine(f"sqlite:///{db_path}")
    tables = inspect(sync_engine).get_table_names()
    assert "books" in tables
    assert "book_sections" in tables
    assert "alembic_version" in tables


@pytest.mark.asyncio
async def test_run_migrations_works_inside_running_event_loop(tmp_path, monkeypatch):
    """Regression: _run_migrations is called from init() which runs under
    asyncio.run() via @async_command. env.py internally calls asyncio.run(),
    which would fail as nested. The worker-thread wrapper prevents that."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")

    _run_migrations()  # must not raise "asyncio.run() cannot be called..."

    sync_engine = create_engine(f"sqlite:///{db_path}")
    assert "books" in inspect(sync_engine).get_table_names()
