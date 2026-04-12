"""Dependency wiring for CLI commands — creates services with proper sessions."""

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path

from app.config import Settings
from app.db.session import create_session_factory

_settings: Settings | None = None


async def check_orphaned_processes(settings: Settings) -> None:
    """Spec requirement: on every CLI invocation, check for orphaned background processes.
    Query processing_jobs for status 'running', check if PID is alive via os.kill(pid, 0).
    If PID dead: mark job as 'failed' with error 'Process terminated unexpectedly'."""
    import os

    try:
        session_factory = create_session_factory(settings)
        async with session_factory() as session:
            from app.db.repositories.processing_repo import ProcessingRepository

            repo = ProcessingRepository(session)
            orphaned = await repo.get_orphaned_jobs()
            for job in orphaned:
                if job.pid:
                    try:
                        os.kill(job.pid, 0)  # Check if process exists
                    except OSError:
                        await repo.update_status(
                            job.id, "failed", error_message="Process terminated unexpectedly"
                        )
            await session.commit()
    except Exception:
        pass  # Don't block CLI on orphan check failure


def auto_check_migrations(settings: Settings) -> None:
    """Spec requirement: auto-check migrations on every CLI invocation.
    Run a lightweight check — compare alembic head vs current. Log warning if behind."""
    import subprocess

    try:
        result = subprocess.run(
            ["uv", "run", "alembic", "current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "head" not in result.stdout:
            import structlog

            structlog.get_logger().warning(
                "database_migrations_behind", hint="Run: bookcompanion init"
            )
    except Exception:
        pass  # Don't block CLI on migration check failure


async def check_db_health(settings: Settings) -> bool:
    """Quick DB connection health check. Returns False if DB unreachable.
    Spec Section 12: DB connection failure -> immediate error with connection details."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.database.url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        from rich.console import Console

        Console().print(
            f"[red]Database connection failed:[/red] {e}\n"
            f"Connection URL: {settings.database.url}\n"
            f"Check: bookcompanion init"
        )
        return False
    finally:
        await engine.dispose()


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _setup_logging(_settings)
    return _settings


def _setup_logging(settings: Settings) -> None:
    """Configure structlog based on settings."""
    try:
        import structlog

        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(
                    __import__("logging"),
                    settings.logging.level.upper(),
                    __import__("logging").INFO,
                )
            ),
        )
    except Exception:
        pass  # Logging setup is non-critical


@asynccontextmanager
async def get_services():
    """Provide all services with a shared DB session."""
    settings = get_settings()
    session_factory = create_session_factory(settings)

    async with session_factory() as session:
        services = {
            "session": session,
            "settings": settings,
        }

        # Import services that may not exist yet (implemented by other agents)
        try:
            from app.services.book_service import BookService

            services["book_service"] = BookService(db=session, config=settings)
        except ImportError:
            pass

        try:
            from app.services.summarizer import create_llm_provider, detect_llm_provider
            from app.services.summarizer.image_captioner import ImageCaptioner
            from app.services.summarizer.summarizer_service import SummarizerService

            provider = settings.llm.provider
            if provider == "auto":
                provider = detect_llm_provider()

            llm = create_llm_provider(
                provider,
                cli_command=settings.llm.cli_command,
                default_model=settings.llm.model,
                default_timeout=settings.llm.timeout_seconds,
                max_budget_usd=settings.llm.max_budget_usd,
                config_dir=settings.llm.config_dir,
            )
            services["llm"] = llm
            if llm:
                captioner = (
                    ImageCaptioner(llm_provider=llm)
                    if settings.images.captioning_enabled
                    else None
                )
                services["summarizer"] = SummarizerService(
                    db=session, llm=llm, config=settings, captioner=captioner
                )
        except ImportError:
            pass

        try:
            from app.services.embedding_service import EmbeddingService

            data_dir = settings.data.directory
            embedding = EmbeddingService(
                cache_dir=str(Path(data_dir) / "models"),
                chunk_size=settings.embedding.chunk_size,
                chunk_overlap=settings.embedding.chunk_overlap,
            )
            services["embedding"] = embedding
        except ImportError:
            pass

        try:
            from app.services.search_service import SearchService

            embedding = services.get("embedding")
            if embedding:
                services["search"] = SearchService(
                    session,
                    embedding,
                    settings.search.rrf_k,
                    settings.search.default_limit,
                )
        except ImportError:
            pass

        try:
            from app.services.summarizer.evaluator import EvalService

            llm = services.get("llm")
            if llm:
                services["eval"] = EvalService(db=session, llm=llm, config=settings)
        except ImportError:
            pass

        # Phase 2 services
        try:
            from app.services.annotation_service import AnnotationService

            services["annotation"] = AnnotationService(session)
        except ImportError:
            pass

        try:
            from app.services.tag_service import TagService

            services["tag"] = TagService(session)
        except ImportError:
            pass

        try:
            from app.services.concept_service import ConceptService

            services["concept"] = ConceptService(session)
        except ImportError:
            pass

        try:
            from app.services.export_service import ExportService

            services["export"] = ExportService(session)
        except ImportError:
            pass

        try:
            from app.services.preset_service import PresetService

            services["preset"] = PresetService()
        except ImportError:
            pass

        try:
            from app.services.quality_service import QualityService

            services["quality"] = QualityService()
        except ImportError:
            pass

        try:
            from app.services.summary_service import SummaryService

            services["summary_service"] = SummaryService(session)
        except ImportError:
            pass

        try:
            from app.services.section_edit_service import SectionEditService

            services["section_edit"] = SectionEditService(session)
        except ImportError:
            pass

        try:
            from app.services.backup_service import BackupService

            db_path = Path(settings.data.directory) / "library.db"
            backup_dir = Path(settings.backup.directory)
            services["backup"] = BackupService(
                db_path=db_path, backup_dir=backup_dir, max_backups=settings.backup.max_backups
            )
        except ImportError:
            pass

        try:
            from app.services.reference_service import ReferenceService

            llm = services.get("llm")
            services["reference"] = ReferenceService(session, llm_service=llm)
        except ImportError:
            pass

        yield services


def async_command(func: Callable) -> Callable:
    """Decorator to run async CLI commands."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper
