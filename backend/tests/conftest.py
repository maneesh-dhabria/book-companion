"""Shared test fixtures — SQLite-based."""

import os
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings
from app.db.models import Base

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    return tmp_path_factory.mktemp("db") / "test.db"


@pytest.fixture(scope="session")
def test_settings(test_db_path) -> Settings:
    os.environ["BOOKCOMPANION_DATA__DIRECTORY"] = str(test_db_path.parent)
    os.environ["BOOKCOMPANION_DATABASE__URL"] = f"sqlite+aiosqlite:///{test_db_path}"
    return Settings()


@pytest_asyncio.fixture
async def engine(test_settings, test_db_path):
    """Create a fresh engine per test with SQLite + FTS5 virtual tables."""
    url = f"sqlite+aiosqlite:///{test_db_path}"
    from sqlalchemy import event

    eng = create_async_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(eng.sync_engine, "connect")
    def _set_pragmas(dbapi_conn, connection_record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # Create FTS5 virtual table
        await conn.execute(
            text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                    chunk_text,
                    content=search_index,
                    content_rowid=id,
                    tokenize='porter unicode61'
                )
            """)
        )
        # FTS5 sync triggers
        await conn.execute(
            text("""
                CREATE TRIGGER IF NOT EXISTS search_fts_ai AFTER INSERT ON search_index BEGIN
                    INSERT INTO search_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
                END
            """)
        )
        await conn.execute(
            text("""
                CREATE TRIGGER IF NOT EXISTS search_fts_ad AFTER DELETE ON search_index BEGIN
                    INSERT INTO search_fts(search_fts, rowid, chunk_text)
                    VALUES ('delete', old.id, old.chunk_text);
                END
            """)
        )
        await conn.execute(
            text("""
                CREATE TRIGGER IF NOT EXISTS search_fts_au AFTER UPDATE ON search_index BEGIN
                    INSERT INTO search_fts(search_fts, rowid, chunk_text)
                    VALUES ('delete', old.id, old.chunk_text);
                    INSERT INTO search_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
                END
            """)
        )
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncSession:
    """Per-test session that rolls back after each test."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


@pytest.fixture
def sample_epub_path() -> Path:
    path = FIXTURES_DIR / "sample_epub" / "art_of_war.epub"
    if not path.exists():
        pytest.skip("Test fixtures not downloaded. Run: python tests/fixtures/download_fixtures.py")
    return path


@pytest.fixture
def sample_pdf_path() -> Path:
    path = FIXTURES_DIR / "sample_pdf" / "the_republic.pdf"
    if not path.exists():
        pytest.skip("Test fixtures not downloaded. Run: python tests/fixtures/download_fixtures.py")
    return path


@pytest.fixture
def sample_mobi_path() -> Path:
    path = FIXTURES_DIR / "sample_mobi" / "art_of_war.mobi"
    if not path.exists():
        pytest.skip("Test fixtures not downloaded. Run: python tests/fixtures/download_fixtures.py")
    return path
