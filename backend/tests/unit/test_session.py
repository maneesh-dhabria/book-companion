"""Tests for SQLite session/engine setup."""

import os

import pytest
from sqlalchemy import text

from app.config import Settings
from app.db.session import create_engine, create_session_factory


@pytest.fixture
def sqlite_settings(tmp_path):
    os.environ["BOOKCOMPANION_DATA__DIRECTORY"] = str(tmp_path)
    os.environ["BOOKCOMPANION_DATABASE__URL"] = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    settings = Settings()
    yield settings
    os.environ.pop("BOOKCOMPANION_DATA__DIRECTORY", None)
    os.environ.pop("BOOKCOMPANION_DATABASE__URL", None)


def test_engine_uses_aiosqlite(sqlite_settings):
    engine = create_engine(sqlite_settings)
    assert "aiosqlite" in str(engine.url)


@pytest.mark.asyncio
async def test_wal_mode_enabled(sqlite_settings):
    factory = create_session_factory(sqlite_settings)
    async with factory() as session:
        result = await session.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
        assert mode == "wal"


@pytest.mark.asyncio
async def test_foreign_keys_enabled(sqlite_settings):
    factory = create_session_factory(sqlite_settings)
    async with factory() as session:
        result = await session.execute(text("PRAGMA foreign_keys"))
        fk = result.scalar()
        assert fk == 1
