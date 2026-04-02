"""Async database session management."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings


def create_engine(settings: Settings):
    """Create async SQLAlchemy engine."""
    return create_async_engine(
        settings.database.url,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    engine = create_engine(settings)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
