"""FastAPI application factory."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import books, health, sections
from app.config import Settings
from app.db.session import create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle — create session factory on startup."""
    settings = Settings()
    app.state.settings = settings
    app.state.session_factory = create_session_factory(settings)
    yield


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
    app.include_router(books.router)
    app.include_router(sections.router)

    # Serve static files (built Vue SPA) if directory exists
    settings = Settings()
    static_dir = Path(os.getcwd()) / settings.web.static_dir
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


# Module-level app instance for uvicorn
app = create_app()
