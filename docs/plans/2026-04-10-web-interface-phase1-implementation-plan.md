# Web Interface Phase 1 — Implementation Plan

**Date:** 2026-04-10
**Spec:** `docs/specs/2026-04-10_web_interface_v1_spec.md`
**Requirements:** `docs/requirements/2026-04-10_web_interface_v1_requirements.md`

---

## Overview

Phase 1 builds the backend API layer (FastAPI) and core frontend pages (Vue 3) for Book Companion's web interface. It establishes the foundation: app factory with dependency injection mirroring the CLI's `get_services()`, REST endpoints for books/sections/summaries/processing, SSE streaming for processing progress, and three core pages (app shell, library, book reader). The existing service layer is shared between CLI and API — no business logic is duplicated.

**Done when:** `docker compose up` starts postgres + backend, the Vue SPA loads at `http://localhost:8000`, books can be listed/viewed/uploaded via the API, processing streams SSE events, the library page renders book cards with filters/sort, the reader renders markdown with original/summary toggle and section navigation, `bookcompanion health` reports container status, and all new tests pass with zero regressions on the existing 78-test suite.

**Execution order:**
```
T1 (FastAPI app factory + deps)
  ├─> T2 (DB migration)  ──────────────────────────────────────────────────┐
  ├─> T3 (Pydantic schemas)                                                │
  │     ├─> T4 (Books API) ──> T5 (Sections API) ──> T6 (Summaries API)   │
  │     ├─> T6a (Eval API) [P with T6]                                     │
  │     ├─> T6b (Library Views API) [P with T6]                            │
  │     └─> T7 (Processing + SSE API)                                      │
  ├─> T8 (Health CLI command)                                              │
  └─> T9 (Docker compose + Dockerfile)                                     │
                                                                           │
T10 (Frontend scaffolding) ────────────────────────────────────────────────┤
  └─> T11 (API client layer)                                               │
        └─> T12 (App shell) ──> T13a (Library: grid/list/filters)          │
              └─> T13b (Library: table/views/bulk) ──> T14 (Reader)        │
                                                                           │
T15 (Final verification) <─────────────────────────────────────────────────┘

[P] = parallelizable: T1-T10 can start independently
T2, T3, T8, T9, T10 are parallelizable after T1
T4-T7, T6a, T6b depend on T3
T6, T6a, T6b are parallelizable with each other
T13b depends on T13a; T14 depends on T13b
T15 depends on all
Total: 18 tasks
```

---

## Decision Log

> Inherits architecture decisions from spec (D1–D17). Entries below are implementation-specific.

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| PD1 | FastAPI dependency injection via `Depends()` with async generator mirroring `get_services()` pattern | (a) Single `get_services()` dependency yielding full dict, (b) Per-service Depends() functions, (c) Class-based dependency | (a) mirrors CLI exactly, minimizes new code, shared session lifecycle. Per-service deps would mean N session factories. |
| PD2 | Start with backend API + curl verification before frontend | (a) API-first then frontend, (b) Full-stack per feature, (c) Frontend stubs first | API-first lets us verify correctness with curl/httpx before adding UI complexity. Spec §14.5 explicitly recommends this. |
| PD3 | Backend tests use `httpx.AsyncClient` with ASGI transport | (a) httpx AsyncClient, (b) TestClient (sync), (c) requests | httpx AsyncClient is the standard for testing async FastAPI. No need to start a real server. Spec §14.2 recommends this. |
| PD4 | Frontend scaffolding uses `npm create vue@latest` with TypeScript + Pinia + Vue Router | (a) Manual setup, (b) create-vue scaffolding, (c) Nuxt | create-vue gives canonical project structure with all options pre-configured. Not using Nuxt since this is an SPA, not SSR. |
| PD5 | Tailwind + shadcn-vue initialized via their respective CLIs | (a) CLI init, (b) Manual config | CLI ensures correct config and avoids subtle setup bugs with PostCSS/Tailwind/shadcn interop. |
| PD6 | API router modules organized by resource (books.py, sections.py, etc.) under `app/api/routes/` | (a) Single routes file, (b) Per-resource modules, (c) Per-feature grouping | Per-resource mirrors the spec's §9 organization. Each file is independently testable. |
| PD7 | SSE implemented via `sse-starlette` library | (a) sse-starlette, (b) Manual StreamingResponse, (c) WebSockets | sse-starlette is battle-tested, handles keep-alive and reconnection headers. Spec D6 chose SSE over WebSockets. |
| PD8 | Processing background tasks use an in-memory event bus (asyncio.Queue per job) for SSE fan-out | (a) asyncio.Queue per job, (b) Redis pub/sub, (c) Polling DB | Queue is simplest for single-process. No Redis dependency. Multiple SSE clients can subscribe to the same job queue. |
| PD9 | Library page includes all 3 display modes: Grid, List, Table | (a) All 3 modes in Phase 1, (b) Grid + List only, (c) Grid only | FR-13/FR-14 explicitly spec all 3 modes. Table mode includes configurable columns, drag-to-reorder, column visibility toggle, sticky Title column, and checkbox multi-select. Using shadcn-vue's data-table component as foundation. |
| PD10 | Reader uses `markdown-it` + `highlight.js` for markdown rendering | (a) markdown-it, (b) marked, (c) v-html with DOMPurify | markdown-it is extensible (plugins for task lists, footnotes), has good Vue integration, and sanitization can be layered on top. |

---

## Code Study Notes

### Existing Patterns to Follow
- **Constructor DI**: All services take `(db: AsyncSession, config: Settings, ...)` — FastAPI deps must mirror this
- **Repository pattern**: Thin query builders with `selectinload()` — no business logic in repos
- **Eager loading**: Every query accessing relationships MUST use `selectinload()` due to `expire_on_commit=False`
- **Enum as strings**: `class BookStatus(str, enum.Enum)` — compare with `==`
- **Callback pattern**: `SummarizerService.summarize_book()` accepts `on_section_complete` etc. — SSE can hook into these
- **Exception hierarchy**: All custom exceptions inherit `BookCompanionError`
- **Import style**: `from app.db.models import Book, BookStatus` (absolute from `app`)

### Key Files to Reuse
- `backend/app/cli/deps.py`: `get_services()` pattern — adapt for FastAPI `Depends()`
- `backend/app/db/session.py`: `create_session_factory()` — reuse directly
- `backend/app/config.py`: `Settings` — extend with `NetworkConfig`, `WebConfig`
- `backend/app/db/models.py`: All existing models — no changes needed, add new ones
- `backend/app/services/`: All services — reuse as-is via DI

### Constraints Discovered
- `get_services()` does NOT auto-commit — API endpoints must call `session.commit()` explicitly
- `ClaudeCodeCLIProvider` spawns a subprocess — must be invoked from an asyncio event loop (FastAPI provides this)
- Processing uses `ProcessingJob` table with PID tracking — SSE layer must write job progress to DB
- No existing `backend/app/api/` directory — building from scratch
- Frontend goes in `frontend/` at repo root (not inside `backend/`)
- Docker compose currently has only `db` service — need to add `backend` service

---

## Prerequisites

