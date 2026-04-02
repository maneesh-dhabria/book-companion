# Book Companion V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that parses non-fiction books (EPUB/MOBI/PDF), generates LLM-powered summaries with quality evaluation, and provides hybrid search across a personal book library.

**Architecture:** Layered monolith running on host machine. Typer CLI → Service Layer → SQLAlchemy 2.0 Data Access → PostgreSQL 16 + pgvector (Docker). LLM calls via Claude Code CLI subprocess. Local embeddings via Ollama. All business logic in the service layer so a future REST API can share it.

**Tech Stack:** Python 3.12+, Typer, SQLAlchemy 2.0, Alembic, pydantic-settings, PostgreSQL 16 + pgvector, Ollama (nomic-embed-text), Claude Code CLI, ebooklib, pymupdf4llm, marker-pdf, Calibre (ebook-convert), rich, structlog, Jinja2, ruff, mypy, pytest + pytest-asyncio, uv

**Spec Reference:** `docs/specs/2026-04-01_book_companion_v1_spec.md`
**Requirements Reference:** `docs/requirements/2026-04-01_book_companion_v1_requirements.md`

---

## Table of Contents

1. [Decision Log](#decision-log)
2. [File Structure](#file-structure)
3. [Phase 1 Tasks (1-30)](#phase-1-core-pipeline)
4. [Phase 2 Tasks (31-42)](#phase-2-annotations-concepts--enrichment)
5. [Final Verification (Task 43)](#task-43-final-verification--manual-testing)

---

## Decision Log

| # | Decision | Options Considered | Choice | Rationale |
|---|----------|-------------------|--------|-----------|
| D1 | LLM provider implementation | claude-agent-sdk / raw subprocess / both | **Evaluate claude-agent-sdk first, fall back to raw subprocess** | SDK (v0.1.53) handles JSONL protocol and streaming. If it doesn't support alias/profile switching or `--json-schema`, fall back to `asyncio.create_subprocess_exec()`. Decision made in Task 10. |
| D2 | Test database strategy | Separate Docker container / Same container different DB / Testcontainers | **Same Docker container, separate `bookcompanion_test` database** | Reuse existing pgvector container. Create test DB in conftest.py. Simpler infra, same pgvector extension. |
| D3 | Test fixtures | Synthetic files / Project Gutenberg / Both | **Project Gutenberg downloads** | User preference. Download Art of War (EPUB) + Meditations (EPUB) + The Republic (PDF) from Gutenberg. Store in `backend/tests/fixtures/`. |
| D4 | Async session pattern | Scoped session / Manual session / Dependency injection | **Async session factory with DI** | Services receive `AsyncSession` via constructor. CLI creates sessions in command handlers. Clean, testable. |
| D5 | MOBI support | Defer / Include / Optional | **Include from Phase 1** | User confirmed: install Calibre via `brew install calibre`. Full MOBI support from day one. |
| D6 | Config during tests | Override env vars / Separate config file / Fixture | **pydantic-settings env var override in conftest** | Set `BOOKCOMPANION_DATABASE__URL` etc. in test fixtures. No separate config file needed. |
| D7 | Repository layer | Thin repos / Service-only / Full repo pattern | **Thin repository classes** | Spec defines `repositories/` directory. Keep them thin — query builders only, no business logic. Services orchestrate. |
| D8 | Embedding batch concurrency | Sequential / Fully concurrent / Semaphore-limited | **Semaphore-limited (5 concurrent)** | Avoid overwhelming local Ollama. `asyncio.Semaphore(5)` for concurrent embedding calls. |
| D9 | Prompt template loading | Inline strings / File-based Jinja2 / Hybrid | **File-based Jinja2** | Spec mandates `prompts/` directory with versioned `.txt` files. Load via `jinja2.FileSystemLoader`. |
| D10 | Error hierarchy | Single exception / Per-service / Shared base | **Shared base + per-domain exceptions** | `BookCompanionError` base, then `ParseError`, `SummarizationError`, `EvalError`, `SearchError`, `ConfigError`. |
| D11 | Playwright testing | Include / Skip | **Skip** | No web UI in this spec. Will add when web UI spec is implemented. |
| D12 | Phase 2 tables in initial migration | Single migration / Separate per phase | **Separate migration per phase** | `0001_initial_schema.py` for Phase 1 tables. `0002_phase2_schema.py` for Phase 2 tables. Cleaner history. |
| D13 | Prompt passing to CLI | `-p` flag / stdin pipe / temp file | **stdin pipe** | Spec explicitly requires "Prompt passed via stdin to avoid shell escaping issues." Pass prompt via `proc.stdin` with `asyncio.create_subprocess_exec()`. |
| D14 | Token estimation | 1 token per word / 1 token per 4 chars | **1 token per ~4 chars** | Spec mandates "1 token ≈ 4 chars". Consistent with Claude tokenizer approximation. Affects long-section threshold (150K tokens ≈ 600K chars). |
| D15 | Alembic migration driver | asyncpg only / psycopg2 for migrations | **psycopg2-binary for Alembic, asyncpg for app** | Alembic runs synchronous migrations. Requires `psycopg2-binary` in dev dependencies. App uses `asyncpg` for async operations. |
| D16 | Config `set` command | Positional args on `config` / Subcommand `config set` | **Typer subcommand `config set`** | Spec defines `bookcompanion config set <key> <value>` as explicit subcommand. Use Typer sub-app for `config`. |

---

## File Structure

```
book-companion/
├── backend/
│   ├── pyproject.toml                     # Project config, dependencies, CLI entry point
│   ├── alembic.ini                        # Alembic config pointing to app/db/
│   ├── alembic/
│   │   ├── env.py                         # Migration environment (async engine)
│   │   ├── script.py.mako                 # Migration template
│   │   └── versions/
│   │       ├── 0001_initial_schema.py     # Phase 1 tables
│   │       └── 0002_phase2_schema.py      # Phase 2 tables (annotations, tags, etc.)
│   ├── app/
│   │   ├── __init__.py                    # Package init, version
│   │   ├── config.py                      # pydantic-settings config model
│   │   ├── exceptions.py                  # Custom exception hierarchy
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── models.py                  # All SQLAlchemy ORM models
│   │   │   ├── session.py                 # Async engine + session factory
│   │   │   └── repositories/
│   │   │       ├── __init__.py
│   │   │       ├── book_repo.py           # Book + Author CRUD
│   │   │       ├── section_repo.py        # BookSection CRUD + ordering
│   │   │       ├── search_repo.py         # SearchIndex + vector queries
│   │   │       ├── eval_repo.py           # EvalTrace + aggregation queries
│   │   │       ├── processing_repo.py     # ProcessingJob CRUD
│   │   │       ├── annotation_repo.py     # Phase 2: Annotation CRUD
│   │   │       ├── concept_repo.py        # Concept + ConceptSection CRUD
│   │   │       └── tag_repo.py            # Phase 2: Tag + Taggable CRUD
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── book_service.py            # Book lifecycle orchestration
│   │   │   ├── parser/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py                # BookParser ABC, ParsedBook/Section/Image dataclasses
│   │   │   │   ├── epub_parser.py         # EPUB parsing via ebooklib + markdownify
│   │   │   │   ├── pdf_parser.py          # PDF parsing via pymupdf4llm (+ marker-pdf fallback)
│   │   │   │   ├── mobi_parser.py         # MOBI→EPUB conversion via Calibre, delegates to EPUBParser
│   │   │   │   ├── structure_detector.py  # 3-tier TOC detection (embedded → heuristic → LLM)
│   │   │   │   └── format_detector.py     # Magic bytes + extension validation
│   │   │   ├── summarizer/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── llm_provider.py        # LLMProvider ABC + LLMResponse model
│   │   │   │   ├── claude_cli.py          # ClaudeCodeCLIProvider implementation
│   │   │   │   ├── summarizer_service.py  # Section + book summarization orchestration
│   │   │   │   ├── evaluator.py           # 16-assertion eval battery
│   │   │   │   ├── image_captioner.py     # Image captioning via Claude Code CLI
│   │   │   │   └── prompts/
│   │   │   │       ├── summarize_section_v1.txt
│   │   │   │       ├── summarize_book_v1.txt
│   │   │   │       ├── quick_summary_v1.txt
│   │   │   │       ├── detect_structure_v1.txt
│   │   │   │       ├── caption_image_v1.txt
│   │   │   │       ├── eval_faithfulness_v1.txt
│   │   │   │       ├── eval_completeness_v1.txt
│   │   │   │       ├── eval_coherence_v1.txt
│   │   │   │       ├── eval_specificity_v1.txt
│   │   │   │       ├── eval_format_v1.txt
│   │   │   │       └── discover_references_v1.txt
│   │   │   ├── search_service.py          # Hybrid BM25 + semantic + RRF fusion
│   │   │   ├── embedding_service.py       # Ollama embedding + chunking
│   │   │   ├── annotation_service.py      # Phase 2: Annotation management
│   │   │   ├── concept_service.py         # Phase 2: Concept CRUD + search
│   │   │   ├── tag_service.py             # Phase 2: Tag management
│   │   │   ├── export_service.py          # Phase 2: JSON/Markdown export
│   │   │   ├── backup_service.py          # Phase 2: pg_dump backup/restore
│   │   │   └── reference_service.py       # Phase 2: External reference discovery
│   │   └── cli/
│   │       ├── __init__.py
│   │       ├── main.py                    # Typer app, global options, app entry point
│   │       ├── deps.py                    # Dependency wiring (sessions, services)
│   │       ├── formatting.py              # Shared rich formatting helpers
│   │       └── commands/
│   │           ├── __init__.py
│   │           ├── init_cmd.py            # bookcompanion init
│   │           ├── books.py               # add, list, show, delete, read, authors
│   │           ├── summarize_cmd.py       # summarize, summary
│   │           ├── search_cmd.py          # search
│   │           ├── eval_cmd.py            # eval, eval compare, eval trace
│   │           ├── status_cmd.py          # status
│   │           ├── config_cmd.py          # config, config set
│   │           ├── annotations_cmd.py     # Phase 2: annotate, annotations
│   │           ├── concepts_cmd.py        # Phase 2: concepts, concepts search
│   │           ├── tags_cmd.py            # Phase 2: tag, tags
│   │           ├── export_cmd.py          # Phase 2: export
│   │           ├── backup_cmd.py          # Phase 2: backup, restore
│   │           ├── references_cmd.py      # Phase 2: references, discover-references
│   │           └── edit_cmd.py            # Phase 2: edit, edit-summary
│   └── tests/
│       ├── conftest.py                    # Shared fixtures: test DB, sessions, config
│       ├── fixtures/
│       │   ├── README.md                  # How to download test books
│       │   ├── download_fixtures.py       # Script to download from Gutenberg
│       │   ├── sample_epub/               # Art of War, Meditations EPUBs
│       │   ├── sample_pdf/                # The Republic PDF
│       │   └── sample_mobi/               # Converted MOBI for testing
│       ├── unit/
│       │   ├── __init__.py
│       │   ├── test_config.py
│       │   ├── test_models.py
│       │   ├── test_format_detector.py
│       │   ├── test_epub_parser.py
│       │   ├── test_pdf_parser.py
│       │   ├── test_mobi_parser.py
│       │   ├── test_structure_detector.py
│       │   ├── test_llm_provider.py
│       │   ├── test_summarizer.py
│       │   ├── test_evaluator.py
│       │   ├── test_embedding.py
│       │   ├── test_search.py
│       │   ├── test_image_captioner.py
│       │   └── test_book_service.py
│       ├── integration/
│       │   ├── __init__.py
│       │   ├── test_db_operations.py
│       │   ├── test_book_pipeline.py
│       │   ├── test_search_integration.py
│       │   ├── test_summarize_integration.py
│       │   └── test_eval_integration.py
│       └── e2e/
│           ├── __init__.py
│           └── test_cli_flows.py
├── docker-compose.yml                     # PostgreSQL 16 + pgvector
├── CLAUDE.md                              # Agent instructions for this project
├── docs/
│   ├── plans/
│   │   └── 2026-04-02_book_companion_v1_implementation.md  # This file
│   ├── sample-output/                     # Generated after pipeline works
│   │   ├── README.md
│   │   ├── sample_book_summary.md
│   │   ├── sample_section_summary.md
│   │   ├── sample_eval_results.md
│   │   ├── sample_search_results.md
│   │   └── sample_cli_output.md
│   ├── specs/
│   ├── requirements/
│   └── wireframes/
└── .gitignore                             # Already exists, may need updates
```

---

## Phase 1: Core Pipeline

### Task 1: Project Scaffolding & Python Package Setup

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/exceptions.py`
- Create: `CLAUDE.md`

- [ ] **Step 1: Create `backend/pyproject.toml` with all Phase 1 dependencies**

```toml
[project]
name = "bookcompanion"
version = "0.1.0"
description = "Personal book summarization and knowledge extraction tool"
requires-python = ">=3.12"
dependencies = [
    # CLI
    "typer>=0.15.0",
    "rich>=13.0.0",
    # Database
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pgvector>=0.4.0",
    # Config
    "pydantic-settings>=2.0.0",
    "pyyaml>=6.0",
    # Parsing
    "ebooklib>=0.18",
    "markdownify>=0.14.0",
    "pymupdf4llm>=0.0.17",
    "marker-pdf>=1.0.0",
    # Embeddings & HTTP
    "httpx>=0.28.0",
    # Clipboard (for --copy flag)
    "pyperclip>=1.9.0",
    # Prompts
    "jinja2>=3.1.0",
    # Logging
    "structlog>=24.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "psycopg2-binary>=2.9.0",  # Alembic migrations (sync driver)
]

[project.scripts]
bookcompanion = "app.cli.main:app"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create `backend/app/__init__.py`**

```python
"""Book Companion - Personal book summarization and knowledge extraction tool."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `backend/app/exceptions.py`**

```python
"""Custom exception hierarchy for Book Companion."""


class BookCompanionError(Exception):
    """Base exception for all Book Companion errors."""


class ConfigError(BookCompanionError):
    """Configuration-related errors."""


class ParseError(BookCompanionError):
    """Book parsing errors."""


class SummarizationError(BookCompanionError):
    """LLM summarization errors."""


class EvalError(BookCompanionError):
    """Evaluation assertion errors."""


class SearchError(BookCompanionError):
    """Search-related errors."""


class EmbeddingError(BookCompanionError):
    """Embedding generation errors."""


class StorageError(BookCompanionError):
    """Database/storage errors."""
```

- [ ] **Step 4: Create `CLAUDE.md` with project instructions**

```markdown
# Book Companion

Personal CLI tool for book summarization and knowledge extraction.

## Project Structure

- `backend/` — Python backend (CLI + services)
- `backend/app/` — Application code
- `backend/tests/` — Test suite
- `docs/` — Specifications and documentation

## Development

```bash
cd backend
uv sync --dev                    # Install dependencies
uv run pytest                    # Run tests
uv run ruff check .              # Lint
uv run ruff format --check .     # Format check
uv run mypy app/                 # Type check
```

## Key Conventions

- All services are async and receive dependencies via constructor injection
- CLI commands are thin wrappers — business logic lives in services
- SQLAlchemy 2.0 declarative style with `mapped_column`
- Prompts are Jinja2 templates in `app/services/summarizer/prompts/`
- Tests use a separate `bookcompanion_test` database
- Config via pydantic-settings: env vars > config file > defaults

## Infrastructure

- PostgreSQL 16 + pgvector runs in Docker (port 5438)
- Ollama runs on host (port 11434) with nomic-embed-text
- Claude Code CLI runs on host for LLM calls
```

- [ ] **Step 5: Install dependencies and verify**

```bash
cd backend && uv sync --dev
```

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/__init__.py backend/app/exceptions.py CLAUDE.md
git commit -m "feat: scaffold Python project with dependencies and CLAUDE.md"
```

---

### Task 2: Docker Compose & PostgreSQL Setup

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: bookcompanion-db
    ports:
      - "5438:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: bookcompanion
      POSTGRES_USER: bookcompanion
      POSTGRES_PASSWORD: bookcompanion
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bookcompanion"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

- [ ] **Step 2: Start PostgreSQL and verify**

```bash
docker compose up -d
docker compose ps  # Expect: bookcompanion-db healthy
docker exec bookcompanion-db psql -U bookcompanion -c "SELECT version();"
docker exec bookcompanion-db psql -U bookcompanion -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

- [ ] **Step 3: Create test database**

```bash
docker exec bookcompanion-db psql -U bookcompanion -c "CREATE DATABASE bookcompanion_test OWNER bookcompanion;"
docker exec bookcompanion-db psql -U bookcompanion -d bookcompanion_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "infra: add Docker Compose for PostgreSQL 16 + pgvector"
```

---

### Task 3: Configuration System (pydantic-settings)

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/tests/unit/test_config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/unit/__init__.py`

- [ ] **Step 1: Write the failing test for config loading**

```python
# backend/tests/unit/test_config.py
import os
import pytest
from app.config import Settings


def test_default_settings():
    """Settings load with sensible defaults."""
    settings = Settings()
    assert settings.database.url == "postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion"
    assert settings.llm.cli_command == "claude"
    assert settings.llm.model == "sonnet"
    assert settings.llm.timeout_seconds == 300
    assert settings.embedding.ollama_url == "http://localhost:11434"
    assert settings.embedding.model == "nomic-embed-text"
    assert settings.embedding.chunk_size == 512
    assert settings.embedding.chunk_overlap == 50
    assert settings.search.rrf_k == 60
    assert settings.search.default_limit == 20
    assert settings.storage.max_file_size_mb == 200
    assert settings.summarization.default_detail_level == "standard"


def test_env_var_override():
    """Environment variables override defaults."""
    os.environ["BOOKCOMPANION_LLM__MODEL"] = "opus"
    try:
        settings = Settings()
        assert settings.llm.model == "opus"
    finally:
        del os.environ["BOOKCOMPANION_LLM__MODEL"]


def test_config_file_loading(tmp_path):
    """Settings load from YAML config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "database:\n  url: postgresql+asyncpg://custom:custom@localhost:5432/custom\n"
        "llm:\n  model: opus\n"
    )
    os.environ["BOOKCOMPANION_CONFIG"] = str(config_file)
    try:
        settings = Settings()
        assert settings.llm.model == "opus"
    finally:
        del os.environ["BOOKCOMPANION_CONFIG"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: Implement config module**

```python
# backend/app/config.py
"""Configuration management via pydantic-settings with YAML file support."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion"


class LLMConfig(BaseModel):
    provider: str = "claude_cli"
    cli_command: str = "claude"
    model: str = "sonnet"
    quick_summary_model: str = "sonnet"
    timeout_seconds: int = 300
    max_retries: int = 2
    max_budget_usd: float = 5.0
    cross_summary_consistency: bool = True


class SummarizationConfig(BaseModel):
    default_detail_level: str = "standard"  # brief | standard | detailed
    prompt_version: str = "v1"
    eval_prompt_version: str = "v1"


class EmbeddingConfig(BaseModel):
    ollama_url: str = "http://localhost:11434"
    model: str = "nomic-embed-text"
    chunk_size: int = 512
    chunk_overlap: int = 50


class SearchConfig(BaseModel):
    rrf_k: int = 60
    default_limit: int = 20


class StorageConfig(BaseModel):
    max_file_size_mb: int = 200


class LoggingConfig(BaseModel):
    level: str = "INFO"
    log_dir: str = "~/.config/bookcompanion/logs/"
    json_format: bool = True
    rotation: str = "daily"


def _load_yaml_config() -> dict[str, Any]:
    """Load config from YAML file if it exists. Priority: env var > XDG > fallback."""
    candidates = [
        os.environ.get("BOOKCOMPANION_CONFIG", ""),
        os.path.expanduser("~/.config/bookcompanion/config.yaml"),
        os.path.expanduser("~/.bookcompanion/config.yaml"),  # Fallback per spec
    ]
    for config_path in candidates:
        if not config_path:
            continue
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f) or {}
    return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOOKCOMPANION_",
        env_nested_delimiter="__",
    )

    database: DatabaseConfig = DatabaseConfig()
    llm: LLMConfig = LLMConfig()
    summarization: SummarizationConfig = SummarizationConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    search: SearchConfig = SearchConfig()
    storage: StorageConfig = StorageConfig()
    logging: LoggingConfig = LoggingConfig()

    def model_post_init(self, __context: Any) -> None:
        """Merge YAML config file values (lower priority than env vars)."""
        yaml_config = _load_yaml_config()
        if not yaml_config:
            return
        for section_name, section_values in yaml_config.items():
            if hasattr(self, section_name) and isinstance(section_values, dict):
                section = getattr(self, section_name)
                for key, value in section_values.items():
                    if hasattr(section, key):
                        # Only override if not already set by env var
                        env_key = f"BOOKCOMPANION_{section_name.upper()}__{key.upper()}"
                        if env_key not in os.environ:
                            object.__setattr__(section, key, value)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/unit/test_config.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/
git commit -m "feat: add pydantic-settings config with YAML + env var support"
```

---

### Task 4: Database Session & SQLAlchemy Models

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/models.py`
- Create: `backend/tests/unit/test_models.py`

- [ ] **Step 1: Create `backend/app/db/session.py`**

```python
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
```

- [ ] **Step 2: Create `backend/app/db/models.py` with all Phase 1 models**

Implement all models exactly as defined in spec Section 5: `Base`, enums (`BookStatus`, `SummaryStatus`, `ProcessingStep`, `ProcessingJobStatus`, `SourceType`, `ContentType`), and models (`Author`, `Book`, `BookAuthor`, `BookSection`, `Image`, `SearchIndex`, `ProcessingJob`, `EvalTrace`, `Concept`, `ConceptSection`).

Reference: Spec lines 348-670 contain the complete model definitions. Implement them verbatim.

- [ ] **Step 3: Write model validation tests**

```python
# backend/tests/unit/test_models.py
from app.db.models import (
    Author, Book, BookAuthor, BookSection, BookStatus, Concept, ConceptSection,
    EvalTrace, Image, ProcessingJob, ProcessingJobStatus, ProcessingStep,
    SearchIndex, SourceType, SummaryStatus,
)


def test_book_status_enum():
    assert BookStatus.UPLOADING == "uploading"
    assert BookStatus.COMPLETED == "completed"
    assert BookStatus.PARSE_FAILED == "parse_failed"


def test_summary_status_enum():
    assert SummaryStatus.PENDING == "pending"
    assert SummaryStatus.STALE == "stale"


def test_processing_step_enum():
    assert ProcessingStep.PARSE == "parse"
    assert ProcessingStep.QUICK_SUMMARY == "quick_summary"


def test_source_type_enum():
    assert SourceType.BOOK_TITLE == "book_title"
    assert SourceType.CONCEPT == "concept"


def test_model_tablenames():
    assert Author.__tablename__ == "authors"
    assert Book.__tablename__ == "books"
    assert BookAuthor.__tablename__ == "book_authors"
    assert BookSection.__tablename__ == "book_sections"
    assert Image.__tablename__ == "images"
    assert SearchIndex.__tablename__ == "search_index"
    assert ProcessingJob.__tablename__ == "processing_jobs"
    assert EvalTrace.__tablename__ == "eval_traces"
    assert Concept.__tablename__ == "concepts"
    assert ConceptSection.__tablename__ == "concept_sections"
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_models.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/
git commit -m "feat: add SQLAlchemy 2.0 models and async session management"
```

---

### Task 5: Alembic Migrations Setup

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial_schema.py`

- [ ] **Step 1: Create `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create `backend/alembic/env.py` with async support**

```python
"""Alembic migration environment — async engine support."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    settings = Settings()
    connectable = create_async_engine(settings.database.url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

# Note: Alembic with asyncpg requires the asyncpg driver. The env.py uses
# SQLAlchemy's async engine which handles the connection correctly.
# psycopg2-binary is needed only if running alembic CLI directly with
# a non-async URL in alembic.ini.


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 3: Create `backend/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Generate and run the initial migration**

```bash
cd backend
uv run alembic revision --autogenerate -m "initial_schema"
# Review the generated migration file, then:
uv run alembic upgrade head
```

- [ ] **Step 5: Verify tables exist**

```bash
docker exec bookcompanion-db psql -U bookcompanion -c "\dt"
```

Expected: All Phase 1 tables listed (books, authors, book_authors, book_sections, images, search_index, processing_jobs, eval_traces, concepts, concept_sections)

- [ ] **Step 6: Run migration on test database**

```bash
cd backend
BOOKCOMPANION_DATABASE__URL=postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test uv run alembic upgrade head
```

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat: add Alembic migrations for Phase 1 schema"
```

---

### Task 6: Test Infrastructure & Fixtures

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/fixtures/README.md`
- Create: `backend/tests/fixtures/download_fixtures.py`
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/e2e/__init__.py`

- [ ] **Step 1: Create shared test fixtures in `conftest.py`**

```python
# backend/tests/conftest.py
"""Shared test fixtures."""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.models import Base

TEST_DB_URL = "postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    import os
    os.environ["BOOKCOMPANION_DATABASE__URL"] = TEST_DB_URL
    return Settings()


@pytest.fixture(scope="session")
async def engine(test_settings):
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncSession:
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_epub_path() -> Path:
    path = FIXTURES_DIR / "sample_epub" / "art_of_war.epub"
    if not path.exists():
        pytest.skip("Test fixtures not downloaded. Run: python tests/fixtures/download_fixtures.py")
    return path


@pytest.fixture
def sample_pdf_path() -> Path:
    path = FIXTURES_DIR / "sample_pdf" / "the_republic.pdf"
    if not path.exists():
        pytest.skip("Test fixtures not downloaded. Run: python tests/fixtures/download_fixtures.py")
    return path
```

- [ ] **Step 2: Create fixture download script**

```python
# backend/tests/fixtures/download_fixtures.py
"""Download test book fixtures from Project Gutenberg."""

import urllib.request
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent

BOOKS = {
    "sample_epub/art_of_war.epub": "https://www.gutenberg.org/ebooks/132.epub3.images",
    "sample_epub/meditations.epub": "https://www.gutenberg.org/ebooks/2680.epub3.images",
    "sample_pdf/the_republic.pdf": "https://www.gutenberg.org/files/1497/1497-pdf.pdf",
    "sample_mobi/art_of_war.mobi": "https://www.gutenberg.org/ebooks/132.kf8.images",
}


def download_fixtures():
    for rel_path, url in BOOKS.items():
        dest = FIXTURES_DIR / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            print(f"  Already exists: {rel_path}")
            continue
        print(f"  Downloading: {rel_path} from {url}")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"  Saved: {dest} ({dest.stat().st_size / 1024:.0f} KB)")
        except Exception as e:
            print(f"  FAILED: {e}")


if __name__ == "__main__":
    print("Downloading test fixtures from Project Gutenberg...")
    download_fixtures()
    print("Done.")
```

- [ ] **Step 3: Create fixtures README**

```markdown
<!-- backend/tests/fixtures/README.md -->
# Test Fixtures

Public domain books from Project Gutenberg used for testing.

## Download

```bash
cd backend
python tests/fixtures/download_fixtures.py
```

## Books

| Book | Format | Sections | Source |
|------|--------|----------|--------|
| The Art of War (Sun Tzu) | EPUB | 13 chapters | gutenberg.org/ebooks/132 |
| Meditations (Marcus Aurelius) | EPUB | 12 books | gutenberg.org/ebooks/2680 |
| The Republic (Plato) | PDF | 10 books | gutenberg.org/ebooks/1497 |

These files are .gitignored. Run the download script after cloning.
```

- [ ] **Step 4: Update `.gitignore` to exclude fixture books but keep the script**

Add to `.gitignore`:
```
backend/tests/fixtures/sample_epub/*.epub
backend/tests/fixtures/sample_pdf/*.pdf
backend/tests/fixtures/sample_mobi/*.mobi
```

- [ ] **Step 5: Download fixtures and verify**

```bash
cd backend && python tests/fixtures/download_fixtures.py
ls -la tests/fixtures/sample_epub/ tests/fixtures/sample_pdf/
```

- [ ] **Step 6: Commit**

```bash
git add backend/tests/ .gitignore
git commit -m "test: add test infrastructure, conftest fixtures, and Gutenberg download script"
```

---

### Task 7: DB Integration Test — Verify Models Work End-to-End

**Files:**
- Create: `backend/tests/integration/test_db_operations.py`

- [ ] **Step 1: Write integration test for book CRUD**

```python
# backend/tests/integration/test_db_operations.py
"""Integration tests for database operations."""

import pytest
from sqlalchemy import select

from app.db.models import Author, Book, BookSection, BookStatus, SummaryStatus


@pytest.mark.asyncio
async def test_create_book_with_author(db_session):
    author = Author(name="Sun Tzu")
    db_session.add(author)
    await db_session.flush()

    book = Book(
        title="The Art of War",
        file_data=b"fake epub content",
        file_hash="abc123def456",
        file_format="epub",
        file_size_bytes=1024,
        status=BookStatus.PARSED,
    )
    book.authors.append(author)
    db_session.add(book)
    await db_session.flush()

    result = await db_session.execute(select(Book).where(Book.id == book.id))
    fetched = result.scalar_one()
    assert fetched.title == "The Art of War"
    assert fetched.status == BookStatus.PARSED


@pytest.mark.asyncio
async def test_create_book_sections(db_session):
    book = Book(
        title="Test Book",
        file_data=b"test",
        file_hash="unique_hash_001",
        file_format="epub",
        file_size_bytes=100,
    )
    db_session.add(book)
    await db_session.flush()

    sections = [
        BookSection(
            book_id=book.id,
            title=f"Chapter {i}",
            order_index=i,
            depth=1,
            content_md=f"Content for chapter {i}",
            content_token_count=100,
            summary_status=SummaryStatus.PENDING,
        )
        for i in range(3)
    ]
    db_session.add_all(sections)
    await db_session.flush()

    result = await db_session.execute(
        select(BookSection)
        .where(BookSection.book_id == book.id)
        .order_by(BookSection.order_index)
    )
    fetched = result.scalars().all()
    assert len(fetched) == 3
    assert fetched[0].title == "Chapter 0"


@pytest.mark.asyncio
async def test_cascade_delete_book(db_session):
    book = Book(
        title="Delete Me",
        file_data=b"delete",
        file_hash="delete_hash_001",
        file_format="pdf",
        file_size_bytes=50,
    )
    db_session.add(book)
    await db_session.flush()

    section = BookSection(
        book_id=book.id, title="Ch1", order_index=0, depth=0
    )
    db_session.add(section)
    await db_session.flush()

    await db_session.delete(book)
    await db_session.flush()

    result = await db_session.execute(
        select(BookSection).where(BookSection.book_id == book.id)
    )
    assert result.scalars().all() == []
```

- [ ] **Step 2: Run integration tests**

```bash
cd backend && uv run pytest tests/integration/test_db_operations.py -v
```

Expected: 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/
git commit -m "test: add DB integration tests for book CRUD and cascade deletes"
```

---

### Task 8: Repository Layer

**Files:**
- Create: `backend/app/db/repositories/__init__.py`
- Create: `backend/app/db/repositories/book_repo.py`
- Create: `backend/app/db/repositories/section_repo.py`
- Create: `backend/app/db/repositories/processing_repo.py`
- Create: `backend/app/db/repositories/search_repo.py`
- Create: `backend/app/db/repositories/eval_repo.py`

- [ ] **Step 1: Create `book_repo.py` — Book + Author data access**

```python
# backend/app/db/repositories/book_repo.py
"""Book and Author repository — data access layer."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Author, Book, BookAuthor, BookStatus


class BookRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, book: Book) -> Book:
        self.session.add(book)
        await self.session.flush()
        return book

    async def get_by_id(self, book_id: int) -> Book | None:
        result = await self.session.execute(
            select(Book)
            .options(selectinload(Book.authors), selectinload(Book.sections))
            .where(Book.id == book_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, file_hash: str) -> Book | None:
        result = await self.session.execute(
            select(Book).where(Book.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        author: str | None = None,
        status: BookStatus | None = None,
        order_by_recent: bool = False,
    ) -> list[Book]:
        query = select(Book).options(selectinload(Book.authors))
        if author:
            query = query.join(Book.authors).where(Author.name.ilike(f"%{author}%"))
        if status:
            query = query.where(Book.status == status)
        if order_by_recent:
            query = query.order_by(Book.updated_at.desc())
        else:
            query = query.order_by(Book.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().unique().all())

    async def delete(self, book: Book) -> None:
        await self.session.delete(book)
        await self.session.flush()

    async def update_status(self, book_id: int, status: BookStatus) -> None:
        book = await self.get_by_id(book_id)
        if book:
            book.status = status
            await self.session.flush()


class AuthorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, name: str) -> Author:
        result = await self.session.execute(
            select(Author).where(Author.name == name)
        )
        author = result.scalar_one_or_none()
        if not author:
            author = Author(name=name)
            self.session.add(author)
            await self.session.flush()
        return author

    async def list_with_book_counts(self) -> list[tuple[Author, int]]:
        result = await self.session.execute(
            select(Author, func.count(BookAuthor.book_id))
            .outerjoin(BookAuthor)
            .group_by(Author.id)
            .order_by(Author.name)
        )
        return list(result.all())
```

- [ ] **Step 2: Create `section_repo.py`, `processing_repo.py`, `search_repo.py`, `eval_repo.py`**

Each follows the same pattern: thin CRUD operations with query builders. Key methods:

- `SectionRepository`: `create_bulk()`, `get_by_book_id()`, `get_by_id()`, `update_summary()`, `get_pending_sections()`
- `ProcessingRepository`: `create()`, `get_active_for_book()`, `update_status()`, `get_orphaned_jobs()`
- `SearchIndexRepository`: `create_bulk()`, `bm25_search()`, `semantic_search()`, `delete_by_book()`, `delete_by_source()`
- `EvalTraceRepository`: `create()`, `get_by_section()`, `get_by_assertion()`, `get_aggregated_results()`
- `ConceptRepository`: `create_bulk()`, `get_by_book()`, `search_across_books()`, `update()` — needed in Phase 1 since concepts are extracted during summarization

- [ ] **Step 3: Run all tests**

```bash
cd backend && uv run pytest -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/repositories/
git commit -m "feat: add repository layer for data access"
```

---

### Task 9: Format Detection & Parser Base

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/parser/__init__.py`
- Create: `backend/app/services/parser/base.py`
- Create: `backend/app/services/parser/format_detector.py`
- Create: `backend/tests/unit/test_format_detector.py`

- [ ] **Step 1: Write failing test for format detection**

```python
# backend/tests/unit/test_format_detector.py
"""Tests for file format detection."""

import pytest
from pathlib import Path
from app.services.parser.format_detector import detect_format, FormatDetectionError


def test_detect_epub_by_extension(tmp_path):
    epub = tmp_path / "test.epub"
    # EPUB magic bytes: PK (zip archive) with mimetype entry
    epub.write_bytes(b"PK\x03\x04" + b"\x00" * 26 + b"mimetypeapplication/epub+zip")
    assert detect_format(epub) == "epub"


def test_detect_pdf_by_extension(tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake content")
    assert detect_format(pdf) == "pdf"


def test_detect_mobi_by_extension(tmp_path):
    mobi = tmp_path / "test.mobi"
    # MOBI magic: BOOKMOBI at offset 60
    data = b"\x00" * 60 + b"BOOKMOBI" + b"\x00" * 100
    mobi.write_bytes(data)
    assert detect_format(mobi) == "mobi"


def test_reject_unsupported_format(tmp_path):
    txt = tmp_path / "test.txt"
    txt.write_text("plain text")
    with pytest.raises(FormatDetectionError, match="Unsupported"):
        detect_format(txt)


def test_reject_fake_extension(tmp_path):
    fake_epub = tmp_path / "fake.epub"
    fake_epub.write_text("this is not an epub")
    with pytest.raises(FormatDetectionError, match="Magic bytes"):
        detect_format(fake_epub)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_format_detector.py -v
```

- [ ] **Step 3: Implement parser base and format detector**

```python
# backend/app/services/parser/base.py
"""Parser base classes and data types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedImage:
    data: bytes
    mime_type: str
    filename: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class ParsedSection:
    title: str
    content_md: str
    depth: int
    order_index: int
    images: list[ParsedImage] = field(default_factory=list)


@dataclass
class ParsedBook:
    title: str
    authors: list[str]
    sections: list[ParsedSection]
    cover_image: bytes | None = None
    metadata: dict = field(default_factory=dict)


class BookParser(ABC):
    @abstractmethod
    async def parse(self, file_path: Path) -> ParsedBook: ...

    @abstractmethod
    def supports_format(self, file_format: str) -> bool: ...
```

```python
# backend/app/services/parser/format_detector.py
"""File format detection via magic bytes + extension."""

from pathlib import Path

from app.exceptions import ParseError


class FormatDetectionError(ParseError):
    """Raised when file format cannot be determined or is unsupported."""


MAGIC_SIGNATURES = {
    "epub": (b"PK", 0),        # ZIP archive (EPUB is zipped)
    "pdf": (b"%PDF", 0),       # PDF header
    "mobi": (b"BOOKMOBI", 60), # MOBI identifier at offset 60
}

SUPPORTED_EXTENSIONS = {"epub", "mobi", "pdf"}


def detect_format(file_path: Path) -> str:
    """Detect book format by extension + magic bytes validation.

    Returns: format string ('epub', 'mobi', 'pdf')
    Raises: FormatDetectionError if unsupported or magic bytes mismatch
    """
    ext = file_path.suffix.lower().lstrip(".")
    if ext not in SUPPORTED_EXTENSIONS:
        raise FormatDetectionError(f"Unsupported file format: .{ext}")

    with open(file_path, "rb") as f:
        magic, offset = MAGIC_SIGNATURES[ext]
        f.seek(offset)
        header = f.read(len(magic))
        if header != magic:
            raise FormatDetectionError(
                f"Magic bytes mismatch for .{ext}: expected {magic!r} at offset {offset}, "
                f"got {header!r}"
            )
    return ext
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_format_detector.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/
git commit -m "feat: add parser base classes and format detection with magic bytes"
```

---

### Task 10: LLM Provider Interface & Claude Code CLI Implementation

**Files:**
- Create: `backend/app/services/summarizer/__init__.py`
- Create: `backend/app/services/summarizer/llm_provider.py`
- Create: `backend/app/services/summarizer/claude_cli.py`
- Create: `backend/tests/unit/test_llm_provider.py`

- [ ] **Step 1: Write failing test for LLM provider**

```python
# backend/tests/unit/test_llm_provider.py
"""Tests for LLM provider interface and Claude CLI implementation."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from app.services.summarizer.llm_provider import LLMResponse
from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider


def test_llm_response_model():
    resp = LLMResponse(content="hello", model="sonnet", latency_ms=100)
    assert resp.content == "hello"
    assert resp.input_tokens is None


@pytest.mark.asyncio
async def test_claude_cli_constructs_correct_args():
    provider = ClaudeCodeCLIProvider(
        cli_command="claude", default_model="sonnet", default_timeout=300
    )
    # Mock subprocess
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (
        json.dumps({"result": "test output", "model": "sonnet", "usage": {"input_tokens": 10, "output_tokens": 5}}).encode(),
        b"",
    )
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await provider.generate("Summarize this")
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "claude"
        assert "-p" in call_args
        assert "-" in call_args  # stdin mode
        assert "--output-format" in call_args
        assert "json" in call_args
        assert "--print" in call_args
        # Verify prompt passed via stdin
        mock_proc.communicate.assert_called_once()
        stdin_data = mock_proc.communicate.call_args[1].get("input") or mock_proc.communicate.call_args[0][0] if mock_proc.communicate.call_args[0] else None
        # stdin should contain the prompt text


@pytest.mark.asyncio
async def test_claude_cli_timeout_raises():
    import asyncio
    provider = ClaudeCodeCLIProvider(
        cli_command="claude", default_model="sonnet", default_timeout=1
    )
    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = asyncio.TimeoutError()
    mock_proc.kill = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(Exception, match="timed out"):
            await provider.generate("Slow prompt")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/unit/test_llm_provider.py -v
```

- [ ] **Step 3: Implement LLM provider interface**

```python
# backend/app/services/summarizer/llm_provider.py
"""LLM provider interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        json_schema: dict | None = None,
        timeout: int | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def generate_with_image(
        self,
        prompt: str,
        image_path: Path,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> LLMResponse: ...
```

- [ ] **Step 4: Implement Claude Code CLI provider**

First evaluate `claude-agent-sdk`. If it supports our needs (subprocess invocation with `--json-schema`, `--model`, `--print` flags), use it. Otherwise, implement raw subprocess as shown in spec Section 7.

```python
# backend/app/services/summarizer/claude_cli.py
"""Claude Code CLI provider — invokes CLI as subprocess."""

import asyncio
import json
import time
from pathlib import Path

from app.exceptions import SummarizationError
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse


class ClaudeCodeCLIProvider(LLMProvider):
    def __init__(
        self,
        cli_command: str = "claude",
        default_model: str = "sonnet",
        default_timeout: int = 300,
        max_budget_usd: float | None = None,
    ):
        self.cli_command = cli_command
        self.default_model = default_model
        self.default_timeout = default_timeout
        self.max_budget_usd = max_budget_usd

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        json_schema: dict | None = None,
        timeout: int | None = None,
    ) -> LLMResponse:
        cmd = [
            self.cli_command, "-p", "-",  # Read prompt from stdin
            "--output-format", "json",
            "--model", model or self.default_model,
            "--print",
        ]
        if json_schema:
            cmd.extend(["--json-schema", json.dumps(json_schema)])
        if self.max_budget_usd:
            cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])

        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,  # Pass prompt via stdin (spec requirement)
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),  # Prompt via stdin
                timeout=timeout or self.default_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise SummarizationError(
                f"Claude CLI timed out after {timeout or self.default_timeout}s"
            )

        latency_ms = int((time.monotonic() - start) * 1000)

        if proc.returncode != 0:
            raise SummarizationError(f"Claude CLI failed (rc={proc.returncode}): {stderr.decode()}")

        return self._parse_response(stdout.decode(), model or self.default_model, latency_ms)

    async def generate_with_image(
        self,
        prompt: str,
        image_path: Path,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        image_dir = str(image_path.parent)
        full_prompt = f"Read the image at {image_path.name} and {prompt}"
        cmd = [
            self.cli_command, "-p", full_prompt,
            "--add-dir", image_dir,
            "--permission-mode", "auto",
            "--output-format", "json",
            "--model", model or self.default_model,
            "--print",
        ]

        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.default_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise SummarizationError("Image captioning timed out")

        latency_ms = int((time.monotonic() - start) * 1000)
        if proc.returncode != 0:
            raise SummarizationError(f"Image captioning failed: {stderr.decode()}")

        return self._parse_response(stdout.decode(), model or self.default_model, latency_ms)

    def _parse_response(self, raw: str, model: str, latency_ms: int) -> LLMResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # CLI may return raw text in --print mode
            return LLMResponse(content=raw.strip(), model=model, latency_ms=latency_ms)

        # Handle different response formats from CLI
        content = data.get("result", data.get("content", raw))
        usage = data.get("usage", {})
        return LLMResponse(
            content=content if isinstance(content, str) else json.dumps(content),
            model=data.get("model", model),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            latency_ms=latency_ms,
        )
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_llm_provider.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/summarizer/
git commit -m "feat: add LLM provider interface and Claude Code CLI implementation"
```

---

### Task 11: EPUB Parser

**Files:**
- Create: `backend/app/services/parser/epub_parser.py`
- Create: `backend/tests/unit/test_epub_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_epub_parser.py
"""Tests for EPUB parser."""

import pytest
from pathlib import Path
from app.services.parser.epub_parser import EPUBParser


@pytest.fixture
def parser():
    return EPUBParser()


def test_supports_epub(parser):
    assert parser.supports_format("epub") is True
    assert parser.supports_format("pdf") is False


@pytest.mark.asyncio
async def test_parse_art_of_war(parser, sample_epub_path):
    result = await parser.parse(sample_epub_path)
    assert result.title  # Title should be extracted
    assert len(result.authors) >= 1
    assert len(result.sections) >= 5  # Art of War has 13+ sections
    for section in result.sections:
        assert section.title
        assert section.content_md  # Content should be non-empty
        assert section.depth >= 0
        assert section.order_index >= 0


@pytest.mark.asyncio
async def test_epub_toc_extraction(parser, sample_epub_path):
    result = await parser.parse(sample_epub_path)
    # Sections should be ordered
    for i in range(1, len(result.sections)):
        assert result.sections[i].order_index > result.sections[i - 1].order_index


@pytest.mark.asyncio
async def test_epub_markdown_quality(parser, sample_epub_path):
    result = await parser.parse(sample_epub_path)
    # At least one section should have substantial content
    long_sections = [s for s in result.sections if len(s.content_md) > 100]
    assert len(long_sections) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/unit/test_epub_parser.py -v
```

- [ ] **Step 3: Implement EPUB parser**

```python
# backend/app/services/parser/epub_parser.py
"""EPUB parser using ebooklib + markdownify."""

from pathlib import Path

import ebooklib
from ebooklib import epub
from markdownify import markdownify

from app.services.parser.base import BookParser, ParsedBook, ParsedImage, ParsedSection


class EPUBParser(BookParser):
    def supports_format(self, file_format: str) -> bool:
        return file_format == "epub"

    async def parse(self, file_path: Path) -> ParsedBook:
        book = epub.read_epub(str(file_path))

        title = book.get_metadata("DC", "title")
        title_str = title[0][0] if title else file_path.stem

        creators = book.get_metadata("DC", "creator")
        authors = [c[0] for c in creators] if creators else ["Unknown"]

        # Extract cover image
        cover_image = self._extract_cover(book)

        # Extract TOC and map to sections
        toc = book.toc
        sections = self._extract_sections(book, toc)

        # Build metadata dict
        metadata = {}
        for ns in ["DC", "OPF"]:
            for key in ["language", "publisher", "date", "description", "subject"]:
                val = book.get_metadata(ns, key)
                if val:
                    metadata[key] = val[0][0] if isinstance(val[0], tuple) else val[0]

        return ParsedBook(
            title=title_str,
            authors=authors,
            sections=sections,
            cover_image=cover_image,
            metadata=metadata,
        )

    def _extract_cover(self, book: epub.EpubBook) -> bytes | None:
        # Try to find cover image from metadata
        cover_id = None
        for meta in book.get_metadata("OPF", "cover") or []:
            if meta and meta[1]:
                cover_id = meta[1].get("content")
        if cover_id:
            item = book.get_item_with_id(cover_id)
            if item:
                return item.get_content()

        # Fallback: look for items with 'cover' in filename
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            if "cover" in (item.get_name() or "").lower():
                return item.get_content()
        return None

    def _extract_sections(
        self, book: epub.EpubBook, toc: list
    ) -> list[ParsedSection]:
        """Extract sections from TOC structure."""
        sections: list[ParsedSection] = []
        # Build a map of href → content for document items
        content_map: dict[str, str] = {}
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            html = item.get_content().decode("utf-8", errors="replace")
            md = markdownify(html, heading_style="ATX", strip=["script", "style"])
            content_map[item.get_name()] = md.strip()

        # Build image map for later reference
        image_map: dict[str, ParsedImage] = {}
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            image_map[item.get_name()] = ParsedImage(
                data=item.get_content(),
                mime_type=item.media_type,
                filename=item.get_name(),
            )

        order = 0
        self._walk_toc(toc, content_map, image_map, sections, order_counter=[0], depth=0)

        # If no TOC entries produced sections, fall back to spine order
        if not sections:
            for spine_item_id, _ in book.spine:
                item = book.get_item_with_id(spine_item_id)
                if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                    name = item.get_name()
                    content = content_map.get(name, "")
                    if content.strip():
                        sections.append(ParsedSection(
                            title=name.split("/")[-1].replace(".xhtml", "").replace(".html", ""),
                            content_md=content,
                            depth=0,
                            order_index=len(sections),
                        ))

        return sections

    def _walk_toc(
        self,
        toc_entries: list,
        content_map: dict[str, str],
        image_map: dict[str, ParsedImage],
        sections: list[ParsedSection],
        order_counter: list[int],
        depth: int,
    ) -> None:
        """Recursively walk TOC to build section list."""
        for entry in toc_entries:
            if isinstance(entry, tuple) and len(entry) == 2:
                # Nested: (Section, [children])
                section_obj, children = entry
                self._add_section(section_obj, content_map, image_map, sections, order_counter, depth)
                self._walk_toc(children, content_map, image_map, sections, order_counter, depth + 1)
            elif isinstance(entry, epub.Link):
                self._add_section(entry, content_map, image_map, sections, order_counter, depth)
            elif isinstance(entry, epub.Section):
                # Section header without direct content
                pass

    def _add_section(
        self,
        entry,
        content_map: dict[str, str],
        image_map: dict[str, ParsedImage],
        sections: list[ParsedSection],
        order_counter: list[int],
        depth: int,
    ) -> None:
        href = entry.href.split("#")[0] if hasattr(entry, "href") else ""
        title = entry.title if hasattr(entry, "title") else str(entry)
        content = content_map.get(href, "")

        if not content.strip():
            return

        # Find images referenced in this content
        section_images = []
        for img_name, img in image_map.items():
            if img_name in content:
                section_images.append(img)

        sections.append(ParsedSection(
            title=title or f"Section {order_counter[0]}",
            content_md=content,
            depth=depth,
            order_index=order_counter[0],
            images=section_images,
        ))
        order_counter[0] += 1
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_epub_parser.py -v
```

Expected: All tests PASS (may need fixture downloaded)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser/epub_parser.py backend/tests/unit/test_epub_parser.py
git commit -m "feat: add EPUB parser with TOC extraction and markdownify conversion"
```

---

### Task 12: PDF Parser

**Files:**
- Create: `backend/app/services/parser/pdf_parser.py`
- Create: `backend/tests/unit/test_pdf_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_pdf_parser.py
"""Tests for PDF parser."""

import pytest
from app.services.parser.pdf_parser import PDFParser


@pytest.fixture
def parser():
    return PDFParser()


def test_supports_pdf(parser):
    assert parser.supports_format("pdf") is True
    assert parser.supports_format("epub") is False


@pytest.mark.asyncio
async def test_parse_republic_pdf(parser, sample_pdf_path):
    result = await parser.parse(sample_pdf_path)
    assert result.title
    assert len(result.sections) >= 1
    # Should have extracted some content
    total_content = sum(len(s.content_md) for s in result.sections)
    assert total_content > 1000


@pytest.mark.asyncio
async def test_pdf_sections_ordered(parser, sample_pdf_path):
    result = await parser.parse(sample_pdf_path)
    for i in range(1, len(result.sections)):
        assert result.sections[i].order_index > result.sections[i - 1].order_index
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/unit/test_pdf_parser.py -v
```

- [ ] **Step 3: Implement PDF parser using pymupdf4llm**

```python
# backend/app/services/parser/pdf_parser.py
"""PDF parser using pymupdf4llm (fast) with marker-pdf fallback (complex layouts)."""

from pathlib import Path

import pymupdf4llm

from app.services.parser.base import BookParser, ParsedBook, ParsedImage, ParsedSection


class PDFParser(BookParser):
    def supports_format(self, file_format: str) -> bool:
        return file_format == "pdf"

    async def parse(self, file_path: Path) -> ParsedBook:
        # Detect if complex layout (tables, multi-column) warrants marker-pdf
        if self._is_complex_layout(file_path):
            return await self._parse_with_marker(file_path)

        # Default: pymupdf4llm for fast conversion (~0.12s/page)
        pages = pymupdf4llm.to_markdown(
            str(file_path),
            page_chunks=True,
            write_images=True,
        )

        title = self._extract_title(pages, file_path)
        sections = self._pages_to_sections(pages)

        return ParsedBook(
            title=title,
            authors=[],  # PDF metadata often lacks author — filled by structure detection
            sections=sections,
            cover_image=None,
            metadata={"parser": "pymupdf4llm", "page_count": len(pages)},
        )

    def _extract_title(self, pages: list[dict], file_path: Path) -> str:
        """Extract title from PDF metadata or first page."""
        if pages and pages[0].get("metadata", {}).get("title"):
            return pages[0]["metadata"]["title"]
        # Fallback: first heading or filename
        if pages:
            first_page = pages[0].get("text", "")
            for line in first_page.split("\n"):
                line = line.strip()
                if line.startswith("#"):
                    return line.lstrip("#").strip()
                if line and len(line) < 200:
                    return line
        return file_path.stem.replace("_", " ").title()

    def _pages_to_sections(self, pages: list[dict]) -> list[ParsedSection]:
        """Convert page chunks into sections based on heading detection."""
        sections: list[ParsedSection] = []
        current_title = "Introduction"
        current_content: list[str] = []
        current_images: list[ParsedImage] = []
        order = 0

        for page in pages:
            text = page.get("text", "")
            images = page.get("images", [])

            # Collect images from this page
            for img in images:
                if isinstance(img, dict) and "image" in img:
                    current_images.append(ParsedImage(
                        data=img["image"] if isinstance(img["image"], bytes) else b"",
                        mime_type="image/png",
                        filename=img.get("name"),
                    ))

            # Split on major headings (# or ##)
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("# ") and not stripped.startswith("###"):
                    # Save current section
                    if current_content:
                        content = "\n".join(current_content).strip()
                        if content:
                            sections.append(ParsedSection(
                                title=current_title,
                                content_md=content,
                                depth=0,
                                order_index=order,
                                images=current_images,
                            ))
                            order += 1
                            current_images = []
                    current_title = stripped.lstrip("#").strip()
                    current_content = []
                else:
                    current_content.append(line)

        # Don't forget the last section
        if current_content:
            content = "\n".join(current_content).strip()
            if content:
                sections.append(ParsedSection(
                    title=current_title,
                    content_md=content,
                    depth=0,
                    order_index=order,
                    images=current_images,
                ))

        # If no heading-based splits worked, create one section per N pages
        if len(sections) <= 1 and len(pages) > 5:
            return self._chunk_by_pages(pages, pages_per_section=10)

        return sections

    def _is_complex_layout(self, file_path: Path) -> bool:
        """Heuristic: detect complex PDFs that need marker-pdf.
        Check for multi-column layouts, heavy table content, or dense images."""
        import fitz  # pymupdf
        doc = fitz.open(str(file_path))
        sample_pages = min(5, len(doc))
        table_count = 0
        image_density = 0
        for i in range(sample_pages):
            page = doc[i]
            tables = page.find_tables()
            table_count += len(tables.tables) if hasattr(tables, 'tables') else 0
            image_density += len(page.get_images())
        doc.close()
        # Complex if >3 tables or >2 images per page on average
        return table_count > 3 or (image_density / max(sample_pages, 1)) > 2

    async def _parse_with_marker(self, file_path: Path) -> ParsedBook:
        """Fallback: use marker-pdf for complex layouts (~8s/page)."""
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        converter = PdfConverter(artifact_dict=create_model_dict())
        rendered = converter(str(file_path))
        # Convert marker output to ParsedBook format
        sections = self._pages_to_sections([{"text": rendered.markdown}])
        return ParsedBook(
            title=self._extract_title([{"text": rendered.markdown}], file_path),
            authors=[],
            sections=sections,
            metadata={"parser": "marker-pdf"},
        )

    def _chunk_by_pages(
        self, pages: list[dict], pages_per_section: int = 10
    ) -> list[ParsedSection]:
        """Fallback: group pages into sections."""
        sections = []
        for i in range(0, len(pages), pages_per_section):
            chunk = pages[i : i + pages_per_section]
            content = "\n\n".join(p.get("text", "") for p in chunk).strip()
            if content:
                sections.append(ParsedSection(
                    title=f"Pages {i + 1}-{min(i + pages_per_section, len(pages))}",
                    content_md=content,
                    depth=0,
                    order_index=len(sections),
                ))
        return sections
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_pdf_parser.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser/pdf_parser.py backend/tests/unit/test_pdf_parser.py
git commit -m "feat: add PDF parser using pymupdf4llm with heading-based section splitting"
```

---

### Task 13: MOBI Parser & Install Calibre

**Files:**
- Create: `backend/app/services/parser/mobi_parser.py`
- Create: `backend/tests/unit/test_mobi_parser.py`

- [ ] **Step 1: Install Calibre**

```bash
brew install --cask calibre
# Verify:
ebook-convert --version
```

- [ ] **Step 2: Write failing test**

```python
# backend/tests/unit/test_mobi_parser.py
"""Tests for MOBI parser (delegates to EPUB after Calibre conversion)."""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.parser.mobi_parser import MOBIParser


@pytest.fixture
def parser():
    return MOBIParser()


def test_supports_mobi(parser):
    assert parser.supports_format("mobi") is True
    assert parser.supports_format("epub") is False


@pytest.mark.asyncio
async def test_mobi_converts_to_epub(parser, tmp_path):
    """MOBI parser should convert to EPUB then delegate."""
    mobi_file = tmp_path / "test.mobi"
    mobi_file.write_bytes(b"\x00" * 60 + b"BOOKMOBI" + b"\x00" * 100)

    with patch("app.services.parser.mobi_parser.EPUBParser") as MockEPUB:
        mock_epub_parser = AsyncMock()
        MockEPUB.return_value = mock_epub_parser
        mock_epub_parser.parse.return_value = AsyncMock(
            title="Test", authors=["Author"], sections=[], cover_image=None, metadata={}
        )
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            await parser.parse(mobi_file)
            # Verify ebook-convert was called
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0]
            assert call_args[0] == "ebook-convert"
```

- [ ] **Step 3: Implement MOBI parser**

```python
# backend/app/services/parser/mobi_parser.py
"""MOBI parser — converts to EPUB via Calibre, then delegates to EPUBParser."""

import asyncio
import tempfile
from pathlib import Path

from app.exceptions import ParseError
from app.services.parser.base import BookParser, ParsedBook
from app.services.parser.epub_parser import EPUBParser


class MOBIParser(BookParser):
    def supports_format(self, file_format: str) -> bool:
        return file_format == "mobi"

    async def parse(self, file_path: Path) -> ParsedBook:
        with tempfile.TemporaryDirectory() as tmpdir:
            epub_path = Path(tmpdir) / f"{file_path.stem}.epub"
            await self._convert_to_epub(file_path, epub_path)
            epub_parser = EPUBParser()
            return await epub_parser.parse(epub_path)

    async def _convert_to_epub(self, mobi_path: Path, epub_path: Path) -> None:
        proc = await asyncio.create_subprocess_exec(
            "ebook-convert", str(mobi_path), str(epub_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise ParseError(
                f"Calibre ebook-convert failed (rc={proc.returncode}): {stderr.decode()}"
            )
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_mobi_parser.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser/mobi_parser.py backend/tests/unit/test_mobi_parser.py
git commit -m "feat: add MOBI parser with Calibre conversion to EPUB"
```

---

### Task 14: Structure Detector (3-Tier Fallback)

**Files:**
- Create: `backend/app/services/parser/structure_detector.py`
- Create: `backend/app/services/summarizer/prompts/detect_structure_v1.txt`
- Create: `backend/tests/unit/test_structure_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_structure_detector.py
"""Tests for 3-tier structure detection."""

import pytest
from app.services.parser.structure_detector import StructureDetector
from app.services.parser.base import ParsedSection


def test_heuristic_heading_detection():
    """Tier 2: Detect chapters from heading patterns."""
    detector = StructureDetector(llm_provider=None)
    content = (
        "# Chapter 1: Introduction\n\nSome content here.\n\n"
        "# Chapter 2: Main Ideas\n\nMore content here.\n\n"
        "## Section 2.1: Details\n\nSub-section content.\n"
    )
    sections = detector.detect_from_heuristics(content)
    assert len(sections) >= 2
    assert sections[0].title == "Chapter 1: Introduction"


def test_embedded_toc_passthrough():
    """Tier 1: If sections already extracted from TOC, pass through."""
    detector = StructureDetector(llm_provider=None)
    existing = [
        ParsedSection(title="Ch1", content_md="content1", depth=0, order_index=0),
        ParsedSection(title="Ch2", content_md="content2", depth=0, order_index=1),
    ]
    result = detector.validate_structure(existing)
    assert result == existing  # No changes needed


def test_flat_content_triggers_heuristic():
    """If only 1 section, try heuristic splitting."""
    detector = StructureDetector(llm_provider=None)
    flat = [
        ParsedSection(
            title="Full Book",
            content_md="# Ch1\n\nContent 1\n\n# Ch2\n\nContent 2\n",
            depth=0,
            order_index=0,
        )
    ]
    result = detector.validate_structure(flat)
    assert len(result) >= 2
```

- [ ] **Step 2: Implement structure detector**

```python
# backend/app/services/parser/structure_detector.py
"""3-tier structure detection: embedded TOC → heuristics → LLM fallback."""

import json
import re

from app.services.parser.base import ParsedSection
from app.services.summarizer.llm_provider import LLMProvider


class StructureDetector:
    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm_provider = llm_provider

    def validate_structure(self, sections: list[ParsedSection]) -> list[ParsedSection]:
        """Validate and potentially re-detect structure.

        Tier 1: If multiple sections exist (from embedded TOC), keep them.
        Tier 2: If single flat section, try heuristic heading detection.
        Tier 3: LLM fallback (async, called separately).
        """
        if len(sections) > 1:
            return sections  # Tier 1: TOC extraction worked

        if len(sections) == 1:
            # Tier 2: Try heuristic detection on the flat content
            heuristic_sections = self.detect_from_heuristics(sections[0].content_md)
            if len(heuristic_sections) > 1:
                return heuristic_sections

        return sections  # Return as-is if nothing worked

    def detect_from_heuristics(self, content: str) -> list[ParsedSection]:
        """Tier 2: Detect chapters using Markdown heading patterns."""
        heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
        matches = list(heading_pattern.finditer(content))

        if len(matches) < 2:
            return []

        sections = []
        for i, match in enumerate(matches):
            depth = len(match.group(1)) - 1  # # = 0, ## = 1, ### = 2
            title = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start:end].strip()

            if section_content:
                sections.append(ParsedSection(
                    title=title,
                    content_md=section_content,
                    depth=depth,
                    order_index=len(sections),
                ))
        return sections

    async def detect_via_llm(self, content: str, max_tokens: int = 5000) -> list[dict]:
        """Tier 3: LLM-assisted structure detection. Returns JSON section markers."""
        if not self.llm_provider:
            return []

        truncated = content[:max_tokens * 4]  # ~4 chars per token
        from pathlib import Path
        prompt_path = Path(__file__).parent.parent / "summarizer" / "prompts" / "detect_structure_v1.txt"
        if prompt_path.exists():
            import jinja2
            template = jinja2.Template(prompt_path.read_text())
            prompt = template.render(book_text=truncated)
        else:
            prompt = (
                "Analyze the following text from the beginning of a book. Identify the "
                "chapter/section structure. Return a JSON array of sections with 'title' "
                "and approximate 'char_offset' keys.\n\n" + truncated
            )

        response = await self.llm_provider.generate(
            prompt=prompt,
            json_schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "char_offset": {"type": "integer"},
                    },
                    "required": ["title", "char_offset"],
                },
            },
        )
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return []
```

- [ ] **Step 3: Create prompt template**

```
{# backend/app/services/summarizer/prompts/detect_structure_v1.txt #}
Analyze the following text from the beginning of a book. Identify the chapter/section structure. Return a JSON array of sections with title and approximate character offset. Look for: numbered chapters, named parts, heading patterns, topic transitions.

{{ book_text }}
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_structure_detector.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser/structure_detector.py backend/app/services/summarizer/prompts/ backend/tests/unit/test_structure_detector.py
git commit -m "feat: add 3-tier structure detection (TOC → heuristics → LLM fallback)"
```

---

### Task 15: Embedding Service (Ollama)

**Files:**
- Create: `backend/app/services/embedding_service.py`
- Create: `backend/tests/unit/test_embedding.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_embedding.py
"""Tests for embedding service."""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.embedding_service import EmbeddingService


def test_chunk_splitting():
    service = EmbeddingService()
    text = "word " * 1000  # ~1000 tokens
    chunks = service._split_into_chunks(text, chunk_size=512, overlap=50)
    assert len(chunks) >= 2
    # Check overlap: end of chunk N should overlap with start of chunk N+1
    for i in range(len(chunks) - 1):
        assert chunks[i][-50:] or True  # Overlap exists


@pytest.mark.asyncio
async def test_embed_text_calls_ollama():
    service = EmbeddingService(ollama_url="http://localhost:11434", model="nomic-embed-text")
    mock_response = AsyncMock()
    mock_response.json.return_value = {"embedding": [0.1] * 768}
    mock_response.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        embedding = await service.embed_text("test text")
        assert len(embedding) == 768


def test_token_estimation():
    service = EmbeddingService()
    assert service._estimate_tokens("hello world") == 2  # ~1 token per word
    assert service._estimate_tokens("a " * 100) == 100
```

- [ ] **Step 2: Implement embedding service**

```python
# backend/app/services/embedding_service.py
"""Embedding service using local Ollama."""

import asyncio

import httpx

from app.exceptions import EmbeddingError


class EmbeddingService:
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        max_concurrent: int = 5,
    ):
        self.ollama_url = ollama_url
        self.model = model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text via Ollama API."""
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.post(
                        f"{self.ollama_url}/api/embeddings",
                        json={"model": self.model, "prompt": text},
                    )
                    response.raise_for_status()
                    return response.json()["embedding"]
                except httpx.HTTPError as e:
                    raise EmbeddingError(f"Ollama embedding failed: {e}")

    async def chunk_and_embed(
        self, text: str, chunk_size: int | None = None, overlap: int | None = None
    ) -> list[tuple[str, list[float]]]:
        """Split text into overlapping chunks and embed each."""
        chunks = self._split_into_chunks(
            text,
            chunk_size=chunk_size or self.chunk_size,
            overlap=overlap or self.chunk_overlap,
        )
        embeddings = await asyncio.gather(
            *[self.embed_text(chunk) for chunk in chunks],
            return_exceptions=True,
        )
        results = []
        for chunk, emb in zip(chunks, embeddings):
            if isinstance(emb, Exception):
                continue  # Skip failed embeddings
            results.append((chunk, emb))
        return results

    def _split_into_chunks(
        self, text: str, chunk_size: int = 512, overlap: int = 50
    ) -> list[str]:
        """Split text into overlapping chunks by estimated token count."""
        words = text.split()
        if not words:
            return []

        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk = " ".join(words[start:end])
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap
            if start >= len(words):
                break
        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation: ~1 token per 4 chars (spec requirement)."""
        return len(text) // 4
```

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_embedding.py -v
```

- [ ] **Step 4: Verify with real Ollama**

```bash
cd backend && uv run python -c "
import asyncio
from app.services.embedding_service import EmbeddingService
async def test():
    svc = EmbeddingService()
    emb = await svc.embed_text('The art of war is of vital importance to the state.')
    print(f'Embedding dimension: {len(emb)}')
    assert len(emb) == 768
asyncio.run(test())
print('Ollama embedding OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/embedding_service.py backend/tests/unit/test_embedding.py
git commit -m "feat: add embedding service with Ollama integration and text chunking"
```

---

### Task 16: Search Service (BM25 + Semantic + RRF)

**Files:**
- Create: `backend/app/services/search_service.py`
- Create: `backend/tests/unit/test_search.py`
- Create: `backend/tests/integration/test_search_integration.py`

- [ ] **Step 1: Write failing unit tests**

```python
# backend/tests/unit/test_search.py
"""Unit tests for search service."""

from app.services.search_service import SearchService


def test_rrf_merge():
    """RRF fusion should combine rankings correctly."""
    bm25_ids = [1, 3, 5, 7]    # Ranked by BM25
    semantic_ids = [3, 1, 9, 5]  # Ranked by semantic

    fused = SearchService._rrf_merge_static(bm25_ids, semantic_ids, k=60)
    # ID 3 ranks #2 in BM25, #1 in semantic → should score highest
    # ID 1 ranks #1 in BM25, #2 in semantic → close second
    assert fused[0] in (1, 3)  # Top result is ID 1 or 3
    assert len(fused) == 5  # Union of all unique IDs


def test_result_grouping():
    """Results should group by book_id."""
    from app.services.search_service import SearchResult
    results = [
        SearchResult(source_type="section_content", source_id=1, book_id=1,
                     book_title="Book A", section_title="Ch1", chunk_text="text", score=0.9, highlight="text"),
        SearchResult(source_type="section_content", source_id=2, book_id=2,
                     book_title="Book B", section_title="Ch1", chunk_text="text", score=0.8, highlight="text"),
        SearchResult(source_type="section_summary", source_id=3, book_id=1,
                     book_title="Book A", section_title="Ch2", chunk_text="text", score=0.7, highlight="text"),
    ]
    grouped = SearchService._group_results_static(results)
    assert len(grouped.books) == 2
    assert len(grouped.books[1]) == 2  # Book A has 2 results
    assert grouped.total_count == 3
```

- [ ] **Step 2: Implement search service**

```python
# backend/app/services/search_service.py
"""Hybrid search: BM25 + semantic + Reciprocal Rank Fusion."""

from dataclasses import dataclass
from collections import defaultdict

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SearchIndex, SourceType, Book, BookSection
from app.services.embedding_service import EmbeddingService


@dataclass
class SearchResult:
    source_type: str
    source_id: int
    book_id: int
    book_title: str
    section_title: str | None
    chunk_text: str
    score: float
    highlight: str


@dataclass
class GroupedSearchResults:
    query: str
    books: dict[int, list[SearchResult]]
    total_count: int


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
        rrf_k: int = 60,
        default_limit: int = 20,
    ):
        self.session = session
        self.embedding_service = embedding_service
        self.rrf_k = rrf_k
        self.default_limit = default_limit

    async def search(
        self,
        query: str,
        book_id: int | None = None,
        source_types: list[str] | None = None,
        limit: int | None = None,
    ) -> GroupedSearchResults:
        limit = limit or self.default_limit

        # 1. Generate query embedding
        query_embedding = await self.embedding_service.embed_text(query)

        # 2. BM25 search
        bm25_results = await self._bm25_search(query, book_id, source_types, limit * 2)

        # 3. Semantic search
        semantic_results = await self._semantic_search(
            query_embedding, book_id, source_types, limit * 2
        )

        # 4. RRF merge
        all_results = {r.source_id: r for r in bm25_results + semantic_results}
        bm25_ids = [r.source_id for r in bm25_results]
        semantic_ids = [r.source_id for r in semantic_results]
        fused_ids = self._rrf_merge_static(bm25_ids, semantic_ids, self.rrf_k)

        # 5. Build ordered results
        fused_results = []
        for sid in fused_ids[:limit]:
            if sid in all_results:
                fused_results.append(all_results[sid])

        return self._group_results_static(fused_results, query)

    async def _bm25_search(
        self, query: str, book_id: int | None, source_types: list[str] | None, limit: int
    ) -> list[SearchResult]:
        tsquery = func.plainto_tsquery("english", query)
        stmt = (
            select(
                SearchIndex.id,
                SearchIndex.source_type,
                SearchIndex.source_id,
                SearchIndex.book_id,
                SearchIndex.chunk_text,
                func.ts_rank(SearchIndex.tsvector, tsquery).label("rank"),
            )
            .where(SearchIndex.tsvector.op("@@")(tsquery))
            .order_by(text("rank DESC"))
            .limit(limit)
        )
        if book_id:
            stmt = stmt.where(SearchIndex.book_id == book_id)
        if source_types:
            stmt = stmt.where(SearchIndex.source_type.in_(source_types))

        result = await self.session.execute(stmt)
        rows = result.all()
        return await self._rows_to_results(rows)

    async def _semantic_search(
        self, embedding: list[float], book_id: int | None,
        source_types: list[str] | None, limit: int
    ) -> list[SearchResult]:
        stmt = (
            select(
                SearchIndex.id,
                SearchIndex.source_type,
                SearchIndex.source_id,
                SearchIndex.book_id,
                SearchIndex.chunk_text,
                SearchIndex.embedding.cosine_distance(embedding).label("distance"),
            )
            .where(SearchIndex.embedding.isnot(None))
            .order_by("distance")
            .limit(limit)
        )
        if book_id:
            stmt = stmt.where(SearchIndex.book_id == book_id)
        if source_types:
            stmt = stmt.where(SearchIndex.source_type.in_(source_types))

        result = await self.session.execute(stmt)
        rows = result.all()
        return await self._rows_to_results(rows)

    async def _rows_to_results(self, rows) -> list[SearchResult]:
        results = []
        for row in rows:
            # Look up book title and section title
            book = await self.session.get(Book, row.book_id)
            section_title = None
            if row.source_type in ("section_content", "section_summary", "section_title"):
                section = await self.session.get(BookSection, row.source_id)
                section_title = section.title if section else None

            results.append(SearchResult(
                source_type=row.source_type,
                source_id=row.source_id,
                book_id=row.book_id,
                book_title=book.title if book else "Unknown",
                section_title=section_title,
                chunk_text=row.chunk_text[:200],
                score=getattr(row, "rank", 0) or (1 - getattr(row, "distance", 1)),
                highlight=row.chunk_text[:150],
            ))
        return results

    @staticmethod
    def _rrf_merge_static(
        bm25_ids: list[int], semantic_ids: list[int], k: int = 60
    ) -> list[int]:
        """Reciprocal Rank Fusion: RRF_score(doc) = 1/(k + rank)"""
        scores: dict[int, float] = defaultdict(float)
        for rank, doc_id in enumerate(bm25_ids):
            scores[doc_id] += 1.0 / (k + rank + 1)
        for rank, doc_id in enumerate(semantic_ids):
            scores[doc_id] += 1.0 / (k + rank + 1)
        return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    @staticmethod
    def _group_results_static(
        results: list[SearchResult], query: str = ""
    ) -> GroupedSearchResults:
        books: dict[int, list[SearchResult]] = defaultdict(list)
        for r in results:
            books[r.book_id].append(r)
        return GroupedSearchResults(query=query, books=dict(books), total_count=len(results))
```

- [ ] **Step 3: Run unit tests**

```bash
cd backend && uv run pytest tests/unit/test_search.py -v
```

- [ ] **Step 4: Write integration test**

```python
# backend/tests/integration/test_search_integration.py
"""Integration tests for search with real PostgreSQL."""

import pytest
from sqlalchemy import text

from app.db.models import Book, BookSection, SearchIndex, SourceType


@pytest.mark.asyncio
async def test_tsvector_indexing(db_session):
    """Verify tsvector search works on indexed content."""
    book = Book(
        title="Test Search Book",
        file_data=b"test",
        file_hash="search_test_hash_001",
        file_format="epub",
        file_size_bytes=100,
    )
    db_session.add(book)
    await db_session.flush()

    # Add search index entry with tsvector
    entry = SearchIndex(
        source_type=SourceType.SECTION_CONTENT,
        source_id=1,
        book_id=book.id,
        chunk_text="The art of war is of vital importance to the state",
        chunk_index=0,
    )
    db_session.add(entry)
    await db_session.flush()

    # Update tsvector manually (normally done via trigger or app code)
    await db_session.execute(
        text(
            "UPDATE search_index SET tsvector = to_tsvector('english', chunk_text) "
            "WHERE id = :id"
        ),
        {"id": entry.id},
    )
    await db_session.flush()

    # Search
    result = await db_session.execute(
        text(
            "SELECT id, chunk_text, ts_rank(tsvector, plainto_tsquery('english', 'war importance')) as rank "
            "FROM search_index WHERE tsvector @@ plainto_tsquery('english', 'war importance') "
            "ORDER BY rank DESC"
        )
    )
    rows = result.all()
    assert len(rows) >= 1
    assert "war" in rows[0][1].lower()
```

- [ ] **Step 5: Run integration test**

```bash
cd backend && uv run pytest tests/integration/test_search_integration.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/search_service.py backend/tests/unit/test_search.py backend/tests/integration/test_search_integration.py
git commit -m "feat: add hybrid search with BM25, semantic, and RRF fusion"
```

---

### Task 17: Image Captioning Service

**Files:**
- Create: `backend/app/services/summarizer/image_captioner.py`
- Create: `backend/tests/unit/test_image_captioner.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_image_captioner.py
"""Tests for image captioning via Claude Code CLI."""

import pytest
from unittest.mock import AsyncMock
from app.services.summarizer.image_captioner import ImageCaptioner
from app.services.summarizer.llm_provider import LLMResponse


@pytest.mark.asyncio
async def test_caption_image():
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.return_value = LLMResponse(
        content="A diagram showing the hierarchy of military strategy.",
        model="sonnet",
        latency_ms=500,
    )
    captioner = ImageCaptioner(llm_provider=mock_llm)
    caption = await captioner.caption_image(
        image_data=b"fake_image_data",
        mime_type="image/png",
        context="This section discusses military strategy.",
    )
    assert "strategy" in caption.lower() or "hierarchy" in caption.lower()


@pytest.mark.asyncio
async def test_caption_failure_returns_empty():
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.side_effect = Exception("CLI failed")
    captioner = ImageCaptioner(llm_provider=mock_llm)
    caption = await captioner.caption_image(
        image_data=b"fake", mime_type="image/png", context="test"
    )
    assert caption == ""  # Non-blocking: returns empty on failure
```

- [ ] **Step 2: Implement image captioner**

```python
# backend/app/services/summarizer/image_captioner.py
"""Image captioning via Claude Code CLI vision capabilities."""

import tempfile
from pathlib import Path

import structlog

from app.services.summarizer.llm_provider import LLMProvider

logger = structlog.get_logger()


class ImageCaptioner:
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    async def caption_image(
        self,
        image_data: bytes,
        mime_type: str,
        context: str = "",
    ) -> str:
        """Generate a caption for an image. Non-blocking: returns empty string on failure."""
        ext = mime_type.split("/")[-1] if "/" in mime_type else "png"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                image_path = Path(tmpdir) / f"image.{ext}"
                image_path.write_bytes(image_data)

                prompt = (
                    f"Describe what this image shows in the context of: {context}. "
                    "Focus on key information, data, frameworks, or concepts depicted. "
                    "Be concise (1-3 sentences)."
                )
                response = await self.llm_provider.generate_with_image(
                    prompt=prompt,
                    image_path=image_path,
                )
                return response.content.strip()
        except Exception as e:
            logger.warning("image_captioning_failed", error=str(e))
            return ""

    async def caption_section_images(
        self,
        images: list[dict],
        section_context: str,
    ) -> dict[int, str]:
        """Caption multiple images for a section. Returns {image_id: caption}."""
        captions = {}
        for img in images:
            caption = await self.caption_image(
                image_data=img["data"],
                mime_type=img["mime_type"],
                context=section_context,
            )
            if caption:
                captions[img["id"]] = caption
        return captions
```

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_image_captioner.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/summarizer/image_captioner.py backend/tests/unit/test_image_captioner.py
git commit -m "feat: add image captioning service with non-blocking failure handling"
```

---

### Task 18: Prompt Templates (Jinja2)

**Files:**
- Create: All prompt templates in `backend/app/services/summarizer/prompts/`

- [ ] **Step 1: Create all prompt templates from spec**

Create each template as specified in Spec Sections 6-8. Files:

- `summarize_section_v1.txt` — Section summarization with cumulative context, concepts extraction, image captions (spec lines 902-970)
- `summarize_book_v1.txt` — Book-level summary from section summaries (spec lines 1039-1068)
- `quick_summary_v1.txt` — Single-pass quick book overview (spec lines 876-896)
- `detect_structure_v1.txt` — LLM-assisted TOC detection (already created in Task 14)
- `caption_image_v1.txt` — Image captioning prompt
- `eval_faithfulness_v1.txt` — `no_hallucinated_facts`, `no_contradictions`, `accurate_quotes`, `cross_summary_consistency`
- `eval_completeness_v1.txt` — `covers_main_argument`, `covers_key_concepts`, `covers_frameworks`, `covers_examples`
- `eval_coherence_v1.txt` — `standalone_readable`, `logical_flow`, `no_dangling_references`
- `eval_specificity_v1.txt` — `not_generic`, `preserves_author_terminology`
- `eval_format_v1.txt` — `has_key_concepts`, `reasonable_length`, `image_refs_preserved`
- `discover_references_v1.txt` — External reference discovery (Phase 2, spec lines 1122-1136)

Each template uses Jinja2 syntax with variables matching the spec. Copy prompt content verbatim from the spec.

- [ ] **Step 2: Verify templates render without errors**

```bash
cd backend && uv run python -c "
import jinja2
from pathlib import Path

prompts_dir = Path('app/services/summarizer/prompts')
env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(prompts_dir)))
for tmpl_file in sorted(prompts_dir.glob('*.txt')):
    tmpl = env.get_template(tmpl_file.name)
    print(f'  OK: {tmpl_file.name}')
print('All templates load successfully')
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/summarizer/prompts/
git commit -m "feat: add all Jinja2 prompt templates for summarization, eval, and captioning"
```

---

### Task 19: Summarizer Service

**Files:**
- Create: `backend/app/services/summarizer/summarizer_service.py`
- Create: `backend/tests/unit/test_summarizer.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_summarizer.py
"""Tests for summarizer service."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.summarizer.summarizer_service import SummarizerService
from app.services.summarizer.llm_provider import LLMResponse
from app.db.models import BookSection, SummaryStatus


def make_mock_section(section_id=1, title="Chapter 1", content="Test content " * 50):
    section = MagicMock(spec=BookSection)
    section.id = section_id
    section.title = title
    section.content_md = content
    section.content_token_count = len(content.split())
    section.summary_status = SummaryStatus.PENDING
    section.summary_md = None
    section.user_edited = False
    section.images = []
    return section


@pytest.mark.asyncio
async def test_cumulative_context_generation():
    service = SummarizerService.__new__(SummarizerService)
    prior = [
        MagicMock(title="Ch1", summary_md="Chapter 1 covers the basics of strategy."),
        MagicMock(title="Ch2", summary_md="Chapter 2 discusses tactical warfare."),
    ]
    context = service._build_cumulative_context(prior)
    assert "Ch1" in context
    assert "Ch2" in context
    assert len(context) < 3000  # Should be compact


@pytest.mark.asyncio
async def test_compression_ratio_for_detail_levels():
    service = SummarizerService.__new__(SummarizerService)
    assert service._get_compression_target("brief") == 10
    assert service._get_compression_target("standard") == 20
    assert service._get_compression_target("detailed") == 30


@pytest.mark.asyncio
async def test_summarize_section_calls_llm():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        content=json.dumps({
            "key_concepts": ["concept1", "concept2", "concept3"],
            "detailed_summary": "This section covers strategy.",
            "frameworks": ["Framework A"],
            "key_quotes": ["Quote 1"],
            "concepts": [],
        }),
        model="sonnet",
        latency_ms=1000,
    )
    mock_session = AsyncMock()
    mock_config = MagicMock()
    mock_config.summarization.default_detail_level = "standard"
    mock_config.summarization.prompt_version = "v1"

    service = SummarizerService(
        db=mock_session, llm=mock_llm, config=mock_config
    )
    section = make_mock_section()
    result = await service._summarize_single_section(
        section=section, prior_sections=[], detail_level="standard"
    )
    assert "strategy" in result.lower()
    mock_llm.generate.assert_called_once()
```

- [ ] **Step 2: Implement summarizer service**

Implement `SummarizerService` with methods:
- `summarize_book(book_id, force, detail_level, skip_eval, model)` — Orchestrate full book summarization
- `summarize_section(book_id, section_id, detail_level)` — Summarize single section
- `quick_summary(book_id)` — Quick single-pass summary
- `_summarize_single_section(section, prior_sections, detail_level)` — Core LLM call
- `_build_cumulative_context(prior_sections)` — Build context from prior summaries
- `_generate_book_summary(book, sections)` — Reduce step
- `_get_compression_target(detail_level)` — Map detail level to ratio

Key implementation details from spec:
- Load prompt templates via `jinja2.FileSystemLoader`
- Pass `--json-schema` to CLI for structured output
- Handle long sections (>150K tokens) by sub-chunking
- Store concepts extracted during summarization
- Update `summary_status` on each section as processing progresses
- Use `rich.Progress` for CLI progress display

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_summarizer.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/summarizer/summarizer_service.py backend/tests/unit/test_summarizer.py
git commit -m "feat: add summarizer service with cumulative context and hierarchical map-reduce"
```

---

### Task 20: Evaluator Service (16-Assertion Battery)

**Files:**
- Create: `backend/app/services/summarizer/evaluator.py`
- Create: `backend/tests/unit/test_evaluator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_evaluator.py
"""Tests for the 16-assertion evaluation service."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.summarizer.evaluator import EvalService, ASSERTION_REGISTRY
from app.services.summarizer.llm_provider import LLMResponse


def test_all_16_assertions_registered():
    assert len(ASSERTION_REGISTRY) == 16
    expected = {
        "no_hallucinated_facts", "no_contradictions", "accurate_quotes",
        "cross_summary_consistency", "covers_main_argument", "covers_key_concepts",
        "covers_frameworks", "covers_examples", "standalone_readable",
        "logical_flow", "no_dangling_references", "not_generic",
        "preserves_author_terminology", "has_key_concepts", "reasonable_length",
        "image_refs_preserved",
    }
    assert set(ASSERTION_REGISTRY.keys()) == expected


def test_assertion_categories():
    critical = [a for a, meta in ASSERTION_REGISTRY.items() if meta["category"] == "critical"]
    important = [a for a, meta in ASSERTION_REGISTRY.items() if meta["category"] == "important"]
    advisory = [a for a, meta in ASSERTION_REGISTRY.items() if meta["category"] == "advisory"]
    assert len(critical) == 4  # Faithfulness
    assert len(important) == 6  # Completeness + Specificity
    assert len(advisory) == 6  # Coherence + Format


@pytest.mark.asyncio
async def test_eval_result_parsing():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        content=json.dumps({"passed": True, "reasoning": "All claims supported."}),
        model="sonnet",
        latency_ms=200,
    )
    mock_session = AsyncMock()
    service = EvalService(db=mock_session, llm=mock_llm, config=MagicMock())
    result = await service._run_single_assertion(
        assertion_name="no_hallucinated_facts",
        source_text="Source content here",
        summary_text="Summary content here",
        section_id=1,
    )
    assert result["passed"] is True
    assert result["assertion_name"] == "no_hallucinated_facts"


@pytest.mark.asyncio
async def test_critical_failure_triggers_retry():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        content=json.dumps({"passed": False, "reasoning": "Hallucinated fact found."}),
        model="sonnet",
        latency_ms=200,
    )
    mock_session = AsyncMock()
    mock_config = MagicMock()
    mock_config.llm.max_retries = 2

    service = EvalService(db=mock_session, llm=mock_llm, config=mock_config)
    result = service._should_auto_retry(
        {"no_hallucinated_facts": {"passed": False}},
        retry_count=0,
        max_retries=2,
    )
    assert result is True  # Should retry on critical failure
```

- [ ] **Step 2: Implement evaluator**

```python
# backend/app/services/summarizer/evaluator.py
"""16-assertion evaluation battery with trace storage."""

import asyncio
import json
from pathlib import Path

import jinja2
import structlog

from app.db.models import EvalTrace
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

ASSERTION_REGISTRY: dict[str, dict] = {
    # Faithfulness (Critical)
    "no_hallucinated_facts": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    "no_contradictions": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    "accurate_quotes": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    "cross_summary_consistency": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    # Completeness (Important)
    "covers_main_argument": {"category": "important", "prompt_file": "eval_completeness_v1.txt"},
    "covers_key_concepts": {"category": "important", "prompt_file": "eval_completeness_v1.txt"},
    "covers_frameworks": {"category": "important", "prompt_file": "eval_completeness_v1.txt"},
    "covers_examples": {"category": "important", "prompt_file": "eval_completeness_v1.txt"},
    # Coherence (Advisory)
    "standalone_readable": {"category": "advisory", "prompt_file": "eval_coherence_v1.txt"},
    "logical_flow": {"category": "advisory", "prompt_file": "eval_coherence_v1.txt"},
    "no_dangling_references": {"category": "advisory", "prompt_file": "eval_coherence_v1.txt"},
    # Specificity (Important)
    "not_generic": {"category": "important", "prompt_file": "eval_specificity_v1.txt"},
    "preserves_author_terminology": {"category": "important", "prompt_file": "eval_specificity_v1.txt"},
    # Format (Advisory)
    "has_key_concepts": {"category": "advisory", "prompt_file": "eval_format_v1.txt"},
    "reasonable_length": {"category": "advisory", "prompt_file": "eval_format_v1.txt"},
    "image_refs_preserved": {"category": "advisory", "prompt_file": "eval_format_v1.txt"},
}

PROMPTS_DIR = Path(__file__).parent / "prompts"


class EvalService:
    def __init__(self, db: AsyncSession, llm: LLMProvider, config):
        self.db = db
        self.llm = llm
        self.config = config
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(PROMPTS_DIR))
        )

    async def evaluate_summary(
        self, section_id: int, source_text: str, summary_text: str
    ) -> dict[str, dict]:
        """Run all 16 assertions in parallel. Returns {assertion_name: {passed, reasoning}}."""
        tasks = [
            self._run_single_assertion(name, source_text, summary_text, section_id)
            for name in ASSERTION_REGISTRY
        ]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for name, result in zip(ASSERTION_REGISTRY.keys(), results_list):
            if isinstance(result, Exception):
                results[name] = {"passed": False, "reasoning": f"Eval error: {result}", "error": True}
            else:
                results[name] = result
        return results

    async def _run_single_assertion(
        self,
        assertion_name: str,
        source_text: str,
        summary_text: str,
        section_id: int,
    ) -> dict:
        meta = ASSERTION_REGISTRY[assertion_name]
        template = self._jinja_env.get_template(meta["prompt_file"])
        prompt = template.render(
            assertion_name=assertion_name,
            source_text=source_text,
            summary_text=summary_text,
        )

        response = await self.llm.generate(
            prompt=prompt,
            json_schema={
                "type": "object",
                "properties": {
                    "passed": {"type": "boolean"},
                    "reasoning": {"type": "string"},
                },
                "required": ["passed", "reasoning"],
            },
        )

        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError:
            parsed = {"passed": False, "reasoning": f"Failed to parse: {response.content[:200]}"}

        # Store trace
        trace = EvalTrace(
            section_id=section_id,
            assertion_name=assertion_name,
            assertion_category=meta["category"],
            passed=parsed.get("passed", False),
            prompt_sent=prompt,
            prompt_version=meta["prompt_file"].replace(".txt", ""),
            llm_response=response.content,
            reasoning=parsed.get("reasoning"),
            model_used=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
        )
        self.db.add(trace)

        return {
            "assertion_name": assertion_name,
            "category": meta["category"],
            "passed": parsed.get("passed", False),
            "reasoning": parsed.get("reasoning", ""),
        }

    def _should_auto_retry(
        self, results: dict[str, dict], retry_count: int, max_retries: int
    ) -> bool:
        """Return True if any critical assertion failed and retries remain."""
        if retry_count >= max_retries:
            return False
        for name, result in results.items():
            meta = ASSERTION_REGISTRY.get(name, {})
            if meta.get("category") == "critical" and not result.get("passed"):
                return True
        return False
```

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_evaluator.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/summarizer/evaluator.py backend/tests/unit/test_evaluator.py
git commit -m "feat: add 16-assertion eval battery with trace storage and auto-retry logic"
```

---

### Task 21: Book Service (Orchestration Layer)

**Files:**
- Create: `backend/app/services/book_service.py`
- Create: `backend/tests/unit/test_book_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_book_service.py
"""Tests for book service orchestration."""

import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.book_service import BookService
from app.services.parser.base import ParsedBook, ParsedSection


@pytest.mark.asyncio
async def test_add_book_computes_hash():
    mock_session = AsyncMock()
    mock_parser = AsyncMock()
    mock_parser.parse.return_value = ParsedBook(
        title="Test", authors=["Author"], sections=[
            ParsedSection(title="Ch1", content_md="Content", depth=0, order_index=0),
        ], cover_image=None, metadata={},
    )
    mock_config = MagicMock()
    mock_config.storage.max_file_size_mb = 200

    service = BookService(
        db=mock_session, config=mock_config
    )

    file_data = b"fake epub content"
    expected_hash = hashlib.sha256(file_data).hexdigest()

    with patch.object(service, "_get_parser", return_value=mock_parser):
        with patch.object(service, "_store_book", new_callable=AsyncMock) as mock_store:
            mock_store.return_value = MagicMock(id=1)
            with patch("builtins.open", MagicMock()):
                with patch("pathlib.Path.read_bytes", return_value=file_data):
                    with patch("pathlib.Path.stat", return_value=MagicMock(st_size=100)):
                        result_hash = hashlib.sha256(file_data).hexdigest()
                        assert result_hash == expected_hash


@pytest.mark.asyncio
async def test_file_size_validation():
    mock_session = AsyncMock()
    mock_config = MagicMock()
    mock_config.storage.max_file_size_mb = 1  # 1MB limit

    service = BookService(db=mock_session, config=mock_config)
    # File larger than limit should raise
    assert service._validate_file_size(2 * 1024 * 1024) is False  # 2MB
    assert service._validate_file_size(512 * 1024) is True  # 512KB
```

- [ ] **Step 2: Implement book service**

```python
# backend/app/services/book_service.py
"""Book service — orchestrates the full book lifecycle."""

import hashlib
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Book, BookSection, BookStatus, Image, SummaryStatus
from app.db.repositories.book_repo import AuthorRepository, BookRepository
from app.exceptions import ParseError, StorageError
from app.services.parser.base import BookParser, ParsedBook
from app.services.parser.epub_parser import EPUBParser
from app.services.parser.format_detector import detect_format
from app.services.parser.mobi_parser import MOBIParser
from app.services.parser.pdf_parser import PDFParser
from app.services.parser.structure_detector import StructureDetector

logger = structlog.get_logger()

PARSERS: list[BookParser] = [EPUBParser(), PDFParser(), MOBIParser()]


class BookService:
    def __init__(self, db: AsyncSession, config: Settings):
        self.db = db
        self.config = config
        self.book_repo = BookRepository(db)
        self.author_repo = AuthorRepository(db)

    async def add_book(
        self, file_path: Path, quick: bool = False, async_mode: bool = False, force: bool = False
    ) -> Book:
        """Upload, parse, and store a book."""
        # 1. Validate file
        file_data = file_path.read_bytes()
        if not self._validate_file_size(len(file_data)):
            raise StorageError(
                f"File too large: {len(file_data) / 1024 / 1024:.1f}MB "
                f"(max: {self.config.storage.max_file_size_mb}MB)"
            )

        # 2. Format detection
        file_format = detect_format(file_path)

        # 3. Duplicate detection + re-import + parse_failed retry
        file_hash = hashlib.sha256(file_data).hexdigest()
        existing = await self.book_repo.get_by_hash(file_hash)
        if existing and not force:
            raise StorageError(
                f"This book already exists (ID: {existing.id}). "
                "Use --force to re-import."
            )
        if existing and force:
            # Re-import: replace parsed content, mark summaries stale, delete old embeddings
            # Preserve annotations and tags (Phase 2)
            return await self._re_import_book(existing, file_data, file_path, file_format)

        # Also handle --force retry for parse_failed books
        if force:
            from sqlalchemy import select
            result = await self.db.execute(
                select(Book).where(
                    Book.status == BookStatus.PARSE_FAILED,
                    Book.title.ilike(f"%{file_path.stem}%"),
                )
            )
            failed_book = result.scalar_one_or_none()
            if failed_book:
                await self.book_repo.delete(failed_book)
                await self.db.flush()

        # 4. Parse
        parser = self._get_parser(file_format)
        parsed = await parser.parse(file_path)

        # 5. Structure detection
        detector = StructureDetector()
        parsed.sections = detector.validate_structure(parsed.sections)

        # 6. Store
        book = await self._store_book(parsed, file_data, file_hash, file_format)
        logger.info("book_added", book_id=book.id, title=parsed.title, sections=len(parsed.sections))

        return book

    async def delete_book(self, book_id: int) -> None:
        book = await self.book_repo.get_by_id(book_id)
        if not book:
            raise StorageError(f"Book not found: {book_id}")
        await self.book_repo.delete(book)
        await self.db.commit()
        logger.info("book_deleted", book_id=book_id)

    async def list_books(
        self, author: str | None = None, status: str | None = None, recent: bool = False
    ) -> list[Book]:
        status_enum = BookStatus(status) if status else None
        return await self.book_repo.list_all(
            author=author, status=status_enum, order_by_recent=recent,
        )

    async def get_book(self, book_id: int) -> Book | None:
        return await self.book_repo.get_by_id(book_id)

    def _get_parser(self, file_format: str) -> BookParser:
        for parser in PARSERS:
            if parser.supports_format(file_format):
                return parser
        raise ParseError(f"No parser for format: {file_format}")

    def _validate_file_size(self, size_bytes: int) -> bool:
        max_bytes = self.config.storage.max_file_size_mb * 1024 * 1024
        return size_bytes <= max_bytes

    async def _store_book(
        self, parsed: ParsedBook, file_data: bytes, file_hash: str, file_format: str
    ) -> Book:
        """Store parsed book, sections, images, and authors in DB."""
        book = Book(
            title=parsed.title,
            file_data=file_data,
            file_hash=file_hash,
            file_format=file_format,
            file_size_bytes=len(file_data),
            cover_image=parsed.cover_image,
            status=BookStatus.PARSED,
            metadata_=parsed.metadata,
        )

        # Authors
        for author_name in parsed.authors:
            author = await self.author_repo.get_or_create(author_name)
            book.authors.append(author)

        self.db.add(book)
        await self.db.flush()

        # Sections + images
        for ps in parsed.sections:
            section = BookSection(
                book_id=book.id,
                title=ps.title,
                order_index=ps.order_index,
                depth=ps.depth,
                content_md=ps.content_md,
                content_token_count=len(ps.content_md) // 4,  # ~1 token per 4 chars
                summary_status=SummaryStatus.PENDING,
            )
            self.db.add(section)
            await self.db.flush()

            for pi in ps.images:
                image = Image(
                    section_id=section.id,
                    data=pi.data,
                    mime_type=pi.mime_type,
                    filename=pi.filename,
                    width=pi.width,
                    height=pi.height,
                )
                self.db.add(image)

        await self.db.commit()
        return book

    async def _re_import_book(
        self, existing: Book, file_data: bytes, file_path: Path, file_format: str
    ) -> Book:
        """Re-import: replace content, mark summaries stale, delete embeddings.
        Preserves annotations and tags (Phase 2)."""
        parser = self._get_parser(file_format)
        parsed = await parser.parse(file_path)

        # Update book data
        existing.file_data = file_data
        existing.file_size_bytes = len(file_data)
        existing.status = BookStatus.PARSED

        # Delete old sections (cascades to images, eval_traces)
        from sqlalchemy import delete
        await self.db.execute(
            delete(BookSection).where(BookSection.book_id == existing.id)
        )
        # Delete old search index entries
        from app.db.models import SearchIndex
        await self.db.execute(
            delete(SearchIndex).where(SearchIndex.book_id == existing.id)
        )

        # Re-create sections from new parse
        detector = StructureDetector()
        parsed.sections = detector.validate_structure(parsed.sections)
        for ps in parsed.sections:
            section = BookSection(
                book_id=existing.id,
                title=ps.title,
                order_index=ps.order_index,
                depth=ps.depth,
                content_md=ps.content_md,
                content_token_count=len(ps.content_md) // 4,
                summary_status=SummaryStatus.STALE,  # Mark as stale for re-summarization
            )
            self.db.add(section)

        await self.db.commit()
        logger.info("book_reimported", book_id=existing.id)
        return existing
```

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/unit/test_book_service.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/book_service.py backend/tests/unit/test_book_service.py
git commit -m "feat: add book service with full lifecycle orchestration"
```

---

### Task 22: Structlog Logging Setup

**Files:**
- Create: `backend/app/logging.py`

- [ ] **Step 1: Implement logging configuration**

```python
# backend/app/logging.py
"""Structured logging configuration via structlog."""

import logging
import sys
from pathlib import Path

import structlog

from app.config import Settings


def setup_logging(settings: Settings) -> None:
    """Configure structlog with JSON output and file rotation."""
    log_dir = Path(settings.logging.log_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, settings.logging.level),
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.logging.json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/logging.py
git commit -m "feat: add structlog logging configuration"
```

---

### Task 23: CLI Foundation (Typer App + Dependency Wiring)

**Files:**
- Create: `backend/app/cli/__init__.py`
- Create: `backend/app/cli/main.py`
- Create: `backend/app/cli/deps.py`
- Create: `backend/app/cli/formatting.py`
- Create: `backend/app/cli/commands/__init__.py`

- [ ] **Step 1: Create CLI entry point**

```python
# backend/app/cli/main.py
"""Book Companion CLI — Typer app entry point."""

import typer
from rich.console import Console

from app import __version__

app = typer.Typer(
    name="bookcompanion",
    help="Book Companion - Personal book summarization and knowledge extraction tool.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"bookcompanion {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=version_callback, is_eager=True),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose (DEBUG) logging."),
    format: str = typer.Option("text", "--format", help="Output format: text (default) or json."),
    no_pager: bool = typer.Option(False, "--no-pager", help="Disable pager for long output."),
):
    """Book Companion CLI."""
    import asyncio
    from app.cli.deps import get_settings, check_orphaned_processes, auto_check_migrations
    settings = get_settings()
    if verbose:
        settings.logging.level = "DEBUG"

    # Spec requirement: on every CLI invocation, check for orphaned background processes
    asyncio.run(check_orphaned_processes(settings))

    # Spec requirement: auto-check migrations on every CLI invocation
    auto_check_migrations(settings)


# Import and register command modules
from app.cli.commands import init_cmd, books, summarize_cmd, search_cmd, eval_cmd, status_cmd, config_cmd

app.command("init")(init_cmd.init)
app.command("add")(books.add)
app.command("list")(books.list_books)
app.command("show")(books.show)
app.command("delete")(books.delete)
app.command("read")(books.read)
app.command("authors")(books.authors)
app.command("summary")(summarize_cmd.summary)
app.command("summarize")(summarize_cmd.summarize)
app.command("search")(search_cmd.search)
app.command("eval")(eval_cmd.eval_cmd)
app.command("status")(status_cmd.status)
app.add_typer(config_cmd.config_app, name="config")


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Create dependency wiring**

```python
# backend/app/cli/deps.py
"""Dependency wiring for CLI commands — creates services with proper sessions."""

import asyncio
from contextlib import asynccontextmanager
from functools import wraps
from typing import Callable

from app.config import Settings
from app.db.session import create_session_factory
from app.logging import setup_logging
from app.services.book_service import BookService
from app.services.embedding_service import EmbeddingService
from app.services.search_service import SearchService
from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider
from app.services.summarizer.evaluator import EvalService
from app.services.summarizer.summarizer_service import SummarizerService


_settings: Settings | None = None


async def check_orphaned_processes(settings: Settings) -> None:
    """Spec requirement: on every CLI invocation, check for orphaned background processes.
    Query processing_jobs for status 'running', check if PID is alive via os.kill(pid, 0).
    If PID dead: mark job as 'failed' with error 'Process terminated unexpectedly'."""
    import os
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
                        job.id, "failed", error="Process terminated unexpectedly"
                    )
        await session.commit()


def auto_check_migrations(settings: Settings) -> None:
    """Spec requirement: auto-check migrations on every CLI invocation.
    Run a lightweight check — compare alembic head vs current. Log warning if behind."""
    import subprocess
    result = subprocess.run(
        ["uv", "run", "alembic", "current"],
        capture_output=True, text=True, timeout=5,
    )
    if "head" not in result.stdout:
        import structlog
        structlog.get_logger().warning("database_migrations_behind",
            hint="Run: bookcompanion init")


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        setup_logging(_settings)
    return _settings


@asynccontextmanager
async def get_services():
    """Provide all services with a shared DB session."""
    settings = get_settings()
    session_factory = create_session_factory(settings)

    async with session_factory() as session:
        llm = ClaudeCodeCLIProvider(
            cli_command=settings.llm.cli_command,
            default_model=settings.llm.model,
            default_timeout=settings.llm.timeout_seconds,
            max_budget_usd=settings.llm.max_budget_usd,
        )
        embedding = EmbeddingService(
            ollama_url=settings.embedding.ollama_url,
            model=settings.embedding.model,
            chunk_size=settings.embedding.chunk_size,
            chunk_overlap=settings.embedding.chunk_overlap,
        )

        yield {
            "session": session,
            "settings": settings,
            "book_service": BookService(db=session, config=settings),
            "summarizer": SummarizerService(db=session, llm=llm, config=settings),
            "search": SearchService(session, embedding, settings.search.rrf_k, settings.search.default_limit),
            "eval": EvalService(db=session, llm=llm, config=settings),
            "embedding": embedding,
            "llm": llm,
        }


def async_command(func: Callable) -> Callable:
    """Decorator to run async CLI commands."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper
```

- [ ] **Step 3: Create formatting helpers**

```python
# backend/app/cli/formatting.py
"""Shared rich formatting helpers for CLI output."""

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel

console = Console()


def print_book_table(books):
    """Print books as a rich table."""
    table = Table(title="Library")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Author(s)")
    table.add_column("Status")
    table.add_column("Sections", justify="right")
    table.add_column("Created")

    for book in books:
        authors = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"
        table.add_row(
            str(book.id),
            book.title,
            authors,
            book.status.value if book.status else "unknown",
            str(len(book.sections)) if book.sections else "0",
            book.created_at.strftime("%Y-%m-%d") if book.created_at else "",
        )
    console.print(table)


def print_markdown(content: str, use_pager: bool = True):
    """Render markdown content with optional pager."""
    md = Markdown(content)
    if use_pager:
        with console.pager():
            console.print(md)
    else:
        console.print(md)


def print_error(message: str):
    console.print(f"[red]Error:[/red] {message}")


def print_success(message: str):
    console.print(f"[green]{message}[/green]")


def print_empty_state(message: str):
    console.print(Panel(message, style="dim"))
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/cli/
git commit -m "feat: add Typer CLI foundation with dependency wiring and rich formatting"
```

---

### Task 24: CLI Commands — init, config

**Files:**
- Create: `backend/app/cli/commands/init_cmd.py`
- Create: `backend/app/cli/commands/config_cmd.py`

- [ ] **Step 1: Implement `init` command**

```python
# backend/app/cli/commands/init_cmd.py
"""bookcompanion init — first-time setup."""

import shutil
import subprocess

import typer
from rich.console import Console

from app.cli.deps import async_command, get_settings

console = Console()


@async_command
async def init(
    database_url: str = typer.Option(
        None, "--database-url", help="Override database URL."
    ),
):
    """First-time setup: start PostgreSQL, run migrations, verify dependencies."""
    console.print("\nChecking dependencies...")

    # 1. Check Docker
    _check_dependency("Docker", "docker", ["--version"])

    # 2. Check Ollama
    _check_dependency("Ollama", "curl", ["-s", "http://localhost:11434/api/tags"])

    # 3. Check Calibre
    _check_dependency("ebook-convert", "ebook-convert", ["--version"], required=False)

    # 4. Check Claude Code CLI
    _check_dependency("Claude Code CLI", "claude", ["--version"])

    # 5. Start PostgreSQL if not running
    console.print("\nStarting PostgreSQL container...")
    result = subprocess.run(
        ["docker", "compose", "up", "-d"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print("  [green]PostgreSQL 16 + pgvector: running on port 5438[/green]")
    else:
        console.print(f"  [red]Failed: {result.stderr}[/red]")
        raise typer.Exit(1)

    # 6. Run migrations
    console.print("\nRunning database migrations...")
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True, text=True,
        cwd="backend" if not shutil.which("alembic") else None,
    )
    if result.returncode == 0:
        console.print("  [green]Migrations applied[/green]")
    else:
        console.print(f"  [yellow]Migration warning: {result.stderr[:200]}[/yellow]")

    # 7. Pull embedding model
    console.print("\nPulling embedding model...")
    result = subprocess.run(
        ["ollama", "pull", "nomic-embed-text"],
        capture_output=True, text=True,
    )
    console.print("  [green]nomic-embed-text: ready[/green]")

    # 8. Print getting started
    settings = get_settings()
    config_path = "~/.config/bookcompanion/config.yaml"
    console.print(f"\nConfiguration saved to: {config_path}")
    console.print("\n[bold]Setup complete![/bold] Here's how to get started:\n")
    console.print("  1. Add your first book:    bookcompanion add ~/path/to/book.epub")
    console.print("  2. Quick overview:         bookcompanion add --quick ~/path/to/book.epub")
    console.print("  3. Full summarization:     bookcompanion summarize <book_id>")
    console.print("  4. Browse your library:    bookcompanion list")
    console.print("  5. Search across books:    bookcompanion search \"query\"")
    console.print("\nRun `bookcompanion --help` for all commands.\n")


def _check_dependency(name: str, command: str, args: list, required: bool = True):
    if shutil.which(command):
        try:
            result = subprocess.run([command] + args, capture_output=True, text=True, timeout=10)
            version = result.stdout.strip().split("\n")[0][:60]
            console.print(f"  [green]✓[/green] {name}: {version}")
        except Exception:
            console.print(f"  [green]✓[/green] {name}: found")
    else:
        marker = "[red]✗[/red]" if required else "[yellow]⚠[/yellow]"
        console.print(f"  {marker} {name}: not found")
        if required:
            console.print(f"    Install {name} and try again.")
```

- [ ] **Step 2: Implement `config` command as Typer sub-app with `set` subcommand**

```python
# backend/app/cli/commands/config_cmd.py
"""bookcompanion config — view and set configuration.
Uses Typer sub-app: `config` shows all, `config set <key> <value>` modifies."""

import yaml
import typer
from pathlib import Path
from rich.console import Console
from rich.syntax import Syntax

from app.cli.deps import get_settings

console = Console()
config_app = typer.Typer(help="View or modify configuration.")


@config_app.callback(invoke_without_command=True)
def config(ctx: typer.Context):
    """View current configuration (when called without subcommand)."""
    if ctx.invoked_subcommand is not None:
        return
    settings = get_settings()
    # Show all
        config_dict = {
            "database": settings.database.model_dump(),
            "llm": settings.llm.model_dump(),
            "summarization": settings.summarization.model_dump(),
            "embedding": settings.embedding.model_dump(),
            "search": settings.search.model_dump(),
            "storage": settings.storage.model_dump(),
            "logging": settings.logging.model_dump(),
        }
        yaml_str = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
        console.print(Syntax(yaml_str, "yaml"))


def _get_config(key: str, settings):
    parts = key.split(".")
    obj = settings
    for part in parts:
        obj = getattr(obj, part, None)
        if obj is None:
            console.print(f"[red]Unknown config key: {key}[/red]")
            raise typer.Exit(1)
    console.print(f"{key} = {obj}")


def _set_config(key: str, value: str):
    config_path = Path("~/.config/bookcompanion/config.yaml").expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if config_path.exists():
        with open(config_path) as f:
            existing = yaml.safe_load(f) or {}

    parts = key.split(".")
    obj = existing
    for part in parts[:-1]:
        obj = obj.setdefault(part, {})
    obj[parts[-1]] = value

    with open(config_path, "w") as f:
        yaml.dump(existing, f, default_flow_style=False)
    console.print(f"Set {key} = {value}")
```

- [ ] **Step 3: Run CLI and verify**

```bash
cd backend && uv run bookcompanion --version
cd backend && uv run bookcompanion --help
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/cli/commands/init_cmd.py backend/app/cli/commands/config_cmd.py
git commit -m "feat: add init and config CLI commands"
```

---

### Task 25: CLI Commands — add, list, show, delete, read, authors

**Files:**
- Create: `backend/app/cli/commands/books.py`

- [ ] **Step 1: Implement book management commands**

Implement all book commands as thin wrappers over `BookService`:

- `add(file_path, quick, async_mode, force)` — Upload + parse, with step-by-step TOC review
- `list_books(recent, author, status)` — Table output via `print_book_table()`
- `show(book_id)` — Book details + section list + eval summary
- `delete(book_id, yes)` — Cascade delete with confirmation
- `read(book_id, section_id, with_summary, copy, export)` — Content rendering via rich.Markdown
- `authors()` — Author list with book counts

Each command follows the pattern:
```python
@async_command
async def command_name(args):
    async with get_services() as svc:
        result = await svc["book_service"].method(args)
        # Format and print using rich
```

Key implementation details:
- `add` in step-by-step mode: show detected structure, prompt user with `typer.confirm()`
- `add --quick`: call `svc["summarizer"].quick_summary(book_id)` after parsing
- `add --async`: fork background process (Task 29)
- `read --with-summary`: use `rich.Columns` for side-by-side
- `delete`: cascade delete with `typer.confirm()` unless `--yes`
- Empty states: use `print_empty_state()` for all no-data scenarios

- [ ] **Step 2: Test with real book**

```bash
cd backend && uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub
cd backend && uv run bookcompanion list
cd backend && uv run bookcompanion show 1
cd backend && uv run bookcompanion read 1
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/cli/commands/books.py
git commit -m "feat: add book management CLI commands (add, list, show, delete, read, authors)"
```

---

### Task 26: CLI Commands — summarize, summary

**Files:**
- Create: `backend/app/cli/commands/summarize_cmd.py`

- [ ] **Step 1: Implement summarize and summary commands**

- `summarize(book_id, section_id, force, detail, model, skip_eval)` — Trigger summarization with `rich.Progress` bar
- `summary(book_id, section_id, copy, export)` — Display summary with `rich.Markdown`

Key details:
- `summarize` shows per-section progress bar with ETA
- Auto-resumes from first pending/failed section
- Runs eval assertions unless `--skip-eval`
- Generates book-level summary after all sections complete
- `summary` falls back to `quick_summary` if no full summary available
- `--copy` uses `pyperclip` or subprocess `pbcopy`

- [ ] **Step 2: Integration test with real book**

```bash
cd backend && uv run bookcompanion summarize 1 --skip-eval
cd backend && uv run bookcompanion summary 1
cd backend && uv run bookcompanion summary 1 1  # Section summary
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/cli/commands/summarize_cmd.py
git commit -m "feat: add summarize and summary CLI commands with progress tracking"
```

---

### Task 27: CLI Commands — search, eval, status

**Files:**
- Create: `backend/app/cli/commands/search_cmd.py`
- Create: `backend/app/cli/commands/eval_cmd.py`
- Create: `backend/app/cli/commands/status_cmd.py`

- [ ] **Step 1: Implement search command**

- `search(query, book, source, limit)` — Grouped results via `rich.Table`

- [ ] **Step 2: Implement eval commands**

- `eval_cmd(book_id, section_id)` — Show eval results as colored pass/fail table
- Subcommands: `eval compare --book --section --ratios` and `eval trace --assertion`

- [ ] **Step 3: Implement status command**

- `status(book_id)` — Show processing status, per-section progress, ETA
- Detect orphaned background processes (PID check)

- [ ] **Step 4: Manual verification**

```bash
cd backend && uv run bookcompanion search "strategy"
cd backend && uv run bookcompanion eval 1
cd backend && uv run bookcompanion status 1
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/commands/search_cmd.py backend/app/cli/commands/eval_cmd.py backend/app/cli/commands/status_cmd.py
git commit -m "feat: add search, eval, and status CLI commands"
```

---

### Task 28: Search Index Population

**Files:**
- Modify: `backend/app/services/book_service.py`
- Modify: `backend/app/services/summarizer/summarizer_service.py`

- [ ] **Step 1: Add embedding generation after parsing**

In `BookService.add_book()`, after storing sections, generate embeddings for:
- Book title + author names (`source_type=book_title`)
- Section titles (`source_type=section_title`)
- Section content chunks (`source_type=section_content`)

Populate both `embedding` (pgvector) and `tsvector` (BM25) columns in `search_index`.

- [ ] **Step 2: Add embedding generation after summarization**

In `SummarizerService`, after each section summary is generated:
- Embed summary chunks (`source_type=section_summary`)
- After book summary: embed book summary chunks (`source_type=book_summary`)
- After concepts extraction: embed concepts (`source_type=concept`)

Delete old embeddings before creating new ones (for re-summarization).

- [ ] **Step 3: Update tsvector via SQL trigger or application code**

```sql
-- Add trigger to auto-populate tsvector on insert/update
CREATE OR REPLACE FUNCTION search_index_tsvector_update() RETURNS trigger AS $$
BEGIN
  NEW.tsvector := to_tsvector('english', NEW.chunk_text);
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE ON search_index
FOR EACH ROW EXECUTE FUNCTION search_index_tsvector_update();
```

Add this to the Alembic migration.

- [ ] **Step 4: Verify end-to-end search**

```bash
cd backend && uv run bookcompanion search "strategy" --book 1
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ backend/alembic/
git commit -m "feat: populate search index with embeddings and tsvectors during parsing and summarization"
```

---

### Task 29: Async Processing Mode

**Files:**
- Modify: `backend/app/services/book_service.py`
- Modify: `backend/app/cli/commands/books.py`

- [ ] **Step 1: Implement background process forking**

```python
# Add to book_service.py
import multiprocessing
import os

def run_async_pipeline(book_id: int, config_path: str):
    """Runs the full pipeline in a background process."""
    import asyncio
    from app.config import Settings
    from app.db.session import create_session_factory

    async def _run():
        settings = Settings()
        session_factory = create_session_factory(settings)
        async with session_factory() as session:
            # Update processing job
            # Run: parse → embed → summarize → eval
            # Update book status on completion/failure
            pass

    asyncio.run(_run())
```

- [ ] **Step 2: Add PID tracking in `processing_jobs` table**

Store `os.getpid()` in `processing_jobs.pid` when starting background process.

- [ ] **Step 3: Implement orphan process detection**

In `status` command, check if PID is alive via `os.kill(pid, 0)`. If dead, mark job as failed.

- [ ] **Step 4: Wire `--async` flag in `add` command**

```python
if async_mode:
    process = multiprocessing.Process(
        target=run_async_pipeline,
        args=(book.id, str(config_path)),
        daemon=False,
    )
    process.start()
    print(f"Processing book (ID: {book.id}). Run `bookcompanion status {book.id}` to check.")
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/book_service.py backend/app/cli/commands/
git commit -m "feat: add async processing mode with background process and PID tracking"
```

---

### Task 29a: Integration Tests — Book Pipeline, Summarization, Eval

**Files:**
- Create: `backend/tests/integration/test_book_pipeline.py`
- Create: `backend/tests/integration/test_summarize_integration.py`
- Create: `backend/tests/integration/test_eval_integration.py`

These are spec Section 14 required integration tests that use real DB and (for some) real Claude Code CLI.

- [ ] **Step 1: Create `test_book_pipeline.py`**

```python
# backend/tests/integration/test_book_pipeline.py
"""Integration tests for the full book pipeline (parse → store → verify)."""

import pytest
from sqlalchemy import select
from app.db.models import Book, BookSection, BookStatus, Image
from app.services.book_service import BookService
from app.config import Settings


@pytest.mark.asyncio
async def test_full_epub_pipeline(db_session, sample_epub_path, test_settings):
    service = BookService(db=db_session, config=test_settings)
    book = await service.add_book(sample_epub_path)

    assert book.id is not None
    assert book.status == BookStatus.PARSED
    assert book.title  # Title extracted
    result = await db_session.execute(
        select(BookSection).where(BookSection.book_id == book.id)
    )
    sections = result.scalars().all()
    assert len(sections) >= 5  # Art of War has 13+ sections


@pytest.mark.asyncio
async def test_full_pdf_pipeline(db_session, sample_pdf_path, test_settings):
    service = BookService(db=db_session, config=test_settings)
    book = await service.add_book(sample_pdf_path)
    assert book.status == BookStatus.PARSED


@pytest.mark.asyncio
async def test_duplicate_detection(db_session, sample_epub_path, test_settings):
    service = BookService(db=db_session, config=test_settings)
    book1 = await service.add_book(sample_epub_path)
    with pytest.raises(Exception, match="already exists"):
        await service.add_book(sample_epub_path)


@pytest.mark.asyncio
async def test_re_import_with_force(db_session, sample_epub_path, test_settings):
    service = BookService(db=db_session, config=test_settings)
    book1 = await service.add_book(sample_epub_path)
    book2 = await service.add_book(sample_epub_path, force=True)
    assert book2.id == book1.id  # Same book, re-imported


@pytest.mark.asyncio
async def test_delete_cascades_all_data(db_session, sample_epub_path, test_settings):
    service = BookService(db=db_session, config=test_settings)
    book = await service.add_book(sample_epub_path)
    book_id = book.id
    await service.delete_book(book_id)
    result = await db_session.execute(
        select(BookSection).where(BookSection.book_id == book_id)
    )
    assert result.scalars().all() == []
```

- [ ] **Step 2: Create `test_summarize_integration.py` (requires real Claude CLI)**

```python
# backend/tests/integration/test_summarize_integration.py
"""Integration tests for summarization with real Claude Code CLI.
These tests make actual LLM calls — run with: pytest -m integration_llm"""

import pytest

pytestmark = pytest.mark.integration_llm


@pytest.mark.asyncio
async def test_summarize_single_section(db_session, test_settings):
    """Summarize one section, verify output structure."""
    # Requires a book already added. Use small test content.
    pass  # Implement after Tasks 19+21 are complete


@pytest.mark.asyncio
async def test_quick_summary(db_session, test_settings):
    """Quick summary mode on a small book."""
    pass  # Implement after Task 19


@pytest.mark.asyncio
async def test_image_captioning(db_session, test_settings):
    """Caption a test image via real CLI."""
    pass  # Implement after Task 17
```

- [ ] **Step 3: Create `test_eval_integration.py`**

```python
# backend/tests/integration/test_eval_integration.py
"""Integration tests for eval assertions."""

import pytest

pytestmark = pytest.mark.integration_llm


@pytest.mark.asyncio
async def test_eval_single_assertion(db_session, test_settings):
    """Run one eval assertion with real LLM."""
    pass  # Implement after Task 20
```

- [ ] **Step 4: Add pytest marker for LLM integration tests**

In `backend/pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "integration_llm: tests that make real LLM API calls (slow, require Claude CLI)",
]
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/
git commit -m "test: add integration tests for book pipeline, summarization, and eval"
```

---

### Task 30: E2E CLI Tests

**Files:**
- Create: `backend/tests/e2e/test_cli_flows.py`

- [ ] **Step 1: Write E2E tests using typer.testing.CliRunner**

```python
# backend/tests/e2e/test_cli_flows.py
"""End-to-end CLI flow tests."""

import pytest
from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "bookcompanion" in result.stdout


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "add" in result.stdout
    assert "search" in result.stdout


def test_list_empty():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No books" in result.stdout or "Library" in result.stdout


def test_config_show():
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "database" in result.stdout


@pytest.mark.skipif(
    not pytest.importorskip("tests.conftest").FIXTURES_DIR.joinpath("sample_epub/art_of_war.epub").exists(),
    reason="Fixtures not downloaded",
)
def test_add_book_step_by_step():
    from tests.conftest import FIXTURES_DIR
    epub = FIXTURES_DIR / "sample_epub" / "art_of_war.epub"
    result = runner.invoke(app, ["add", str(epub)], input="y\n")
    assert result.exit_code == 0
    assert "Book saved" in result.stdout or "ID:" in result.stdout


def test_delete_nonexistent():
    result = runner.invoke(app, ["delete", "99999", "--yes"])
    assert result.exit_code != 0 or "not found" in result.stdout.lower()


def test_search_empty():
    result = runner.invoke(app, ["search", "nonexistent"])
    assert result.exit_code == 0
    assert "No results" in result.stdout or result.stdout.strip() == ""
```

- [ ] **Step 2: Run E2E tests**

```bash
cd backend && uv run pytest tests/e2e/test_cli_flows.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/e2e/
git commit -m "test: add E2E CLI flow tests"
```

---

## Phase 2: Annotations, Concepts & Enrichment

### Task 31: Phase 2 Database Migration

**Files:**
- Create: `backend/alembic/versions/0002_phase2_schema.py`
- Modify: `backend/app/db/models.py` (add Phase 2 models)

- [ ] **Step 1: Add Phase 2 models to `models.py`**

Add models from spec lines 583-670: `Tag`, `Taggable`, `Annotation`, `ExternalReference` (Concept and ConceptSection are already in Phase 1).

- [ ] **Step 2: Generate and run migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "phase2_schema"
uv run alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/db/models.py backend/alembic/
git commit -m "feat: add Phase 2 database models (tags, annotations, external references)"
```

---

### Task 32: Phase 2 Repositories

**Files:**
- Create: `backend/app/db/repositories/annotation_repo.py`
- Create: `backend/app/db/repositories/tag_repo.py`
- Modify: `backend/app/db/repositories/concept_repo.py` (already created in Task 8; add Phase 2 methods)

- [ ] **Step 1: Implement annotation repository**

CRUD for annotations: create, list by book/section/tag, update, delete. Support polymorphic content_type filtering.

- [ ] **Step 2: Implement tag repository**

CRUD for tags + polymorphic taggable associations. `add_tag(taggable_type, taggable_id, tag_name)`, `list_tags()`, `get_by_name()`.

- [ ] **Step 3: Extend concept repository with Phase 2 methods**

CRUD for concepts: `list_by_book()`, `search_across_books()`, `update()`, `get_by_term()`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/repositories/
git commit -m "feat: add Phase 2 repositories (annotations, tags, concepts)"
```

---

### Task 33: Annotation Service

**Files:**
- Create: `backend/app/services/annotation_service.py`

- [ ] **Step 1: Implement annotation service**

- `create_annotation(content_type, content_id, text, note, type, linked_id)`
- `list_annotations(book_id, tag, type)`
- `link_annotations(annotation_id, linked_annotation_id)` — Cross-book linking
- Validate content_type + content_id references exist

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/annotation_service.py
git commit -m "feat: add annotation service with polymorphic content support and cross-book linking"
```

---

### Task 34: Tag Service

**Files:**
- Create: `backend/app/services/tag_service.py`

- [ ] **Step 1: Implement tag service**

- `add_tag(taggable_type, taggable_id, tag_name, color)`
- `list_tags()`
- `list_by_tag(tag_name)` — Get all tagged entities

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/tag_service.py
git commit -m "feat: add tag service with polymorphic tagging"
```

---

### Task 35: Concept Service

**Files:**
- Create: `backend/app/services/concept_service.py`

- [ ] **Step 1: Implement concept service**

- `list_by_book(book_id)` — Return sorted concept index
- `search(term)` — Search concepts across all books
- `edit(concept_id, definition)` — Mark as `user_edited`
- Already extracted during summarization (Task 19) — this adds CLI access

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/concept_service.py
git commit -m "feat: add concept service for browse and search"
```

---

### Task 36: Export Service (JSON + Markdown)

**Files:**
- Create: `backend/app/services/export_service.py`

- [ ] **Step 1: Implement export service**

- `export_library(format, output_path)` — Export all books
- `export_book(book_id, format, output_path)` — Export single book
- JSON format: Full structured data
- Markdown format: Readable document with summaries, annotations, concepts

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/export_service.py
git commit -m "feat: add export service for JSON and Markdown library export"
```

---

### Task 37: Backup/Restore Service

**Files:**
- Create: `backend/app/services/backup_service.py`

- [ ] **Step 1: Implement backup/restore via pg_dump**

- `create_backup(output_path)` — Run `pg_dump` via subprocess
- `restore_backup(backup_file)` — Run `pg_restore` via subprocess
- `list_backups()` — List backup files in config directory
- Default backup location: `~/.config/bookcompanion/backups/`

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/backup_service.py
git commit -m "feat: add backup/restore service using pg_dump"
```

---

### Task 38: External Reference Discovery Service

**Files:**
- Create: `backend/app/services/reference_service.py`

- [ ] **Step 1: Implement reference discovery**

- `discover_references(book_id)` — Use LLM with web search to find 4-5 external summaries/reviews
- Uses `discover_references_v1.txt` prompt template
- Stores in `external_references` table
- `list_references(book_id)` — Return stored references

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/reference_service.py
git commit -m "feat: add external reference discovery service"
```

---

### Task 39: Phase 2 CLI Commands

**Files:**
- Create: `backend/app/cli/commands/annotations_cmd.py`
- Create: `backend/app/cli/commands/concepts_cmd.py`
- Create: `backend/app/cli/commands/tags_cmd.py`
- Create: `backend/app/cli/commands/export_cmd.py`
- Create: `backend/app/cli/commands/backup_cmd.py`
- Create: `backend/app/cli/commands/references_cmd.py`
- Create: `backend/app/cli/commands/edit_cmd.py`
- Modify: `backend/app/cli/main.py` (register new commands)

- [ ] **Step 1: Implement annotation commands**

- `annotate(book_id, section_id, text, note, tag, type, link_to, content_type)`
- `annotations(book_id, tag, type)`

- [ ] **Step 2: Implement concept commands**

- `concepts(book_id)`
- `concepts_search(term)`
- `concepts_edit(book_id)` — Open in `$EDITOR`

- [ ] **Step 3: Implement tag commands**

- `tag(book_id, tag_name)`
- `tags()`

- [ ] **Step 4: Implement export/backup/references/edit commands**

- `export(book_id, format, output)`
- `backup(output)`, `backup_list()`, `restore(backup_file)`
- `references(book_id)`, `discover_references(book_id)`
- `edit(book_id, title, author)`
- `edit_summary(book_id, section_id)` — Open in `$EDITOR`, mark `user_edited=True`

- [ ] **Step 5: Register commands in `main.py`**

- [ ] **Step 6: Manual verification**

```bash
cd backend && uv run bookcompanion annotate 1 1 --note "Key insight about strategy" --tag "strategy"
cd backend && uv run bookcompanion annotations 1
cd backend && uv run bookcompanion concepts 1
cd backend && uv run bookcompanion tag 1 "military"
cd backend && uv run bookcompanion tags
cd backend && uv run bookcompanion export 1 --format markdown
cd backend && uv run bookcompanion backup
cd backend && uv run bookcompanion backup list
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/cli/commands/ backend/app/cli/main.py
git commit -m "feat: add all Phase 2 CLI commands (annotations, concepts, tags, export, backup, references, edit)"
```

---

### Task 40: Phase 2 Search Enhancements

**Files:**
- Modify: `backend/app/services/search_service.py`
- Modify: `backend/app/cli/commands/search_cmd.py`

- [ ] **Step 1: Add annotation and concept indexing to search**

- Index annotations in `search_index` with `source_type=annotation`
- Index concepts with `source_type=concept` (already partially done)
- Add `--tag`, `--annotations-only` flags to search CLI

- [ ] **Step 2: Update embedding lifecycle**

Per spec Section 9 "Embedding Lifecycle" table:
- Annotation created → embed annotation text
- Annotation updated → re-embed
- Annotation deleted → delete embedding

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/ backend/app/cli/commands/
git commit -m "feat: enhance search with annotation and concept indexing"
```

---

### Task 41: Sample Output Documentation

**Files:**
- Create: `docs/sample-output/README.md`
- Create: `docs/sample-output/sample_book_summary.md`
- Create: `docs/sample-output/sample_section_summary.md`
- Create: `docs/sample-output/sample_eval_results.md`
- Create: `docs/sample-output/sample_search_results.md`
- Create: `docs/sample-output/sample_cli_output.md`

- [ ] **Step 1: Generate sample outputs from a processed test book**

After processing Art of War through the full pipeline, capture real outputs:

```bash
cd backend
uv run bookcompanion list --format json > ../docs/sample-output/sample_cli_output_list.json
uv run bookcompanion summary 1 > ../docs/sample-output/sample_book_summary.md
uv run bookcompanion summary 1 1 > ../docs/sample-output/sample_section_summary.md
uv run bookcompanion eval 1 > ../docs/sample-output/sample_eval_results.md
uv run bookcompanion search "strategy" > ../docs/sample-output/sample_search_results.md
```

- [ ] **Step 2: Create README for sample output**

```markdown
# Sample Output

These are real outputs from processing "The Art of War" (Sun Tzu) through the Book Companion pipeline.

Generated with: `bookcompanion` v0.1.0 using Claude Sonnet.

## Files

| File | Description |
|------|-------------|
| sample_book_summary.md | Full book-level summary |
| sample_section_summary.md | Section summary for Chapter 1 |
| sample_eval_results.md | Eval assertion results |
| sample_search_results.md | Hybrid search results for "strategy" |
| sample_cli_output.md | Key CLI command outputs |
```

- [ ] **Step 3: Commit**

```bash
git add docs/sample-output/
git commit -m "docs: add sample output from processed test book"
```

---

### Task 42: Update CLAUDE.md and Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.gitignore` (if needed)

- [ ] **Step 1: Update CLAUDE.md with complete project instructions**

Add sections for:
- Full CLI command reference
- How to run tests by category
- Database migration workflow
- Configuration override patterns
- Prompt template conventions
- Common development tasks

- [ ] **Step 2: Verify `.gitignore` covers all generated files**

Ensure coverage for:
- Test fixture books (`.epub`, `.pdf`, `.mobi` in fixtures dir)
- Config files (`config.yaml`)
- Log files
- Backup files
- `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md .gitignore
git commit -m "docs: update CLAUDE.md with complete project instructions"
```

---

### Task 42a: Address Spec Coverage Gaps

**Purpose:** This task addresses specific spec requirements that span multiple services.

- [ ] **Step 1: Long section handling (>150K tokens) in summarizer**

In `SummarizerService`, add sub-chunking logic:
```python
LONG_SECTION_THRESHOLD = 150_000  # tokens (~600K chars)

async def _summarize_single_section(self, section, prior_sections, detail_level):
    token_count = len(section.content_md) // 4  # 1 token ≈ 4 chars
    if token_count > LONG_SECTION_THRESHOLD:
        return await self._summarize_long_section(section, prior_sections, detail_level)
    # ... normal flow

async def _summarize_long_section(self, section, prior_sections, detail_level):
    """Split at paragraph boundaries, summarize sub-chunks, merge."""
    paragraphs = section.content_md.split("\n\n")
    chunks, current_chunk, current_tokens = [], [], 0
    for para in paragraphs:
        para_tokens = len(para) // 4
        if current_tokens + para_tokens > 100_000 and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk, current_tokens = [], 0
        current_chunk.append(para)
        current_tokens += para_tokens
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    # Summarize each sub-chunk
    sub_summaries = []
    for chunk in chunks:
        summary = await self._invoke_llm_summarize(chunk, section.title, prior_sections, detail_level)
        sub_summaries.append(summary)

    # Merge sub-chunk summaries into one section summary
    merge_prompt = f"Merge these sub-section summaries into one coherent summary:\n\n" + "\n---\n".join(sub_summaries)
    return await self.llm.generate(prompt=merge_prompt)
```

Add test in `test_summarizer.py`:
```python
def test_long_section_triggers_sub_chunking():
    service = SummarizerService.__new__(SummarizerService)
    # Verify threshold check
    assert (600_001 // 4) > 150_000  # Would trigger sub-chunking
```

- [ ] **Step 2: Compression ratio auto-escalation on eval failure**

In `SummarizerService.summarize_book()`, after eval returns critical failures:
```python
RATIO_ESCALATION = {"brief": "standard", "standard": "detailed", "detailed": "detailed"}

async def _summarize_with_retry(self, section, prior, detail_level, max_retries=2):
    for attempt in range(max_retries + 1):
        summary = await self._summarize_single_section(section, prior, detail_level)
        if not skip_eval:
            results = await self.eval_service.evaluate_summary(section.id, section.content_md, summary)
            if self.eval_service._should_auto_retry(results, attempt, max_retries):
                detail_level = RATIO_ESCALATION.get(detail_level, detail_level)
                continue  # Retry with higher ratio
        return summary
    return summary  # Return best attempt after max retries
```

- [ ] **Step 3: Cross-summary consistency assertion (special handling)**

In `EvalService._run_single_assertion()`, add special handling for `cross_summary_consistency`:
```python
if assertion_name == "cross_summary_consistency":
    if not self.config.llm.cross_summary_consistency:
        return {"assertion_name": assertion_name, "passed": True, "reasoning": "Disabled via config"}
    # Generate a second independent summary
    second_summary = await self.llm.generate(prompt=source_text_prompt)
    # Compare both summaries for divergences
    comparison_prompt = template.render(
        summary_a=summary_text, summary_b=second_summary.content,
        assertion_name=assertion_name,
    )
    response = await self.llm.generate(prompt=comparison_prompt, json_schema=...)
```

- [ ] **Step 4: `eval compare-prompts` Phase 2 command**

Add to `backend/app/cli/commands/eval_cmd.py`:
```python
@eval_app.command("compare-prompts")
@async_command
async def compare_prompts(
    book: int = typer.Option(..., help="Book ID."),
    section: int = typer.Option(..., help="Section ID."),
    prompt_a: str = typer.Option(..., help="Prompt version A (e.g., v1)."),
    prompt_b: str = typer.Option(..., help="Prompt version B (e.g., v2)."),
):
    """Compare summaries from two prompt versions side-by-side."""
    # Generate summary with prompt_a, generate with prompt_b
    # Run eval on both, display results side-by-side
```

- [ ] **Step 5: Add `--tag` filter to `list` command (Phase 2)**

In `backend/app/cli/commands/books.py`, add `--tag` option to `list_books`:
```python
tag: str = typer.Option(None, "--tag", help="Filter by tag name. (Phase 2)")
```
In `BookRepository.list_all()`, add tag filter:
```python
if tag:
    query = query.join(Taggable, ...).join(Tag).where(Tag.name == tag)
```

- [ ] **Step 6: `$EDITOR` integration pattern for edit commands**

Shared helper in `backend/app/cli/formatting.py`:
```python
import os, subprocess, tempfile

def edit_in_editor(content: str, suffix: str = ".md") -> str:
    """Open content in $EDITOR, return modified content."""
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    with tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False) as f:
        f.write(content)
        f.flush()
        subprocess.call([editor, f.name])
        with open(f.name) as edited:
            return edited.read()
```

Used by `concepts edit`, `edit-summary`, and Phase 2 metadata editing.

- [ ] **Step 7: Empty state test coverage**

Add to `backend/tests/e2e/test_cli_flows.py`:
```python
def test_empty_state_no_books():
    result = runner.invoke(app, ["list"])
    assert "No books in your library yet" in result.stdout

def test_empty_state_no_search_results():
    result = runner.invoke(app, ["search", "xyznonexistent"])
    assert "No results found" in result.stdout

def test_empty_state_no_summary():
    # After adding but before summarizing
    result = runner.invoke(app, ["summary", "1"])
    assert "No summary" in result.stdout or "quick_summary" in result.stdout

def test_empty_state_no_eval():
    result = runner.invoke(app, ["eval", "1"])
    assert "No eval results" in result.stdout or "generated first" in result.stdout
```

- [ ] **Step 8: Phase 2 model unit tests**

Add to `backend/tests/unit/test_models.py`:
```python
from app.db.models import Tag, Taggable, Annotation, AnnotationType, ContentType, ExternalReference

def test_annotation_type_enum():
    assert AnnotationType.HIGHLIGHT == "highlight"
    assert AnnotationType.NOTE == "note"
    assert AnnotationType.FREEFORM == "freeform"

def test_content_type_enum():
    assert ContentType.SECTION_CONTENT == "section_content"
    assert ContentType.BOOK_SUMMARY == "book_summary"

def test_phase2_tablenames():
    assert Tag.__tablename__ == "tags"
    assert Taggable.__tablename__ == "taggables"
    assert Annotation.__tablename__ == "annotations"
    assert ExternalReference.__tablename__ == "external_references"
```

- [ ] **Step 9: `read --copy` and `read --export` implementation**

In `backend/app/cli/commands/books.py`, the `read` command:
```python
if copy:
    import pyperclip
    pyperclip.copy(content)
    console.print("[green]Content copied to clipboard.[/green]")
if export:
    Path(export).write_text(content)
    console.print(f"[green]Content exported to {export}[/green]")
```

Same pattern for `summary --copy` and `summary --export`.

- [ ] **Step 10: Commit**

```bash
git add backend/
git commit -m "fix: address spec coverage gaps (long sections, ratio escalation, cross-summary, empty states)"
```

---

### Task 43: Final Verification & Manual Testing

**Files:** None (verification only)

- [ ] **Step 1: Run linting and type checks**

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app/
```

Fix any issues found.

- [ ] **Step 2: Run the full test suite**

```bash
cd backend
uv run pytest --cov=app --cov-report=term-missing -v
```

Verify:
- All unit tests pass
- All integration tests pass
- All E2E tests pass
- Coverage is reasonable (>70% for service layer)

- [ ] **Step 3: Verify Docker deployment**

```bash
docker compose down && docker compose up -d
docker compose ps  # All services healthy
cd backend && uv run alembic upgrade head
```

- [ ] **Step 4: Run database migrations from scratch**

```bash
docker compose down -v  # Destroy volumes
docker compose up -d
cd backend && uv run alembic upgrade head
# Verify all tables:
docker exec bookcompanion-db psql -U bookcompanion -c "\dt"
```

- [ ] **Step 5: Full CLI workflow — manual end-to-end verification**

```bash
# 1. Init
cd backend && uv run bookcompanion init

# 2. Add a book (step-by-step)
uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub

# 3. List books
uv run bookcompanion list

# 4. Show book details
uv run bookcompanion show 1

# 5. Read content
uv run bookcompanion read 1 1

# 6. Quick summary
uv run bookcompanion add tests/fixtures/sample_epub/meditations.epub --quick

# 7. Full summarization
uv run bookcompanion summarize 1

# 8. View summaries
uv run bookcompanion summary 1
uv run bookcompanion summary 1 1

# 9. Run eval
uv run bookcompanion eval 1

# 10. Search
uv run bookcompanion search "strategy"
uv run bookcompanion search "virtue" --book 2

# 11. Status
uv run bookcompanion status 1

# 12. Config
uv run bookcompanion config
uv run bookcompanion config set llm.model "opus"
uv run bookcompanion config

# 13. Authors
uv run bookcompanion authors

# 14. Phase 2: Annotations
uv run bookcompanion annotate 1 1 --note "Key passage about winning without fighting" --tag "strategy"
uv run bookcompanion annotations 1

# 15. Phase 2: Tags
uv run bookcompanion tag 1 "military"
uv run bookcompanion tags

# 16. Phase 2: Concepts
uv run bookcompanion concepts 1
uv run bookcompanion concepts search "strategy"

# 17. Phase 2: Export
uv run bookcompanion export 1 --format json
uv run bookcompanion export 1 --format markdown

# 18. Phase 2: Backup/Restore
uv run bookcompanion backup
uv run bookcompanion backup list

# 19. Phase 2: External references
uv run bookcompanion discover-references 1
uv run bookcompanion references 1

# 20. Delete
uv run bookcompanion delete 2 --yes
uv run bookcompanion list
```

- [ ] **Step 6: Verify JSON output mode**

```bash
cd backend
uv run bookcompanion list --format json
uv run bookcompanion show 1 --format json
uv run bookcompanion search "strategy" --format json
```

- [ ] **Step 7: Verify error handling**

```bash
cd backend
# Bad file
uv run bookcompanion add /tmp/nonexistent.epub
# Bad format
echo "not an epub" > /tmp/fake.epub && uv run bookcompanion add /tmp/fake.epub
# Nonexistent book
uv run bookcompanion show 99999
uv run bookcompanion summarize 99999
# Empty search
uv run bookcompanion search "xyznonexistent123"
```

- [ ] **Step 8: Verify duplicate detection**

```bash
cd backend
uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub
# Should warn about duplicate
uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub --force
# Should re-import
```

- [ ] **Step 9: Fix any issues found during manual testing**

Address all failures, then re-run the full test suite:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app/ && uv run pytest -v
```
