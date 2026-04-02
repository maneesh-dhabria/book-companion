"""Async CLI utilities -- helpers for running async code in Typer commands."""

import asyncio
import functools
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.session import create_session_factory


def async_command(func):
    """Decorator to run an async function as a Typer command.

    Wraps the async function so it runs in an event loop, compatible
    with Typer's synchronous command registration.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    settings = Settings()
    factory = create_session_factory(settings)
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def get_services():
    """Get a dict of initialized services for use in CLI commands.

    Usage:
        async with get_services() as svc:
            result = await svc["annotation"].create_annotation(...)
    """
    settings = Settings()
    factory = create_session_factory(settings)
    session = factory()
    try:
        from app.services.annotation_service import AnnotationService
        from app.services.backup_service import BackupService
        from app.services.concept_service import ConceptService
        from app.services.export_service import ExportService
        from app.services.reference_service import ReferenceService
        from app.services.tag_service import TagService

        services = {
            "annotation": AnnotationService(session),
            "tag": TagService(session),
            "concept": ConceptService(session),
            "export": ExportService(session),
            "backup": BackupService(settings),
            "reference": ReferenceService(session),
            "session": session,
            "settings": settings,
        }
        yield services
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
