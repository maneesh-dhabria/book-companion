"""Async database session management for SQLite via aiosqlite."""

import logging

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings

logger = logging.getLogger(__name__)


def create_engine(settings: Settings):
    """Create async SQLAlchemy engine for SQLite."""
    engine = create_async_engine(
        settings.database.url,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_conn, connection_record):
        """Configure SQLite pragmas and load extensions on each connection."""
        # Enable WAL mode for concurrent reads during writes
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        # Enable foreign key enforcement (off by default in SQLite)
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    engine = create_engine(settings)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
