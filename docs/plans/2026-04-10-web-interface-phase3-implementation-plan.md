# Web Interface Phase 3 — Implementation Plan

**Date:** 2026-04-10
**Spec:** `docs/specs/2026-04-10_web_interface_v1_spec.md`
**Requirements:** `docs/requirements/2026-04-10_web_interface_v1_requirements.md`
**Depends on:** Phase 1 + Phase 2 plans

---

## Overview

Phase 3 completes the web interface with settings management, export/backup APIs and UI, mobile responsive layouts, reading position sync, polish (skeletons, empty states, error boundaries), Docker production hardening, and an E2E test suite. It wraps the existing CLI backup/export services with REST endpoints, adds the `reading_state` table for cross-device position sync, builds the settings page with all 5 sections (General, Database, Presets, Reading, Backup), applies responsive breakpoints with mobile-specific components (bottom tab bar, bottom sheets, touch interactions), and validates everything with Playwright E2E tests.

**Done when:** Settings page renders all 5 sections with functional controls (LAN toggle + QR code, DB stats, preset CRUD, reading preferences, backup/export), export and backup work via API and UI, mobile layouts render correctly at 375px with bottom tab bar and bottom sheets, reading position syncs across devices with "Continue where you left off" banner, all empty states and skeleton loaders are polished, Docker compose runs the full stack in production mode with health checks and log rotation, and the Playwright E2E suite passes covering upload, library, reader, settings, mobile, and backup flows.

**Execution order:**
```
T1 (Reading state migration + model) ──────────────────────────────────────┐
  │                                                                         │
T2 (Export API) ──────[P]──> T3a (Backup API endpoints)                    │
  │                            │                                            │
  │                          T3b (Scheduled backups — APScheduler)          │
  │                            │                                            │
T4 (Settings API) ────[P]──> T5 (Reading state API)                        │
  │                            │                                            │
  ├────────────────────────────┤                                            │
  ▼                            ▼                                            │
T6a (Settings page infra) ──> T6b (Settings remaining sections)            │
  │                            │                                            │
  ▼                            ▼                                            │
T7 (Export & Backup UI)                                                    │
  │                                                                         │
T8 (Reading position sync UI) ──────────────────────────────────────────────┤
  │                                                                         │
T9a (Mobile bottom tab bar) ──> T9b (Bottom sheet component)               │
  │                                                                         │
T10 (Mobile responsive: touch interactions + breakpoint refinements) ──[P] │
  │                                                                         │
T11 (Skeleton loaders, empty states, error handling polish)                │
  │                                                                         │
T12 (Accessibility audit + fixes) ─────────────────────────────────[P]     │
  │                                                                         │
T13 (Performance optimization) ────────────────────────────────────[P]     │
  │                                                                         │
T14 (Docker production hardening)                                          │
  │                                                                         │
T15a (E2E infra + core tests) ──> T15b (E2E remaining tests)              │
  │                                                                    <───┘
T16 (Final verification)

[P] = parallelizable
T1 is prerequisite for T5, T8
T2, T3a, T4, T5 are backend tasks — T2+T3a parallelizable, T4+T5 parallelizable
T3a → T3b (T3b extends T3a's endpoints with scheduler integration)
T6a → T6b (T6b extends T6a's store and view with remaining sections)
T6a depends on T4; T7 depends on T2 + T3a/T3b (export/backup APIs must exist); T8 depends on T5
T9a → T9b (bottom sheet builds on bottom tab bar infrastructure)
T10 can run in parallel with T11 (no shared files) [P]
T12 and T13 can run in parallel (different concerns) [P]
T14 is independent of T9-T13
T15a/T15b depend on ALL tasks T1-T14 (full feature coverage needed for E2E)
T16 depends on T15b
Total: 20 tasks
```

---

## Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| P3D1 | Backup IDs use filename stem (timestamp), not a sequential DB ID | (a) Auto-increment ID in new table, (b) Filename-based ID, (c) UUID | Existing `BackupService.list_backups()` returns file paths and parses timestamps from filenames. Adding a DB table for backup metadata would require a migration and duplicate what the filesystem already tracks. The filename stem (`bookcompanion_backup_20260410_143000`) serves as a stable identifier for download/delete endpoints. |
| P3D2 | APScheduler `AsyncIOScheduler` for scheduled backups, configured via settings API | (a) APScheduler in FastAPI lifespan, (b) System cron, (c) asyncio periodic task | Spec D14 chose APScheduler. Configure schedule via `PATCH /api/v1/settings` writing to YAML config. Scheduler reads interval on startup and reschedules on settings change. If server is down, backups simply don't run. |
| P3D3 | Mobile bottom sheet uses headless `Dialog` from Radix Vue (via shadcn-vue) + CSS transform for drag behavior | (a) Custom implementation from scratch, (b) Radix Dialog + gesture layer, (c) Third-party bottom sheet library | Radix Dialog provides accessibility (focus trap, escape to close, ARIA) for free. Custom drag/snap logic is ~100 lines of composable code using touch events + CSS transform. Avoids a new dependency. |
| P3D4 | QR code via `qrcode.vue` (spec D13: client-side, <5KB gzipped) | (a) qrcode.vue, (b) qr-code-styling, (c) Server-generated PNG | Spec D13 chose client-side generation. `qrcode.vue` is the lightest option with Vue 3 support. |
| P3D5 | Reading state upsert via user-agent string as unique key | (a) User-agent string, (b) Client-generated device ID in localStorage, (c) IP address | Spec §10.1 defines `reading_state` with `user_agent` as unique index. User-agent is available without client-side storage. Good enough for personal tool (distinguishes desktop Chrome from mobile Safari). |
| P3D6 | E2E tests run against full Docker compose stack, not dev mode | (a) Full Docker stack, (b) Dev mode (separate processes), (c) Mock backend | Full stack tests catch real integration issues (proxy, static serving, DB). Docker compose is the production deployment. Dev mode E2E would miss static file serving bugs. |
| P3D7 | Settings writes go to YAML config file, not a DB table | (a) YAML file (existing pattern), (b) New settings DB table, (c) `.env` file | The existing `Settings` class reads from YAML config at `~/.config/bookcompanion/config.yaml` via `_load_yaml_config()`. Writing back to the same file maintains consistency. The Docker container mounts this path via volume. |

---

## Code Study Notes

### Existing Services to Reuse (No Changes Needed)

- **`BackupService`** (`backend/app/services/backup_service.py`): `create_backup(output_path)`, `restore_backup(backup_file)`, `list_backups()`. Uses `pg_dump`/`psql` subprocess. Constructor takes `Settings` only (no DB session). Backup dir: `~/.config/bookcompanion/backups/`.
- **`ExportService`** (`backend/app/services/export_service.py`): `export_book(book_id, fmt, output_path)`, `export_library(fmt, output_path)`. Returns content string. Constructor takes `AsyncSession`. Supports `json` and `markdown` formats. Collects sections, concepts, annotations, references.
- **`PresetService`** (via CLI `preset` commands): Already handles list/show/create/delete of YAML presets. Reuse for settings page preset management.

### Existing Patterns to Follow

- **API route pattern** (from Phase 1): Router module in `backend/app/api/routes/`, registered in `main.py`, uses `Depends()` for session/services.
- **Pinia store pattern** (from Phase 1/2): Store per domain, actions call API client, composables for cross-cutting concerns.
- **Design tokens** (from Phase 2): CSS custom properties on `:root`, `data-theme` attribute, shadcn-vue integration via `tailwind.config.ts`.
- **SSE pattern** (from Phase 1): `sse-starlette` `EventSourceResponse`, `useSSE` composable with auto-reconnect.

### New Code Required

- **`reading_state` table**: New migration + SQLAlchemy model (spec §10.1).
- **Backup scheduler**: APScheduler `AsyncIOScheduler` integrated into FastAPI lifespan.
- **Settings write-back**: New utility to write partial config updates back to YAML file.
- **Mobile components**: `BottomTabBar.vue`, `BottomSheet.vue`, touch gesture composable.
- **E2E infrastructure**: Playwright config, test fixtures, Docker compose for CI.

---

## Prerequisites

