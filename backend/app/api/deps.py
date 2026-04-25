"""FastAPI dependency injection — mirrors CLI's get_services() pattern."""

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings

_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


async def get_db(request: Request) -> AsyncGenerator[AsyncSession]:
    """Yield an AsyncSession from the app's session factory."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_book_service(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Construct BookService with shared session."""
    from app.services.book_service import BookService

    return BookService(db=db, config=settings)


def _get_llm_provider(settings: Settings):
    """Create the LLM provider based on settings, with auto-detection."""
    from app.services.summarizer import create_llm_provider, detect_llm_provider

    provider = settings.llm.provider
    if provider == "auto":
        provider = detect_llm_provider()

    return create_llm_provider(
        provider,
        cli_command=settings.llm.cli_command,
        default_model=settings.llm.model,
        default_timeout=settings.llm.timeout_seconds,
        max_budget_usd=settings.llm.max_budget_usd,
    )


def get_summarizer_service(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Construct SummarizerService with shared session and LLM provider."""
    from app.services.summarizer.image_captioner import ImageCaptioner
    from app.services.summarizer.summarizer_service import SummarizerService

    llm = _get_llm_provider(settings)
    if llm is None:
        return None
    captioner = ImageCaptioner(llm_provider=llm) if settings.images.captioning_enabled else None
    return SummarizerService(db=db, llm=llm, config=settings, captioner=captioner)


def get_eval_service(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Construct EvalService with shared session."""
    from app.services.summarizer.evaluator import EvalService

    llm = _get_llm_provider(settings)
    if llm is None:
        return None
    return EvalService(db=db, llm=llm, config=settings)


def get_summary_service(
    db: AsyncSession = Depends(get_db),
):
    """Construct SummaryService with shared session."""
    from app.services.summary_service import SummaryService

    return SummaryService(db)


def get_section_edit_service(
    db: AsyncSession = Depends(get_db),
):
    """Construct SectionEditService with shared session."""
    from app.services.section_edit_service import SectionEditService

    return SectionEditService(db)


def get_annotation_repo(
    db: AsyncSession = Depends(get_db),
):
    """Construct AnnotationRepository with shared session."""
    from app.db.repositories.annotation_repo import AnnotationRepository

    return AnnotationRepository(db)


def get_concept_repo(
    db: AsyncSession = Depends(get_db),
):
    """Construct ConceptRepository with shared session."""
    from app.db.repositories.concept_repo import ConceptRepository

    return ConceptRepository(db)


def get_search_service(
    db: AsyncSession = Depends(get_db),
):
    """Construct SearchService — degrades to BM25-only if Ollama unavailable."""
    from app.services.embedding_service import EmbeddingService
    from app.services.search_service import SearchService

    embedding_service = EmbeddingService()
    return SearchService(session=db, embedding_service=embedding_service)


def get_export_service(
    db: AsyncSession = Depends(get_db),
):
    """Construct ExportService with shared session."""
    from app.services.export_service import ExportService

    return ExportService(session=db)


def get_backup_service(
    settings: Settings = Depends(get_settings),
):
    """Construct BackupService with settings."""
    from pathlib import Path

    from app.services.backup_service import BackupService

    db_path = Path(settings.data.directory) / "library.db"
    backup_dir = Path(settings.backup.directory)
    return BackupService(db_path=db_path, backup_dir=backup_dir, max_backups=settings.backup.max_backups)


def get_reading_state_repo(
    db: AsyncSession = Depends(get_db),
):
    """Construct ReadingStateRepository with shared session."""
    from app.db.repositories.reading_state_repo import ReadingStateRepository

    return ReadingStateRepository(session=db)


def get_tag_service(
    db: AsyncSession = Depends(get_db),
):
    """Construct TagService with shared session."""
    from app.services.tag_service import TagService

    return TagService(session=db)


def get_settings_service(
    settings: Settings = Depends(get_settings),
):
    """Construct SettingsService (T8)."""
    from app.services.settings_service import SettingsService

    return SettingsService(settings)
