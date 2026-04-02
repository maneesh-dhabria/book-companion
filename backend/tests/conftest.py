"""Shared test fixtures."""

import os
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings
from app.db.models import Base

TEST_DB_URL = "postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    os.environ["BOOKCOMPANION_DATABASE__URL"] = TEST_DB_URL
    return Settings()


@pytest_asyncio.fixture
async def engine(test_settings):
    """Create a fresh engine per test module to avoid event loop issues."""
    eng = create_async_engine(TEST_DB_URL, pool_pre_ping=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
