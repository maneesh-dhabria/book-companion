"""Shared fixtures for API integration tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import create_app
from app.config import Settings
from app.db.session import create_session_factory


@pytest.fixture
def app():
    """Create a FastAPI app with session factory pre-initialized (no lifespan needed)."""
    application = create_app()
    settings = Settings()
    # Override DB URL to use test database
    settings.database.url = (
        "postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test"
    )
    application.state.settings = settings
    application.state.session_factory = create_session_factory(settings)
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
