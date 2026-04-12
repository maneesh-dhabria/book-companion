"""FastAPI application factory."""

import os
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.api.static_files import CachingStaticFiles, _assets_present, _resolve_static_dir
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
    backup_freq = getattr(getattr(settings, "backup", None), "frequency", "disabled")
    if backup_freq and backup_freq != "disabled":
        try:
            from app.api.scheduler import create_backup_scheduler
            from app.services.backup_service import BackupService

            db_path = Path(settings.data.directory) / "library.db"
            backup_dir = Path(settings.backup.directory)
            backup_service = BackupService(
                db_path=db_path, backup_dir=backup_dir, max_backups=settings.backup.max_backups
            )
            # Map frequency to hours
            freq_hours = {"hourly": 1, "daily": 24, "weekly": 168}.get(backup_freq, 24)
            scheduler = create_backup_scheduler(freq_hours, backup_service)
            scheduler.start()
            app.state.backup_scheduler = scheduler
        except Exception:
            pass  # Scheduler is non-critical

    yield

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


def build_cors_origins(port: int) -> list[str]:
    """Build CORS origin list including localhost and LAN IPs."""
    origins = [
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
    ]

    # Detect LAN IPs
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                origins.append(f"http://{ip}:{port}")
    except Exception:
        pass  # Graceful degradation if detection fails

    # Extra origins from env var
    extra = os.environ.get("BOOKCOMPANION_CORS_EXTRA_ORIGINS", "")
    if extra:
        origins.extend(o.strip() for o in extra.split(",") if o.strip())

    return list(set(origins))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Book Companion",
        description="Personal book summarization and knowledge extraction",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — dynamic origins including LAN IPs
    from app.config import Settings

    _settings = Settings()
    cors_origins = build_cors_origins(_settings.network.port)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
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

    # Serve built Vue SPA if assets are present. Mounted AFTER routers
    # so /api/*, /health, /docs always match first (FR-11a).
    api_only = os.environ.get("BOOKCOMPANION_API_ONLY", "") not in ("", "0", "false", "False")
    if not api_only and _assets_present():
        static_dir = _resolve_static_dir()
        app.mount("/", CachingStaticFiles(directory=str(static_dir), html=True), name="static")

    return app


# Module-level app instance for uvicorn
app = create_app()