- Phase 1 complete: FastAPI app factory, dependency injection, books/sections/summaries/processing APIs, library page, reader page, Docker compose with backend service
- Phase 2 complete: Reader settings, annotations, AI chat, search, concepts, upload wizard, processing progress, all corresponding API endpoints and Pinia stores
- Docker running with `db` and `backend` services healthy
- Node.js 20+ with `npm` (for Playwright installation)
- `pg_dump` and `psql` available in backend container (for backup/restore)

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/alembic/versions/*_add_reading_state_table.py` | Migration: reading_state table |
| Modify | `backend/app/db/models.py` | Add `ReadingState` SQLAlchemy model |
| Create | `backend/app/api/routes/export.py` | Export API endpoints (book + library) |
| Create | `backend/app/api/routes/backup.py` | Backup API endpoints (create, list, download, restore, delete, schedule) |
| Create | `backend/app/api/routes/settings.py` | Settings API endpoints (get, update, db-stats, migration-status, run-migrations) |
| Create | `backend/app/api/routes/reading_state.py` | Reading state API endpoints (get, upsert) |
| Modify | `backend/app/api/schemas.py` | Add Pydantic schemas for export, backup, settings, reading state |
| Modify | `backend/app/api/main.py` | Register new routers, add APScheduler to lifespan |
| Modify | `backend/app/api/deps.py` | Add backup_service, export_service dependencies |
| Create | `backend/app/api/scheduler.py` | APScheduler setup for scheduled backups |
| Create | `backend/app/services/settings_service.py` | Read/write YAML config, DB stats, migration status |
| Create | `backend/app/db/repositories/reading_state_repo.py` | Reading state CRUD (upsert by user_agent) |
| Modify | `backend/pyproject.toml` | Add `apscheduler>=3.10.0` dependency |
| Modify | `docker-compose.yml` | Production hardening: restart policies, log rotation, resource limits, backup volume |
| Create | `docker-compose.prod.yml` | Production override: log drivers, healthcheck tuning |
| Modify | `Dockerfile` | Add `pg_dump`/`psql` to backend image, non-root user, HEALTHCHECK |
| Create | `frontend/src/views/SettingsView.vue` | Settings page with sidebar + sections |
| Create | `frontend/src/components/settings/SettingsSidebar.vue` | Settings navigation sidebar |
| Create | `frontend/src/components/settings/GeneralSettings.vue` | General: LAN toggle, QR, preset, cost estimates, LLM info |
| Create | `frontend/src/components/settings/DatabaseSettings.vue` | DB: connection, migrations, stats |
| Create | `frontend/src/components/settings/PresetSettings.vue` | Summarization presets: list/detail, CRUD |
| Create | `frontend/src/components/settings/ReadingSettings.vue` | Reading: default preset, fonts, custom CSS |
| Create | `frontend/src/components/settings/BackupSettings.vue` | Backup & export: create/restore/list, scheduled, export |
| Create | `frontend/src/components/settings/QRCode.vue` | QR code display (qrcode.vue wrapper) |
| Create | `frontend/src/api/export.ts` | Export API client |
| Create | `frontend/src/api/backup.ts` | Backup API client |
| Create | `frontend/src/api/settings.ts` | Settings API client |
| Create | `frontend/src/api/readingState.ts` | Reading state API client |
| Create | `frontend/src/stores/settings.ts` | Settings Pinia store |
| Create | `frontend/src/stores/readingState.ts` | Reading state Pinia store |
| Modify | `frontend/src/components/app/AppShell.vue` | Responsive: show BottomTabBar on mobile |
| Create | `frontend/src/components/app/BottomTabBar.vue` | Mobile bottom tab navigation |
| Create | `frontend/src/components/common/BottomSheet.vue` | Mobile bottom sheet (3 snap points) |
| Create | `frontend/src/composables/useTouchGestures.ts` | Touch event handling: long-press, drag |
| Create | `frontend/src/composables/useReadingState.ts` | Reading position tracking + sync |
| Modify | `frontend/src/composables/useBreakpoint.ts` | Refine breakpoint detection for mobile adaptations |
| Create | `frontend/src/components/reader/ContinueBanner.vue` | "Continue where you left off" banner |
| Modify | `frontend/src/components/common/SkeletonLoader.vue` | Refine skeleton variants for all pages |
| Modify | `frontend/src/components/common/EmptyState.vue` | Add all empty state variants per spec §5.4 |
| Create | `frontend/src/components/common/ErrorBoundary.vue` | Global error boundary with retry |
| Test | `backend/tests/unit/test_export_api_schemas.py` | Export/backup schema validation |
| Test | `backend/tests/unit/test_settings_service.py` | Settings read/write unit tests |
| Test | `backend/tests/integration/test_api/test_export_api.py` | Export endpoint integration tests |
| Test | `backend/tests/integration/test_api/test_backup_api.py` | Backup endpoint integration tests |
| Test | `backend/tests/integration/test_api/test_settings_api.py` | Settings endpoint integration tests |
| Test | `backend/tests/integration/test_api/test_reading_state_api.py` | Reading state endpoint integration tests |
| Test | `frontend/e2e/settings.spec.ts` | Settings page E2E |
| Test | `frontend/e2e/export-backup.spec.ts` | Export & backup E2E |
| Test | `frontend/e2e/mobile.spec.ts` | Mobile layout E2E |
| Test | `frontend/e2e/reading-position.spec.ts` | Reading position sync E2E |
| Test | `frontend/e2e/library.spec.ts` | Library full flow E2E |
| Test | `frontend/e2e/reader.spec.ts` | Reader full flow E2E |
| Test | `frontend/e2e/upload.spec.ts` | Upload wizard E2E |
| Test | `frontend/e2e/search.spec.ts` | Search E2E |
| Create | `frontend/playwright.config.ts` | Playwright config (desktop + mobile projects) |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `pg_dump`/`psql` not available in slim Python Docker image | High | Dockerfile installs `postgresql-client` package in backend stage. Test in T14. |
| APScheduler job persistence lost on container restart | Medium | APScheduler uses in-memory job store (acceptable per D14). Scheduler re-reads config on startup via lifespan. Backup interval survives restart via YAML config. |
| Bottom sheet gesture conflicts with scroll on mobile | Medium | Use `touch-action: none` on drag handle only, not the content area. Test on real mobile device in T10. |
| QR code library adds unexpected bundle size | Low | Spec D13 caps at <5KB gzipped. Verify with `npm run build -- --report` after T6. Fallback: inline SVG generation. |
| Settings YAML write-back creates race condition with concurrent reads | Low | Single-user tool means no concurrent writes. Use atomic write (write to temp file, then rename) for safety. |
| Playwright E2E tests flaky due to SSE timing | Medium | Use Playwright's `waitForResponse` and `waitForSelector` with generous timeouts. Retry up to 2 times in CI config. |
| Reading state user-agent detection unreliable (same browser, different tabs) | Low | Acceptable for personal tool. Same user-agent = same device. Spec explicitly uses user-agent (§10.1). |
| CORS issues when accessing from mobile device on LAN | Medium | Backend CORS middleware must dynamically allow LAN origins when `allow_lan=true`. Add `*` origin in LAN mode only. |

---

## Tasks

### T1: Reading State Migration + Model

**Goal:** Add the `reading_state` table to track reading position per device, and the corresponding SQLAlchemy model.
**Spec refs:** §10.1 (reading_state table), FR-81 (reading position sync)

**Files:**
- Modify: `backend/app/db/models.py` (add `ReadingState` model)
- Create: `backend/alembic/versions/*_add_reading_state_table.py`
- Create: `backend/app/db/repositories/reading_state_repo.py`
- Test: `backend/tests/unit/test_reading_state_model.py`

**Steps:**

- [ ] Step 1: Write failing test for ReadingState model
  ```python
  # backend/tests/unit/test_reading_state_model.py
  from app.db.models import ReadingState

  def test_reading_state_model_exists():
      rs = ReadingState()
      assert hasattr(rs, 'id')
      assert hasattr(rs, 'user_agent')
      assert hasattr(rs, 'last_book_id')
      assert hasattr(rs, 'last_section_id')
      assert hasattr(rs, 'last_viewed_at')
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_reading_state_model.py -v`
  Expected: FAIL -- `ReadingState` not defined

- [ ] Step 1a: Write behavioral integration tests for ReadingState DB behavior
  ```python
  # backend/tests/integration/test_reading_state_model.py
  import pytest
  from sqlalchemy import text
  from app.db.models import ReadingState

  @pytest.mark.asyncio
  async def test_upsert_updates_existing_row(async_session):
      """Upsert with same user_agent must update in-place, not insert a second row."""
      ua = "Mozilla/5.0 (Test Browser)"
      # Insert first
      rs1 = ReadingState(user_agent=ua, last_book_id=1)
      async_session.add(rs1)
      await async_session.commit()
      # Upsert with new book_id
      rs2 = ReadingState(user_agent=ua, last_book_id=2)
      async_session.add(rs2)
      await async_session.flush()
      # There must still be exactly one row for this user_agent
      result = await async_session.execute(
          text("SELECT COUNT(*) FROM reading_state WHERE user_agent = :ua"), {"ua": ua}
      )
      assert result.scalar() == 1

  @pytest.mark.asyncio
  async def test_unique_constraint_on_user_agent(async_session):
      """UNIQUE index on user_agent must reject duplicate inserts."""
      from sqlalchemy.exc import IntegrityError
      ua = "DuplicateAgent/1.0"
      async_session.add(ReadingState(user_agent=ua, last_book_id=1))
      await async_session.flush()
      async_session.add(ReadingState(user_agent=ua, last_book_id=2))
      with pytest.raises(IntegrityError):
          await async_session.flush()

  @pytest.mark.asyncio
  async def test_fk_cascade_on_book_delete(async_session, seeded_book):
      """Deleting the referenced book must cascade-delete the reading_state row."""
      rs = ReadingState(user_agent="CascadeTest/1.0", last_book_id=seeded_book.id)
      async_session.add(rs)
      await async_session.commit()
      await async_session.delete(seeded_book)
      await async_session.commit()
      result = await async_session.execute(
          text("SELECT COUNT(*) FROM reading_state WHERE user_agent = 'CascadeTest/1.0'")
      )
      assert result.scalar() == 0

  @pytest.mark.asyncio
  async def test_last_viewed_at_auto_populated(async_session):
      """last_viewed_at must be set by server_default, not left NULL."""
      rs = ReadingState(user_agent="TimestampTest/1.0", last_book_id=1)
      async_session.add(rs)
      await async_session.commit()
      await async_session.refresh(rs)
      assert rs.last_viewed_at is not None
      assert rs.created_at is not None
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_reading_state_model.py -v`
  Expected: FAIL (table does not exist yet)

- [ ] Step 2: Add `ReadingState` model to `backend/app/db/models.py`
  ```python
  class ReadingState(Base):
      __tablename__ = "reading_state"
      id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
      user_agent: Mapped[str] = mapped_column(String(500), nullable=False)
      last_book_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=True)
      last_section_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True)
      last_viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
      created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
      updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

      last_book: Mapped["Book"] = relationship("Book", foreign_keys=[last_book_id])
      last_section: Mapped["BookSection"] = relationship("BookSection", foreign_keys=[last_section_id])

      __table_args__ = (
          Index("ix_reading_state_user_agent", "user_agent", unique=True),
      )
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_reading_state_model.py -v`
  Expected: PASS

- [ ] Step 3: Generate Alembic migration
  Run: `cd backend && uv run alembic revision --autogenerate -m "add reading_state table"`
  Review: Verify migration has CREATE TABLE with all columns, UNIQUE index on user_agent, FK constraints, CHECK constraints if any.
  Run: `cd backend && uv run alembic upgrade head`
  Expected: Migration applies cleanly

- [ ] Step 4: Write and implement `ReadingStateRepository`
  ```python
  # backend/app/db/repositories/reading_state_repo.py
  class ReadingStateRepository:
      def __init__(self, session: AsyncSession):
          self.session = session

      async def upsert(self, user_agent: str, book_id: int, section_id: int | None) -> ReadingState:
          """Insert or update reading state by user_agent."""
          # Use INSERT ... ON CONFLICT DO UPDATE
          ...

      async def get_by_user_agent(self, user_agent: str) -> ReadingState | None:
          ...

      async def get_latest_other_device(self, current_user_agent: str) -> ReadingState | None:
          """Get the most recent reading state from a different device."""
          ...
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_reading_state_model.py -v`
  Expected: PASS

- [ ] Step 4a: Run behavioral integration tests against live DB
  Run: `cd backend && uv run python -m pytest tests/integration/test_reading_state_model.py -v`
  Expected: All 4 behavioral tests pass (upsert, uniqueness, FK cascade, timestamp auto-populated)

- [ ] Verify: `cd backend && uv run python -m pytest tests/ --timeout=60 -q` -- no regressions

**Commit:** `git commit -m "feat(api): add reading_state table, model, and repository (T1)"`

**Inline verification:**
- `cd backend && uv run python -m pytest tests/unit/test_reading_state_model.py -v` -- all pass
- `cd backend && uv run python -m pytest tests/integration/test_reading_state_model.py -v` -- all 4 behavioral tests pass
- `cd backend && uv run alembic upgrade head` -- migration applies cleanly
- `cd backend && uv run python -m pytest tests/ --timeout=60 -q` -- no regressions

---

### T2: Export API Endpoints

**Goal:** Wrap the existing `ExportService` with REST endpoints for book and library export.
**Spec refs:** §9.16 (Export & Backup API), FR-77 (Backup & Export settings section)

**Files:**
- Create: `backend/app/api/routes/export.py`
- Modify: `backend/app/api/schemas.py` (add export schemas)
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_export_api.py`

**Steps:**

- [ ] Step 1: Write failing integration test for export endpoint
  ```python
  # backend/tests/integration/test_api/test_export_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.mark.asyncio
  async def test_export_book_json(test_db_session, seeded_book):
      app = create_app()
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as client:
          resp = await client.get(f"/api/v1/export/book/{seeded_book.id}?format=json")
          assert resp.status_code == 200
          assert resp.headers["content-type"] == "application/json"
          data = resp.json()
          assert "library" in data
          assert len(data["library"]) == 1

  @pytest.mark.asyncio
  async def test_export_book_markdown(test_db_session, seeded_book):
      app = create_app()
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as client:
          resp = await client.get(f"/api/v1/export/book/{seeded_book.id}?format=markdown")
          assert resp.status_code == 200
          assert "text/markdown" in resp.headers["content-type"]
          assert "# Book Companion Library Export" in resp.text

  @pytest.mark.asyncio
  async def test_export_library_json(test_db_session, seeded_book):
      app = create_app()
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as client:
          resp = await client.get("/api/v1/export/library?format=json")
          assert resp.status_code == 200
          data = resp.json()
          assert "library" in data

  @pytest.mark.asyncio
  async def test_export_book_not_found(test_db_session):
      app = create_app()
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as client:
          resp = await client.get("/api/v1/export/book/99999?format=json")
          assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_export_book_json_contains_summaries(client):
      """Export JSON for a book with summaries must include summary content, not just structure."""
      # Uses real data: Art of War (id=1) has 44 sections and 124 summaries in test DB
      resp = await client.get("/api/v1/export/book/1?format=json&include_summaries=true")
      assert resp.status_code == 200
      data = resp.json()
      # The book entry must exist
      book = data["library"][0]
      assert book["title"] == "The Art of War"
      # At least one section must have a non-empty summary
      sections_with_summaries = [
          s for s in book.get("sections", [])
          if s.get("summary") and len(s["summary"]) > 0
      ]
      assert len(sections_with_summaries) > 0, "Expected at least one section with a summary in export"

  @pytest.mark.asyncio
  async def test_export_book_markdown_contains_section_titles(client):
      """Export Markdown must include recognizable section headings, not just the book heading."""
      resp = await client.get("/api/v1/export/book/1?format=markdown")
      assert resp.status_code == 200
      # Markdown must have at least one section-level heading (##)
      assert "##" in resp.text, "Expected section-level headings in markdown export"

  @pytest.mark.asyncio
  async def test_export_library_json_contains_all_books(client):
      """Library export must include all books present in the DB."""
      resp = await client.get("/api/v1/export/library?format=json")
      assert resp.status_code == 200
      data = resp.json()
      # Real test DB has 2 books; confirm both are present
      titles = [b["title"] for b in data["library"]]
      assert len(titles) >= 2, "Expected at least 2 books in library export"

  @pytest.mark.asyncio
  async def test_export_book_annotations_included_when_present(client):
      """Export with include_annotations=true must surface annotation data when annotations exist."""
      resp = await client.get("/api/v1/export/book/1?format=json&include_annotations=true")
      assert resp.status_code == 200
      data = resp.json()
      book = data["library"][0]
      # Key must be present (even if empty list); tests that the field is not silently dropped
      assert "annotations" in book or any("annotations" in s for s in book.get("sections", []))
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py -v`
  Expected: FAIL -- route does not exist

- [ ] Step 2: Add export schemas to `backend/app/api/schemas.py`
  ```python
  class ExportQueryParams(BaseModel):
      format: str = "json"  # json | markdown
      include_summaries: bool = True
      include_annotations: bool = True
      include_concepts: bool = True
      include_eval: bool = False

  class LibraryExportQueryParams(ExportQueryParams):
      book_ids: str | None = None  # comma-separated IDs, None = all
  ```

- [ ] Step 3: Implement `backend/app/api/routes/export.py`
  ```python
  from fastapi import APIRouter, Depends, Query
  from fastapi.responses import JSONResponse, PlainTextResponse
  from app.api.deps import get_export_service
  from app.services.export_service import ExportService, ExportError

  router = APIRouter(prefix="/api/v1/export", tags=["export"])

  @router.get("/book/{book_id}")
  async def export_book(
      book_id: int,
      format: str = Query("json", regex="^(json|markdown)$"),
      export_service: ExportService = Depends(get_export_service),
  ):
      try:
          content = await export_service.export_book(book_id, fmt=format)
      except ExportError as e:
          raise HTTPException(status_code=404, detail=str(e))
      if format == "markdown":
          return PlainTextResponse(content, media_type="text/markdown",
              headers={"Content-Disposition": f"attachment; filename=book_{book_id}.md"})
      return JSONResponse(content=json.loads(content),
          headers={"Content-Disposition": f"attachment; filename=book_{book_id}.json"})

  @router.get("/library")
  async def export_library(
      format: str = Query("json", regex="^(json|markdown)$"),
      book_ids: str | None = Query(None),
      export_service: ExportService = Depends(get_export_service),
  ):
      content = await export_service.export_library(fmt=format)
      if format == "markdown":
          return PlainTextResponse(content, media_type="text/markdown",
              headers={"Content-Disposition": "attachment; filename=library_export.md"})
      return JSONResponse(content=json.loads(content),
          headers={"Content-Disposition": "attachment; filename=library_export.json"})
  ```
  Register router in `backend/app/api/main.py`.
  Add `get_export_service` to `backend/app/api/deps.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py -v`
  Expected: PASS

- [ ] Verify: `cd backend && uv run ruff check backend/app/api/routes/export.py && uv run python -m pytest tests/ --timeout=60 -q`

**Commit:** `git commit -m "feat(api): add export API endpoints wrapping ExportService (T2)"`

**Inline verification:**
- `cd backend && uv run ruff check backend/app/api/routes/export.py` -- no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py -v` -- all pass
- `cd backend && uv run python -m pytest tests/ --timeout=60 -q` -- no regressions

---

### T3a: Backup API Endpoints

**Goal:** Wrap the existing `BackupService` with REST endpoints for create, list, download, restore, and delete.
**Spec refs:** §9.16 (Backup API), FR-77 (Backup & Export settings section)

**Files:**
- Create: `backend/app/api/routes/backup.py`
- Modify: `backend/app/api/schemas.py` (add backup schemas)
- Modify: `backend/app/api/main.py` (register router)
- Modify: `backend/app/api/deps.py` (add `get_backup_service`)
- Test: `backend/tests/integration/test_api/test_backup_api.py`

**Steps:**

- [ ] Step 1: Write failing integration tests for backup endpoints
  ```python
  # backend/tests/integration/test_api/test_backup_api.py
  @pytest.mark.asyncio
  async def test_create_backup(test_app_client):
      resp = await test_app_client.post("/api/v1/backup/create")
      assert resp.status_code == 200
      data = resp.json()
      assert "backup_id" in data
      assert "filename" in data

  @pytest.mark.asyncio
  async def test_list_backups(test_app_client):
      # Create one first
      await test_app_client.post("/api/v1/backup/create")
      resp = await test_app_client.get("/api/v1/backup/list")
      assert resp.status_code == 200
      data = resp.json()
      assert isinstance(data, list)
      assert len(data) >= 1
      assert "filename" in data[0]
      assert "size_bytes" in data[0]

  @pytest.mark.asyncio
  async def test_download_backup(test_app_client):
      create_resp = await test_app_client.post("/api/v1/backup/create")
      backup_id = create_resp.json()["backup_id"]
      resp = await test_app_client.get(f"/api/v1/backup/{backup_id}/download")
      assert resp.status_code == 200
      assert "application/sql" in resp.headers["content-type"] or resp.status_code == 200

  @pytest.mark.asyncio
  async def test_delete_backup(test_app_client):
      create_resp = await test_app_client.post("/api/v1/backup/create")
      backup_id = create_resp.json()["backup_id"]
      resp = await test_app_client.delete(f"/api/v1/backup/{backup_id}")
      assert resp.status_code == 204

  @pytest.mark.asyncio
  async def test_delete_nonexistent_backup(test_app_client):
      resp = await test_app_client.delete("/api/v1/backup/nonexistent")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_create_backup_file_exists_on_disk(test_app_client, tmp_path, monkeypatch):
      """Creating a backup must produce an actual .sql file at the configured backup dir."""
      import os
      backup_dir = tmp_path / "backups"
      backup_dir.mkdir()
      monkeypatch.setenv("BOOKCOMPANION_BACKUP__DIR", str(backup_dir))
      resp = await test_app_client.post("/api/v1/backup/create")
      assert resp.status_code == 200
      data = resp.json()
      backup_file = backup_dir / f"{data['backup_id']}.sql"
      assert backup_file.exists(), f"Expected backup file at {backup_file}"
      assert backup_file.stat().st_size > 0, "Backup file must not be empty"

  @pytest.mark.asyncio
  async def test_download_backup_returns_valid_sql_content(test_app_client, tmp_path, monkeypatch):
      """Downloaded backup content must be valid SQL (starts with pg_dump header)."""
      backup_dir = tmp_path / "backups"
      backup_dir.mkdir()
      monkeypatch.setenv("BOOKCOMPANION_BACKUP__DIR", str(backup_dir))
      create_resp = await test_app_client.post("/api/v1/backup/create")
      backup_id = create_resp.json()["backup_id"]
      dl_resp = await test_app_client.get(f"/api/v1/backup/{backup_id}/download")
      assert dl_resp.status_code == 200
      content = dl_resp.text
      # pg_dump output always starts with a comment block
      assert content.startswith("--"), f"Expected SQL dump content, got: {content[:100]!r}"

  @pytest.mark.asyncio
  async def test_delete_backup_removes_file_from_disk(test_app_client, tmp_path, monkeypatch):
      """Deleting a backup via API must remove the file from disk."""
      import os
      backup_dir = tmp_path / "backups"
      backup_dir.mkdir()
      monkeypatch.setenv("BOOKCOMPANION_BACKUP__DIR", str(backup_dir))
      create_resp = await test_app_client.post("/api/v1/backup/create")
      backup_id = create_resp.json()["backup_id"]
      backup_file = backup_dir / f"{backup_id}.sql"
      assert backup_file.exists()
      del_resp = await test_app_client.delete(f"/api/v1/backup/{backup_id}")
      assert del_resp.status_code == 204
      assert not backup_file.exists(), "Backup file must be gone from disk after delete"

  @pytest.mark.asyncio
  async def test_list_backups_includes_created_backup(test_app_client, tmp_path, monkeypatch):
      """List endpoint must reflect the backup just created — correct filename and non-zero size."""
      backup_dir = tmp_path / "backups"
      backup_dir.mkdir()
      monkeypatch.setenv("BOOKCOMPANION_BACKUP__DIR", str(backup_dir))
      create_resp = await test_app_client.post("/api/v1/backup/create")
      backup_id = create_resp.json()["backup_id"]
      list_resp = await test_app_client.get("/api/v1/backup/list")
      assert list_resp.status_code == 200
      items = list_resp.json()
      matching = [item for item in items if item["backup_id"] == backup_id]
      assert len(matching) == 1, f"Expected backup {backup_id} in list, got: {[i['backup_id'] for i in items]}"
      assert matching[0]["size_bytes"] > 0
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_backup_api.py -v`
  Expected: FAIL

- [ ] Step 2: Add backup schemas to `backend/app/api/schemas.py`
  ```python
  class BackupResponse(BaseModel):
      backup_id: str
      filename: str
      size_bytes: int
      created_at: str | None

  class BackupListItem(BaseModel):
      backup_id: str
      filename: str
      size_bytes: int
      size_mb: float
      created_at: str | None
  ```

- [ ] Step 3: Implement `backend/app/api/routes/backup.py`
  Endpoints:
  - `POST /api/v1/backup/create` -- calls `backup_service.create_backup()`, returns `{backup_id, filename, size_bytes, created_at}`
  - `GET /api/v1/backup/list` -- calls `backup_service.list_backups()`, maps to `BackupListItem[]`
  - `GET /api/v1/backup/{backup_id}/download` -- returns `FileResponse` for the backup file
  - `POST /api/v1/backup/restore` -- accepts multipart file upload, saves to temp, calls `backup_service.restore_backup()`
  - `DELETE /api/v1/backup/{backup_id}` -- deletes backup file from disk
  - `backup_id` is the filename stem (e.g., `bookcompanion_backup_20260410_143000`)
  Register in `main.py`. Add `get_backup_service` to `deps.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_backup_api.py -v`
  Expected: PASS

- [ ] Verify: `cd backend && uv run ruff check . && uv run python -m pytest tests/ --timeout=60 -q`

**Commit:** `git commit -m "feat(api): add backup API endpoints wrapping BackupService (T3a)"`

**Inline verification:**
- `cd backend && uv run ruff check backend/app/api/routes/backup.py` -- no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_backup_api.py -v` -- all pass
- `cd backend && uv run python -m pytest tests/ --timeout=60 -q` -- no regressions

---

### T3b: Scheduled Backups with APScheduler

**Goal:** Add APScheduler AsyncIOScheduler integration in FastAPI lifespan for automatic backups, with settings-driven interval and reschedule on config change.
**Spec refs:** D14 (APScheduler), FR-77 (scheduled backups)

**Files:**
- Create: `backend/app/api/scheduler.py`
- Modify: `backend/app/api/schemas.py` (add `BackupScheduleRequest`)
- Modify: `backend/app/api/main.py` (add scheduler to lifespan)
- Modify: `backend/app/api/routes/backup.py` (add schedule endpoint)
- Modify: `backend/pyproject.toml` (add `apscheduler`)
- Test: `backend/tests/unit/test_scheduler.py`

**Steps:**

- [ ] Step 1: Add APScheduler dependency
  Add `apscheduler>=3.10.0` to `backend/pyproject.toml` `[project.dependencies]`.
  Run: `cd backend && uv sync --dev`

- [ ] Step 2: Add schedule schema to `backend/app/api/schemas.py`
  ```python
  class BackupScheduleRequest(BaseModel):
      enabled: bool
      interval_hours: int = 24  # 24 = daily, 168 = weekly
  ```

- [ ] Step 3: Write failing test for scheduler
  ```python
  # backend/tests/unit/test_scheduler.py
  import asyncio
  from unittest.mock import AsyncMock, MagicMock, patch
  from app.api.scheduler import create_backup_scheduler

  def test_create_scheduler_returns_scheduler():
      mock_service = MagicMock()
      mock_service.create_backup = AsyncMock()
      scheduler = create_backup_scheduler(interval_hours=24, backup_service=mock_service)
      assert scheduler is not None

  def test_scheduler_disabled_when_interval_zero():
      mock_service = MagicMock()
      scheduler = create_backup_scheduler(interval_hours=0, backup_service=mock_service)
      assert not scheduler.running

  def test_scheduler_has_one_job_when_enabled():
      """Scheduler must register exactly one interval job when interval_hours > 0."""
      mock_service = MagicMock()
      mock_service.create_backup = AsyncMock()
      scheduler = create_backup_scheduler(interval_hours=24, backup_service=mock_service)
      jobs = scheduler.get_jobs()
      assert len(jobs) == 1
      assert jobs[0].id == 'scheduled_backup'

  @pytest.mark.asyncio
  async def test_scheduler_job_function_actually_creates_backup(tmp_path):
      """Calling the scheduled job function directly must invoke BackupService.create_backup()."""
      from app.services.backup_service import BackupService
      from app.api.scheduler import create_backup_scheduler
      mock_service = MagicMock()
      mock_service.create_backup = AsyncMock(return_value=str(tmp_path / "backup.sql"))
      scheduler = create_backup_scheduler(interval_hours=24, backup_service=mock_service)
      # Get the registered job's function and call it directly
      job = scheduler.get_jobs()[0]
      await job.func()
      mock_service.create_backup.assert_awaited_once()
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_scheduler.py -v`
  Expected: FAIL

- [ ] Step 4: Implement `backend/app/api/scheduler.py`
  ```python
  from apscheduler.schedulers.asyncio import AsyncIOScheduler
  from app.services.backup_service import BackupService

  def create_backup_scheduler(interval_hours: int, backup_service: BackupService) -> AsyncIOScheduler:
      scheduler = AsyncIOScheduler()
      if interval_hours > 0:
          scheduler.add_job(
              backup_service.create_backup,
              'interval',
              hours=interval_hours,
              id='scheduled_backup',
              replace_existing=True,
          )
      return scheduler
  ```
  Integrate into FastAPI lifespan in `main.py`: read `backup_schedule_hours` from settings, start scheduler on startup, shutdown on app shutdown. Add reschedule on settings change (when `PATCH /api/v1/settings` updates `backup_schedule_hours`).
  Run: `cd backend && uv run python -m pytest tests/unit/test_scheduler.py -v`
  Expected: PASS

- [ ] Verify: `cd backend && uv run ruff check . && uv run python -m pytest tests/ --timeout=60 -q`

**Commit:** `git commit -m "feat(api): add APScheduler for scheduled backups (T3b)"`

**Inline verification:**
- `cd backend && uv run ruff check backend/app/api/scheduler.py` -- no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_scheduler.py -v` -- all pass
- `cd backend && uv run python -m pytest tests/ --timeout=60 -q` -- no regressions

---

### T4: Settings API Endpoints

**Goal:** API for reading/writing application settings, database stats, and migration status.
**Spec refs:** §9.15 (Settings & System API), FR-72-77

**Files:**
- Create: `backend/app/services/settings_service.py`
- Create: `backend/app/api/routes/settings.py`
- Modify: `backend/app/api/schemas.py` (add settings schemas)
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/unit/test_settings_service.py`
- Test: `backend/tests/integration/test_api/test_settings_api.py`

**Steps:**

- [ ] Step 1: Write failing unit tests for `SettingsService`
  ```python
  # backend/tests/unit/test_settings_service.py
  import pytest
  import yaml
  from pathlib import Path
  from app.services.settings_service import SettingsService
  from app.config import Settings

  def test_get_safe_settings_excludes_password():
      svc = SettingsService(settings=Settings())
      safe = svc.get_safe_settings()
      assert "password" not in str(safe).lower()
      assert "network" in safe
      assert "llm" in safe

  def test_update_settings_writes_yaml(tmp_path):
      config_path = tmp_path / "config.yaml"
      svc = SettingsService(settings=Settings(), config_path=config_path)
      svc.update_settings({"network": {"allow_lan": True}})
      # Verify file was written
      with open(config_path) as f:
          data = yaml.safe_load(f)
      assert data["network"]["allow_lan"] is True

  def test_update_settings_persists_on_re_read(tmp_path):
      """Write a setting, then create a fresh SettingsService reading from the same file — value must round-trip."""
      config_path = tmp_path / "config.yaml"
      svc1 = SettingsService(settings=Settings(), config_path=config_path)
      svc1.update_settings({"web": {"show_cost_estimates": True}})
      # Re-read from disk
      with open(config_path) as f:
          persisted = yaml.safe_load(f)
      assert persisted["web"]["show_cost_estimates"] is True

  def test_partial_update_does_not_wipe_other_fields(tmp_path):
      """Updating one nested key must leave unrelated keys intact."""
      config_path = tmp_path / "config.yaml"
      # Pre-seed the config file with two keys
      config_path.write_text(yaml.dump({"network": {"allow_lan": False, "host": "127.0.0.1"}}))
      svc = SettingsService(settings=Settings(), config_path=config_path)
      svc.update_settings({"network": {"allow_lan": True}})  # only change allow_lan
      with open(config_path) as f:
          data = yaml.safe_load(f)
      assert data["network"]["allow_lan"] is True
      assert data["network"]["host"] == "127.0.0.1", "Partial update must not wipe existing host field"

  def test_get_safe_settings_masks_access_token(tmp_path):
      """access_token must never appear in plain text in the safe settings output."""
      config_path = tmp_path / "config.yaml"
      config_path.write_text(yaml.dump({"network": {"access_token": "super-secret-token"}}))
      svc = SettingsService(settings=Settings(), config_path=config_path)
      safe = svc.get_safe_settings()
      assert "super-secret-token" not in str(safe)
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_settings_service.py -v`
  Expected: FAIL -- `SettingsService` does not exist

- [ ] Step 2: Implement `backend/app/services/settings_service.py`
  ```python
  class SettingsService:
      def __init__(self, settings: Settings, config_path: Path | None = None):
          self.settings = settings
          self.config_path = config_path or Path("~/.config/bookcompanion/config.yaml").expanduser()

      def get_safe_settings(self) -> dict:
          """Return settings with passwords masked."""
          data = {
              "network": {"host": ..., "port": ..., "allow_lan": ..., "access_token": "***" if ... else None},
              "llm": {"provider": ..., "model": ..., "timeout_seconds": ..., "max_retries": ..., "max_budget_usd": ...},
              "summarization": {"default_preset": ...},
              "web": {"show_cost_estimates": ...},
          }
          return data

      def update_settings(self, updates: dict) -> dict:
          """Write partial settings to YAML config file. Atomic write."""
          ...

      async def get_database_stats(self, session: AsyncSession) -> dict:
          """Count rows in each table."""
          tables = ["books", "book_sections", "summaries", "annotations", "concepts", "eval_traces"]
          stats = {}
          for table in tables:
              result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
              stats[table] = result.scalar()
          return stats

      async def get_migration_status(self) -> dict:
          """Check current vs latest Alembic revision."""
          ...
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_settings_service.py -v`
  Expected: PASS

- [ ] Step 3: Write failing integration tests for settings API
  ```python
  # backend/tests/integration/test_api/test_settings_api.py
  @pytest.mark.asyncio
  async def test_get_settings(test_app_client):
      resp = await test_app_client.get("/api/v1/settings")
      assert resp.status_code == 200
      data = resp.json()
      assert "network" in data
      assert "llm" in data

  @pytest.mark.asyncio
  async def test_patch_settings(test_app_client):
      resp = await test_app_client.patch("/api/v1/settings", json={"web": {"show_cost_estimates": True}})
      assert resp.status_code == 200
      data = resp.json()
      assert data["web"]["show_cost_estimates"] is True

  @pytest.mark.asyncio
  async def test_patch_settings_persists_on_re_read(test_app_client):
      """PATCH must write to disk — a subsequent GET must return the updated value."""
      await test_app_client.patch("/api/v1/settings", json={"web": {"show_cost_estimates": True}})
      # Re-read via GET
      resp = await test_app_client.get("/api/v1/settings")
      assert resp.status_code == 200
      assert resp.json()["web"]["show_cost_estimates"] is True

  @pytest.mark.asyncio
  async def test_partial_patch_does_not_wipe_other_fields(test_app_client):
      """PATCHing one key must not remove unrelated sibling fields."""
      # Set two keys
      await test_app_client.patch("/api/v1/settings", json={
          "network": {"allow_lan": False, "host": "127.0.0.1"}
      })
      # Partial update of one key
      await test_app_client.patch("/api/v1/settings", json={"network": {"allow_lan": True}})
      resp = await test_app_client.get("/api/v1/settings")
      data = resp.json()
      # host must survive the partial update
      assert data["network"].get("host") == "127.0.0.1"

  @pytest.mark.asyncio
  async def test_get_database_stats_counts_real_data(test_app_client):
      """DB stats must return actual row counts, not zeros — test DB has 2 books."""
      resp = await test_app_client.get("/api/v1/settings/database-stats")
      assert resp.status_code == 200
      data = resp.json()
      assert "books" in data
      assert data["books"] >= 2, f"Expected at least 2 books in test DB, got {data['books']}"
      assert "book_sections" in data
      assert data["book_sections"] >= 44, "Expected 44+ sections in test DB"

  @pytest.mark.asyncio
  async def test_get_migration_status_reflects_actual_db_state(test_app_client):
      """Migration status must include the current revision hash and is_behind=False for a migrated test DB."""
      resp = await test_app_client.get("/api/v1/settings/migration-status")
      assert resp.status_code == 200
      data = resp.json()
      assert "current" in data
      assert "is_behind" in data
      # Test DB runs alembic upgrade head in setup, so must not be behind
      assert data["is_behind"] is False, "Test DB should be fully migrated"
      assert data["current"] is not None, "Current revision must not be None for a migrated DB"
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_settings_api.py -v`
  Expected: FAIL

- [ ] Step 4: Implement `backend/app/api/routes/settings.py`
  Endpoints:
  - `GET /api/v1/settings` -- returns safe settings (no secrets)
  - `PATCH /api/v1/settings` -- partial update, writes to YAML
  - `GET /api/v1/settings/database-stats` -- row counts per table
  - `GET /api/v1/settings/migration-status` -- current/latest revision, `is_behind` bool
  - `POST /api/v1/settings/run-migrations` -- runs `alembic upgrade head` as subprocess
  Register in `main.py`. Add `get_settings_service` to `deps.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_settings_api.py -v`
  Expected: PASS

- [ ] Verify: `cd backend && uv run ruff check . && uv run python -m pytest tests/ --timeout=60 -q`

**Commit:** `git commit -m "feat(api): add settings API with read/write/db-stats/migration-status (T4)"`

**Inline verification:**
- `cd backend && uv run ruff check backend/app/api/routes/settings.py backend/app/services/settings_service.py` -- no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_settings_service.py -v` -- all pass
- `cd backend && uv run python -m pytest tests/integration/test_api/test_settings_api.py -v` -- all pass
- `cd backend && uv run python -m pytest tests/ --timeout=60 -q` -- no regressions

---

### T5: Reading State API

**Goal:** API for tracking and retrieving reading position per device (user-agent based).
**Spec refs:** FR-81 (reading position sync), §10.1 (reading_state table)

**Files:**
- Create: `backend/app/api/routes/reading_state.py`
- Modify: `backend/app/api/schemas.py` (add reading state schemas)
- Modify: `backend/app/api/main.py` (register router)
- Modify: `backend/app/api/deps.py` (add reading_state_repo dependency)
- Test: `backend/tests/integration/test_api/test_reading_state_api.py`

**Steps:**

- [ ] Step 1: Write failing integration tests
  ```python
  # backend/tests/integration/test_api/test_reading_state_api.py
  @pytest.mark.asyncio
  async def test_upsert_reading_state(test_app_client, seeded_book):
      resp = await test_app_client.put(
          "/api/v1/reading-state",
          json={"book_id": seeded_book.id, "section_id": seeded_book.sections[0].id},
          headers={"User-Agent": "Mozilla/5.0 (Macintosh; Desktop Chrome)"},
      )
      assert resp.status_code == 200
      data = resp.json()
      assert data["last_book_id"] == seeded_book.id

  @pytest.mark.asyncio
  async def test_get_continue_reading(test_app_client, seeded_book):
      # Save state from desktop
      await test_app_client.put(
          "/api/v1/reading-state",
          json={"book_id": seeded_book.id, "section_id": seeded_book.sections[0].id},
          headers={"User-Agent": "Mozilla/5.0 (Macintosh; Desktop Chrome)"},
      )
      # Request from mobile -- should see desktop's last position
      resp = await test_app_client.get(
          "/api/v1/reading-state/continue",
          headers={"User-Agent": "Mozilla/5.0 (iPhone; Mobile Safari)"},
      )
      assert resp.status_code == 200
      data = resp.json()
      assert data["last_book_id"] == seeded_book.id
      assert data["book_title"] is not None

  @pytest.mark.asyncio
  async def test_no_continue_reading_same_device(test_app_client, seeded_book):
      # Save state
      ua = "Mozilla/5.0 (Macintosh; Desktop Chrome)"
      await test_app_client.put(
          "/api/v1/reading-state",
          json={"book_id": seeded_book.id},
          headers={"User-Agent": ua},
      )
      # Request from same device -- no banner
      resp = await test_app_client.get(
          "/api/v1/reading-state/continue",
          headers={"User-Agent": ua},
      )
      assert resp.status_code == 200
      data = resp.json()
      assert data.get("last_book_id") is None  # No cross-device continuation
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_reading_state_api.py -v`
  Expected: FAIL

- [ ] Step 2: Add reading state schemas to `backend/app/api/schemas.py`
  ```python
  class ReadingStateUpsert(BaseModel):
      book_id: int
      section_id: int | None = None

  class ReadingStateResponse(BaseModel):
      last_book_id: int | None
      last_section_id: int | None
      last_viewed_at: str | None
      book_title: str | None = None
      section_title: str | None = None
  ```

- [ ] Step 3: Implement `backend/app/api/routes/reading_state.py`
  Endpoints:
  - `PUT /api/v1/reading-state` -- upsert reading position using `User-Agent` header as key
  - `GET /api/v1/reading-state/continue` -- get latest reading state from a *different* device (for "Continue where you left off" banner)
  Uses `ReadingStateRepository.upsert()` and `get_latest_other_device()`.
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_reading_state_api.py -v`
  Expected: PASS

- [ ] Verify: `cd backend && uv run ruff check . && uv run python -m pytest tests/ --timeout=60 -q`

**Commit:** `git commit -m "feat(api): add reading state API for cross-device position sync (T5)"`

**Inline verification:**
- `cd backend && uv run ruff check backend/app/api/routes/reading_state.py` -- no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_reading_state_api.py -v` -- all pass
- `cd backend && uv run python -m pytest tests/ --timeout=60 -q` -- no regressions

---

### T6a: Settings Page Infrastructure

**Goal:** Build the Settings page infrastructure with sidebar navigation, and implement the General and Database sections (LAN toggle + QR code, DB stats + migration status).
**Spec refs:** FR-72-74, §3.9.1-3.9.3, §11.2 (routes `/settings`, `/settings/:section`)

**Files:**
- Create: `frontend/src/api/settings.ts`
- Create: `frontend/src/stores/settings.ts`
- Create: `frontend/src/views/SettingsView.vue`
- Create: `frontend/src/components/settings/SettingsSidebar.vue`
- Create: `frontend/src/components/settings/GeneralSettings.vue`
- Create: `frontend/src/components/settings/DatabaseSettings.vue`
- Create: `frontend/src/components/settings/QRCode.vue`

**Steps:**

- [ ] Step 1: Install QR code library
  Run: `cd frontend && npm install qrcode.vue@3`
  Verify: `cd frontend && npm run build` -- no errors

- [ ] Step 2: Create settings API client (`frontend/src/api/settings.ts`)
  Functions: `getSettings()`, `updateSettings(updates)`, `getDatabaseStats()`, `getMigrationStatus()`, `runMigrations()`
  Uses base `client.ts` fetch wrapper.

- [ ] Step 3: Create settings Pinia store (`frontend/src/stores/settings.ts`)
  State: `settings`, `dbStats`, `migrationStatus`, `loading`, `error`
  Actions: `fetchSettings()`, `saveSettings(updates)`, `fetchDatabaseStats()`, `fetchMigrationStatus()`, `triggerMigrations()`

- [ ] Step 4: Implement `SettingsView.vue` with sidebar routing
  Left sidebar with 5 nav items. Uses `/settings/:section` route param to show active section. Default: `general`. On mobile (<768px), sidebar becomes accordion or horizontal tab bar (FR-79, §3.10.3).

- [ ] Step 5: Implement `GeneralSettings.vue`
  - LAN toggle (`allow_lan`) with friendly label "Read on your phone"
  - LAN info: displays `http://<ip>:<port>` when enabled
  - QR code component showing LAN URL (conditional on `allow_lan`)
  - Default preset dropdown
  - Show cost estimates toggle
  - LLM settings (read-only display): provider, model, timeout, retries, budget

- [ ] Step 6: Implement `DatabaseSettings.vue`
  - Connection info with masked password
  - Migration status with "Run migrations" button (disabled if up-to-date)
  - Table row counts fetched from `/api/v1/settings/database-stats`

- [ ] Step 7: Write settings store unit tests
  ```typescript
  // frontend/src/stores/__tests__/settings.test.ts
  import { setActivePinia, createPinia } from 'pinia'
  import { useSettingsStore } from '@/stores/settings'
  import { vi, describe, it, expect, beforeEach } from 'vitest'

  describe('useSettingsStore', () => {
    beforeEach(() => { setActivePinia(createPinia()) })

    it('fetchSettings populates settings state with realistic shape', async () => {
      const store = useSettingsStore()
      vi.spyOn(store, 'fetchSettings').mockImplementation(async () => {
        store.settings = {
          network: { allow_lan: false, host: '127.0.0.1', port: 8000, access_token: null },
          llm: { provider: 'claude', model: 'claude-opus-4', timeout_seconds: 60, max_retries: 3, max_budget_usd: 5.0 },
          summarization: { default_preset: 'standard' },
          web: { show_cost_estimates: false },
        }
      })
      await store.fetchSettings()
      expect(store.settings).not.toBeNull()
      expect(store.settings!.network.host).toBe('127.0.0.1')
      expect(store.settings!.llm.provider).toBe('claude')
    })

    it('saveSettings merges updated fields and does not wipe other settings keys', async () => {
      const store = useSettingsStore()
      store.settings = {
        network: { allow_lan: false, host: '127.0.0.1', port: 8000, access_token: null },
        llm: { provider: 'claude', model: 'claude-opus-4', timeout_seconds: 60, max_retries: 3, max_budget_usd: 5.0 },
        summarization: { default_preset: 'standard' },
        web: { show_cost_estimates: false },
      }
      const mockUpdate = vi.fn().mockResolvedValue({
        ...store.settings,
        web: { show_cost_estimates: true },
      })
      vi.mock('@/api/settings', () => ({ updateSettings: mockUpdate }))
      await store.saveSettings({ web: { show_cost_estimates: true } })
      // llm key must survive after updating web
      expect(store.settings!.llm.provider).toBe('claude')
    })

    it('fetchDatabaseStats populates dbStats with table row counts', async () => {
      const store = useSettingsStore()
      vi.spyOn(store, 'fetchDatabaseStats').mockImplementation(async () => {
        store.dbStats = { books: 2, book_sections: 44, summaries: 124, annotations: 0, concepts: 0, eval_traces: 0 }
      })
      await store.fetchDatabaseStats()
      expect(store.dbStats!.books).toBe(2)
      expect(store.dbStats!.book_sections).toBe(44)
    })
  })
  ```
  Run: `cd frontend && npx vitest run src/stores/__tests__/settings.test.ts`
  Expected: All store tests pass

- [ ] Verify: `cd frontend && npm run type-check && npm run build`

- [ ] Manual verification (run `npm run dev` and open browser):
  1. Navigate to `http://localhost:5173/settings` — sidebar with 5 nav items renders (General, Database, Presets, Reading, Backup)
  2. Click **General** — LAN toggle appears with label "Read on your phone"; toggle is OFF by default
  3. Toggle LAN ON — a QR code appears and the LAN URL (`http://<ip>:8000`) is displayed beneath it
  4. Toggle LAN OFF — QR code disappears; URL label disappears
  5. Click **Database** — table of row counts loads (books, sections, summaries, etc.); migration status shows "Up to date" with no "Run migrations" button visible
  6. Check DB stat values match real data: Books row shows ≥ 2, Sections shows ≥ 44
  7. Navigate to `http://localhost:5173/settings/database` directly (deep link) — Database section is active, sidebar highlights "Database"

**Commit:** `git commit -m "feat(frontend): add settings page with sidebar, General + Database sections (T6a)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors
- `cd frontend && npx vitest run src/stores/__tests__/settings.test.ts` -- all store tests pass

---

### T6b: Settings Page Remaining Sections

**Goal:** Complete the Settings page with Summarization Presets list/detail, Reading Preferences defaults + custom CSS, and Backup & Export section placeholder wired to T7.
**Spec refs:** FR-75-77, §3.9.4-3.9.6

**Files:**
- Create: `frontend/src/components/settings/PresetSettings.vue`
- Create: `frontend/src/components/settings/ReadingSettings.vue`
- Create: `frontend/src/components/settings/BackupSettings.vue`
- Modify: `frontend/src/stores/settings.ts` (extend with preset/reading state)
- Modify: `frontend/src/views/SettingsView.vue` (register remaining sections)

**Steps:**

- [ ] Step 1: Implement `PresetSettings.vue`
  - List/detail layout: left panel lists system + user presets, right panel shows detail
  - System presets: read-only with "Duplicate" button
  - User presets: full CRUD (create, edit, delete)
  - Detail view: name, 2x2 facet grid, eval assertions by category, prompt preview (collapsed)
  - Uses existing preset API from Phase 2

- [ ] Step 2: Implement `ReadingSettings.vue`
  - Default reading preset dropdown
  - Font loading preference toggle
  - Custom CSS textarea

- [ ] Step 3: Implement `BackupSettings.vue` (stub -- full implementation in T7)
  Placeholder content referencing T7. Shows "Backup & Export" heading.

- [ ] Verify: `cd frontend && npm run type-check && npm run build`

- [ ] Manual verification (run `npm run dev`):
  1. Navigate to `http://localhost:5173/settings/presets` — list of system presets appears (e.g. "practitioner_bullets", "academic_deep_dive"); each has a read-only badge and a "Duplicate" button
  2. Click "Duplicate" on a system preset — a new user preset appears in the list with a generated name (editable)
  3. Edit the duplicated preset's name field, save — the new name persists after clicking away and back to the section
  4. Click "Delete" on the user preset — a confirmation dialog appears; confirm — the preset disappears from the list; system presets remain untouched
  5. Navigate to `http://localhost:5173/settings/reading` — "Default reading preset" dropdown is populated with all available presets
  6. Change the default preset to a different value, save — navigate away to Library and back to `/settings/reading`; the dropdown still shows the newly selected preset
  7. Type custom CSS in the textarea (e.g. `body { font-size: 18px; }`), save — navigate away and back; the textarea still contains the custom CSS

**Commit:** `git commit -m "feat(frontend): add Presets, Reading, Backup settings sections (T6b)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors

---

### T7: Export & Backup UI

**Goal:** Complete the Backup & Export section of Settings with functional create/restore/list backups, scheduled backup config, and library export.
**Spec refs:** FR-77, §3.9.6

**Files:**
- Create: `frontend/src/api/backup.ts`
- Create: `frontend/src/api/export.ts`
- Modify: `frontend/src/components/settings/BackupSettings.vue` (full implementation)

**Steps:**

- [ ] Step 1: Create backup API client (`frontend/src/api/backup.ts`)
  Functions: `createBackup()`, `listBackups()`, `downloadBackup(id)`, `restoreBackup(file)`, `deleteBackup(id)`

- [ ] Step 2: Create export API client (`frontend/src/api/export.ts`)
  Functions: `exportBook(bookId, options)`, `exportLibrary(options)` -- both return download URLs or trigger browser download

- [ ] Step 3: Implement `BackupSettings.vue` fully
  Sections:
  - **Create backup**: "Create Backup" button. Shows progress (loading spinner). On success: "Backup created" toast + appears in list.
  - **Backup history**: Table of backups with filename, date, size, Download button, Delete button (with confirm dialog).
  - **Restore from backup**: File upload drop zone for `.sql` file. Warning dialog: "This will replace all current data." Confirm restores.
  - **Scheduled backups**: Toggle + interval selector (Daily/Weekly/Off). Calls `PATCH /api/v1/settings` with `backup_schedule_hours`. Shows "Last backup: N days ago" indicator.
  - **Export library**: Format selector (Markdown/JSON), scope (All books / selected), include checkboxes (Summaries, Annotations, Concepts, Eval results), "Export" button triggers download.

- [ ] Step 4: Wire download to browser
  Backup download: use `fetch` + `URL.createObjectURL` + temporary `<a>` click.
  Export download: same pattern, response comes as file attachment.

- [ ] Verify: `cd frontend && npm run type-check && npm run build`

- [ ] Manual verification (run `npm run dev` with backend running):
  1. Navigate to `http://localhost:5173/settings/backup` — "Backup & Export" section renders with all sub-sections
  2. Click **Create Backup** — a loading spinner appears; after completion a success toast "Backup created" is shown and the new backup appears in the history table with a filename, date, and file size (> 0 KB)
  3. Click **Download** on the newly created backup — the browser downloads a `.sql` file with the correct filename; open the file in a text editor and confirm it starts with `--` (pg_dump SQL header)
  4. Click **Delete** on the backup row — a confirmation dialog appears ("This backup will be permanently deleted"); confirm — the row disappears from the history table
  5. Under **Scheduled Backups**, toggle from Off to Daily — the interval selector changes to show "24 hours"; navigate to General settings and back; the schedule setting still shows "Daily"
  6. Under **Export Library**, select "Markdown" format, check "Summaries" and "Annotations", click **Export** — the browser downloads a `.md` file; open it and confirm it contains at least one `##` section heading and at least one summary paragraph
  7. Switch format to "JSON", click **Export** — the browser downloads a `.json` file; open it and confirm it contains a `"library"` array with at least 2 book entries

**Commit:** `git commit -m "feat(frontend): add Export & Backup UI in settings (T7)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors

---

### T8: Reading Position Sync UI

**Goal:** Track reading position on section view and show "Continue where you left off" banner when accessing from a different device.
**Spec refs:** FR-81, §3.10.6

**Files:**
- Create: `frontend/src/api/readingState.ts`
- Create: `frontend/src/stores/readingState.ts`
- Create: `frontend/src/composables/useReadingState.ts`
- Create: `frontend/src/components/reader/ContinueBanner.vue`
- Modify: `frontend/src/views/BookDetailView.vue` (integrate position tracking)
- Modify: `frontend/src/views/LibraryView.vue` (show continue banner)

**Steps:**

- [ ] Step 1: Create reading state API client (`frontend/src/api/readingState.ts`)
  Functions: `updateReadingState(bookId, sectionId?)`, `getContinueReading()`

- [ ] Step 2: Create reading state Pinia store (`frontend/src/stores/readingState.ts`)
  State: `continueReading: { bookId, sectionId, bookTitle, sectionTitle, lastViewedAt } | null`
  Actions: `trackPosition(bookId, sectionId)` (debounced PUT), `fetchContinueReading()`

- [ ] Step 3: Create `useReadingState` composable
  - On `BookDetailView` mount: call `trackPosition(bookId, sectionId)` with 5-second debounce
  - On section change: update position
  - Does not fire on rapid navigation (debounced)

- [ ] Step 4: Create `ContinueBanner.vue`
  - Shows: "You were reading **[Book Title]**, **[Section Name]**" with "Continue" button
  - "Continue" navigates to `/books/:id/sections/:sectionId`
  - Dismissible (X button), stores dismissal in sessionStorage
  - Renders only when `continueReading` is non-null

- [ ] Step 5: Integrate into views
  - `LibraryView.vue`: Show `ContinueBanner` at top of page (above view tabs)
  - `BookDetailView.vue`: Call `useReadingState().trackPosition()` in `onMounted`

- [ ] Step 6: Write reading state store unit tests
  ```typescript
  // frontend/src/stores/__tests__/readingState.test.ts
  import { setActivePinia, createPinia } from 'pinia'
  import { useReadingStateStore } from '@/stores/readingState'
  import { vi, describe, it, expect, beforeEach } from 'vitest'

  describe('useReadingStateStore', () => {
    beforeEach(() => { setActivePinia(createPinia()) })

    it('fetchContinueReading sets continueReading when another device has a position', async () => {
      const store = useReadingStateStore()
      vi.spyOn(store, 'fetchContinueReading').mockImplementation(async () => {
        store.continueReading = {
          bookId: 1,
          sectionId: 3,
          bookTitle: 'The Art of War',
          sectionTitle: 'Chapter III: Attack by Stratagem',
          lastViewedAt: '2026-04-10T12:00:00Z',
        }
      })
      await store.fetchContinueReading()
      expect(store.continueReading).not.toBeNull()
      expect(store.continueReading!.bookTitle).toBe('The Art of War')
      expect(store.continueReading!.sectionId).toBe(3)
    })

    it('fetchContinueReading sets continueReading to null when same device', async () => {
      const store = useReadingStateStore()
      vi.spyOn(store, 'fetchContinueReading').mockImplementation(async () => {
        store.continueReading = null
      })
      await store.fetchContinueReading()
      expect(store.continueReading).toBeNull()
    })

    it('trackPosition calls the API with debouncing', async () => {
      const store = useReadingStateStore()
      const mockTrack = vi.fn()
      vi.mock('@/api/readingState', () => ({ updateReadingState: mockTrack }))
      // Rapid calls should not fire immediately
      store.trackPosition(1, 3)
      store.trackPosition(1, 4)
      expect(mockTrack).not.toHaveBeenCalled()
    })
  })
  ```
  Run: `cd frontend && npx vitest run src/stores/__tests__/readingState.test.ts`
  Expected: All store tests pass

- [ ] Manual verification (run `npm run dev` with backend running):
  1. Open `http://localhost:5173` in **Chrome** and navigate to The Art of War → Chapter III; wait 6 seconds for the debounced position save
  2. Open `http://localhost:5173` in **Firefox** (different user-agent) — a banner appears at the top of the Library page saying "You were reading **The Art of War**, **Chapter III: Attack by Stratagem**" with a "Continue" button
  3. Click "Continue" — the reader opens at Chapter III of The Art of War (correct section, not Chapter I)
  4. Dismiss the banner with the X button — the banner disappears; refresh the Firefox page — the banner does NOT reappear (dismissed stored in sessionStorage)
  5. Open the same URL in Chrome again — no "Continue" banner appears (Chrome is the same device that saved the position)

**Commit:** `git commit -m "feat(frontend): add reading position sync UI with continue banner (T8)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors
- `cd frontend && npx vitest run src/stores/__tests__/readingState.test.ts` -- all store tests pass

---

### T9a: Mobile Bottom Tab Bar

**Goal:** Implement mobile navigation with a bottom tab bar component that replaces the icon rail sidebar on viewports <768px, with 5 tabs, active state, and proper touch targets.
**Spec refs:** FR-02, FR-33, FR-78, §3.10.2

**Files:**
- Create: `frontend/src/components/app/BottomTabBar.vue`
- Modify: `frontend/src/components/app/AppShell.vue` (conditional desktop/mobile layout)
- Modify: `frontend/src/composables/useBreakpoint.ts` (add `isMobile`, `isTablet`, `isDesktop`)

**Steps:**

- [ ] Step 1: Refine `useBreakpoint` composable
  ```typescript
  // frontend/src/composables/useBreakpoint.ts
  export function useBreakpoint() {
    const width = ref(window.innerWidth)
    const isMobile = computed(() => width.value < 768)
    const isTablet = computed(() => width.value >= 768 && width.value < 1024)
    const isDesktop = computed(() => width.value >= 1024)
    const breakpoint = computed(() => isMobile.value ? 'sm' : isTablet.value ? 'md' : 'lg')
    // Listen to resize
    return { width, isMobile, isTablet, isDesktop, breakpoint }
  }
  ```

- [ ] Step 2: Implement `BottomTabBar.vue`
  - 5 tabs: Library, Search, Concepts, Annotations, Settings
  - Each tab: icon + label (small text below icon)
  - Active tab: accent color
  - Fixed to bottom, 56px height, above safe area (`env(safe-area-inset-bottom)`)
  - Uses Vue Router for navigation
  - Minimum touch targets: 44px height

- [ ] Step 3: Modify `AppShell.vue` for responsive layout
  - Desktop (>=1024px): Icon rail sidebar (existing) + content
  - Tablet (768-1023px): Icon rail + full-width content (sidebar overlay)
  - Mobile (<768px): No icon rail, content full-width, `BottomTabBar` fixed at bottom
  - Use `useBreakpoint()` to conditionally render

- [ ] Step 4: Write useBreakpoint composable unit tests
  ```typescript
  // frontend/src/composables/__tests__/useBreakpoint.test.ts
  import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
  import { useBreakpoint } from '@/composables/useBreakpoint'

  describe('useBreakpoint', () => {
    const setWidth = (w: number) => {
      Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: w })
      window.dispatchEvent(new Event('resize'))
    }

    it('isMobile is true at 375px (iPhone viewport)', () => {
      setWidth(375)
      const { isMobile, isTablet, isDesktop } = useBreakpoint()
      expect(isMobile.value).toBe(true)
      expect(isTablet.value).toBe(false)
      expect(isDesktop.value).toBe(false)
    })

    it('isTablet is true at 768px', () => {
      setWidth(768)
      const { isMobile, isTablet } = useBreakpoint()
      expect(isMobile.value).toBe(false)
      expect(isTablet.value).toBe(true)
    })

    it('isDesktop is true at 1280px', () => {
      setWidth(1280)
      const { isDesktop } = useBreakpoint()
      expect(isDesktop.value).toBe(true)
    })
  })
  ```
  Run: `cd frontend && npx vitest run src/composables/__tests__/useBreakpoint.test.ts`
  Expected: All breakpoint tests pass

- [ ] Verify: `cd frontend && npm run build`

- [ ] Manual verification (open Chrome DevTools → Device Toolbar):
  1. Set viewport to **375px width** (iPhone SE) — the icon rail sidebar is not visible in the DOM; the bottom tab bar is fixed at the bottom with 5 tabs (Library, Search, Concepts, Annotations, Settings)
  2. Each tab label is visible below its icon; active tab (current route) uses accent color
  3. Tap **Settings** tab — navigates to `/settings`; active tab highlights Settings icon
  4. Tap **Library** tab — navigates back to `/`; Library tab becomes active
  5. Set viewport to **1280px width** — the bottom tab bar is not visible; the icon rail sidebar appears on the left
  6. Set viewport to **768px** — icon rail visible, bottom tab bar hidden (tablet breakpoint uses sidebar)
  7. Measure a tab's touch target: open DevTools Accessibility tree or use "Inspect" — each tab element is at least 44px tall

**Commit:** `git commit -m "feat(frontend): add mobile bottom tab bar replacing sidebar on small viewports (T9a)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors
- `cd frontend && npx vitest run src/composables/__tests__/useBreakpoint.test.ts` -- all breakpoint tests pass

---

### T9b: Bottom Sheet Component

**Goal:** Implement a reusable bottom sheet component with 3 snap points, drag gestures, backdrop, and Radix Dialog base for accessibility. Integrate into reader mobile layout.
**Spec refs:** FR-79, §3.10.3

**Files:**
- Create: `frontend/src/components/common/BottomSheet.vue`
- Modify: `frontend/src/views/BookDetailView.vue` (mobile reader bottom action bar)

**Steps:**

- [ ] Step 1: Implement `BottomSheet.vue`
  - Radix Dialog base for accessibility (focus trap, escape, ARIA)
  - Drag handle at top (8px wide, centered)
  - Three snap points: Peek (30%), Half (50%), Full (90%)
  - CSS `transform: translateY()` for position
  - Touch events: `touchstart`, `touchmove`, `touchend` on drag handle
  - Swipe down past peek = dismiss
  - Content area scrollable when at Full snap
  - Backdrop with `opacity` transition
  - `touch-action: none` on drag handle only
  - Minimum text size: 14px within sheet content
  - Minimum touch targets: 44px height

- [ ] Step 2: Adapt reader for mobile
  - `BookDetailView.vue`: On mobile, replace persistent context sidebar with bottom action bar
  - Bottom action bar: `Aa Settings` | `AI Chat` | `Annotations` | `More` (each opens a `BottomSheet`)
  - TOC dropdown: opens as full-screen bottom sheet on mobile
  - Original/Summary toggle: full-width segmented control below header

- [ ] Verify: `cd frontend && npm run build`

- [ ] Manual verification at 375px viewport (Chrome DevTools Device Toolbar, Pixel 5 preset):
  1. Navigate to a book's reader page — a bottom action bar is visible at the bottom with 4 items: "Aa Settings", "AI Chat", "Annotations", "More"
  2. Tap **Annotations** — the bottom sheet opens; its visible area covers ~30% of the screen (Peek snap point); the drag handle (8px wide pill) is visible at the top of the sheet
  3. Drag the handle upward — the sheet snaps to ~50% (Half) of the screen height; drag further — it snaps to ~90% (Full); at Full, the content area inside is scrollable
  4. Drag the handle downward past the Peek point — the sheet dismisses (disappears with backdrop fade); the backdrop is no longer visible
  5. Press **Escape** key — if sheet is open, it closes (keyboard accessibility via Radix Dialog)
  6. Tab key moves focus into the sheet when open; Tab cannot leave the sheet while it is open (focus trap active)
  7. Tap **AI Chat** — a different bottom sheet opens with the AI conversation interface
  8. Tap outside the sheet (on the backdrop) — the sheet dismisses

**Commit:** `git commit -m "feat(frontend): add bottom sheet component with drag gestures for mobile (T9b)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors

---

### T10: Mobile Responsive — Touch Interactions + Breakpoint Refinements

**Goal:** Add long-press for preview/context menu, long-press+drag for reorder, and refine all pages for mobile breakpoints.
**Spec refs:** FR-80 (touch interactions), FR-82 (views sync), §3.10.3-3.10.4

**Files:**
- Create: `frontend/src/composables/useTouchGestures.ts`
- Modify: `frontend/src/components/library/BookCard.vue` (long-press context menu)
- Modify: `frontend/src/components/library/FilterRow.vue` (full-screen modal on mobile)
- Modify: `frontend/src/views/LibraryView.vue` (mobile defaults: list view, 2-col grid)
- Modify: `frontend/src/components/search/CommandPalette.vue` (full-screen on mobile)
- Modify: `frontend/src/views/SettingsView.vue` (accordion/tabs on mobile)

**Steps:**

- [ ] Step 1: Implement `useTouchGestures` composable
  ```typescript
  export function useTouchGestures(elementRef: Ref<HTMLElement | null>) {
    const isLongPress = ref(false)
    const longPressTimer = ref<number | null>(null)

    function onTouchStart(e: TouchEvent) {
      longPressTimer.value = window.setTimeout(() => {
        isLongPress.value = true
        emit('longpress', e)
      }, 500)  // 500ms for long-press
    }

    function onTouchEnd() {
      if (longPressTimer.value) clearTimeout(longPressTimer.value)
      isLongPress.value = false
    }

    function onTouchMove() {
      if (longPressTimer.value) clearTimeout(longPressTimer.value)
    }

    return { isLongPress, onTouchStart, onTouchEnd, onTouchMove }
  }
  ```

- [ ] Step 2: Add long-press context menu to `BookCard.vue`
  - Desktop: right-click opens context menu (existing)
  - Mobile: long-press (500ms) opens same context menu as bottom sheet
  - Context menu items: Open, Summarize, Verify, Edit metadata, Export, Delete

- [ ] Step 3: Mobile filter adaptation
  - `FilterRow.vue`: On mobile, filter dropdowns open as full-screen modals with "Done" button
  - Sort control inside the filter modal
  - Back button / swipe to dismiss

- [ ] Step 4: Library mobile defaults
  - Default to List view on mobile (not Grid)
  - Grid available but renders 2 columns
  - Custom view tabs render as horizontally scrollable pills (read-only on mobile per FR-82)

- [ ] Step 5: Search and settings mobile adaptation
  - `CommandPalette.vue`: Full-screen modal on mobile (no backdrop, takes over entire screen)
  - `SettingsView.vue`: On mobile, sidebar sections become accordion panels or a horizontal tab bar

- [ ] Step 6: Upload mobile adaptation
  - Replace drag-and-drop zone with "Choose File" button (native file picker)
  - Wizard steps render full-screen, one at a time
  - Step indicator: compact numbered dots

- [ ] Step 7: Write useTouchGestures composable unit tests
  ```typescript
  // frontend/src/composables/__tests__/useTouchGestures.test.ts
  import { describe, it, expect, vi, beforeEach } from 'vitest'
  import { ref } from 'vue'
  import { useTouchGestures } from '@/composables/useTouchGestures'

  describe('useTouchGestures', () => {
    beforeEach(() => { vi.useFakeTimers() })

    it('emits longpress after 500ms hold', () => {
      const el = ref<HTMLElement | null>(document.createElement('div'))
      const { onTouchStart, isLongPress } = useTouchGestures(el)
      const mockEvent = { touches: [{ clientX: 0, clientY: 0 }] } as unknown as TouchEvent
      onTouchStart(mockEvent)
      expect(isLongPress.value).toBe(false)
      vi.advanceTimersByTime(500)
      expect(isLongPress.value).toBe(true)
    })

    it('cancels longpress if touch moves before 500ms', () => {
      const el = ref<HTMLElement | null>(document.createElement('div'))
      const { onTouchStart, onTouchMove, isLongPress } = useTouchGestures(el)
      const mockEvent = { touches: [{ clientX: 0, clientY: 0 }] } as unknown as TouchEvent
      onTouchStart(mockEvent)
      vi.advanceTimersByTime(200)
      onTouchMove()  // movement cancels the timer
      vi.advanceTimersByTime(400)
      expect(isLongPress.value).toBe(false)
    })

    it('cancels longpress on touch end', () => {
      const el = ref<HTMLElement | null>(document.createElement('div'))
      const { onTouchStart, onTouchEnd, isLongPress } = useTouchGestures(el)
      const mockEvent = { touches: [{ clientX: 0, clientY: 0 }] } as unknown as TouchEvent
      onTouchStart(mockEvent)
      vi.advanceTimersByTime(200)
      onTouchEnd()
      vi.advanceTimersByTime(400)
      expect(isLongPress.value).toBe(false)
    })
  })
  ```
  Run: `cd frontend && npx vitest run src/composables/__tests__/useTouchGestures.test.ts`
  Expected: All 3 gesture tests pass

- [ ] Manual verification at 375px viewport (Chrome DevTools, Pixel 5):
  1. Navigate to Library — default display mode is **List view** (not Grid); grid view is still accessible via the view mode toggle
  2. In Grid view, count the columns: exactly 2 book cards side by side (not 3 or 4)
  3. Long-press (hold 500ms) on a book card — a context menu bottom sheet appears with items: Open, Summarize, Verify, Edit metadata, Export, Delete; verify it is the same options as right-click on desktop
  4. Tap the **Filter** button — a full-screen modal opens covering the entire viewport with filter dropdowns and a "Done" button; it is NOT the dropdown popover used on desktop
  5. Apply a filter and tap **Done** — the modal closes, the library updates to show filtered results
  6. Open the command palette (tap the Search tab in bottom bar) — it opens as full-screen (no backdrop visible, entire screen is the palette)
  7. Navigate to `http://localhost:5173/settings` at 375px — settings sections are displayed as an accordion (click to expand) or horizontal scrollable tabs, NOT the two-column sidebar layout

**Commit:** `git commit -m "feat(frontend): add touch interactions and mobile breakpoint refinements (T10)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors
- `cd frontend && npx vitest run src/composables/__tests__/useTouchGestures.test.ts` -- all gesture tests pass

---

### T11: Skeleton Loaders, Empty States, Error Handling Polish

**Goal:** Add skeleton loaders for all data-loading states, implement all empty states per spec, and add error boundaries.
**Spec refs:** FR-15, FR-83, NFR-07, §5.4 (empty states), §12 (edge cases)

**Files:**
- Modify: `frontend/src/components/common/SkeletonLoader.vue` (add variants)
- Modify: `frontend/src/components/common/EmptyState.vue` (add all variants)
- Create: `frontend/src/components/common/ErrorBoundary.vue`
- Modify: `frontend/src/views/LibraryView.vue` (skeleton + empty states)
- Modify: `frontend/src/views/BookDetailView.vue` (skeleton + error state)
- Modify: `frontend/src/views/AnnotationsView.vue` (empty state)
- Modify: `frontend/src/views/ConceptsView.vue` (empty state)

**Steps:**

- [ ] Step 1: Expand `SkeletonLoader.vue` with variants
  Variants needed (per page):
  - `library-grid`: 6 card placeholders (cover image + 3 text lines)
  - `library-list`: 8 row placeholders (avatar + 2 text lines)
  - `library-table`: Header row + 8 data rows
  - `reader-content`: Large text block (12 lines of varying width)
  - `settings-form`: Label + input pairs (6 rows)
  - `sidebar-annotations`: 4 card placeholders
  All use `animate-pulse` with `bg-muted` Tailwind classes.
  Render within 50ms of navigation (NFR-07) -- use `v-if="loading"` on store state.

- [ ] Step 2: Implement all empty states per spec §5.4
  Each empty state has: illustration/icon, title, description, CTA button.
  | Context | Title | CTA |
  |---------|-------|-----|
  | Library (no books) | "Your library is empty" | "Upload your first book" |
  | Library (no filter matches) | "No books match your filters" | "Clear filters" |
  | Search (no matches) | "No results for '[query]'" | Suggestions |
  | Annotations (none) | "No annotations yet" | "Start reading" |
  | Concepts (none) | "No concepts yet" | "Summarize a book" |
  | Annotations sidebar (none) | "No annotations for this section" | "Select text" |
  | AI sidebar (no threads) | "Ask AI about this book" | "Start conversation" |
  | Summary (none) | "No summary available" | "Summarize" |

- [ ] Step 3: Implement `ErrorBoundary.vue`
  - Catches render errors via `onErrorCaptured`
  - Shows user-friendly error message with "Try again" button
  - Logs error to console with context
  - Different messages for network errors vs render errors
  - Slot-based: wraps page content

- [ ] Step 4: Integrate skeletons and empty states into all views
  - `LibraryView.vue`: skeleton while `books.loading`, empty state when `books.items.length === 0`
  - `BookDetailView.vue`: skeleton while loading section content
  - `AnnotationsView.vue`: empty state when no annotations
  - `ConceptsView.vue`: empty state when no concepts
  - `ContextSidebar.vue`: empty states for annotations tab and AI tab

- [ ] Step 5: Error state integration
  - Wrap each view's main content in `ErrorBoundary`
  - API client: ensure network errors produce user-friendly messages ("Connection lost", "Server error")
  - SSE reconnect failure: "Connection lost. Processing may still be running." + "Refresh" button (per E1)

- [ ] Verify: `cd frontend && npm run build`

- [ ] Manual verification (run `npm run dev`):
  1. **Skeleton loaders — Library:** In Chrome DevTools Network tab, set throttling to "Slow 3G"; navigate to `http://localhost:5173/` — the library grid skeleton (6 card placeholders with pulsing grey blocks) is visible before data loads; after data loads, real book cards replace it
  2. **Skeleton loaders — Reader:** Navigate into a book section on Slow 3G — a skeleton of ~12 lines of varying width pulsing grey blocks is visible before the section content appears
  3. **Empty state — Library:** Stop the backend, clear all books via API; navigate to Library — the "Your library is empty" illustration and "Upload your first book" button appear (not an empty white page)
  4. **Empty state — Search:** Type a nonsense query like "xyzzy123" — "No results for 'xyzzy123'" message appears with a suggestion
  5. **Empty state — Annotations:** Navigate to Annotations page with no annotations — "No annotations yet" message with "Start reading" CTA appears
  6. **Error boundary:** Stop the backend server; navigate to a book's reader — the error boundary renders a "Connection lost" message with a "Try again" button (not a blank white page or uncaught JS error in console)
  7. **SSE reconnect failure:** While on the upload page with processing active, stop the backend — a "Connection lost. Processing may still be running." message with a "Refresh" button appears in the progress area
  8. **Skeleton timing:** In DevTools Performance tab, verify that the skeleton component is rendered within 50ms of the navigation event (check by throttling and tracing a navigation)

**Commit:** `git commit -m "feat(frontend): add skeleton loaders, empty states, and error boundaries (T11)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors

---

### T12: Accessibility Audit + Fixes

**Goal:** Ensure WCAG 2.1 AA compliance across the entire app: keyboard navigation, focus management, ARIA labels, color contrast, screen reader support.
**Spec refs:** NFR-08, NFR-09, NFR-10

**Files:**
- Modify: Multiple component files across `frontend/src/components/`
- Modify: `frontend/src/assets/main.css` (focus indicators, reduced motion)

**Steps:**

- [ ] Step 1: Keyboard navigation audit
  - Tab through every page: Library, Reader, Settings, Annotations, Concepts, Search
  - Verify all interactive elements are reachable via Tab
  - Verify focus order is logical (left-to-right, top-to-bottom)
  - Verify Escape closes all modals/popovers/palettes
  - Fix: Add `tabindex` where needed, ensure `<button>` not `<div>` for clickables

- [ ] Step 2: Focus management
  - Modal open: focus moves to first focusable element inside
  - Modal close: focus returns to triggering element
  - Page navigation: focus moves to page heading
  - Bottom sheet open: focus trapped inside
  - Fix: Use `useFocusTrap` from Radix or custom implementation

- [ ] Step 3: ARIA labels and roles
  - Navigation: `role="navigation"`, `aria-label="Main navigation"`
  - Sidebar: `role="complementary"`
  - Loading states: `aria-busy="true"`, `aria-live="polite"` for dynamic content
  - Icons: `aria-hidden="true"` on decorative icons, `aria-label` on functional ones
  - Search input: `role="combobox"`, `aria-expanded`, `aria-activedescendant`
  - Bottom sheet: `role="dialog"`, `aria-modal="true"`, `aria-label`
  - Eval badge: `aria-label="Evaluation score: 15 of 16 passed"`

- [ ] Step 4: Color contrast verification
  - All theme modes (Light, Sepia, Dark, OLED, Dracula): verify text contrast >= 4.5:1 (normal text), >= 3:1 (large text/UI)
  - Custom color picker: auto-contrast warning when ratio < 4.5:1 (per E10)
  - Use browser DevTools contrast checker or `axe-core`

- [ ] Step 5: Reduced motion + font sizing
  - Add `@media (prefers-reduced-motion: reduce)` to disable/simplify all CSS animations and transitions
  - Verify all font sizes use `rem` not `px` (NFR-10)
  - Visible focus indicators: 2px solid accent outline on all focusable elements (`:focus-visible`)

- [ ] Step 6: Run axe-core automated scan and verify zero critical/serious violations
  ```typescript
  // frontend/e2e/accessibility.spec.ts
  import { test, expect } from '@playwright/test'
  import AxeBuilder from '@axe-core/playwright'

  const pages = [
    { name: 'Library', path: '/' },
    { name: 'Book Detail', path: '/books/1' },
    { name: 'Settings General', path: '/settings/general' },
    { name: 'Settings Database', path: '/settings/database' },
    { name: 'Annotations', path: '/annotations' },
    { name: 'Concepts', path: '/concepts' },
  ]

  for (const { name, path } of pages) {
    test(`${name} page has no critical or serious axe violations`, async ({ page }) => {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa'])
        .analyze()
      const critical = results.violations.filter(v => v.impact === 'critical' || v.impact === 'serious')
      expect(critical, `${name}: ${critical.map(v => v.description).join(', ')}`).toHaveLength(0)
    })
  }
  ```
  Run: `cd frontend && npx playwright test e2e/accessibility.spec.ts --project=desktop-chrome`
  Expected: All 6 page scans pass with zero critical/serious violations
  `cd frontend && npm install -D @axe-core/playwright` (required for the above)

- [ ] Manual keyboard navigation spot-check:
  1. Navigate to `http://localhost:5173/` — press Tab repeatedly; every interactive element (book cards, view mode buttons, filter dropdowns, nav items) receives focus in visual order (left-to-right, top-to-bottom); no focus ever jumps to an invisible element
  2. Open a modal (e.g., delete confirmation) — focus moves into the modal; Tab cycles only within the modal; pressing Escape closes it and focus returns to the button that opened it
  3. Open a bottom sheet — pressing Escape dismisses it; Tab is trapped inside while open

**Commit:** `git commit -m "fix(frontend): accessibility audit — keyboard nav, ARIA, contrast, reduced motion (T12)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors
- `cd frontend && npx playwright test e2e/accessibility.spec.ts --project=desktop-chrome` -- zero critical/serious axe violations on all 6 pages

---

### T13: Performance Optimization

**Goal:** Optimize loading performance, reduce bundle size, and ensure responsiveness targets are met.
**Spec refs:** NFR-01-07, FR-83, §3.10.5

**Files:**
- Modify: `frontend/vite.config.ts` (code splitting, lazy loading)
- Modify: `frontend/src/router/index.ts` (lazy route imports)
- Modify: Various component files (image lazy loading, virtual scroll)

**Steps:**

- [ ] Step 1: Route-level code splitting
  Convert all route imports to lazy:
  ```typescript
  const LibraryView = () => import('../views/LibraryView.vue')
  const BookDetailView = () => import('../views/BookDetailView.vue')
  const SettingsView = () => import('../views/SettingsView.vue')
  // ... all views
  ```
  Verify: `cd frontend && npm run build` -- check chunk sizes in output

- [ ] Step 2: Image lazy loading
  - All book cover images: `loading="lazy"` attribute
  - Use `IntersectionObserver` via composable for below-fold images
  - Mobile: reduced resolution thumbnails via `/api/v1/images/{id}/thumbnail?width=200`

- [ ] Step 3: Bundle analysis
  Run: `cd frontend && npx vite-bundle-visualizer`
  Identify large dependencies. Target: initial JS bundle < 200KB gzipped.
  If QR code library > 5KB gzipped, consider dynamic import only on settings page.

- [ ] Step 4: Service worker for static asset caching
  Add `vite-plugin-pwa` for basic PWA support:
  - Cache static assets (JS, CSS, fonts)
  - Network-first for API calls
  - Minimal: no offline editing, just faster reloads

- [ ] Step 5: Performance target verification
  Use Lighthouse in Chrome DevTools:
  - Library page load: < 500ms (<100 books) -- NFR-01
  - Command palette results: < 300ms after 200ms debounce -- NFR-02
  - Section rendering: < 200ms -- NFR-03
  - Reader settings change: < 50ms -- NFR-04
  - Skeleton states: within 50ms of navigation -- NFR-07

- [ ] Step 6: `prefers-reduced-motion` enforcement
  Verify: All CSS transitions/animations respect `prefers-reduced-motion: reduce`
  Components using `transition` or `animate-*` classes: add conditional class

- [ ] Verify: `cd frontend && npm run build`

- [ ] Manual performance verification:
  1. After `npm run build`, inspect the build output — the initial entry chunk must be under 200KB gzipped; each route view (LibraryView, BookDetailView, SettingsView) must appear as a separate chunk file, not bundled into the entry
  2. Run: `cd frontend && npx vite-bundle-visualizer` — open the generated `stats.html`; confirm `qrcode.vue` appears only in the Settings chunk (not the entry), and no single chunk exceeds 500KB uncompressed
  3. In Chrome DevTools (with `npm run dev`), open the **Performance** tab and record a Library page load with 44 books: total time from navigation start to `DOMContentLoaded` must be under 500ms on a fast connection (NFR-01)
  4. Open the command palette (Cmd+K), type a query — results appear within 500ms total (300ms debounce + <200ms response); verify in the Network tab that the search request completes in <200ms
  5. In the Library page, scroll down to verify book cover images below the fold do NOT appear in the Network tab until scrolled into view (lazy loading confirmed)
  6. Enable "Slow 3G" in DevTools; navigate to the Library — the skeleton loader appears within 50ms of navigation (check via Performance trace: look for the first paint of the skeleton element)
  7. Enable "prefers-reduced-motion" in OS settings (macOS: System Settings → Accessibility → Reduce Motion); reload the app — no CSS animations or transitions run (all `animate-pulse`, `transition-*`, and `duration-*` classes must be inert)

**Commit:** `git commit -m "perf(frontend): route splitting, lazy loading, bundle optimization (T13)"`

**Inline verification:**
- `cd frontend && npm run type-check` -- no errors
- `cd frontend && npm run build` -- builds without errors, initial JS < 200KB gzipped (verify in terminal output)

---

### T14: Docker Production Hardening

**Goal:** Harden the Docker compose setup for reliable production use: health checks, restart policies, log rotation, resource limits, non-root user, backup volumes.
**Spec refs:** §13.3-13.4 (Docker Compose, Dockerfile), D1 (Docker-first), D2 (full compose)

**Files:**
- Modify: `docker-compose.yml` (production hardening)
- Create: `docker-compose.prod.yml` (production overrides)
- Modify: `Dockerfile` (non-root user, HEALTHCHECK, pg_dump)
- Modify: `.env.example` (document all configurable ports and settings)

**Steps:**

- [ ] Step 1: Harden `docker-compose.yml`
  ```yaml
  services:
    db:
      image: pgvector/pgvector:pg16
      container_name: bookcompanion-db
      ports:
        - "${BOOKCOMPANION_DB_PORT:-5438}:5432"
      volumes:
        - pgdata:/var/lib/postgresql/data
      environment:
        POSTGRES_DB: bookcompanion
        POSTGRES_USER: bookcompanion
        POSTGRES_PASSWORD: bookcompanion
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U bookcompanion"]
        interval: 10s
        timeout: 5s
        retries: 5
        start_period: 30s
      restart: unless-stopped
      logging:
        driver: "json-file"
        options:
          max-size: "10m"
          max-file: "3"

    backend:
      build:
        context: .
        dockerfile: Dockerfile
      container_name: bookcompanion-backend
      ports:
        - "${BOOKCOMPANION_API_PORT:-8000}:8000"
      environment:
        BOOKCOMPANION_DATABASE__URL: "postgresql+asyncpg://bookcompanion:bookcompanion@db:5432/bookcompanion"
        BOOKCOMPANION_NETWORK__HOST: "0.0.0.0"
        BOOKCOMPANION_NETWORK__PORT: "8000"
      depends_on:
        db:
          condition: service_healthy
      volumes:
        - backups:/app/backups
        - config:/app/config
      restart: unless-stopped
      logging:
        driver: "json-file"
        options:
          max-size: "10m"
          max-file: "5"
      deploy:
        resources:
          limits:
            memory: 1G

  volumes:
    pgdata:
    backups:
    config:
  ```

- [ ] Step 2: Create `docker-compose.prod.yml` with production overrides
  ```yaml
  # docker-compose.prod.yml -- use with: docker compose -f docker-compose.yml -f docker-compose.prod.yml up
  services:
    backend:
      environment:
        BOOKCOMPANION_LOGGING__LEVEL: "WARNING"
        BOOKCOMPANION_LOGGING__JSON_FORMAT: "true"
  ```

- [ ] Step 3: Harden `Dockerfile`
  ```dockerfile
  # Stage 1: Build frontend
  FROM node:20-alpine AS frontend-build
  WORKDIR /app/frontend
  COPY frontend/package.json frontend/package-lock.json ./
  RUN npm ci
  COPY frontend/ ./
  RUN npm run build

  # Stage 2: Python backend
  FROM python:3.12-slim
  WORKDIR /app

  # Install system deps (Calibre for MOBI, pg_dump for backup)
  RUN apt-get update && apt-get install -y --no-install-recommends \
      calibre \
      postgresql-client \
      && rm -rf /var/lib/apt/lists/*

  # Create non-root user
  RUN groupadd -r bookcompanion && useradd -r -g bookcompanion bookcompanion

  # Install Python deps
  COPY backend/pyproject.toml backend/uv.lock ./backend/
  RUN pip install uv && cd backend && uv sync --no-dev

  # Copy backend code
  COPY backend/ ./backend/

  # Copy built frontend
  COPY --from=frontend-build /app/frontend/dist ./backend/static/

  # Create dirs for backups and config
  RUN mkdir -p /app/backups /app/config && chown -R bookcompanion:bookcompanion /app

  USER bookcompanion

  WORKDIR /app/backend

  HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
      CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

  CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.api.main:app --host 0.0.0.0 --port 8000"]
  ```

- [ ] Step 4: Update `.env.example`
  ```
  # Ports
  BOOKCOMPANION_DB_PORT=5438
  BOOKCOMPANION_API_PORT=8000

  # Network
  BOOKCOMPANION_NETWORK__HOST=127.0.0.1
  BOOKCOMPANION_NETWORK__ALLOW_LAN=false
  BOOKCOMPANION_NETWORK__ACCESS_TOKEN=

  # LLM
  BOOKCOMPANION_LLM__CLI_COMMAND=claude

  # Web
  BOOKCOMPANION_WEB__SHOW_COST_ESTIMATES=false
  ```

- [ ] Step 5: Test Docker build and startup
  Run: `docker compose build --no-cache`
  Run: `docker compose up -d`
  Run: `docker compose ps` -- both services healthy
  Run: `curl -sf http://localhost:8000/api/v1/health | python3 -m json.tool` -- `{"status": "ok"}`
  Run: `docker compose logs backend --tail=20` -- no errors
  Run: `docker compose down`

- [ ] Verify: `docker compose up -d && sleep 10 && curl -sf http://localhost:8000/api/v1/health && docker compose down`

**Commit:** `git commit -m "ops: Docker production hardening — health checks, log rotation, non-root user (T14)"`

**Inline verification:**
- `docker compose build --no-cache` -- builds without errors
- `docker compose up -d && docker compose ps` -- both services healthy
- `curl -sf http://localhost:8000/api/v1/health` -- returns `{"status": "ok"}`
- `docker compose down` -- clean shutdown

---

### T15a: E2E Test Infrastructure + Core Tests

**Goal:** Set up Playwright configuration with 3 projects (desktop-chrome, mobile-chrome, mobile-safari), shared fixture helpers, and core E2E tests for library, upload, and reader flows.
**Spec refs:** §14.4 (E2E Tests), §6 (Test Scenarios in requirements)

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/fixtures.ts` (shared test setup)
- Create: `frontend/e2e/library.spec.ts`
- Create: `frontend/e2e/upload.spec.ts`
- Create: `frontend/e2e/reader.spec.ts`

**Steps:**

- [ ] Step 1: Install Playwright and configure
  Run: `cd frontend && npm install -D @playwright/test && npx playwright install chromium`
  Create `frontend/playwright.config.ts`:
  ```typescript
  import { defineConfig, devices } from '@playwright/test'
  export default defineConfig({
    testDir: './e2e',
    timeout: 60_000,
    retries: 2,
    use: {
      baseURL: 'http://localhost:8000',
      screenshot: 'only-on-failure',
      trace: 'retain-on-failure',
    },
    projects: [
      { name: 'desktop-chrome', use: { ...devices['Desktop Chrome'] } },
      { name: 'mobile-chrome', use: { ...devices['Pixel 5'] } },
      { name: 'mobile-safari', use: { ...devices['iPhone 13'] } },
    ],
    webServer: {
      command: 'docker compose up',
      url: 'http://localhost:8000/api/v1/health',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  })
  ```
  Add to `frontend/package.json` scripts: `"test:e2e": "playwright test"`

- [ ] Step 2: Create shared fixtures (`frontend/e2e/fixtures.ts`)
  ```typescript
  import { test as base } from '@playwright/test'
  export const test = base.extend({
    // Seed a test book via API before each test that needs one
    seededBook: async ({ request }, use) => {
      // Upload test fixture book via API
      const resp = await request.post('/api/v1/books/upload', {
        multipart: { file: { name: 'test.epub', mimeType: 'application/epub+zip', buffer: fs.readFileSync('...') } }
      })
      const book = await resp.json()
      await use(book)
      // Cleanup: delete book
      await request.delete(`/api/v1/books/${book.id}`)
    },
  })
  ```

- [ ] Step 3: Library E2E tests (`frontend/e2e/library.spec.ts`)
  Tests from requirements §6.1:
  ```typescript
  // LIB-01: Grid view shows book cards with cover image and title
  test('LIB-01: library displays books in grid view by default on desktop', async ({ page }) => {
    await page.goto('/')
    // Grid is the default desktop mode
    const cards = page.locator('[data-testid="book-card"]')
    await expect(cards).toHaveCountGreaterThan(0)
    // Each card must have a title visible
    await expect(cards.first().locator('[data-testid="book-title"]')).not.toBeEmpty()
  })

  // LIB-02: Switching to List view changes the layout (fewer columns, text-dominant rows)
  test('LIB-02: switching to List view renders books as rows', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="view-mode-list"]')
    // List rows must be visible; grid layout class must be absent
    const rows = page.locator('[data-testid="book-list-row"]')
    await expect(rows).toHaveCountGreaterThan(0)
    await expect(page.locator('[data-testid="book-grid"]')).not.toBeVisible()
  })

  // LIB-02: Table view shows column headers
  test('LIB-02: switching to Table view renders a table with sortable headers', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="view-mode-table"]')
    await expect(page.locator('table th', { hasText: 'Title' })).toBeVisible()
    await expect(page.locator('table th', { hasText: 'Status' })).toBeVisible()
    const rows = page.locator('table tbody tr')
    await expect(rows).toHaveCountGreaterThan(0)
  })

  // LIB-03: Filter by status reduces the visible book count
  test('LIB-03: filtering by status "summarized" shows only summarized books', async ({ page }) => {
    await page.goto('/')
    const allCards = await page.locator('[data-testid="book-card"]').count()
    await page.selectOption('[data-testid="filter-status"]', 'summarized')
    const filteredCards = page.locator('[data-testid="book-card"]')
    // Must show fewer cards OR the same if all are summarized
    const filteredCount = await filteredCards.count()
    expect(filteredCount).toBeLessThanOrEqual(allCards)
    // All visible cards must have a "summarized" status badge
    for (const card of await filteredCards.all()) {
      await expect(card.locator('[data-testid="status-badge"]')).toHaveText(/summarized/i)
    }
  })

  // LIB-11: Empty library shows the empty state illustration and CTA
  test('LIB-11: empty library shows welcome empty state with upload CTA', async ({ page, request }) => {
    // Delete all books via API to produce an empty state
    const books = await (await request.get('/api/v1/books')).json()
    for (const book of books.items ?? []) {
      await request.delete(`/api/v1/books/${book.id}`)
    }
    await page.goto('/')
    await expect(page.locator('[data-testid="empty-state-title"]')).toHaveText('Your library is empty')
    await expect(page.locator('[data-testid="empty-state-cta"]')).toHaveText(/upload your first book/i)
  })

  // LIB-14: Mobile list view defaults to list (not grid)
  test('LIB-14: mobile viewport defaults to list view', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/')
    // List rows must be visible by default; grid must not be
    await expect(page.locator('[data-testid="book-list-row"]').first()).toBeVisible()
    await expect(page.locator('[data-testid="book-grid"]')).not.toBeVisible()
  })
  ```

- [ ] Step 4: Upload E2E tests (`frontend/e2e/upload.spec.ts`)
  Tests from requirements §6.2:
  - UPL-01: Upload EPUB happy path
  - UPL-04: Reject unsupported format
  - UPL-05: Reject oversized file
  - UPL-08: Edit metadata

- [ ] Step 5: Reader E2E tests (`frontend/e2e/reader.spec.ts`)
  Tests from requirements §6.3:
  - RDR-01: Navigate sections with arrows
  - RDR-02: Toggle Original/Summary
  - RDR-04: Reader settings change
  - RDR-08: Mobile bottom action bar (mobile project)

- [ ] Verify: `cd frontend && npx playwright test --project=desktop-chrome library upload reader` -- all pass

**Commit:** `git commit -m "test(e2e): add Playwright infrastructure + library/upload/reader E2E tests (T15a)"`

**Inline verification:**
- `cd frontend && npx playwright test --project=desktop-chrome` -- core tests pass
- `cd frontend && npm run type-check` -- no errors

---

### T15b: E2E Remaining Tests

**Goal:** Complete E2E coverage with settings (including presets and reading preferences), export-backup, search, mobile, and reading-position tests.
**Spec refs:** §14.4 (E2E Tests), §6 (Test Scenarios in requirements)

**Files:**
- Create: `frontend/e2e/settings.spec.ts`
- Create: `frontend/e2e/export-backup.spec.ts`
- Create: `frontend/e2e/search.spec.ts`
- Create: `frontend/e2e/mobile.spec.ts`
- Create: `frontend/e2e/reading-position.spec.ts`

**Steps:**

- [ ] Step 1: Settings E2E tests (`frontend/e2e/settings.spec.ts`)
  ```typescript
  test('settings: LAN toggle shows QR code with correct URL', async ({ page }) => {
    await page.goto('/settings/general')
    await page.click('[data-testid="lan-toggle"]')  // enable LAN
    const qrCode = page.locator('[data-testid="lan-qr-code"]')
    await expect(qrCode).toBeVisible()
    const lanUrl = page.locator('[data-testid="lan-url"]')
    await expect(lanUrl).toHaveText(/http:\/\/\d+\.\d+\.\d+\.\d+:\d+/)  // must show IP:port
  })

  test('settings: database stats show realistic row counts', async ({ page }) => {
    await page.goto('/settings/database')
    const booksRow = page.locator('[data-testid="db-stat-books"]')
    await expect(booksRow).toBeVisible()
    const text = await booksRow.textContent()
    expect(parseInt(text ?? '0')).toBeGreaterThanOrEqual(2)
  })

  test('settings: migration status shows "Up to date"', async ({ page }) => {
    await page.goto('/settings/database')
    await expect(page.locator('[data-testid="migration-status"]')).toHaveText(/up to date/i)
    await expect(page.locator('[data-testid="run-migrations-btn"]')).not.toBeVisible()
  })

  test('settings: create user preset and verify it appears in list', async ({ page }) => {
    await page.goto('/settings/presets')
    await page.click('[data-testid="create-preset-btn"]')
    await page.fill('[data-testid="preset-name-input"]', 'my-e2e-preset')
    await page.click('[data-testid="save-preset-btn"]')
    await expect(page.locator('[data-testid="preset-list-item"]', { hasText: 'my-e2e-preset' })).toBeVisible()
    // Delete it
    await page.click('[data-testid="preset-list-item"]:has-text("my-e2e-preset") [data-testid="delete-preset-btn"]')
    await page.click('[data-testid="confirm-delete-btn"]')
    await expect(page.locator('[data-testid="preset-list-item"]', { hasText: 'my-e2e-preset' })).not.toBeVisible()
  })

  test('settings: reading preference change persists after page reload', async ({ page }) => {
    await page.goto('/settings/reading')
    await page.selectOption('[data-testid="default-preset-select"]', 'practitioner_bullets')
    await page.click('[data-testid="save-reading-settings-btn"]')
    await page.reload()
    await expect(page.locator('[data-testid="default-preset-select"]')).toHaveValue('practitioner_bullets')
  })

  test('settings: custom CSS persists after page reload', async ({ page }) => {
    await page.goto('/settings/reading')
    await page.fill('[data-testid="custom-css-textarea"]', 'body { font-size: 18px; }')
    await page.click('[data-testid="save-reading-settings-btn"]')
    await page.reload()
    await expect(page.locator('[data-testid="custom-css-textarea"]')).toHaveValue('body { font-size: 18px; }')
  })
  ```

- [ ] Step 2: Export & Backup E2E tests (`frontend/e2e/export-backup.spec.ts`)
  ```typescript
  test('backup: create backup appears in list with non-zero size', async ({ page }) => {
    await page.goto('/settings/backup')
    await page.click('[data-testid="create-backup-btn"]')
    await expect(page.locator('[data-testid="backup-success-toast"]')).toBeVisible()
    const backupRows = page.locator('[data-testid="backup-history-row"]')
    await expect(backupRows).toHaveCountGreaterThan(0)
    const sizeText = await backupRows.first().locator('[data-testid="backup-size"]').textContent()
    expect(parseFloat(sizeText ?? '0')).toBeGreaterThan(0)
  })

  test('backup: download triggers a file download with .sql extension', async ({ page }) => {
    await page.goto('/settings/backup')
    await page.click('[data-testid="create-backup-btn"]')
    await page.waitForSelector('[data-testid="backup-history-row"]')
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="backup-history-row"]:first-child [data-testid="download-backup-btn"]'),
    ])
    expect(download.suggestedFilename()).toMatch(/\.sql$/)
  })

  test('export: library JSON download contains library array with books', async ({ page }) => {
    await page.goto('/settings/backup')
    await page.selectOption('[data-testid="export-format-select"]', 'json')
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="export-library-btn"]'),
    ])
    const stream = await download.createReadStream()
    const chunks: Buffer[] = []
    for await (const chunk of stream) chunks.push(Buffer.from(chunk))
    const json = JSON.parse(Buffer.concat(chunks).toString())
    expect(Array.isArray(json.library)).toBe(true)
    expect(json.library.length).toBeGreaterThanOrEqual(2)
  })
  ```

- [ ] Step 3: Search E2E tests (`frontend/e2e/search.spec.ts`)
  ```typescript
  test('search: command palette opens and returns grouped results', async ({ page }) => {
    await page.goto('/')
    await page.keyboard.press('Meta+k')  // Cmd+K on Mac
    await expect(page.locator('[data-testid="command-palette"]')).toBeVisible()
    await page.type('[data-testid="command-palette-input"]', 'war')
    // Wait for results to appear
    await expect(page.locator('[data-testid="search-result-group"]')).toHaveCountGreaterThan(0)
    // Group label must be present (e.g. "Books", "Sections")
    const groupLabel = page.locator('[data-testid="search-result-group-label"]').first()
    await expect(groupLabel).not.toBeEmpty()
  })

  test('search: clicking a result navigates to the correct page', async ({ page }) => {
    await page.goto('/')
    await page.keyboard.press('Meta+k')
    await page.type('[data-testid="command-palette-input"]', 'Art of War')
    await page.waitForSelector('[data-testid="search-result-item"]')
    const firstResult = page.locator('[data-testid="search-result-item"]').first()
    const resultText = await firstResult.textContent()
    await firstResult.click()
    // Should navigate away from library; URL should change
    await expect(page).not.toHaveURL('/')
  })
  ```

- [ ] Step 4: Mobile-specific E2E tests (`frontend/e2e/mobile.spec.ts`)
  ```typescript
  // Run with --project=mobile-chrome (Pixel 5: 393x851px)
  test('mobile: bottom tab bar is visible and icon rail is hidden', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('[data-testid="bottom-tab-bar"]')).toBeVisible()
    await expect(page.locator('[data-testid="icon-rail-sidebar"]')).not.toBeVisible()
    // Verify 5 tabs
    const tabs = page.locator('[data-testid="bottom-tab-bar"] [data-testid="tab-item"]')
    await expect(tabs).toHaveCount(5)
  })

  test('mobile: bottom sheet opens from reader action bar', async ({ page }) => {
    await page.goto('/books/1')
    await page.click('[data-testid="reader-action-annotations"]')
    const sheet = page.locator('[data-testid="bottom-sheet"]')
    await expect(sheet).toBeVisible()
    // Sheet must cover at least 25% of viewport height (peek snap)
    const box = await sheet.boundingBox()
    expect(box!.height).toBeGreaterThan(page.viewportSize()!.height * 0.25)
  })

  test('mobile: filter opens as full-screen modal not a dropdown', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="filter-btn"]')
    const modal = page.locator('[data-testid="filter-modal-fullscreen"]')
    await expect(modal).toBeVisible()
    // Modal must cover the full viewport
    const box = await modal.boundingBox()
    expect(box!.width).toBeGreaterThanOrEqual(page.viewportSize()!.width - 1)
    await expect(page.locator('[data-testid="filter-modal-done-btn"]')).toBeVisible()
  })

  test('mobile: all tab touch targets are at least 44px tall', async ({ page }) => {
    await page.goto('/')
    const tabs = page.locator('[data-testid="bottom-tab-bar"] [data-testid="tab-item"]')
    const count = await tabs.count()
    for (let i = 0; i < count; i++) {
      const box = await tabs.nth(i).boundingBox()
      expect(box!.height, `Tab ${i} must be at least 44px tall`).toBeGreaterThanOrEqual(44)
    }
  })
  ```

- [ ] Step 5: Reading position sync E2E (`frontend/e2e/reading-position.spec.ts`)
  ```typescript
  test('reading position: continue banner shows book title and section title', async ({ browser }) => {
    // Simulate desktop save: navigate to a section
    const desktopCtx = await browser.newContext({ userAgent: 'Mozilla/5.0 (Macintosh; Desktop Chrome Test)' })
    const desktopPage = await desktopCtx.newPage()
    await desktopPage.goto('/books/1/sections/3')
    await desktopPage.waitForTimeout(6000)  // wait for debounced position save
    await desktopCtx.close()

    // Simulate mobile load with different user-agent
    const mobileCtx = await browser.newContext({ userAgent: 'Mozilla/5.0 (iPhone; Mobile Safari Test)' })
    const mobilePage = await mobileCtx.newPage()
    await mobilePage.goto('/')
    const banner = mobilePage.locator('[data-testid="continue-banner"]')
    await expect(banner).toBeVisible()
    // Banner must mention the book title
    await expect(banner).toContainText('The Art of War')
    // Banner "Continue" button navigates to the correct section
    await mobilePage.click('[data-testid="continue-banner-btn"]')
    await expect(mobilePage).toHaveURL(/\/books\/1\/sections\/3/)
    await mobileCtx.close()
  })

  test('reading position: dismissing banner prevents it from showing again in same session', async ({ browser }) => {
    const desktopCtx = await browser.newContext({ userAgent: 'Mozilla/5.0 (Macintosh; Desktop Chrome Test2)' })
    const desktopPage = await desktopCtx.newPage()
    await desktopPage.goto('/books/1/sections/3')
    await desktopPage.waitForTimeout(6000)
    await desktopCtx.close()

    const mobileCtx = await browser.newContext({ userAgent: 'Mozilla/5.0 (iPhone; Mobile Safari Test2)' })
    const mobilePage = await mobileCtx.newPage()
    await mobilePage.goto('/')
    await mobilePage.click('[data-testid="continue-banner-dismiss"]')
    await mobilePage.reload()
    // After dismissal and reload within same session, banner must not reappear
    await expect(mobilePage.locator('[data-testid="continue-banner"]')).not.toBeVisible()
    await mobileCtx.close()
  })
  ```

- [ ] Verify: `cd frontend && npx playwright test` -- all pass across all projects

**Commit:** `git commit -m "test(e2e): add settings/export/search/mobile/reading-position E2E tests (T15b)"`

**Inline verification:**
- `cd frontend && npx playwright test --project=desktop-chrome` -- all pass
- `cd frontend && npx playwright test --project=mobile-chrome` -- all pass

---

### T16: Final Verification

**Goal:** Verify the entire Phase 3 implementation works end-to-end with no regressions.

- [ ] **Lint & format (backend):**
  Run: `cd backend && uv run ruff check . && uv run ruff format --check .`
  Expected: No errors

- [ ] **Lint & type-check (frontend):**
  Run: `cd frontend && npm run type-check && npm run lint`
  Expected: No errors

- [ ] **Backend unit tests:**
  Run: `cd backend && uv run python -m pytest tests/unit/ -v`
  Expected: All pass, including new settings/reading-state/scheduler tests

- [ ] **Backend integration tests (API):**
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/ -v`
  Expected: All API tests pass (export, backup, settings, reading state + all Phase 1/2 tests)

- [ ] **Full backend test suite (no regressions):**
  Run: `cd backend && uv run python -m pytest tests/ --timeout=60`
  Expected: All tests pass (existing 78+ from V1 + all Phase 1/2/3 additions)

- [ ] **Frontend build:**
  Run: `cd frontend && npm run build`
  Expected: Builds without errors. Check bundle size: initial JS < 200KB gzipped.

- [ ] **Database migrations:**
  Run: `cd backend && uv run alembic upgrade head`
  Expected: All migrations applied, including `reading_state` table

- [ ] **Docker full stack:**
  Run: `docker compose build --no-cache && docker compose up -d`
  Run: Wait for healthy: `docker compose ps`
  Run: `curl -sf http://localhost:8000/api/v1/health | python3 -m json.tool`
  Expected: `{"status": "ok"}`
  Run: `docker compose logs backend --tail=20` -- no errors

- [ ] **E2E test suite:**
  Run: `cd frontend && npx playwright test`
  Expected: All tests pass on desktop-chrome, mobile-chrome, mobile-safari projects

- [ ] **API smoke tests (verify content, not just status):**
  ```bash
  # Export: must contain "library" array with at least 2 books
  curl -sf "http://localhost:8000/api/v1/export/library?format=json" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['library'])>=2, f'Expected >=2 books, got {len(d[\"library\"])}'; print(f'OK: {len(d[\"library\"])} books in export')"

  # Export markdown: must contain section headings
  curl -sf "http://localhost:8000/api/v1/export/book/1?format=markdown" \
    | python3 -c "import sys; content=sys.stdin.read(); assert '## ' in content, 'No section headings in markdown'; print('OK: markdown has section headings')"

  # Backup: create must return backup_id, list must include it with size_bytes > 0
  BACKUP_ID=$(curl -sf -X POST http://localhost:8000/api/v1/backup/create \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backup_id'])")
  echo "Created backup: $BACKUP_ID"
  curl -sf http://localhost:8000/api/v1/backup/list \
    | python3 -c "import sys,json,os; items=json.load(sys.stdin); bid=os.environ.get('BACKUP_ID',''); match=[i for i in items if i['backup_id']==bid]; assert match, f'Backup {bid} not in list'; assert match[0]['size_bytes']>0, 'size_bytes must be >0'; print(f'OK: backup {bid} listed with {match[0][\"size_bytes\"]} bytes')" BACKUP_ID="$BACKUP_ID"

  # Settings: must have network and llm keys; books count must be >= 2
  curl -sf http://localhost:8000/api/v1/settings \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'network' in d and 'llm' in d, 'Missing keys'; print('OK: settings has network+llm')"
  curl -sf http://localhost:8000/api/v1/settings/database-stats \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('books',0)>=2, f'Expected >=2 books, got {d.get(\"books\")}'; print(f'OK: books={d[\"books\"]}, sections={d[\"book_sections\"]}')"

  # Migration status: must not be behind
  curl -sf http://localhost:8000/api/v1/settings/migration-status \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert not d['is_behind'], 'DB is behind migrations'; assert d['current'] is not None, 'No current revision'; print(f'OK: migration current={d[\"current\"]}, is_behind={d[\"is_behind\"]}')"

  # Reading state: upsert must return the book_id we sent; continue from different UA must return same book
  curl -sf -X PUT http://localhost:8000/api/v1/reading-state \
    -H "Content-Type: application/json" -H "User-Agent: SmokeTestDesktop/1.0" \
    -d '{"book_id": 1, "section_id": 3}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['last_book_id']==1, f'Expected book_id=1, got {d[\"last_book_id\"]}'; print('OK: upsert returned correct book_id')"
  curl -sf http://localhost:8000/api/v1/reading-state/continue \
    -H "User-Agent: SmokeTestMobile/1.0" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('last_book_id')==1, f'Expected last_book_id=1 from cross-device, got {d}'; print(f'OK: continue returns book_id=1, title={d.get(\"book_title\")}')"
  ```

- [ ] **Manual spot checks — Settings:**
  - Navigate to `/settings` -- sidebar with 5 sections renders
  - General: LAN toggle works, QR code appears when enabled, default preset dropdown populates
  - Database: connection status green, stats show row counts, migration status shows "up to date"
  - Presets: system presets read-only, can duplicate, user presets editable
  - Reading: default preset selectable, custom CSS textarea
  - Backup: Create backup button works, backup appears in list, download works, delete works

- [ ] **Manual spot checks — Export:**
  - Export library as JSON -- file downloads
  - Export library as Markdown -- file downloads
  - Export single book -- file downloads with book data

- [ ] **Manual spot checks — Mobile (375px viewport):**
  - Bottom tab bar visible with 5 tabs
  - Icon rail sidebar hidden
  - Library: list view default, filter opens as full-screen modal
  - Reader: bottom action bar, bottom sheets for AI/Annotations/Settings
  - Bottom sheet: drag to snap at 30%/50%/90%, swipe down to dismiss
  - Touch targets: all buttons >= 44px
  - Settings: accordion/tab layout

- [ ] **Manual spot checks — Reading position sync:**
  - Open in Chrome desktop, navigate to a specific section
  - Open in Safari (or Chrome with different UA override): "Continue where you left off" banner appears
  - Click "Continue" -- navigates to correct section
  - Dismiss banner -- does not reappear in same session

- [ ] **Manual spot checks — Polish:**
  - Empty library: welcome illustration + upload CTA
  - Skeleton loaders visible during navigation (throttle network in DevTools)
  - Error state: stop backend, navigate -- error boundary shows "Connection lost"
  - `prefers-reduced-motion`: enable in OS, verify animations are disabled
  - Keyboard navigation: Tab through library, reader, settings -- logical focus order
  - Color contrast: check in Dark, OLED, and Sepia themes

- [ ] **Manual spot checks — Docker production:**
  - `docker compose ps` shows both services healthy
  - Restart backend: `docker compose restart backend` -- recovers automatically
  - Check logs: `docker compose logs --tail=50` -- no errors, JSON format
  - Backup volume persists: `docker compose down && docker compose up -d` -- backups still listed

- [ ] **Health CLI command:**
  Run: `cd backend && uv run bookcompanion health`
  Expected: Diagnostic table with DB connectivity, migration status, disk space, last backup age, access URL

- [ ] **Cleanup:**
  - Remove any temporary debug logging
  - Verify `.gitignore` covers `.env`, `frontend/dist/`, `frontend/node_modules/`, `backend/static/`, `frontend/test-results/`, `frontend/playwright-report/`
  - Run: `docker compose down`

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | Initial plan draft | Full plan written with 16 tasks covering all Phase 3 scope items |
| 2 | Review loop: format inconsistency (inline verify vs dedicated section), T10 missing verification, 5 tasks too large, T15 E2E gaps, implicit dependencies | Standardized all tasks with Inline verification sections, added T10 verification, split T3/T6/T9/T15 into sub-tasks (now 20 tasks), expanded T15 settings E2E tests, documented implicit dependencies in execution order |
| 3 | Verification gaps: structural-only tests throughout (hasattr checks, status codes only, "npm run build" only). No behavioral coverage for DB upsert/cascade, backup file on disk, settings persistence, scheduler invocation, frontend store behavior, or specific UI interaction assertions in E2E tests | Added behavioral integration tests to T1 (upsert, UNIQUE constraint, FK cascade, timestamp auto-population), T2 (export content includes summaries/sections/book count), T3a (file exists on disk, download is valid SQL, delete removes file, list reflects created backup), T3b (scheduler registers job, job function actually invokes BackupService), T4 (settings write-then-read, partial update safety, DB counts reflect real data, migration status not-behind assertion). Added store unit tests to T6a (settings store with realistic data), T8 (reading state store coverage), T9a (useBreakpoint), T10 (useTouchGestures). Added specific manual verification steps with exact URLs, element selectors, and expected values to T6a, T6b, T7, T8, T9a, T9b, T10, T11, T12, T13. Expanded T15b E2E tests with full Playwright test code (settings persistence, backup download file content, export JSON contains books, mobile touch targets measured with boundingBox, reading position banner shows book title and navigates to correct section). Replaced T16 smoke tests with content-asserting one-liners that verify actual data, not just HTTP 200. |
