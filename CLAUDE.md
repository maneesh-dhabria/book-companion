# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Book Companion is a personal CLI tool for non-fiction book summarization and knowledge extraction. It parses EPUB/MOBI/PDF books, generates LLM-powered section and book summaries via Claude Code CLI subprocess, evaluates quality with a 16-assertion battery, and provides hybrid search (BM25 + semantic + RRF fusion) across a PostgreSQL + pgvector library. Layered monolith: Typer CLI → async service layer → SQLAlchemy 2.0 repositories → PostgreSQL 16.

## Tech Stack

- Python 3.12+, uv (package manager), hatchling (build)
- Typer + Rich (CLI), pydantic-settings (config), structlog (logging)
- SQLAlchemy 2.0 async (`asyncpg`), Alembic (migrations), pgvector
- PostgreSQL 16 + pgvector in Docker (port 5438)
- Ollama (`nomic-embed-text`, port 11434) for local embeddings
- Claude Code CLI as subprocess for LLM calls (stdin prompt, JSON output)
- ebooklib + markdownify (EPUB), pymupdf4llm (PDF), Calibre ebook-convert (MOBI)
- Jinja2 prompt templates, pytest + pytest-asyncio

## Commands

All commands run from `backend/`:

```bash
# Dev
uv sync --dev                          # Install all dependencies
uv run bookcompanion --help            # CLI help
uv run bookcompanion init              # First-time setup (Docker, migrations, Ollama)

# Test
uv run python -m pytest tests/                    # Full suite (78 tests)
uv run python -m pytest tests/unit/ -v             # Unit tests only
uv run python -m pytest tests/integration/ -v      # Integration (needs running DB)
uv run python -m pytest tests/e2e/ -v              # E2E CLI tests
uv run python -m pytest tests/unit/test_config.py::test_default_settings -v  # Single test
uv run python -m pytest -m "not integration_llm"   # Skip tests needing real Claude CLI
uv run python -m pytest --cov=app --cov-report=term-missing  # With coverage

# Lint
uv run ruff check .                    # Lint
uv run ruff format --check .           # Format check
uv run ruff format .                   # Auto-format

# Database
docker compose up -d                              # Start PostgreSQL (from repo root)
docker compose down -v                            # Destroy and recreate DB
uv run alembic upgrade head                       # Run migrations
uv run alembic revision --autogenerate -m "desc"  # Generate migration after model changes
BOOKCOMPANION_DATABASE__URL=postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test uv run alembic upgrade head  # Migrate test DB

# Fixtures
python3 tests/fixtures/download_fixtures.py       # Download Gutenberg test books

# V1.1 CLI Commands
uv run bookcompanion preset list              # List all presets
uv run bookcompanion preset show <name>        # Show preset details
uv run bookcompanion preset create <name>      # Create user preset
uv run bookcompanion preset delete <name>      # Delete user preset
uv run bookcompanion summary read <book_id> [section_id]  # Read default summary
uv run bookcompanion summary list <book_id>    # List all summaries
uv run bookcompanion summary compare <id1> <id2>  # Compare summaries
uv run bookcompanion summary set-default <id>  # Set default summary
uv run bookcompanion summary show <id>         # Show summary with metadata
uv run bookcompanion read <book_id> <section_id> [--with-summary]  # Read section content
uv run bookcompanion edit sections <book_id>   # Interactive section editing
```

## Architecture

```
CLI Command (Typer)
  │  @async_command wraps asyncio.run()
  ▼
deps.get_services()  →  yields dict of services sharing one AsyncSession
  │
  ▼
Service Layer (async)
  ├── BookService         — parse, store, lifecycle orchestration
  ├── SummarizerService   — map-reduce: section summaries → book summary
  ├── EvalService         — 16 assertions in parallel, EvalTrace storage
  ├── SearchService       — BM25 (tsvector) + semantic (cosine) + RRF fusion
  ├── EmbeddingService    — Ollama HTTP, semaphore-limited (5 concurrent)
  ├── PresetService        — Load/validate/create/delete YAML presets
  ├── QualityService       — 10 deterministic extraction quality checks
  ├── SummaryService       — List, compare, set-default, concept diff
  ├── SectionEditService   — Merge/split/reorder/delete (memory + DB)
  └── [Phase 2]           — annotation, tag, concept, export, backup, reference
  │
  ▼
Repository Layer (thin query builders)
  │  selectinload() for eager relationship loading
  ▼
SQLAlchemy 2.0 async  →  asyncpg  →  PostgreSQL 16 + pgvector
```

