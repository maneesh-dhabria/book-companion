import pytest
from sqlalchemy import text

from app.config import Settings
from app.db.session import create_session_factory


@pytest.mark.asyncio
async def test_busy_timeout_pragma_set(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
    session_factory = create_session_factory(Settings())
    async with session_factory() as session:
        result = await session.execute(text("PRAGMA busy_timeout"))
        assert result.scalar() == 5000


@pytest.mark.asyncio
async def test_journal_mode_still_wal(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
    session_factory = create_session_factory(Settings())
    async with session_factory() as session:
        result = await session.execute(text("PRAGMA journal_mode"))
        assert result.scalar().lower() == "wal"


@pytest.mark.asyncio
async def test_foreign_keys_pragma_set(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
    session_factory = create_session_factory(Settings())
    async with session_factory() as session:
        result = await session.execute(text("PRAGMA foreign_keys"))
        assert result.scalar() == 1
