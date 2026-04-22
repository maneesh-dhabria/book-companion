"""FastAPI application factory."""

import os
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api.routes import (
    ai_threads,
    annotations,
    backup,
    books,
    concepts,
    eval,
    export,
    health,
    images,
    processing,
    reading_presets,
    reading_state,
    search,
    sections,
    summaries,
    summarize_presets,
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


_logger = structlog.get_logger()


def register_db_busy_handler(app: FastAPI) -> None:
    """Convert SQLite 'database is locked' into a clean 503; other OperationalErrors → 500."""

    @app.exception_handler(OperationalError)
    async def _handle_op_error(request: Request, exc: OperationalError):
        msg = str(getattr(exc, "orig", exc))
        if "database is locked" in msg:
            _logger.warning(
                "db_busy_timeout", path=request.url.path, method=request.method
            )
            return JSONResponse(
                status_code=503,
                content={"detail": "Database busy, please retry"},
            )
        _logger.error(
            "operational_error",
            path=request.url.path,
            method=request.method,
            error=msg,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )


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
    app.include_router(images.router)
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
    app.include_router(summarize_presets.router)

    register_db_busy_handler(app)

    # Serve built Vue SPA if assets are present. Mounted AFTER routers
    # so /api/*, /health, /docs always match first (FR-11a).
    api_only = os.environ.get("BOOKCOMPANION_API_ONLY", "") not in ("", "0", "false", "False")
    if not api_only and _assets_present():
        static_dir = _resolve_static_dir()
        app.mount("/", CachingStaticFiles(directory=str(static_dir), html=True), name="static")

    return app


# Module-level app instance for uvicorn
app = create_app()
