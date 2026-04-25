# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Book Companion is a personal tool for non-fiction book summarization and knowledge extraction. It parses EPUB/MOBI/PDF books, generates LLM-powered section and book summaries via a pluggable CLI provider (Claude Code or Codex), evaluates quality with a 16-assertion battery, and provides hybrid search (BM25 via FTS5 + semantic via in-process cosine similarity + RRF fusion). Two interfaces: a Typer CLI and a Vue 3 web UI backed by FastAPI. Layered monolith: CLI/API → async service layer → SQLAlchemy 2.0 repositories → SQLite (embedded). Zero-service install: `pip install bookcompanion && bookcompanion serve`.

## Tech Stack

**Backend** (in `backend/`):
- Python 3.12+, uv (package manager), hatchling (build)
- Typer + Rich (CLI), FastAPI + uvicorn (web API), pydantic-settings (config), structlog (logging)
- SQLAlchemy 2.0 async with **aiosqlite**, Alembic (migrations with `render_as_batch=True`)
- **SQLite** with FTS5 virtual table for BM25 full-text search
- **fastembed** (`sentence-transformers/all-MiniLM-L6-v2`, 384-dim) for in-process embeddings
- Cosine similarity computed in Python via **numpy** (no vector DB extension)
- LLM via subprocess: auto-detects **Claude Code CLI** or **Codex CLI** on `$PATH`
- ebooklib + markdownify (EPUB), pymupdf4llm (PDF), Calibre ebook-convert (MOBI, optional)
- Jinja2 prompt templates, pytest + pytest-asyncio, platformdirs (XDG data directory)
- SSE via `sse-starlette` for real-time updates, APScheduler for periodic backups

**Frontend** (in `frontend/`):
- Vue 3 + TypeScript + Vite 5
- Tailwind CSS v4 (`@tailwindcss/vite` plugin)
- Pinia (state), Vue Router 4, markdown-it + DOMPurify (rendering)
- Vitest (unit tests), Playwright (e2e tests)

**Data location (XDG-compliant via `platformdirs`):**
- Linux: `~/.local/share/bookcompanion/`
- macOS: `~/Library/Application Support/bookcompanion/`
- Windows: `%LOCALAPPDATA%/bookcompanion/`
- Override via `BOOKCOMPANION_DATA__DIRECTORY` env var

## Commands

> **Front door:** `make help` lists every dev-loop and verification target. The Makefile delegates to `./test.sh` for the packaging/verification ladder (see `docs/specs/2026-04-25-makefile-dev-loop-spec.md`).

### Backend (run from `backend/`)

