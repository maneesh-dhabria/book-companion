# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Book Companion is a personal tool for non-fiction book summarization and knowledge extraction. It parses EPUB/MOBI/PDF books, generates LLM-powered section and book summaries via Claude Code CLI subprocess, evaluates quality with a 16-assertion battery, and provides hybrid search (BM25 + semantic + RRF fusion) across a PostgreSQL + pgvector library. Two interfaces: a Typer CLI and a Vue 3 web UI backed by FastAPI. Layered monolith: CLI/API → async service layer → SQLAlchemy 2.0 repositories → PostgreSQL 16.

## Tech Stack

**Backend** (in `backend/`):
- Python 3.12+, uv (package manager), hatchling (build)
- Typer + Rich (CLI), FastAPI + uvicorn (web API), pydantic-settings (config), structlog (logging)
- SQLAlchemy 2.0 async (`asyncpg`), Alembic (migrations), pgvector
- PostgreSQL 16 + pgvector in Docker (port 5438)
- Ollama (`nomic-embed-text`, port 11434) for local embeddings
- Claude Code CLI as subprocess for LLM calls (stdin prompt, JSON output)
- ebooklib + markdownify (EPUB), pymupdf4llm (PDF), Calibre ebook-convert (MOBI)
- Jinja2 prompt templates, pytest + pytest-asyncio
- SSE via `sse-starlette` for real-time updates, APScheduler for automated backups

**Frontend** (in `frontend/`):
- Vue 3 + TypeScript + Vite 5
- Tailwind CSS v4 (`@tailwindcss/vite` plugin)
- Pinia (state), Vue Router 4, markdown-it + DOMPurify (rendering)
- Vitest (unit tests), Playwright (e2e tests)

**Environment**: Copy `.env.example` to `.env` before running Docker. Configures ports for DB (5438), API (8000), and Vite dev server (5173).

## Commands

### Backend (run from `backend/`)

```bash
# Dev
uv sync --dev                          # Install all dependencies
uv run bookcompanion --help            # CLI help
uv run bookcompanion init              # First-time setup (Docker, migrations, Ollama)
uv run uvicorn app.api.main:app --reload --port 8000  # Start API dev server

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

# V1.3 CLI Additions
uv run bookcompanion summarize <book_id> --no-retry          # Skip auto-retry on eval failure
uv run bookcompanion summarize <book_id> --skip-eval         # Skip eval (implies no retry)
uv run bookcompanion eval <book_id> --book-only              # Show only book-level eval results
uv run bookcompanion eval <book_id> <section_id> --force     # Re-run eval on section
uv run bookcompanion eval <book_id> --summary-id <id>        # Evaluate a specific summary
```

### Frontend (run from `frontend/`)

```bash
npm install                            # Install dependencies
npm run dev                            # Vite dev server (port 5173, proxies /api → localhost:8000)
npm run build                          # Production build (type-check + vite build → dist/)
npm run test:unit                      # Vitest unit tests
npm run test:e2e                       # Playwright e2e tests
npm run lint                           # ESLint --fix
npm run format                         # Prettier
npm run type-check                     # vue-tsc type checking
```

### Docker (production, from repo root)

```bash
docker compose up -d                   # Start DB + backend (builds frontend in multi-stage Dockerfile)
docker compose down -v                 # Destroy volumes and recreate
```

The Dockerfile is a two-stage build: Node 20 builds the Vue SPA, then Python 3.12-slim serves it as static files via FastAPI alongside the API. Container runs `alembic upgrade head` on startup, then launches uvicorn on port 8000. Bind mounts: `./data/backups` and `./data/config`.

## Architecture

```
Vue 3 SPA (frontend/)              CLI Command (Typer)
  │  Axios → /api/*                  │  @async_command wraps asyncio.run()
  ▼                                  ▼
FastAPI (app/api/)              deps.get_services()
  │  SSE for real-time updates       │  yields dict of services sharing one AsyncSession
  ▼                                  ▼
                    Service Layer (async, shared)
  ├── BookService         — parse, store, lifecycle orchestration
  ├── SummarizerService   — map-reduce: section summaries → book summary
  ├── EvalService         — 16 assertions in parallel, EvalTrace storage
  ├── SearchService       — BM25 (tsvector) + semantic (cosine) + RRF fusion
  ├── EmbeddingService    — Ollama HTTP, semaphore-limited (5 concurrent)
  ├── PresetService        — Load/validate/create/delete YAML presets
  ├── QualityService       — 10 deterministic extraction quality checks
  ├── SummaryService       — List, compare, set-default, concept diff
  ├── SectionEditService   — Merge/split/reorder/delete (memory + DB)
  ├── BackupService        — Automated/manual backups with APScheduler
  ├── AnnotationService, ConceptService, ExportService, etc.
  │
  ▼
Repository Layer (thin query builders)
  │  selectinload() for eager relationship loading
  ▼
SQLAlchemy 2.0 async  →  asyncpg  →  PostgreSQL 16 + pgvector
```

