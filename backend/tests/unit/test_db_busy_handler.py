import sqlite3

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.api.main import register_db_busy_handler


def _make_app_with_routes():
    app = FastAPI()
    register_db_busy_handler(app)

    @app.get("/_test/busy")
    async def busy():
        raise OperationalError(
            "PRAGMA something",
            {},
            sqlite3.OperationalError("database is locked"),
        )

    @app.get("/_test/other")
    async def other():
        raise OperationalError(
            "INSERT INTO ...",
            {},
            sqlite3.OperationalError("disk I/O error"),
        )

    return app


@pytest.mark.asyncio
async def test_busy_returns_503():
    app = _make_app_with_routes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/_test/busy")
    assert r.status_code == 503
    assert r.json() == {"detail": "Database busy, please retry"}


@pytest.mark.asyncio
async def test_other_operational_error_returns_500():
    app = _make_app_with_routes()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://t",
    ) as ac:
        r = await ac.get("/_test/other")
    assert r.status_code == 500