```bash
# Dev
uv sync --dev                          # Install all dependencies
uv run bookcompanion --help            # CLI help
uv run bookcompanion init              # First-time setup: create data dir, run migrations, download fastembed model, detect LLM providers
uv run bookcompanion serve             # Start web server (auto-runs init if library.db is missing); prints localhost + LAN URLs

# Test
uv run python -m pytest tests/                    # Full suite (~440 tests pass)
uv run python -m pytest tests/unit/ -v             # Unit tests only
uv run python -m pytest tests/integration/ -v      # Integration
uv run python -m pytest tests/e2e/ -v              # E2E CLI tests
uv run python -m pytest tests/unit/test_config.py::test_default_settings -v  # Single test
uv run python -m pytest -m "not integration_llm"   # Skip tests needing real Claude CLI
uv run python -m pytest --cov=app --cov-report=term-missing  # With coverage

# Lint
uv run ruff check .                    # Lint
uv run ruff format --check .           # Format check
uv run ruff format .                   # Auto-format

# Database
uv run alembic -c app/migrations/alembic.ini upgrade head          # Run migrations (SQLite file)
uv run alembic -c app/migrations/alembic.ini revision --autogenerate -m "desc"  # Generate migration

# Fixtures
python3 tests/fixtures/download_fixtures.py       # Download Gutenberg test books

# CLI — Core
uv run bookcompanion add path/to/book.epub                        # Parse + store + index
uv run bookcompanion summarize <book_id> --preset practitioner_bullets
uv run bookcompanion search "query"
uv run bookcompanion list

# CLI — Presets & summaries
uv run bookcompanion preset list                                   # List all presets
uv run bookcompanion preset show <name>                            # Show preset details
uv run bookcompanion preset create <name>                          # Create user preset
uv run bookcompanion summary read <book_id> [section_id]           # Read default summary
uv run bookcompanion summary list <book_id>                        # List all summaries
uv run bookcompanion summary compare <id1> <id2>                   # Compare summaries
uv run bookcompanion summary set-default <id>                      # Set default summary
uv run bookcompanion read <book_id> <section_id> [--with-summary]  # Read section content
uv run bookcompanion edit sections <book_id>                       # Interactive section editing

# CLI — Eval & auto-retry
uv run bookcompanion summarize <book_id> --no-retry                # Skip auto-retry on eval failure
uv run bookcompanion summarize <book_id> --skip-eval               # Skip eval (implies no retry)
uv run bookcompanion eval <book_id> --book-only                    # Show only book-level eval results
uv run bookcompanion eval <book_id> <section_id> --force           # Re-run eval on section
uv run bookcompanion eval <book_id> --summary-id <id>              # Evaluate a specific summary
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

### Distribution

The tool is designed to install and run with zero external services:
- No Docker required
- No PostgreSQL/Ollama/external DBs
- Only `claude` or `codex` CLI needs to be installed on the host (auto-detected)
- Embedding model (~23MB) is downloaded to the data directory on first `init`

## Architecture

```
Vue 3 SPA (frontend/)              CLI Command (Typer)
  │  fetch → /api/*                  │  @async_command wraps asyncio.run()
  ▼                                  ▼
FastAPI (app/api/)              deps.get_services()
  │  SSE for real-time updates       │  yields dict of services sharing one AsyncSession
  │  Dynamic CORS (auto LAN IPs)     │
  ▼                                  ▼
                    Service Layer (async, shared)
  ├── BookService         — parse, store, lifecycle orchestration
  ├── SummarizerService   — map-reduce: section summaries → book summary; resolves facets via PresetService
  ├── EvalService         — 16 assertions in parallel, EvalTrace storage, auto-retry
  ├── SearchService       — BM25 (FTS5) + semantic (numpy cosine) + RRF fusion
  ├── EmbeddingService    — fastembed in-process (lazy init, asyncio.to_thread wrapping)
  ├── PresetService        — Load/validate/create/delete YAML presets
  ├── QualityService       — 10 deterministic extraction quality checks
  ├── SummaryService       — List, compare, set-default, concept diff
  ├── SectionEditService   — Merge/split/reorder/delete
  ├── BackupService        — shutil.copy2 of library.db with retention; scheduled via APScheduler
  ├── AnnotationService, ConceptService, ExportService, etc.
  │
  ▼
Repository Layer (thin query builders)
  │  selectinload() for eager relationship loading; undefer() for deferred columns
  ▼
SQLAlchemy 2.0 async  →  aiosqlite  →  SQLite (library.db) + FTS5 virtual table
```

**LLM Provider (pluggable):**
```
LLMProvider (ABC) — app/services/summarizer/llm_provider.py
  ├── ClaudeCodeCLIProvider — subprocess: claude -p - --output-format json
  └── CodexCLIProvider       — subprocess: codex -p <prompt> --model <model>

Factory: app/services/summarizer/__init__.py
  ├── detect_llm_provider() — shutil.which("claude") || shutil.which("codex")
  └── create_llm_provider(provider, **kwargs) — returns provider or None
```

### Key Patterns

- **Constructor DI**: Services receive `AsyncSession`, `LLMProvider`, `Settings` via constructor. CLI wired in `cli/deps.py:get_services()`. API wired via FastAPI dependency injection in `app/api/deps.py` using `app.state.session_factory`.
- **Async-first**: Everything is async. CLI boundary uses `asyncio.run()`. No sync DB access.
- **Eager loading required**: `expire_on_commit=False` on sessions means lazy-loaded relationships break after commit. Every repo query that feeds downstream services must use `selectinload()`. Deferred columns (e.g., `Image.data`) need `undefer()`.
- **LLM via subprocess**: `ClaudeCodeCLIProvider` invokes `claude -p - --output-format json --print` with prompt piped via stdin. JSON schema for structured output via `--json-schema`. `CodexCLIProvider` mirrors this with Codex CLI flags (injects schema into prompt since Codex lacks a `--json-schema` flag).
- **Provider auto-detection**: `LLMConfig.provider` defaults to `"auto"`. On startup, `detect_llm_provider()` picks the first CLI found on `$PATH` (Claude preferred over Codex). If neither is installed, summarization features are disabled; library/search/reading/annotations still work.
- **Faceted prompts**: Jinja2 base templates include fragment files based on 4 facet dimensions (style, audience, compression, content_focus). Preset YAML files define named combinations. `SummarizerService.summarize_book()` resolves facets from `preset_name` via `PresetService.resolve_facets()` if the caller didn't provide a full `facets` dict. Validation raises `PresetError` if any dimension is missing or invalid.
- **SQLite WAL mode**: `session.py` enables `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` via a `connect` event listener. WAL allows concurrent reads during writes (acceptable for single-user tool).
- **Hybrid search**: BM25 via raw SQL against FTS5 virtual table; semantic via loading `SearchIndex.embedding` BLOBs (serialized float32 via `struct.pack`) and computing cosine similarity in numpy. No sqlite-vec extension — avoids the macOS system-Python extension-loading limitation.
- **Dynamic CORS**: `app/api/main.py:build_cors_origins()` detects all non-loopback IPv4 interfaces and adds `http://{ip}:{port}` to the allowed origins so any LAN device can reach the UI. `BOOKCOMPANION_CORS_EXTRA_ORIGINS` env var for extras.
- **Graceful degradation**: Service imports in `deps.py` are wrapped in try/except. When no LLM provider is detected, `get_summarizer_service()` and `get_eval_service()` return `None`; callers check and handle gracefully.
- **Compression enforcement**: Prompt templates receive `target_chars` (explicit character count). `SummarizerService` retries once if summary >= source length.

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
| Summary Log | Append-only summaries table |
| Default Summary | The active summary for a section/book (default_summary_id FK) |
| Section Type | Auto-detected type: chapter, glossary, notes, appendix, etc. |
| Eval Run ID | UUID grouping all traces from one `evaluate_summary()` call |
| Deterministic Assertion | Eval check using pure code (regex/math), not LLM |
| Auto-Retry | When critical/important eval assertions fail, re-summarize with fix instructions |
| FTS5 shadow table | SQLite virtual table `search_fts` auto-synced to `search_index` via triggers |
| Embedding BLOB | 384 float32 values packed via `struct.pack("<384f", ...)` stored in `SearchIndex.embedding` |

## Code Style

- Imports: `from app.db.models import Book, BookStatus` (absolute from `app` root)
- Services: async methods, receive deps via constructor, no global state
- Repositories: thin query builders only, no business logic. Return model instances.
- CLI commands: thin wrappers that call `async with get_services() as svc:` then delegate to services
- Enums: `class BookStatus(str, enum.Enum)` — stored as strings in DB, comparable with `==`
- Exceptions: inherit from `BookCompanionError` in `app/exceptions.py`
- Logging: `structlog.get_logger()` at module level, structured key-value events
- IDs: use `Integer` for primary keys (SQLite requires `INTEGER PRIMARY KEY` for autoincrement, not `BIGINT`)

## Gotchas

1. **SQLite + deferred columns**: `Image.data` is `deferred(mapped_column(LargeBinary, ...))`. Accessing it later triggers async lazy-load which fails in sync contexts with `MissingGreenlet`. `section_repo.get_by_book_id()` must use `selectinload(BookSection.images).undefer(Image.data)` so image bytes are loaded eagerly.
2. **SQLite autoincrement requires Integer PK**: Use `Integer` (not `BigInteger`) for primary keys. SQLite's INTEGER is already 8 bytes and is the only type that supports autoincrement with RETURNING.
3. **Facet resolution lives in the service**: `SummarizerService.summarize_book()` resolves facets from `preset_name` if the caller's `facets` dict is incomplete. Do NOT call `resolve_facets()` only at the CLI — that caused the web UI to crash with `'audience' undefined`.
4. **API route validates preset_name upfront**: The `POST /api/v1/books/{id}/summarize` route calls `PresetService().load()` before queuing the job. Invalid preset → 400 immediately, not a silent background failure.
5. **Job completion semantics**: `summarize_book()` returns `{completed, skipped, failed, retried}`. The processing route marks the job `FAILED` only if `completed == 0 and failed > 0`. Partial failures still mark `COMPLETED` but include counts in `error_message`.
6. **LLM provider may be None**: Never assume `get_summarizer_service()` / `get_eval_service()` return a service. When Claude/Codex CLI is not on `$PATH`, they return `None`. UI must show the "no LLM provider" banner and skip summarization actions.
7. **Lazy loading after commit crashes**: Accessing `book.sections` or `book.authors` after `session.commit()` raises `MissingGreenlet`. Fix: use `selectinload()` in repo queries, or re-fetch via `get_by_id()` after commit.
8. **Alembic async engine**: `app/migrations/env.py` runs `asyncio.run(run_migrations_online())`, uses `render_as_batch=True` for SQLite ALTER TABLE compatibility. `env.py` reads `Settings().database.url` directly — it does NOT honor `Config.set_main_option("sqlalchemy.url", ...)`, so tests that need to redirect migrations use `BOOKCOMPANION_DATABASE__URL` env var. `init_cmd._run_migrations()` dispatches to a worker thread because `init` already runs inside an `asyncio.run` via `@async_command`; nested `asyncio.run` is forbidden.
9. **FTS5 triggers auto-sync**: `search_fts` virtual table has AI/AD/AU triggers on `search_index`. Inserts/updates/deletes on `search_index` propagate to FTS5 automatically — do NOT manually insert into `search_fts`.
10. **Semantic search loads all embeddings into Python**: `SearchIndex.embedding` BLOBs are fetched for the query scope and compared via numpy cosine similarity. Fine for personal library scale (<100 books); would need chunked comparison for 100k+ documents.
11. **Claude CLI `structured_output` field**: With `--json-schema`, the CLI returns parsed JSON in `structured_output`, not `result` (which is empty). `ClaudeCodeCLIProvider._parse_response()` checks `structured_output` first.
12. **Codex CLI lacks JSON schema flag**: `CodexCLIProvider.generate()` injects the schema into the prompt text instead of using a CLI flag. The evaluator still receives schema-aware output.
13. **Re-import must preserve section IDs**: `_re_import_book` updates sections in-place by `order_index`. Delete-and-recreate orphans summaries/evals since `Summary.content_id` is not a FK and won't cascade.
14. **`get_services()` does not auto-commit**: CLI commands that persist data must call `session.commit()` explicitly. `flush()` alone loses changes when the session closes.
15. **`eval_json` is derived from traces**: `Summary.eval_json` is computed from `EvalTrace` rows via `EvalService.compute_eval_json()`. Wrapped format: `{passed, total, eval_run_id, assertions: {name: {passed, reasoning, ...}}}`. All callers consume the `assertions` key.
16. **Stale eval traces**: Re-import marks traces as `is_stale=True` before section deletion. `eval_repo` queries filter `WHERE is_stale = 0` by default.
17. **Deterministic assertions skip LLM**: `reasonable_length`, `has_key_concepts`, `image_refs_preserved` use pure code checks. Their `EvalTrace` has `model_used="deterministic"`, `prompt_sent=None`.
18. **Vite proxy**: In dev, the frontend proxies `/api` requests to `localhost:8000`. In production (single Python process), FastAPI serves the built SPA from `./static/`.
19. **Backup file format**: Backups are `library-{YYYYMMDD_HHMMSS}.db` (direct SQLite file copies). The backup route serves them with `application/octet-stream`. Restore validates SQLite header before overwriting.
20. **In-app image URLs use absolute path scheme**: `Summary.summary_md` and `BookSection.content_md` reference images via `/api/v1/images/{id}` (per `backend/app/services/parser/image_url_rewrite.py:63-96`), NOT a custom `image://N` scheme — older docs may say otherwise. Any code that emits content for use OUTSIDE the app (Markdown export, share-to-clipboard, render-to-PDF, etc.) must sanitize these references; otherwise external viewers show broken images.

## Extended Docs

| Path | Description |
|------|-------------|
| `docs/specs/2026-04-12-zero-dependency-packaging-spec.md` | Zero-dependency packaging spec (SQLite, fastembed, multi-provider LLM) |
| `docs/plans/2026-04-12-zero-dependency-packaging-implementation-plan.md` | 15-task implementation plan |
| `docs/requirements/2026-04-11-self-contained-packaging.md` | Zero-dependency requirements |
| `docs/specs/2026-04-01_book_companion_v1_spec.md` | V1 spec: models, CLI signatures, eval assertions, search algorithm |
| `docs/requirements/2026-04-10_web_interface_v1_requirements.md` | Web interface requirements |
| `docs/specs/2026-04-10_web_interface_v1_spec.md` | Web interface spec: API routes, Vue components, SSE events |
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
3. Use `get_db` dependency from `app/api/deps.py` for DB access
4. Use `app.state.event_bus` for SSE notifications if needed

### Adding a new LLM provider
1. Create `backend/app/services/summarizer/<name>_cli.py` implementing `LLMProvider` ABC
2. Add it to `create_llm_provider()` in `backend/app/services/summarizer/__init__.py`
3. Update `detect_llm_provider()` if the CLI should be auto-detected
4. Provider is then usable via `settings.llm.provider = "<name>"` or auto-detection

### Adding a new prompt version
1. Copy existing template: `cp prompts/summarize_section_v1.txt prompts/summarize_section_v2.txt`
2. Edit the new template
3. Update `Settings.summarization.prompt_version` default or use: `bookcompanion config set summarization.prompt_version v2`
4. Update template loading in the relevant service to use `f"summarize_section_{version}.txt"`

### Running a book through the full pipeline
```bash
bookcompanion add path/to/book.epub           # Parse + store + index for search
bookcompanion summarize <book_id> --preset practitioner_bullets
bookcompanion summary list <book_id>          # View summary log
bookcompanion summary read <book_id>          # Read default book summary
bookcompanion eval <book_id>                  # View eval assertion results
bookcompanion search "query"                  # Hybrid search across library
bookcompanion export book <book_id> --format markdown
```

### Fresh database setup
```bash
rm -rf ~/.local/share/bookcompanion      # Linux
# rm -rf ~/Library/Application\ Support/bookcompanion      # macOS
bookcompanion init                       # Re-creates data dir, runs migrations, warms embedding model
```

### Interactive verification (Playwright MCP)

Manual / Playwright MCP verification is **Phase 4 work in `/verify`**, not setup to offload to the user. When a /verify run needs a live UI:

1. **Don't fight a running dev server.** The user often has `bookcompanion serve` on `:8000` pointing at the root repo. Start your verification server on a free port instead:
   ```bash
   cd backend && uv run bookcompanion serve --port 8765 &
   curl -sf http://localhost:8765/api/v1/health   # gate before Playwright
   ```
2. **Ship the frontend build into the backend's static dir** so the backend serves both API + SPA — avoids the vite-proxy dance:
   ```bash
   cd frontend && npm run build
   rm -rf ../backend/app/static && cp -R dist ../backend/app/static
   ```
   Rebuild + recopy after every frontend fix. The backend serves whatever is in `backend/app/static/index.html` — stale builds will look like working bugs.
3. **Seed at least one book** if the DB is empty (`sqlite3 ~/Library/Application\ Support/bookcompanion/library.db "SELECT count(*) FROM books"` → 0):
   ```bash
   cd backend && uv run python tests/fixtures/download_fixtures.py
   uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub
   # answer N to the section-cleanup prompt — the book persists as ID 1
   ```
4. **Drive the UI via Playwright MCP** (`browser_navigate`, `browser_evaluate`, `browser_snapshot`). `browser_evaluate` with `async () => fetch(...)` is the fastest way to probe API state from inside the same origin. Check `browser_console_messages(level: 'error')` after every interaction.
5. **Tear down** at the end: `kill $(lsof -ti:8765)`, don't touch the :8000 server.

If the MCP browser is already in use (error: `Browser is already in use for .../mcp-chrome-*`), identify the holding Chrome process (`pgrep -f ms-playwright/mcp-chrome`), kill it, then re-call `browser_navigate`.

### Session logging & changelog
- Before ending a significant session (meaningful work done, not trivial fixes), offer to run `/session-log` to capture learnings
- After merging to main, run `/changelog` to record user-facing changes

+ SQLAlchemy rollback expires all ORM objects in the session even with `expire_on_commit=False`. When iterating a pre-fetched list after rollback, re-issue the SELECT to refresh identity-mapped objects. See `summarizer_service.py` rollback branch for the pattern.

+ `.pmos/settings.yaml` says `docs_path: .pmos`, but the observed convention in this repo is to put pipeline artifacts under `docs/` (`docs/requirements/`, `docs/specs/`, `docs/plans/`, `docs/simulations/`, `docs/audits/`, `docs/changelog.md`, `docs/session-log.md`). When pipeline skills (/requirements, /spec, /plan, /verify, etc.) read settings.yaml they may try to write under `.pmos/` — follow the observed `docs/` convention and write alongside existing siblings instead. Update settings.yaml's `docs_path` to `docs` if you want to align the setting with the convention.