### Key Patterns

- **Constructor DI**: Services receive `AsyncSession`, `LLMProvider`, `Settings` via constructor. CLI wired in `cli/deps.py:get_services()`. API wired via FastAPI dependency injection in `app/api/deps.py` using `app.state.session_factory`.
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
| Section Type | Auto-detected type: chapter, glossary, notes, appendix, etc. (`SectionType` enum) |
| Eval Run ID | UUID grouping all traces from one `evaluate_summary()` call |
| Golden Set | Synthetic test fixtures in `tests/fixtures/golden_eval/` for regression testing |
| Deterministic Assertion | Eval check using pure code (regex/math), not LLM: `reasonable_length`, `has_key_concepts`, `image_refs_preserved` |
| Quality Warning | Post-processing check stored on Summary (e.g., paraphrased quotes) |
| Auto-Retry | When critical/important eval assertions fail, re-summarize with fix instructions |

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
15. **`eval_json` is derived from traces (V1.3)**: `Summary.eval_json` is computed from `EvalTrace` rows via `EvalService.compute_eval_json()`. The wrapped format includes `{passed, total, eval_run_id, assertions: {name: {passed, reasoning, ...}}}`. All callers must consume the `assertions` key.
16. **Stale eval traces**: Re-import marks traces as `is_stale=True` before section deletion. All `eval_repo` queries filter `WHERE is_stale = FALSE` by default. Pass `include_stale=True` to see old traces.
17. **Deterministic assertions skip LLM**: `reasonable_length`, `has_key_concepts`, `image_refs_preserved` use pure code checks. Their `EvalTrace` has `model_used="deterministic"`, `prompt_sent=None`.
18. **Vite proxy**: In dev, the frontend proxies `/api` requests to `localhost:8000`. In production Docker, FastAPI serves the built SPA from `./static/` — no separate frontend server.
19. **CORS in dev**: FastAPI CORS middleware allows `localhost:5173` (Vite dev server). Not needed in production since same-origin.
20. **Two-stage Docker build**: Node 20 builds the Vue SPA, Python 3.12-slim runs it. If frontend build fails, the entire Docker build fails.

## Extended Docs

| Path | Description |
|------|-------------|
| `docs/specs/2026-04-01_book_companion_v1_spec.md` | V1 spec: models, CLI signatures, eval assertions, search algorithm |
| `docs/requirements/2026-04-01_book_companion_v1_requirements.md` | Product requirements |
| `docs/plans/2026-04-02_book_companion_v1_implementation.md` | 43-task implementation plan with complete code |
| `docs/requirements/2026-04-10_web_interface_v1_requirements.md` | Web interface requirements |
| `docs/specs/2026-04-10_web_interface_v1_spec.md` | Web interface spec: API routes, Vue components, SSE events |
| `docs/plans/2026-04-10-web-interface-phase*` | Web interface implementation plans (3 phases) |
| `docs/changelog.md` | User-facing changelog |
| `backend/tests/fixtures/README.md` | How to download Gutenberg test books |

## Workflows

### Adding a new CLI command
1. Create `backend/app/cli/commands/my_cmd.py` with `@async_command` decorated function
2. Wire service dependencies via `async with get_services() as svc:`
3. Register in `backend/app/cli/main.py`: `app.command("my-cmd")(my_cmd.my_function)`
4. Add to `cli/deps.py:get_services()` if the command needs a new service

### Adding a new API route
1. Create `backend/app/api/routes/my_route.py` with FastAPI router
2. Import and include in `backend/app/api/main.py` with appropriate prefix
3. Use `get_session` dependency from `app/api/deps.py` for DB access
4. Use `app.state.event_bus` for SSE notifications if needed

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
