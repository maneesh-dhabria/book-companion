"""Shared fixtures for API integration tests."""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.main import create_app
from app.config import Settings
from app.db.models import Base
from app.db.session import create_session_factory


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a FastAPI app with SQLite test database."""
    db_path = tmp_path / "api_test.db"
    os.environ["BOOKCOMPANION_DATA__DIRECTORY"] = str(tmp_path)
    os.environ["BOOKCOMPANION_DATABASE__URL"] = f"sqlite+aiosqlite:///{db_path}"

    # Redirect SettingsService writes to tmp_path so PATCH /settings does not
    # touch the developer's real ~/.config/bookcompanion/settings.yaml.
    from app.services import settings_service as ss

    monkeypatch.setattr(ss, "DEFAULT_CONFIG_PATH", tmp_path / "settings.yaml")
    monkeypatch.setattr(ss, "default_user_settings_path", lambda: tmp_path / "settings.yaml")

    application = create_app()
    settings = Settings()
    application.state.settings = settings
    application.state.session_factory = create_session_factory(settings)

    # Initialize schema synchronously
    import asyncio

    async def _init_schema():
        eng = create_async_engine(settings.database.url, connect_args={"check_same_thread": False})
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                        chunk_text, content=search_index, content_rowid=id,
                        tokenize='porter unicode61'
                    )
                """)
            )
        await eng.dispose()

    asyncio.run(_init_schema())
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