### Key Patterns

- **Constructor DI**: Services receive `AsyncSession`, `LLMProvider`, `Settings` via constructor. Wired in `cli/deps.py:get_services()`.
- **Async-first**: Everything is async. CLI boundary uses `asyncio.run()`. No sync DB access.
- **Eager loading required**: `expire_on_commit=False` on sessions means lazy-loaded relationships break after commit. Every repo query must use `selectinload()` for relationships accessed after the query.
- **LLM via subprocess**: `ClaudeCodeCLIProvider` invokes `claude -p - --output-format json --print` with prompt piped via stdin. JSON schema for structured output via `--json-schema`.
- **Faceted prompts**: Jinja2 base templates include fragment files based on 4 facet dimensions. Preset YAML files define named combinations. `PresetService.resolve_facets()` merges preset + CLI overrides.
- **Graceful degradation**: Service imports in `deps.py` are wrapped in try/except — commands work even if some services aren't fully implemented.
- **Relationship-level ordering**: Collection ordering (e.g., `Book.sections`) uses `order_by` on the `relationship()` definition, not per-query. Prevents sorting regressions across commands.
- **Compression enforcement**: Prompt templates receive `target_chars` (explicit character count) alongside percentage guidance. `SummarizerService` retries once if summary >= source length.

### Domain Terms

| Term | Meaning |
|------|---------|
| Section | Chapter/part of a book (`BookSection` model) |
| Cumulative context | Summaries of prior sections passed to LLM for coherence |
| Detail level | Compression ratio: brief (10%), standard (20%), detailed (30%) |
| Assertion | One eval check (e.g., `no_hallucinated_facts`). 16 total across 5 categories. |
| RRF | Reciprocal Rank Fusion — merges BM25 and semantic search rankings |
| Processing job | Background task tracked in DB with PID for orphan detection |
| Preset | Named facet combination (YAML file) for summarization |
| Facet | One of 4 dimensions: style, audience, compression, content_focus |
| Fragment | Jinja2 template snippet for one facet value |
| Summary Log | Append-only summaries table (replaces inline summary_md) |
| Default Summary | The active summary for a section/book (default_summary_id FK) |

## Code Style

- Imports: `from app.db.models import Book, BookStatus` (absolute from `app` root)
- Services: async methods, receive deps via constructor, no global state
- Repositories: thin query builders only, no business logic. Return model instances.
- CLI commands: thin wrappers that call `async with get_services() as svc:` then delegate to services
- Enums: `class BookStatus(str, enum.Enum)` — stored as strings in DB, comparable with `==`
- Exceptions: inherit from `BookCompanionError` in `app/exceptions.py`
- Logging: `structlog.get_logger()` at module level, structured key-value events

## Gotchas