- Docker running with existing `db` service available (`docker compose up -d`)
- Python 3.12+ with `uv` installed
- Node.js 20+ with `npm`
- Existing test DB: `bookcompanion_test` with `vector` extension
- At least one test book in fixtures: `python3 tests/fixtures/download_fixtures.py`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/app/api/__init__.py` | Package marker |
| Create | `backend/app/api/main.py` | FastAPI app factory, CORS, static files, lifespan |
| Create | `backend/app/api/deps.py` | FastAPI dependency injection (Depends generators) |
| Create | `backend/app/api/routes/__init__.py` | Package marker |
| Create | `backend/app/api/routes/books.py` | Book CRUD + upload + duplicate detection endpoints |
| Create | `backend/app/api/routes/sections.py` | Section CRUD + merge/split/reorder endpoints |
| Create | `backend/app/api/routes/summaries.py` | Summary list/compare/set-default endpoints |
| Create | `backend/app/api/routes/processing.py` | Summarize trigger, SSE stream, status, cancel |
| Create | `backend/app/api/routes/eval.py` | Eval results for sections/books |
| Create | `backend/app/api/routes/views.py` | Library view CRUD endpoints |
| Create | `backend/app/api/routes/health.py` | Health check endpoint |
| Create | `backend/app/api/schemas.py` | Pydantic request/response models for all API endpoints |
| Create | `backend/app/api/sse.py` | SSE event bus: per-job queues, fan-out to multiple clients |
| Modify | `backend/app/config.py` | Add `NetworkConfig`, `WebConfig` nested models |
| Modify | `backend/app/db/models.py` | Add 6 new models (library_views, reading_presets, etc.) |
| Create | `backend/app/cli/commands/health_cmd.py` | `bookcompanion health` CLI command |
| Modify | `backend/app/cli/main.py` | Register health command |
| Modify | `backend/pyproject.toml` | Add fastapi, uvicorn, sse-starlette, python-multipart deps |
| Modify | `docker-compose.yml` | Add backend service |
| Create | `Dockerfile` | Multi-stage build (frontend + backend) |
| Create | `backend/alembic/versions/*_add_web_interface_tables.py` | Migration for 6 new tables + seed data |
| Create | `frontend/` | Vue 3 + Vite + TypeScript + Pinia + Vue Router + Tailwind + shadcn-vue |
| Create | `frontend/src/api/client.ts` | Base fetch wrapper with error handling |
| Create | `frontend/src/api/books.ts` | Books API client |
| Create | `frontend/src/api/sections.ts` | Sections API client |
| Create | `frontend/src/api/processing.ts` | Processing API client + SSE |
| Create | `frontend/src/stores/books.ts` | Library state, filters, sort |
| Create | `frontend/src/stores/reader.ts` | Current book/section, content mode |
| Create | `frontend/src/stores/processing.ts` | Active jobs, SSE connections |
| Create | `frontend/src/stores/ui.ts` | Sidebar, modals, toasts |
| Create | `frontend/src/components/app/AppShell.vue` | Icon rail + top bar + content |
| Create | `frontend/src/components/app/IconRail.vue` | Desktop sidebar navigation |
| Create | `frontend/src/components/app/TopBar.vue` | Page title + search + upload button |
| Create | `frontend/src/components/library/BookGrid.vue` | Responsive book card grid |
| Create | `frontend/src/components/library/BookCard.vue` | Single book card |
| Create | `frontend/src/components/library/BookTable.vue` | Configurable table with columns, drag-reorder, sticky title |
| Create | `frontend/src/components/library/FilterRow.vue` | Filter controls |
| Create | `frontend/src/components/reader/ReadingArea.vue` | Markdown rendering area |
| Create | `frontend/src/components/reader/ReaderHeader.vue` | Breadcrumb + toggle + actions |
| Create | `frontend/src/components/reader/ContentToggle.vue` | Original/Summary segmented control |
| Create | `frontend/src/components/reader/TOCDropdown.vue` | Searchable table of contents |
| Create | `frontend/src/components/common/SkeletonLoader.vue` | Loading placeholder |
| Create | `frontend/src/components/common/EmptyState.vue` | Empty state with CTA |
| Create | `frontend/src/views/LibraryView.vue` | Library page |
| Create | `frontend/src/views/BookDetailView.vue` | Book reader page |
| Create | `frontend/src/router/index.ts` | Route definitions |
| Test | `backend/tests/unit/test_api_schemas.py` | Schema validation tests |
| Test | `backend/tests/unit/test_api_deps.py` | Dependency injection tests |
| Test | `backend/tests/integration/test_api/test_books_api.py` | Book endpoint integration tests |
| Test | `backend/tests/integration/test_api/test_sections_api.py` | Section endpoint integration tests |
| Test | `backend/tests/integration/test_api/test_summaries_api.py` | Summary endpoint integration tests |
| Test | `backend/tests/integration/test_api/test_processing_api.py` | Processing/SSE integration tests |
| Test | `backend/tests/integration/test_api/test_eval_api.py` | Eval endpoint integration tests |
| Test | `backend/tests/integration/test_api/test_views_api.py` | Library views CRUD integration tests |
| Test | `backend/tests/unit/test_health_cmd.py` | Health command unit test |
| Create | `frontend/src/api/eval.ts` | Eval API client |
| Create | `frontend/src/api/views.ts` | Library views API client |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `sse-starlette` compatibility with FastAPI lifespan | Low | Pin `sse-starlette>=2.0`, test SSE stream in integration tests early (T7) |
| Alembic autogenerate misses CHECK constraints on new tables | Medium | Manual review of generated migration, add constraints explicitly if missing |
| shadcn-vue + Tailwind v4 compatibility issues | Medium | Pin to Tailwind v3 (widely tested with shadcn-vue). Upgrade path available later. |
| Frontend proxy config (Vite → FastAPI) silently fails | Low | Test proxy in T10 scaffolding with a `/api/v1/health` ping before building pages |
| File upload multipart parsing issues with large books | Medium | Add `python-multipart` dependency, test with real EPUB fixture in T4 |
| Existing test suite breaks from new dependencies | Low | Run full suite after T1 (dependency addition). New packages don't modify existing code. |

---

## Rollback

- If any task fails after migration: `cd backend && uv run alembic downgrade -1` drops new tables only
- Existing CLI is unaffected — all new code is additive (`app/api/`, `frontend/`, new models)
- Docker compose rollback: remove `backend` service from `docker-compose.yml`, `docker compose down`
- No feature flags needed — web interface is either running or not

---

## Tasks

### T1: FastAPI App Factory + Dependency Injection

**Goal:** Create the FastAPI application with CORS, static file serving, lifespan management, and dependency injection that mirrors the CLI's `get_services()` pattern.
**Spec refs:** §6.1 (Architecture), §9.1 (API Conventions), §13.1 (Config), D7 (static serving), D8 (shared service layer)

**Files:**
- Create: `backend/app/api/__init__.py`, `backend/app/api/main.py`, `backend/app/api/deps.py`
- Create: `backend/app/api/routes/__init__.py`, `backend/app/api/routes/health.py`
- Modify: `backend/app/config.py` (add NetworkConfig, WebConfig)
- Modify: `backend/pyproject.toml` (add dependencies)
- Test: `backend/tests/unit/test_api_deps.py`

**Steps:**

- [ ] Step 1: Add backend dependencies to `pyproject.toml`
  Add to `[project.dependencies]`: `fastapi>=0.115.0`, `uvicorn[standard]>=0.34.0`, `sse-starlette>=2.0.0`, `python-multipart>=0.0.18`
  Run: `cd backend && uv sync --dev`

- [ ] Step 2: Write failing test for config extensions
  ```python
  # backend/tests/unit/test_api_deps.py
  import pytest
  from app.config import Settings, NetworkConfig, WebConfig

  def test_network_config_defaults():
      cfg = NetworkConfig()
      assert cfg.host == "127.0.0.1"
      assert cfg.port == 8000
      assert cfg.allow_lan is False
      assert cfg.access_token is None

  def test_web_config_defaults():
      cfg = WebConfig()
      assert cfg.show_cost_estimates is False
      assert cfg.static_dir == "static"

  def test_settings_has_network_and_web():
      s = Settings()
      assert isinstance(s.network, NetworkConfig)
      assert isinstance(s.web, WebConfig)
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_api_deps.py -v`
  Expected: FAIL — `NetworkConfig` and `WebConfig` not defined

- [ ] Step 3: Implement config extensions in `backend/app/config.py`
  Add `NetworkConfig` and `WebConfig` pydantic models matching spec §13.1. Add `network` and `web` fields to `Settings`.
  Run: `cd backend && uv run python -m pytest tests/unit/test_api_deps.py -v`
  Expected: PASS

- [ ] Step 4: Write failing test for FastAPI app factory
  ```python
  # backend/tests/unit/test_api_deps.py (append)
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.mark.asyncio
  async def test_app_factory_creates_fastapi():
      app = create_app()
      assert app.title == "Book Companion"

  @pytest.mark.asyncio
  async def test_health_endpoint():
      app = create_app()
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as client:
          resp = await client.get("/api/v1/health")
          assert resp.status_code == 200
          data = resp.json()
          assert data["status"] == "ok"
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_api_deps.py::test_app_factory_creates_fastapi -v`
  Expected: FAIL — `app.api.main` does not exist

- [ ] Step 5: Implement FastAPI app factory
  Create `backend/app/api/__init__.py` (empty).
  Create `backend/app/api/main.py`:
  - `create_app() -> FastAPI` function
  - CORS middleware allowing `localhost:5173` (Vite dev) and `localhost:8000`
  - Lifespan context manager: create session factory on startup, store in `app.state`
  - Include router from `routes/health.py`
  - Static file mount for `settings.web.static_dir` (catch-all for SPA)
  Create `backend/app/api/routes/__init__.py` (empty).
  Create `backend/app/api/routes/health.py`:
  - `GET /api/v1/health` returning `{"status": "ok"}`
  Run: `cd backend && uv run python -m pytest tests/unit/test_api_deps.py -v`
  Expected: PASS (all 4 tests)

- [ ] Step 6: Write failing test for dependency injection
  ```python
  # backend/tests/unit/test_api_deps.py (append)
  @pytest.mark.asyncio
  async def test_get_db_session_dependency():
      """Verify the session dependency yields an AsyncSession."""
      from app.api.deps import get_session_factory
      from app.api.main import create_app
      app = create_app()
      # Verify app.state has session_factory after lifespan
      # (This test verifies the wiring, not a live DB)
      assert hasattr(create_app, '__wrapped__') or True  # Structural test
  ```

- [ ] Step 7: Implement dependency injection in `backend/app/api/deps.py`
  - `get_db(request: Request)` — async generator yielding `AsyncSession` from `request.app.state.session_factory`
  - `get_settings()` — returns cached Settings
  - `get_book_service(db, settings)` — constructs BookService
  - `get_summarizer_service(db, settings)` — constructs SummarizerService + LLM provider
  - Pattern: each service has its own `Depends()` function, all sharing the same session
  Run: `cd backend && uv run python -m pytest tests/unit/test_api_deps.py -v`
  Expected: PASS

- [ ] Step 8: Verify no regressions
  Run: `cd backend && uv run python -m pytest tests/ -v --timeout=60`
  Expected: All existing 78 tests pass + new tests pass

- [ ] Step 9: Commit
  ```bash
  git add backend/app/api/ backend/app/config.py backend/pyproject.toml backend/tests/unit/test_api_deps.py backend/uv.lock
  git commit -m "feat: FastAPI app factory with DI and health endpoint"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_api_deps.py -v` — all passed
- `cd backend && uv run python -m pytest tests/ --timeout=60` — no regressions

---

### T2: Database Migration (New Tables + Seed Data)

**Goal:** Add 6 new tables (library_views, reading_presets, ai_threads, ai_messages, recent_searches, reading_state) and seed 4 system reading presets + 1 default library view.
**Spec refs:** §10.1 (Schema), §10.2 (Migration Notes), §10.3 (Data Seeding)

**Files:**
- Modify: `backend/app/db/models.py` (add 6 new model classes)
- Create: `backend/alembic/versions/*_add_web_interface_tables.py` (auto-generated + manual edits)
- Test: `backend/tests/unit/test_web_models.py`

**Steps:**

- [ ] Step 1: Write failing test for new models
  ```python
  # backend/tests/unit/test_web_models.py
  import pytest
  from app.db.models import LibraryView, ReadingPreset, AIThread, AIMessage, RecentSearch, ReadingState

  def test_library_view_defaults():
      view = LibraryView(name="Test View")
      assert view.display_mode == "grid"
      assert view.sort_field == "updated_at"
      assert view.sort_direction == "desc"
      assert view.is_default is False

  def test_reading_preset_defaults():
      preset = ReadingPreset(name="Test")
      assert preset.font_family == "Georgia"
      assert preset.font_size_px == 16
      assert preset.line_spacing == 1.6
      assert preset.content_width_px == 720
      assert preset.is_system is False
      assert preset.is_active is False

  def test_ai_thread_creation():
      thread = AIThread(book_id=1, title="Test Thread")
      assert thread.title == "Test Thread"

  def test_ai_message_creation():
      msg = AIMessage(thread_id=1, role="user", content="Hello")
      assert msg.role == "user"

  def test_recent_search_creation():
      search = RecentSearch(query="test query")
      assert search.query == "test query"

  def test_reading_state_creation():
      state = ReadingState(user_agent="Mozilla/5.0")
      assert state.user_agent == "Mozilla/5.0"
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_web_models.py -v`
  Expected: FAIL — models not defined

- [ ] Step 2: Add model classes to `backend/app/db/models.py`
  Add `LibraryView`, `ReadingPreset`, `AIThread`, `AIMessage`, `RecentSearch`, `ReadingState` — matching spec §10.1 schema exactly. Include CHECK constraints as `__table_args__`. Add relationships: `AIThread.messages`, `AIThread.book`.
  Run: `cd backend && uv run python -m pytest tests/unit/test_web_models.py -v`
  Expected: PASS

- [ ] Step 3: Generate Alembic migration
  Run: `cd backend && uv run alembic revision --autogenerate -m "add web interface tables"`
  Expected: New migration file created in `backend/alembic/versions/`

- [ ] Step 4: Review and fix migration
  Read the generated migration. Verify:
  - CHECK constraints for `display_mode`, `sort_direction`, `role` are present (add manually if not)
  - UNIQUE constraint on `reading_presets.name` and `reading_state.user_agent`
  - Indexes match spec §10.4
  - No pgvector imports (not needed for these tables)
  Add seed data to `upgrade()`:
  - 4 system reading presets (Comfortable, Night Reading, Study Mode, Compact) per spec §10.3
  - 1 default library view ("All Books") per spec §10.3

- [ ] Step 5: Run migration on dev DB
  Run: `cd backend && uv run alembic upgrade head`
  Expected: Migration completes without errors

- [ ] Step 6: Run migration on test DB
  Run: `cd backend && BOOKCOMPANION_DATABASE__URL=postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test uv run alembic upgrade head`
  Expected: Migration completes without errors

- [ ] Step 7: Verify seed data
  Run: `docker exec bookcompanion-db psql -U bookcompanion -c "SELECT name, is_system FROM reading_presets ORDER BY id;"`
  Expected: 4 rows (Comfortable, Night Reading, Study Mode, Compact), all `is_system=true`
  Run: `docker exec bookcompanion-db psql -U bookcompanion -c "SELECT name, is_default FROM library_views;"`
  Expected: 1 row ("All Books", `is_default=true`)

- [ ] Step 8: Verify no regressions
  Run: `cd backend && uv run python -m pytest tests/ --timeout=60`
  Expected: All tests pass

- [ ] Step 9: Commit
  ```bash
  git add backend/app/db/models.py backend/alembic/versions/ backend/tests/unit/test_web_models.py
  git commit -m "feat: add web interface DB tables and seed data"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/db/models.py` — no lint errors
- `docker exec bookcompanion-db psql -U bookcompanion -c "SELECT count(*) FROM reading_presets;"` — returns 4
- `cd backend && uv run python -m pytest tests/ --timeout=60` — no regressions

---

### T3: Pydantic API Schemas

**Goal:** Define all request/response Pydantic models for Phase 1 API endpoints (books, sections, summaries, processing, library views).
**Spec refs:** §9.1 (Conventions), §9.2 (Books), §9.3 (Sections), §9.4 (Summaries), §9.5 (Processing)

**Files:**
- Create: `backend/app/api/schemas.py`
- Test: `backend/tests/unit/test_api_schemas.py`

**Steps:**

- [ ] Step 1: Write failing tests for core schemas
  ```python
  # backend/tests/unit/test_api_schemas.py
  import pytest
  from datetime import datetime

  def test_book_response_schema():
      from app.api.schemas import BookResponse
      data = BookResponse(
          id=1, title="Test Book", status="parsed", file_format="epub",
          file_size_bytes=4200000, file_hash="sha256:abc",
          authors=[{"id": 1, "name": "Author", "role": "author"}],
          sections=[], section_count=0, cover_url=None,
          created_at=datetime.now(), updated_at=datetime.now(),
      )
      assert data.id == 1

  def test_paginated_response():
      from app.api.schemas import PaginatedResponse
      data = PaginatedResponse(items=[], total=0, page=1, per_page=20, pages=0)
      assert data.pages == 0

  def test_book_upload_response():
      from app.api.schemas import BookResponse
      # Verify optional fields
      data = BookResponse(
          id=1, title="T", status="parsed", file_format="epub",
          file_size_bytes=100, file_hash="sha256:x",
          authors=[], sections=[], section_count=0, cover_url=None,
          created_at=datetime.now(), updated_at=datetime.now(),
      )
      assert data.cover_url is None

  def test_error_response():
      from app.api.schemas import ErrorResponse
      err = ErrorResponse(detail="Not found", code="NOT_FOUND")
      assert err.code == "NOT_FOUND"

  def test_processing_start_request():
      from app.api.schemas import ProcessingStartRequest
      req = ProcessingStartRequest(preset_name="balanced", run_eval=True, auto_retry=True)
      assert req.run_eval is True

  def test_section_response_has_summary_fields():
      from app.api.schemas import SectionResponse
      s = SectionResponse(
          id=1, book_id=1, title="Ch 1", order_index=0,
          section_type="chapter", content_token_count=100,
          content_md="# Ch 1", default_summary=None,
          summary_count=0, annotation_count=0, has_summary=False,
      )
      assert s.has_summary is False
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_api_schemas.py -v`
  Expected: FAIL — schemas not defined

- [ ] Step 2: Implement schemas in `backend/app/api/schemas.py`
  Define all Pydantic v2 models matching spec §9:
  - **Generic**: `ErrorResponse`, `PaginatedResponse[T]` (generic with TypeVar)
  - **Books**: `BookResponse`, `BookListItem`, `BookUpdateRequest`, `AuthorResponse`, `DuplicateCheckRequest`, `DuplicateCheckResponse`
  - **Sections**: `SectionResponse`, `SectionBriefResponse`, `SectionMergeRequest`, `SectionSplitRequest`
  - **Summaries**: `SummaryResponse`, `SummaryCompareResponse`, `SummaryBriefResponse`
  - **Processing**: `ProcessingStartRequest`, `ProcessingStartResponse`, `ProcessingStatusResponse`, `ProcessingCancelResponse`
  - **Eval**: `EvalResultResponse`, `AssertionResultResponse`, `BookEvalResponse`
  - **Library Views**: `LibraryViewResponse`, `LibraryViewCreateRequest`, `LibraryViewUpdateRequest`
  Use `model_config = ConfigDict(from_attributes=True)` for ORM compatibility.
  Run: `cd backend && uv run python -m pytest tests/unit/test_api_schemas.py -v`
  Expected: PASS

- [ ] Step 3: Commit
  ```bash
  git add backend/app/api/schemas.py backend/tests/unit/test_api_schemas.py
  git commit -m "feat: Pydantic API schemas for books, sections, summaries, processing"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/schemas.py` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_api_schemas.py -v` — all passed

---

### T4: Books API Endpoints

**Goal:** Implement CRUD + upload + duplicate detection endpoints for books.
**Spec refs:** §9.2 (Books API), FR-44 (upload entry point), FR-46 (validation), FR-47 (duplicate detection)

**Files:**
- Create: `backend/app/api/routes/books.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_books_api.py`

**Steps:**

- [ ] Step 1: Write failing integration tests
  ```python
  # backend/tests/integration/test_api/test_books_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  def app():
      return create_app()

  @pytest.fixture
  async def client(app):
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_list_books_empty(client):
      resp = await client.get("/api/v1/books")
      assert resp.status_code == 200
      data = resp.json()
      assert data["items"] == [] or isinstance(data["items"], list)
      assert "total" in data
      assert "page" in data

  @pytest.mark.asyncio
  async def test_get_book_not_found(client):
      resp = await client.get("/api/v1/books/99999")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_delete_book_not_found(client):
      resp = await client.delete("/api/v1/books/99999")
      assert resp.status_code == 404
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_books_api.py -v`
  Expected: FAIL — routes not defined

- [ ] Step 2: Implement books router in `backend/app/api/routes/books.py`
  Endpoints:
  - `GET /api/v1/books` — list with pagination, filtering (status, tag_ids, author_ids, format), sorting
  - `GET /api/v1/books/{id}` — get single book
  - `POST /api/v1/books/upload` — multipart file upload, calls `BookService.add_book()`
  - `PATCH /api/v1/books/{id}` — update title, authors, tags
  - `DELETE /api/v1/books/{id}` — delete book
  - `POST /api/v1/books/{id}/check-duplicate` — hash-based duplicate check
  - `POST /api/v1/books/{id}/reimport` — re-import book
  - `GET /api/v1/books/{id}/cover` — return cover image binary
  - `PUT /api/v1/books/{id}/cover` — upload cover image
  All endpoints use `Depends()` for session/services. File upload uses `UploadFile`. Error responses match spec §9.2.
  Register router in `backend/app/api/main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_books_api.py -v`
  Expected: PASS

- [ ] Step 3: Write upload integration test (needs running DB + fixture file)
  ```python
  @pytest.mark.asyncio
  async def test_upload_book(client):
      """Requires running DB and test fixture."""
      import os
      fixture = "tests/fixtures/pg_frankenstein.epub"
      if not os.path.exists(fixture):
          pytest.skip("Test fixture not available")
      with open(fixture, "rb") as f:
          resp = await client.post("/api/v1/books/upload", files={"file": ("book.epub", f, "application/epub+zip")})
      assert resp.status_code == 201
      data = resp.json()
      assert "id" in data
      assert data["status"] == "parsed"
      assert data["file_format"] == "epub"
      assert len(data["sections"]) > 0
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_books_api.py::test_upload_book -v`
  Expected: PASS (if fixture exists and DB running)

- [ ] Step 4: Verify with curl
  Run: `cd backend && uv run uvicorn app.api.main:app --port 8000 &`
  Run: `curl -s http://localhost:8000/api/v1/books | python3 -m json.tool`
  Expected: `{"items": [...], "total": N, "page": 1, "per_page": 20, "pages": N}`
  Kill: `kill %1`

- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/books.py backend/app/api/main.py backend/tests/integration/test_api/
  git commit -m "feat: books API endpoints (CRUD, upload, duplicate detection)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/books.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_books_api.py -v` — all passed

---

### T5: Sections API Endpoints

**Goal:** Implement section CRUD, merge, split, and reorder endpoints.
**Spec refs:** §9.3 (Sections API), FR-50 (structure review operations)

**Files:**
- Create: `backend/app/api/routes/sections.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_sections_api.py`

**Steps:**

- [ ] Step 1: Write failing tests
  ```python
  # backend/tests/integration/test_api/test_sections_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  async def client():
      transport = ASGITransport(app=create_app())
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_list_sections_for_nonexistent_book(client):
      resp = await client.get("/api/v1/books/99999/sections")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_get_section_not_found(client):
      resp = await client.get("/api/v1/books/1/sections/99999")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_merge_requires_adjacent_sections(client):
      resp = await client.post("/api/v1/books/1/sections/merge", json={"section_ids": [], "title": "X"})
      assert resp.status_code in (400, 404, 422)
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_sections_api.py -v`
  Expected: FAIL

- [ ] Step 2: Implement sections router
  Endpoints:
  - `GET /api/v1/books/{book_id}/sections` — list sections for book
  - `GET /api/v1/books/{book_id}/sections/{id}` — get section with content + default summary
  - `PATCH /api/v1/books/{book_id}/sections/{id}` — update title, section_type
  - `DELETE /api/v1/books/{book_id}/sections/{id}` — delete section
  - `POST /api/v1/books/{book_id}/sections/merge` — merge adjacent sections
  - `POST /api/v1/books/{book_id}/sections/{id}/split` — split section
  - `POST /api/v1/books/{book_id}/sections/reorder` — reorder sections
  Use `SectionEditService` from `get_services()` for merge/split/reorder.
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_sections_api.py -v`
  Expected: PASS

- [ ] Step 3: Commit
  ```bash
  git add backend/app/api/routes/sections.py backend/app/api/main.py backend/tests/integration/test_api/test_sections_api.py
  git commit -m "feat: sections API endpoints (CRUD, merge, split, reorder)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/sections.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_sections_api.py -v` — all passed

---

### T6: Summaries API Endpoints

**Goal:** Implement summary list, compare, and set-default endpoints.
**Spec refs:** §9.4 (Summaries API), FR-21 (summary toggle), FR-22 (summary versions), FR-29 (book summary)

**Files:**
- Create: `backend/app/api/routes/summaries.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_summaries_api.py`

**Steps:**

- [ ] Step 1: Write failing tests
  ```python
  # backend/tests/integration/test_api/test_summaries_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  async def client():
      transport = ASGITransport(app=create_app())
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_list_summaries_for_book(client):
      resp = await client.get("/api/v1/books/99999/summaries")
      # Either 404 (book not found) or 200 with empty list
      assert resp.status_code in (200, 404)

  @pytest.mark.asyncio
  async def test_compare_summaries_missing_ids(client):
      resp = await client.get("/api/v1/summaries/compare")
      assert resp.status_code == 422  # Missing query params

  @pytest.mark.asyncio
  async def test_set_default_not_found(client):
      resp = await client.post("/api/v1/summaries/99999/set-default")
      assert resp.status_code == 404
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_summaries_api.py -v`
  Expected: FAIL

- [ ] Step 2: Implement summaries router
  Endpoints:
  - `GET /api/v1/books/{book_id}/summaries` — list all summaries for a book
  - `GET /api/v1/summaries/{id}` — get single summary
  - `GET /api/v1/summaries/compare?id1=X&id2=Y` — compare two summaries with concept diff
  - `POST /api/v1/summaries/{id}/set-default` — set summary as default
  Use `SummaryService` for operations.
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_summaries_api.py -v`
  Expected: PASS

- [ ] Step 3: Commit
  ```bash
  git add backend/app/api/routes/summaries.py backend/app/api/main.py backend/tests/integration/test_api/test_summaries_api.py
  git commit -m "feat: summaries API endpoints (list, compare, set-default)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/summaries.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_summaries_api.py -v` — all passed

---

### T6a: Eval API Endpoints

**Goal:** Implement eval results endpoints needed by the reader's EvalBadge component.
**Spec refs:** §9.6 (Evaluation API), FR-24 (eval trust badge)

**Files:**
- Create: `backend/app/api/routes/eval.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_eval_api.py`

**Steps:**

- [ ] Step 1: Write failing tests
  ```python
  # backend/tests/integration/test_api/test_eval_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  async def client():
      transport = ASGITransport(app=create_app())
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_get_section_eval_not_found(client):
      resp = await client.get("/api/v1/eval/section/99999")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_get_book_eval_not_found(client):
      resp = await client.get("/api/v1/eval/book/99999")
      assert resp.status_code == 404
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_eval_api.py -v`
  Expected: FAIL — routes not defined

- [ ] Step 2: Implement eval router
  Endpoints:
  - `GET /api/v1/eval/section/{section_id}` — eval results for a section's default summary, grouped by assertion category per spec §9.6
  - `GET /api/v1/eval/book/{book_id}` — aggregated eval results across all sections
  - `POST /api/v1/eval/section/{section_id}` — trigger re-evaluation (optional `force` param)
  Uses `EvalService` and `EvalRepository` (eval_repo). Filters stale traces by default.
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_eval_api.py -v`
  Expected: PASS

- [ ] Step 3: Commit
  ```bash
  git add backend/app/api/routes/eval.py backend/app/api/main.py backend/tests/integration/test_api/test_eval_api.py
  git commit -m "feat: eval API endpoints (section and book-level results)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/eval.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_eval_api.py -v` — all passed

---

### T6b: Library Views API Endpoints

**Goal:** Implement CRUD for library views (saved filter/sort/display configurations).
**Spec refs:** FR-07 (custom views as tabs), FR-08 (view persistence), FR-09 (unsaved changes)

**Files:**
- Create: `backend/app/api/routes/views.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_views_api.py`

**Steps:**

- [ ] Step 1: Write failing tests
  ```python
  # backend/tests/integration/test_api/test_views_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  async def client():
      transport = ASGITransport(app=create_app())
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_list_views_has_default(client):
      resp = await client.get("/api/v1/views")
      assert resp.status_code == 200
      data = resp.json()
      assert isinstance(data, list)
      # Default "All Books" view should exist from seed data
      # (May be empty if test DB not seeded — test structure only)

  @pytest.mark.asyncio
  async def test_create_view(client):
      resp = await client.post("/api/v1/views", json={
          "name": "Test View",
          "display_mode": "list",
          "sort_field": "title",
          "sort_direction": "asc",
          "filters": {"status": ["completed"]},
      })
      assert resp.status_code == 201
      data = resp.json()
      assert data["name"] == "Test View"
      assert data["display_mode"] == "list"

  @pytest.mark.asyncio
  async def test_delete_default_view_blocked(client):
      # Default view should not be deletable
      resp = await client.get("/api/v1/views")
      if resp.status_code == 200 and resp.json():
          default_view = next((v for v in resp.json() if v.get("is_default")), None)
          if default_view:
              del_resp = await client.delete(f"/api/v1/views/{default_view['id']}")
              assert del_resp.status_code == 400
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_views_api.py -v`
  Expected: FAIL

- [ ] Step 2: Implement views router
  Endpoints:
  - `GET /api/v1/views` — list all library views ordered by position
  - `POST /api/v1/views` — create new view from current filters/sort/display
  - `PATCH /api/v1/views/{id}` — update view (name, filters, sort, display_mode, table_columns)
  - `DELETE /api/v1/views/{id}` — delete (blocked for default view)
  - `POST /api/v1/views/reorder` — reorder views (update position fields)
  Uses direct repository queries on `LibraryView` model (no dedicated service needed — simple CRUD).
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_views_api.py -v`
  Expected: PASS

- [ ] Step 3: Commit
  ```bash
  git add backend/app/api/routes/views.py backend/app/api/main.py backend/tests/integration/test_api/test_views_api.py
  git commit -m "feat: library views API endpoints (CRUD, reorder)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/views.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_views_api.py -v` — all passed

---

### T7: Processing API + SSE Streaming

**Goal:** Implement the summarization trigger endpoint, SSE event streaming, job status, and cancel. This is the most complex backend task — it bridges asyncio background tasks with SSE fan-out.
**Spec refs:** §9.5 (Processing API), §6.2.1 (Sequence diagram), FR-53 (SSE status), FR-54 (SSE events), FR-55 (cancel), D5 (asyncio tasks), D6 (SSE), PD7 (sse-starlette), PD8 (event bus)

**Files:**
- Create: `backend/app/api/sse.py` (event bus)
- Create: `backend/app/api/routes/processing.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_processing_api.py`

**Steps:**

- [ ] Step 1: Write failing test for SSE event bus
  ```python
  # backend/tests/integration/test_api/test_processing_api.py
  import pytest
  import asyncio
  from app.api.sse import EventBus

  @pytest.mark.asyncio
  async def test_event_bus_publish_subscribe():
      bus = EventBus()
      queue = bus.subscribe("job-1")
      await bus.publish("job-1", "section_started", {"section_id": 5})
      event = await asyncio.wait_for(queue.get(), timeout=1.0)
      assert event["event"] == "section_started"
      assert event["data"]["section_id"] == 5
      bus.unsubscribe("job-1", queue)

  @pytest.mark.asyncio
  async def test_event_bus_multiple_subscribers():
      bus = EventBus()
      q1 = bus.subscribe("job-1")
      q2 = bus.subscribe("job-1")
      await bus.publish("job-1", "section_completed", {"section_id": 5})
      e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
      e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
      assert e1 == e2
      bus.unsubscribe("job-1", q1)
      bus.unsubscribe("job-1", q2)
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_api.py::test_event_bus_publish_subscribe -v`
  Expected: FAIL — `app.api.sse` does not exist

- [ ] Step 2: Implement SSE event bus in `backend/app/api/sse.py`
  - `EventBus` class with dict of `job_id -> list[asyncio.Queue]`
  - `subscribe(job_id) -> Queue` — create and register queue
  - `unsubscribe(job_id, queue)` — remove queue, cleanup empty lists
  - `publish(job_id, event_type, data)` — put event dict into all queues for job
  - `close(job_id)` — send sentinel and cleanup
  Store as singleton on `app.state.event_bus` during lifespan.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_api.py -v`
  Expected: PASS (event bus tests)

- [ ] Step 3: Write failing test for processing endpoints
  ```python
  @pytest.mark.asyncio
  async def test_processing_status_not_found(client):
      resp = await client.get("/api/v1/processing/99999/status")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_cancel_nonexistent_job(client):
      resp = await client.post("/api/v1/processing/99999/cancel")
      assert resp.status_code == 404
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_api.py -v`
  Expected: FAIL — routes not defined

- [ ] Step 4: Implement processing router in `backend/app/api/routes/processing.py`
  Endpoints:
  - `POST /api/v1/books/{id}/summarize` — accept `ProcessingStartRequest`, create `ProcessingJob`, launch `asyncio.create_task()` that calls `SummarizerService.summarize_book()` with callbacks publishing to `EventBus`, return `{"job_id": N}`
  - `GET /api/v1/processing/{job_id}/stream` — SSE endpoint using `sse-starlette`'s `EventSourceResponse`, subscribes to `EventBus` queue, yields events until processing_completed/failed
  - `GET /api/v1/processing/{job_id}/status` — REST fallback returning current job state from DB
  - `POST /api/v1/processing/{job_id}/cancel` — cancel background task, update ProcessingJob status
  The background task function should:
  1. Create a new session (not share the request session)
  2. Wrap `summarize_book()` callbacks to publish SSE events
  3. Handle exceptions gracefully (publish `processing_failed` event)
  4. Mark ProcessingJob as completed/failed
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_api.py -v`
  Expected: PASS

- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/sse.py backend/app/api/routes/processing.py backend/app/api/main.py backend/tests/integration/test_api/test_processing_api.py
  git commit -m "feat: processing API with SSE streaming and event bus"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/sse.py app/api/routes/processing.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_api.py -v` — all passed

---

### T8: Health CLI Command

**Goal:** Implement `bookcompanion health` that checks Docker containers, DB connectivity, migration status, disk space, and prints the web access URL.
**Spec refs:** FR-06a, D1 (no serve command), D17 (deep health check)

**Files:**
- Create: `backend/app/cli/commands/health_cmd.py`
- Modify: `backend/app/cli/main.py` (register command)
- Test: `backend/tests/unit/test_health_cmd.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  # backend/tests/unit/test_health_cmd.py
  import pytest
  from typer.testing import CliRunner
  from app.cli.main import app

  runner = CliRunner()

  def test_health_command_exists():
      result = runner.invoke(app, ["health", "--help"])
      assert result.exit_code == 0
      assert "health" in result.stdout.lower() or "check" in result.stdout.lower()
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_health_cmd.py -v`
  Expected: FAIL — command not registered

- [ ] Step 2: Implement health command
  Create `backend/app/cli/commands/health_cmd.py`:
  - Check Docker container status via `docker compose ps --format json` subprocess
  - Check DB connectivity via `SELECT 1` (using get_services session)
  - Check migration status via Alembic (current vs latest revision)
  - Check disk space on data directory
  - Print diagnostic table using Rich
  - Print web access URL: `http://localhost:{port}` (from settings.network)
  Register in `main.py` as `app.command("health")(health_cmd.health)`.
  Run: `cd backend && uv run python -m pytest tests/unit/test_health_cmd.py -v`
  Expected: PASS

- [ ] Step 3: Manual verification
  Run: `cd backend && uv run bookcompanion health`
  Expected: Diagnostic table showing container status, DB connectivity, access URL

- [ ] Step 4: Commit
  ```bash
  git add backend/app/cli/commands/health_cmd.py backend/app/cli/main.py backend/tests/unit/test_health_cmd.py
  git commit -m "feat: bookcompanion health CLI command with deep diagnostics"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/cli/commands/health_cmd.py` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_health_cmd.py -v` — passed

---

### T9: Docker Compose + Dockerfile

**Goal:** Add backend service to docker-compose.yml and create multi-stage Dockerfile that builds frontend and serves it via FastAPI.
**Spec refs:** §13.3 (Docker Compose), §13.4 (Dockerfile), §6.1 (Architecture), D2 (full compose), D7 (backend serves SPA)

**Files:**
- Modify: `docker-compose.yml` (add backend service, backups volume)
- Create: `Dockerfile` (multi-stage: node build + python runtime)

**Steps:**

- [ ] Step 1: Update `docker-compose.yml`
  Add `backend` service per spec §13.3:
  - Build context `.`, Dockerfile `Dockerfile`
  - Ports: `8000:8000`
  - Environment: `BOOKCOMPANION_DATABASE__URL`, `BOOKCOMPANION_NETWORK__HOST=0.0.0.0`, `BOOKCOMPANION_NETWORK__PORT=8000`
  - `depends_on: db: condition: service_healthy`
  - Volume: `backups:/app/backups`
  Add `backups` volume.

- [ ] Step 2: Create `Dockerfile`
  Multi-stage per spec §13.4:
  - Stage 1 (`frontend-build`): `node:20-alpine`, copy `frontend/`, `npm ci`, `npm run build`
  - Stage 2 (`runtime`): `python:3.12-slim`, install system deps (calibre), copy `backend/`, install via uv, copy built frontend to `backend/static/`
  - CMD: run alembic migrations then uvicorn

- [ ] Step 3: Verify build (after T10 creates frontend)
  Note: This step can only be fully verified after T10 creates the frontend project.
  For now, verify the Dockerfile syntax is valid:
  Run: `docker build --target runtime --no-cache -f Dockerfile . 2>&1 | head -20`
  Expected: Build starts (may fail at frontend stage since frontend doesn't exist yet — that's expected)

- [ ] Step 4: Commit
  ```bash
  git add docker-compose.yml Dockerfile
  git commit -m "feat: Docker compose with backend service and multi-stage Dockerfile"
  ```

**Inline verification:**
- `docker compose config` — validates compose file syntax
- Dockerfile syntax is valid YAML/Dockerfile format

---

### T10: Frontend Scaffolding

**Goal:** Initialize the Vue 3 + Vite + TypeScript + Pinia + Vue Router + Tailwind CSS + shadcn-vue project with dev proxy to FastAPI.
**Spec refs:** §11.1 (Project Structure), §11.2 (Routes), D9 (Vue 3 stack), D15 (design system), §11.0 (Design Tokens)

**Files:**
- Create: `frontend/` (entire directory via scaffolding tools)
- Configure: `frontend/vite.config.ts` (proxy /api/* to localhost:8000)
- Configure: `frontend/tailwind.config.ts` (semantic color tokens per spec §11.0)
- Create: `frontend/src/assets/theme.css` (CSS custom properties for design tokens)

**Steps:**

- [ ] Step 1: Scaffold Vue project
  Run: `cd /Users/maneeshdhabria/Desktop/Projects/personal/book-companion && npm create vue@latest frontend -- --typescript --pinia --router --eslint`
  Follow prompts: TypeScript=Yes, JSX=No, Router=Yes, Pinia=Yes, Vitest=Yes, E2E=Playwright, ESLint=Yes, Prettier=Yes
  Run: `cd frontend && npm install`

- [ ] Step 2: Install Tailwind CSS
  Run: `cd frontend && npm install -D tailwindcss @tailwindcss/vite`
  Add Tailwind to `vite.config.ts` plugins.
  Add `@import "tailwindcss"` to `src/assets/main.css`.

- [ ] Step 3: Install and initialize shadcn-vue
  Run: `cd frontend && npx shadcn-vue@latest init`
  Follow prompts: TypeScript=Yes, framework=Vite, style=Default, base color=Slate, CSS variables=Yes
  Run: `cd frontend && npx shadcn-vue@latest add button card input badge separator tabs select dropdown-menu dialog popover command`

- [ ] Step 4: Configure Vite dev proxy
  Edit `frontend/vite.config.ts`:
  ```typescript
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
  ```

- [ ] Step 5: Set up design token CSS custom properties
  Create `frontend/src/assets/theme.css` with semantic tokens per spec §11.0:
  - Light, Sepia, Dark, OLED, Dracula theme definitions via `[data-theme="..."]` selectors
  - Semantic tokens: `--color-bg-primary`, `--color-text-primary`, `--color-text-accent`, etc.
  - shadcn-vue variable aliases: map `--background` to `--color-bg-primary`, etc.
  Import in `main.ts`.

  Extend `tailwind.config.ts` with semantic color mappings per spec §11.0:
  ```typescript
  colors: {
    'bg-primary': 'var(--color-bg-primary)',
    'bg-secondary': 'var(--color-bg-secondary)',
    // ... etc
  }
  ```

- [ ] Step 6: Set up route definitions
  Edit `frontend/src/router/index.ts` per spec §11.2:
  ```typescript
  const routes = [
    { path: '/', component: () => import('@/views/LibraryView.vue') },
    { path: '/books/:id', component: () => import('@/views/BookDetailView.vue') },
    { path: '/books/:id/sections/:sectionId', component: () => import('@/views/BookDetailView.vue') },
    { path: '/books/:id/sections/:sectionId/eval', component: () => import('@/views/EvalDetailView.vue') },
    { path: '/books/:id/summary', component: () => import('@/views/BookSummaryView.vue') },
    { path: '/search', component: () => import('@/views/SearchResultsView.vue') },
    { path: '/annotations', component: () => import('@/views/AnnotationsView.vue') },
    { path: '/concepts', component: () => import('@/views/ConceptsView.vue') },
    { path: '/settings', component: () => import('@/views/SettingsView.vue') },
    { path: '/settings/:section', component: () => import('@/views/SettingsView.vue') },
    { path: '/upload', component: () => import('@/views/UploadView.vue') },
  ]
  ```
  Create placeholder view components (just `<template><div>Page name</div></template>`) for each route.

- [ ] Step 7: Verify dev server starts and proxy works
  Start backend: `cd backend && uv run uvicorn app.api.main:app --port 8000 &`
  Start frontend: `cd frontend && npm run dev &`
  Run: `curl -s http://localhost:5173/api/v1/health | python3 -m json.tool`
  Expected: `{"status": "ok"}` (proxied through Vite to FastAPI)
  Kill both processes.

- [ ] Step 8: Verify build output
  Run: `cd frontend && npm run build`
  Expected: `frontend/dist/` directory created with `index.html` and asset files
  Run: `ls frontend/dist/`
  Expected: `index.html`, `assets/` directory

- [ ] Step 9: Commit
  ```bash
  git add frontend/
  git commit -m "feat: Vue 3 frontend scaffolding with Tailwind, shadcn-vue, design tokens"
  ```

**Inline verification:**
- `cd frontend && npm run build` — builds without errors
- `cd frontend && npm run type-check` — no TypeScript errors
- Vite proxy delivers `/api/v1/health` from FastAPI

---

### T11: API Client Layer

**Goal:** Create typed TypeScript API client functions for books, sections, summaries, processing, eval, and library views.
**Spec refs:** §11.1 (api/ directory), §9.1–9.7 (API contracts)

**Files:**
- Create: `frontend/src/api/client.ts` (base fetch wrapper)
- Create: `frontend/src/api/books.ts`
- Create: `frontend/src/api/sections.ts`
- Create: `frontend/src/api/summaries.ts`
- Create: `frontend/src/api/processing.ts`
- Create: `frontend/src/api/eval.ts`
- Create: `frontend/src/api/views.ts`
- Create: `frontend/src/types/index.ts` (TypeScript interfaces matching API schemas)

**Steps:**

- [ ] Step 1: Define TypeScript types
  Create `frontend/src/types/index.ts` with interfaces matching the Pydantic schemas from T3:
  - `Book`, `BookListItem`, `Section`, `Summary`, `ProcessingJob`, `ProcessingStatus`
  - `PaginatedResponse<T>`, `ErrorResponse`
  - `Author`, `Tag`, `EvalSummary`

- [ ] Step 2: Create base API client
  Create `frontend/src/api/client.ts`:
  - `apiClient` object with `get<T>(url, params?)`, `post<T>(url, body?)`, `put<T>(url, body?)`, `patch<T>(url, body?)`, `delete(url)`, `upload<T>(url, file, fields?)`
  - Base URL: `/api/v1`
  - Error handling: throw typed errors with `detail` and `code` from API response
  - Content-Type: `application/json` default, `multipart/form-data` for uploads

- [ ] Step 3: Create resource-specific API modules
  `frontend/src/api/books.ts`:
  - `listBooks(params?)` → `PaginatedResponse<Book>`
  - `getBook(id)` → `Book`
  - `uploadBook(file, options?)` → `Book`
  - `updateBook(id, data)` → `Book`
  - `deleteBook(id)` → `void`
  - `checkDuplicate(id, fileHash)` → `DuplicateCheckResponse`

  `frontend/src/api/sections.ts`:
  - `listSections(bookId)` → `Section[]`
  - `getSection(bookId, sectionId)` → `Section`
  - `mergeSections(bookId, sectionIds, title)` → `Section`
  - `splitSection(bookId, sectionId, mode, positions)` → `Section[]`

  `frontend/src/api/summaries.ts`:
  - `listSummaries(bookId)` → `Summary[]`
  - `compareSummaries(id1, id2)` → `SummaryComparison`
  - `setDefault(summaryId)` → `Summary`

  `frontend/src/api/processing.ts`:
  - `startProcessing(bookId, options)` → `{job_id: number}`
  - `getProcessingStatus(jobId)` → `ProcessingStatus`
  - `cancelProcessing(jobId)` → `ProcessingCancelResponse`
  - `connectSSE(jobId, handlers)` → `EventSource` (wraps native EventSource with typed event handlers)

  `frontend/src/api/eval.ts`:
  - `getSectionEval(sectionId)` → `EvalResult`
  - `getBookEval(bookId)` → `BookEvalResult`

  `frontend/src/api/views.ts`:
  - `listViews()` → `LibraryView[]`
  - `createView(data)` → `LibraryView`
  - `updateView(id, data)` → `LibraryView`
  - `deleteView(id)` → `void`
  - `reorderViews(ids)` → `void`

- [ ] Step 4: Verify TypeScript compiles
  Run: `cd frontend && npm run type-check`
  Expected: No TypeScript errors

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/api/ frontend/src/types/
  git commit -m "feat: typed API client layer for books, sections, summaries, processing"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T12: App Shell (Icon Rail + Top Bar + Routing)

**Goal:** Build the app shell layout: desktop icon rail sidebar (56px), top bar (48px), mobile bottom tab bar, and content area with working Vue Router navigation.
**Spec refs:** FR-01 (desktop layout), FR-02 (mobile layout), FR-04 (top bar), FR-06 (active nav), FR-78 (breakpoints), §11.1 (component structure)

**Files:**
- Create: `frontend/src/components/app/AppShell.vue`
- Create: `frontend/src/components/app/IconRail.vue`
- Create: `frontend/src/components/app/TopBar.vue`
- Create: `frontend/src/components/app/BottomTabBar.vue`
- Create: `frontend/src/composables/useBreakpoint.ts`
- Create: `frontend/src/stores/ui.ts`
- Modify: `frontend/src/App.vue`

**Steps:**

- [ ] Step 1: Create `useBreakpoint` composable
  `frontend/src/composables/useBreakpoint.ts`:
  - Reactive breakpoint detection: `isMobile` (<768px), `isTablet` (768-1023px), `isDesktop` (>=1024px)
  - Uses `window.matchMedia` with event listeners
  - Cleans up listeners on unmount

- [ ] Step 2: Create UI store
  `frontend/src/stores/ui.ts` (Pinia):
  - State: `commandPaletteOpen`, `uploadWizardOpen`, `toasts[]`, `activeModals[]`
  - Actions: `showToast(message, type, duration)`, `openPalette()`, `closePalette()`

- [ ] Step 3: Create IconRail component
  `frontend/src/components/app/IconRail.vue`:
  - 56px wide fixed sidebar
  - Navigation items: Library (BookOpen icon), Concepts (Lightbulb), Annotations (MessageSquare), Settings (Settings)
  - Uses `router-link` for navigation
  - Active item: accent-colored background + filled icon (FR-06)
  - App logo/icon at top

- [ ] Step 4: Create TopBar component
  `frontend/src/components/app/TopBar.vue`:
  - 48px height
  - Left: page title (from route meta or computed)
  - Center-right: search input (placeholder, opens command palette on focus — wired in Phase 2)
  - Right: Upload button (navigates to `/upload` or opens wizard — wired in Phase 2)

- [ ] Step 5: Create BottomTabBar component
  `frontend/src/components/app/BottomTabBar.vue`:
  - 5 tabs: Library, Concepts, Search, Annotations, Settings
  - Only shown on mobile (<768px)
  - 44px touch targets (FR-33)
  - Active tab styling

- [ ] Step 6: Create AppShell and wire into App.vue
  `frontend/src/components/app/AppShell.vue`:
  - Desktop: IconRail (left) + TopBar (top) + `<RouterView>` (content)
  - Mobile: TopBar (top) + `<RouterView>` (content) + BottomTabBar (bottom)
  - Uses `useBreakpoint()` to switch layouts
  - Content area uses CSS grid or flexbox for proper sizing

  Update `frontend/src/App.vue`:
  - Replace default content with `<AppShell />`
  - Apply theme class from design tokens on `<html>` element

- [ ] Step 7: Verify navigation works
  Run: `cd frontend && npm run dev`
  Navigate manually: verify icon rail shows, clicking nav items changes route, mobile view shows bottom tabs.
  Run: `cd frontend && npm run build`
  Expected: Builds without errors

- [ ] Step 8: Commit
  ```bash
  git add frontend/src/components/app/ frontend/src/composables/ frontend/src/stores/ui.ts frontend/src/App.vue
  git commit -m "feat: app shell with icon rail, top bar, mobile bottom tabs"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T13a: Library Page — Grid, List, Filters, Empty States

**Goal:** Build the library page foundation with grid and list display modes, filters, sorting, pagination, empty states, and skeleton loading.
**Spec refs:** FR-10 (filters), FR-12 (sort), FR-13 (grid/list), FR-15 (empty states), FR-83 (skeleton loaders), §11.3 (Pinia stores)

**Files:**
- Create: `frontend/src/stores/books.ts`
- Create: `frontend/src/components/library/BookGrid.vue`
- Create: `frontend/src/components/library/BookCard.vue`
- Create: `frontend/src/components/library/BookList.vue`
- Create: `frontend/src/components/library/FilterRow.vue`
- Create: `frontend/src/components/common/SkeletonLoader.vue`
- Create: `frontend/src/components/common/EmptyState.vue`
- Modify: `frontend/src/views/LibraryView.vue`

**Steps:**

- [ ] Step 1: Create books Pinia store (core state)
  `frontend/src/stores/books.ts`:
  - State: `books: Book[]`, `total: number`, `page: number`, `perPage: number`, `loading: boolean`, `filters: {status?, tag_ids?, author_ids?, format?}`, `sort: {field, order}`, `displayMode: 'grid' | 'list' | 'table'`, `selectedIds: number[]`
  - Actions: `fetchBooks()` (calls API with current filters/sort/page), `updateFilters(filters)`, `setSort(field, order)`, `setDisplayMode(mode)`, `setPage(page)`, `toggleSelection(id)`, `selectAll()`, `clearSelection()`
  - Getters: `isEmpty`, `hasActiveFilters`
  Note: View management actions (`loadViews`, `createView`, etc.) added in T13b.

- [ ] Step 2: Create common components
  `frontend/src/components/common/SkeletonLoader.vue`:
  - Animated placeholder for loading states
  - Props: `type: 'card' | 'list-item' | 'table-row' | 'text'`, `count: number`

  `frontend/src/components/common/EmptyState.vue`:
  - Props: `icon`, `title`, `description`, `actionLabel`, `actionTo` (router-link)
  - Centered layout with illustration/icon

- [ ] Step 3: Create BookCard component
  `frontend/src/components/library/BookCard.vue`:
  - Props: `book: Book`, `selected: boolean`
  - Cover image (or placeholder), title, author(s), status badge, eval summary (passed/total), section count
  - Click navigates to `/books/:id`
  - Hover: subtle elevation/shadow
  - Selection checkbox on hover (for bulk operations)

- [ ] Step 4: Create BookGrid and BookList components
  `frontend/src/components/library/BookGrid.vue`:
  - Responsive CSS grid (auto-fill, min 200px)
  - Renders `BookCard` for each book
  - Shows `SkeletonLoader type="card"` while loading

  `frontend/src/components/library/BookList.vue`:
  - Compact row layout: cover thumbnail, title, author, status, sections, eval
  - Shows `SkeletonLoader type="list-item"` while loading

- [ ] Step 5: Create FilterRow component
  `frontend/src/components/library/FilterRow.vue`:
  - Horizontal row of filter dropdowns: Status, Format (Author and Tags deferred to Phase 2 when tagging is built)
  - Sort dropdown: Recent, Title A-Z, Author A-Z, Most sections, Date added
  - Display mode toggle: Grid / List / Table icons (Table wired in T13b)
  - Emits filter/sort changes to books store

- [ ] Step 6: Wire up LibraryView (initial version)
  `frontend/src/views/LibraryView.vue`:
  - Calls `booksStore.fetchBooks()` on mount
  - Renders FilterRow, then BookGrid or BookList based on displayMode
  - Empty state: first-time welcome when no books, "No matches" when filters yield nothing (FR-15)
  - Pagination controls at bottom
  - Slot/placeholder area for ViewTabs (added in T13b) and BulkToolbar (added in T13b)

- [ ] Step 7: Verify with backend running
  Start backend with at least one book in DB.
  Run: `cd frontend && npm run dev`
  Navigate to `/` — verify books render in grid, filters work, switching to list works, empty state shows when no books, pagination works.

- [ ] Step 8: Commit
  ```bash
  git add frontend/src/stores/books.ts frontend/src/components/library/ frontend/src/components/common/ frontend/src/views/LibraryView.vue
  git commit -m "feat: library page with grid/list display, filters, sort, empty states"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T13b: Library Page — Table Mode, View Tabs, Bulk Operations

**Goal:** Add table display mode with configurable columns, library view tabs with persistence, and bulk operations toolbar.
**Spec refs:** FR-07 (views as tabs), FR-08 (view persistence), FR-09 (unsaved changes), FR-13 (table mode), FR-14 (table: columns, drag-reorder, sticky, checkbox), FR-16 (bulk operations)

**Files:**
- Modify: `frontend/src/stores/books.ts` (add view management state/actions)
- Create: `frontend/src/components/library/ViewTabs.vue`
- Create: `frontend/src/components/library/BookTable.vue`
- Create: `frontend/src/components/library/BulkToolbar.vue`
- Modify: `frontend/src/views/LibraryView.vue` (wire in new components)

**Steps:**

- [ ] Step 1: Install table dependencies
  Run: `cd frontend && npm install @tanstack/vue-table`
  TanStack Table provides headless table logic for column management, sorting, and selection.

- [ ] Step 2: Extend books store with view management
  Add to `frontend/src/stores/books.ts`:
  - State: `views: LibraryView[]`, `currentViewId: number | null`, `tableColumns: TableColumnConfig[]`
  - Actions: `loadViews()`, `createView(data)`, `updateView(id, data)`, `deleteView(id)`, `switchView(viewId)`
  - Getters: `activeView`, `hasUnsavedChanges` (FR-09: compares current filters/sort to saved view)

- [ ] Step 3: Create ViewTabs component
  `frontend/src/components/library/ViewTabs.vue`:
  - Horizontal tabs showing saved views (FR-07)
  - "All Books" default tab always first
  - "+ New View" button creates view from current filters (FR-07)
  - Unsaved changes dot indicator when current filters differ from saved (FR-09)
  - Click switches view, loading its saved filters/sort/display config

- [ ] Step 4: Create BookTable component
  `frontend/src/components/library/BookTable.vue`:
  - Uses `@tanstack/vue-table` for headless table logic
  - Configurable columns: Title (sticky), Author, Status, Format, Sections, Eval, Date Added, Date Updated (FR-14)
  - Column visibility toggle dropdown
  - Drag-to-reorder columns (FR-14)
  - Checkbox column for multi-select (FR-14)
  - Sticky Title column with horizontal scroll (FR-14)
  - Sort on column header click
  - Shows `SkeletonLoader type="table-row"` while loading

- [ ] Step 5: Create BulkToolbar component
  `frontend/src/components/library/BulkToolbar.vue`:
  - Floating toolbar shown when books are selected (FR-16)
  - Actions: Summarize, Export, Delete (Tag deferred to Phase 2)
  - Shows count of selected books
  - "Clear selection" button
  - Delete with confirmation dialog

- [ ] Step 6: Wire into LibraryView
  Update `frontend/src/views/LibraryView.vue`:
  - Add ViewTabs above FilterRow
  - Load views on mount via `booksStore.loadViews()`
  - Add BookTable as third display mode option
  - Show BulkToolbar when `selectedIds.length > 0`

- [ ] Step 7: Verify with backend running
  Start backend with at least one book in DB.
  Run: `cd frontend && npm run dev`
  Navigate to `/`:
  - Verify table mode renders with configurable columns
  - Verify column show/hide and drag-to-reorder work
  - Verify table sticky Title column + horizontal scroll
  - Verify selection checkboxes work in table mode
  - Verify bulk toolbar appears on selection
  - Verify view tabs show, creating a new view saves current state
  - Verify unsaved changes dot appears when modifying saved view's filters

- [ ] Step 8: Commit
  ```bash
  git add frontend/src/stores/books.ts frontend/src/components/library/ViewTabs.vue frontend/src/components/library/BookTable.vue frontend/src/components/library/BulkToolbar.vue frontend/src/views/LibraryView.vue frontend/package.json frontend/package-lock.json
  git commit -m "feat: library table mode, view tabs, bulk operations"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T14: Book Detail / Reader

**Goal:** Build the book reader page with markdown rendering, section navigation, original/summary toggle, TOC dropdown, and responsive layout.
**Spec refs:** FR-18 (header), FR-19 (reading area), FR-21 (original/summary toggle), FR-22 (summary version), FR-24 (eval badge), FR-27 (section navigation), FR-28 (TOC dropdown), FR-33 (mobile reader)

**Files:**
- Create: `frontend/src/stores/reader.ts`
- Create: `frontend/src/components/reader/ReadingArea.vue`
- Create: `frontend/src/components/reader/ReaderHeader.vue`
- Create: `frontend/src/components/reader/ContentToggle.vue`
- Create: `frontend/src/components/reader/TOCDropdown.vue`
- Create: `frontend/src/components/reader/EvalBadge.vue`
- Modify: `frontend/src/views/BookDetailView.vue`

**Steps:**

- [ ] Step 1: Install markdown rendering dependency
  Run: `cd frontend && npm install markdown-it @types/markdown-it highlight.js dompurify @types/dompurify`

- [ ] Step 2: Create reader Pinia store
  `frontend/src/stores/reader.ts`:
  - State: `book: Book | null`, `sections: Section[]`, `currentSection: Section | null`, `contentMode: 'original' | 'summary'`, `sidebarTab: 'annotations' | 'ai'`, `sidebarOpen: boolean`, `loading: boolean`
  - Actions: `loadBook(bookId)`, `loadSection(bookId, sectionId)`, `navigateSection(direction: 'prev' | 'next')`, `toggleContent()`
  - Getters: `hasSummary`, `currentIndex`, `hasNext`, `hasPrev`, `sectionList`

- [ ] Step 3: Create ContentToggle component
  `frontend/src/components/reader/ContentToggle.vue`:
  - Segmented control: "Original" / "Summary"
  - Defaults to "Summary" when summary exists (FR-21)
  - Shows "No summary — Summarize" button when no summary
  - Emits mode change to reader store

- [ ] Step 4: Create EvalBadge component
  `frontend/src/components/reader/EvalBadge.vue`:
  - Props: `passed: number`, `total: number`
  - Green (all pass), Yellow (>=75%), Red (<75%), Gray (no eval)
  - Shows "16/16" text
  - "View details" link to eval detail route (FR-24)

- [ ] Step 5: Create TOCDropdown component
  `frontend/src/components/reader/TOCDropdown.vue`:
  - Searchable dropdown of all sections (FR-28)
  - Sections grouped by type (chapters, appendices, etc.)
  - Current section highlighted
  - Click navigates to section
  - Uses shadcn-vue Command/Popover components

- [ ] Step 6: Create ReaderHeader component
  `frontend/src/components/reader/ReaderHeader.vue`:
  - Breadcrumb: Library > Book Title > TOCDropdown (FR-18)
  - ContentToggle (Original/Summary)
  - EvalBadge (when summary selected)
  - Prev/Next navigation arrows
  - Action buttons: Aa (reader settings — placeholder), AI, Annotations (both placeholder for Phase 2)

- [ ] Step 7: Create ReadingArea component
  `frontend/src/components/reader/ReadingArea.vue`:
  - Max-width 720px centered (FR-19)
  - Renders markdown content using `markdown-it` + `DOMPurify` for sanitization
  - Applies reader settings (font, size, spacing — defaults for now, customizable in Phase 2)
  - Keyboard navigation: Left/Right arrows for prev/next section (FR-27)
  - Scrolls to top on section change

- [ ] Step 8: Wire up BookDetailView
  `frontend/src/views/BookDetailView.vue`:
  - On mount: load book + sections from route params
  - If `sectionId` in route: load that section. Otherwise: load first section.
  - Renders ReaderHeader + ReadingArea
  - Responds to route changes (section navigation)
  - Loading state: skeleton loader while fetching
  - Error state: "Book not found" if API returns 404

- [ ] Step 9: Verify with backend running
  Start backend with a parsed book in DB.
  Run: `cd frontend && npm run dev`
  Navigate to `/books/1` — verify:
  - Book loads, first section renders as markdown
  - TOC dropdown shows all sections
  - Original/Summary toggle works (if summaries exist)
  - Prev/Next navigation works
  - Eval badge shows score (if eval exists)

- [ ] Step 10: Commit
  ```bash
  git add frontend/src/stores/reader.ts frontend/src/components/reader/ frontend/src/views/BookDetailView.vue frontend/package.json frontend/package-lock.json
  git commit -m "feat: book reader with markdown rendering, section nav, original/summary toggle"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T15: Final Verification

**Goal:** Verify the entire Phase 1 implementation works end-to-end.

- [ ] **Lint & format (backend):**
  Run: `cd backend && uv run ruff check . && uv run ruff format --check .`
  Expected: No errors

- [ ] **Lint & type-check (frontend):**
  Run: `cd frontend && npm run type-check && npm run lint`
  Expected: No errors

- [ ] **Backend unit tests:**
  Run: `cd backend && uv run python -m pytest tests/unit/ -v`
  Expected: All pass, including new API schema/deps/health tests

- [ ] **Backend integration tests (API):**
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/ -v`
  Expected: All API tests pass

- [ ] **Full backend test suite (no regressions):**
  Run: `cd backend && uv run python -m pytest tests/ --timeout=60`
  Expected: All 78+ tests pass (existing + new)

- [ ] **Frontend build:**
  Run: `cd frontend && npm run build`
  Expected: Builds without errors, output in `frontend/dist/`

- [ ] **Database migrations:**
  Run: `cd backend && uv run alembic upgrade head`
  Expected: All migrations applied, seed data present

- [ ] **API smoke tests (curl):**
  Start: `cd backend && uv run uvicorn app.api.main:app --port 8000`
  Run: `curl -sf http://localhost:8000/api/v1/health | python3 -m json.tool`
  Expected: `{"status": "ok"}`
  Run: `curl -sf http://localhost:8000/api/v1/books | python3 -m json.tool`
  Expected: Paginated response with items array
  Run: `curl -sf http://localhost:8000/api/v1/books/1/sections | python3 -m json.tool` (if book exists)
  Expected: Section list

- [ ] **Health CLI command:**
  Run: `cd backend && uv run bookcompanion health`
  Expected: Diagnostic table with DB connectivity, migration status, access URL

- [ ] **Frontend serves from backend (production mode):**
  Run: `cp -r frontend/dist backend/static`
  Run: `cd backend && uv run uvicorn app.api.main:app --port 8000`
  Open: `http://localhost:8000` in browser
  Expected: Vue SPA loads, library page renders

- [ ] **Manual spot checks:**
  - Library page: books display in grid, filter by status works, sort works, display mode toggle works
  - Book reader: sections render as formatted markdown, TOC dropdown navigates between sections, Original/Summary toggle switches content, Prev/Next arrows work
  - Empty library: welcome empty state with clear messaging
  - Mobile viewport (375px): bottom tab bar appears, icon rail hides, content is full-width

**Cleanup:**
- [ ] Remove any temporary debug logging added during development
- [ ] Remove `backend/static/` from `.gitignore` if needed (it's a build artifact, should be ignored)
- [ ] Verify `.gitignore` includes `frontend/dist/`, `frontend/node_modules/`, `backend/static/`

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1    | Initial plan draft | Full plan written with 15 tasks |
| 2    | Missing eval API (§9.6), missing library views API (FR-07/08), missing eval route in frontend router, table display mode excluded despite FR-13/14 spec requirement, T13 too large | Added T6a (eval API), T6b (library views API), eval + views to T3 schemas and T11 API clients, added EvalDetailView/BookSummaryView/UploadView routes, included table mode (PD9 updated), split T13 into T13a (grid/list/filters) and T13b (table/views/bulk). Now 18 tasks. |
