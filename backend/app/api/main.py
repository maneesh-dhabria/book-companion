"""FastAPI application factory."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    ai_threads,
    annotations,
    backup,
    books,
    concepts,
    eval,
    export,
    health,
    processing,
    reading_presets,
    reading_state,
    search,
    sections,
    summaries,
    views,
)
from app.api.routes import (
    settings as settings_routes,
)
from app.api.sse import EventBus
from app.config import Settings
from app.db.session import create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle — create session factory on startup."""
    settings = Settings()
    app.state.settings = settings
    app.state.session_factory = create_session_factory(settings)
    app.state.event_bus = EventBus()

    # Start backup scheduler if configured
    scheduler = None
    backup_hours = getattr(getattr(settings, "backup", None), "schedule_hours", 0)
    if backup_hours and backup_hours > 0:
        from app.api.scheduler import create_backup_scheduler
        from app.services.backup_service import BackupService

        backup_service = BackupService(settings=settings)
        scheduler = create_backup_scheduler(backup_hours, backup_service)
        scheduler.start()
        app.state.backup_scheduler = scheduler

    yield

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Book Companion",
        description="Personal book summarization and knowledge extraction",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for Vite dev server and self
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:8000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(health.router)
    app.include_router(annotations.router)
    app.include_router(search.router)
    app.include_router(concepts.router)
    app.include_router(reading_presets.router)
    app.include_router(ai_threads.router)
    app.include_router(books.router)
    app.include_router(sections.router)
    app.include_router(summaries.router)
    app.include_router(eval.router)
    app.include_router(views.router)
    app.include_router(processing.router)
    app.include_router(export.router)
    app.include_router(backup.router)
    app.include_router(settings_routes.router)
    app.include_router(reading_state.router)

    # Serve static files (built Vue SPA) if directory exists
    settings = Settings()
    static_dir = Path(os.getcwd()) / settings.web.static_dir
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


# Module-level app instance for uvicorn
app = create_app()