1. **Lazy loading after commit crashes**: Accessing `book.sections` or `book.authors` after `session.commit()` raises `MissingGreenlet`. Fix: use `selectinload()` in repo queries, or re-fetch via `get_by_id()` after commit.
2. **Config test pollution**: The e2e `config set` test writes to `~/.config/bookcompanion/config.yaml`. Unit config tests must clean this up (see `tests/unit/test_config.py` `clean_env` fixture).
3. **Integration tests commit to real DB**: `book_service.add_book()` calls `session.commit()`. Integration tests must clean up via explicit DELETE statements (not rollback), using the `clean_db` fixture pattern.
4. **Two `async_command` decorators exist**: One in `cli/deps.py` (used by Phase 1 commands) and one in `cli/async_utils.py` (used by some Phase 2 commands). Both wrap `asyncio.run()` identically.
5. **Every CLI invocation runs orphan checks + migration checks**: Both are non-blocking (failures silently caught), but they hit the DB. Set `--verbose` for debug logs.
6. **Alembic uses async engine**: `alembic/env.py` runs `asyncio.run(run_migrations_online())`. The `alembic.ini` URL is only used for offline mode.
7. **Test DB must be created manually**: `CREATE DATABASE bookcompanion_test` with `CREATE EXTENSION vector` — not handled by Alembic.
8. **pgvector import in migrations**: Auto-generated migrations reference `pgvector.sqlalchemy.vector.VECTOR`. Must manually fix to `from pgvector.sqlalchemy import Vector` and use `Vector(dim=768)`.
9. **`SummaryStatus` enum removed in V1.1**: Replaced by `default_summary_id` FK pattern.
10. **`summary_md` removed from `BookSection`**: Summaries now live in `summaries` table.
11. **`overall_summary` removed from `Book`**: Use `default_summary_id` to point to a Summary row.
12. **Claude CLI `structured_output` field**: With `--json-schema`, the CLI returns parsed JSON in `structured_output`, not `result` (which is empty). Any code parsing structured responses must check `structured_output` first.
13. **Re-import must preserve section IDs**: `_re_import_book` updates sections in-place by `order_index`. Delete-and-recreate orphans summaries/evals since `Summary.content_id` is not a FK and won't cascade.
14. **`get_services()` does not auto-commit**: CLI commands that persist data must call `session.commit()` explicitly. `flush()` alone loses changes when the session closes.

## Extended Docs

| Path | Description |
|------|-------------|
| `docs/specs/2026-04-01_book_companion_v1_spec.md` | V1 spec: models, CLI signatures, eval assertions, search algorithm |
| `docs/requirements/2026-04-01_book_companion_v1_requirements.md` | Product requirements |
| `docs/plans/2026-04-02_book_companion_v1_implementation.md` | 43-task implementation plan with complete code |
| `backend/tests/fixtures/README.md` | How to download Gutenberg test books |

## Workflows

### Adding a new CLI command
1. Create `backend/app/cli/commands/my_cmd.py` with `@async_command` decorated function
2. Wire service dependencies via `async with get_services() as svc:`
3. Register in `backend/app/cli/main.py`: `app.command("my-cmd")(my_cmd.my_function)`
4. Add to `cli/deps.py:get_services()` if the command needs a new service

### Adding a new prompt version
1. Copy existing template: `cp prompts/summarize_section_v1.txt prompts/summarize_section_v2.txt`
2. Edit the new template
3. Update `Settings.summarization.prompt_version` default or use: `bookcompanion config set summarization.prompt_version v2`
4. Update template loading in the relevant service to use `f"summarize_section_{version}.txt"`

### Running a book through the full pipeline
```bash
bookcompanion add path/to/book.epub           # Parse + store (quality checks + section editing)
bookcompanion summarize <book_id> --preset practitioner_bullets  # Summarize with preset
bookcompanion summary list <book_id>          # View summary log
bookcompanion summary read <book_id>          # Read default book summary
bookcompanion eval <book_id>                  # View eval assertion results
bookcompanion search "query"                  # Hybrid search across library
bookcompanion export book <book_id> --format markdown  # Export
```

### Fresh database setup
```bash
docker compose down -v && docker compose up -d
sleep 5
docker exec bookcompanion-db psql -U bookcompanion -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec bookcompanion-db psql -U bookcompanion -c "CREATE DATABASE bookcompanion_test OWNER bookcompanion;"
docker exec bookcompanion-db psql -U bookcompanion -d bookcompanion_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
cd backend && uv run alembic upgrade head
```

### Session logging & changelog
- Before ending a significant session (meaningful work done, not trivial fixes), offer to run `/session-log` to capture learnings
- After merging to main, run `/changelog` to record user-facing changes
