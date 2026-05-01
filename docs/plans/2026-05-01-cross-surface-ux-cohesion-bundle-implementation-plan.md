# Cross-Surface UX Cohesion Bundle — Implementation Plan

**Date:** 2026-05-01
**Spec:** `docs/specs/2026-05-01-cross-surface-ux-cohesion-bundle-spec.md`
**Simulation:** `docs/simulations/2026-05-01-cross-surface-ux-cohesion-bundle-simulation.md`
**Requirements:** `docs/requirements/2026-05-01-cross-surface-ux-cohesion-bundle.md`

---

## Overview

Closes 18 cross-surface UX defects across Book Detail, Section Reader, app shell, and 4 Settings pages. Mostly presentation-layer work plus 4 real backend changes (migration-status rewrite, preset CRUD, malformed-YAML resilience, idempotency-payload check). Tasks group by surface for context-locality, but each is independently committable.

**Done when:** All 18 ACs from the requirements doc verifiable on `localhost:8000`; the verified pre-fix failure modes (`"FAILED:"` in migration-status, sidebar staying white on Dark theme, 0 highlights on Summary tab, TOC `0` chars, "Read Summary" disabled button, missing book-summary IA home) no longer reproducible; backend + frontend test suites green; no Tailwind `dark:` classes remain in `frontend/src/components/settings/`.

**Execution order:**

```
Phase A — Backend (parallelizable)
  T1 Migration-status rewrite [P]
  T2 PresetService extensions [P]
  T3 Preset CRUD API endpoints  (depends on T2)
  T4 Verify 409 idempotency payload [P]
  T5 Verify GET /books/{id} default_summary shape [P]

Phase B — Frontend infrastructure (parallelizable)
  T6 Move ThemeCard to shared/ [P]
  T7 Compression formatter [P]
  T8 MarkdownRenderer scoped styles [P]
  T9 TocDropdown char-count fix [P]
  T10 ReadingAreaFooterNav [P]

Phase C — Book Detail surface
  T11 BookDetailTabs strip + ?tab= routing  (depends on T7)
  T12 OverflowMenu reshape  (depends on T11)
  T13 BookSummaryTab  (depends on T5, T11)

Phase D — Section Reader cross-cutting
  T14 Side-panel reader-theme scope [P]
  T15 Annotation Summary-tab filter + create wiring [P]

Phase E — App shell
  T16 IconRail + TopBar router-link [P]

Phase F — Settings UI
  T17 DatabaseSettings (stripes + Unknown) [P]
  T18 ReadingSettings → shared ThemeCard  (depends on T6)
  T19a PresetCreateEditForm component  [P]
  T19b PresetTemplateViewer component  (depends on T3)
  T19c PresetSettings rewrite — wire CRUD + viewer  (depends on T19a, T19b, T3)
  T20 LlmSettings restyle [P]

Phase G — Routing tail
  T21 Legacy /books/:id/summary redirect [P]

Phase H — Verification
  T22 Final regression + Playwright MCP gate
```

---

## Decision Log

> Inherits SD1–SD22 from spec § 4. Entries below are plan-level decisions made during planning.

| # | Decision | Options Considered | Rationale |
|---|----------|--------------------|-----------|
| P1 | Cancel endpoint = `POST /api/v1/processing/{job_id}/cancel` | (a) POST .../cancel (existing in `processing.py:259-337`), (b) DELETE | (a) — confirmed by code study; existing endpoint handles PENDING (delete) and RUNNING (SIGTERM) phases and emits `job_cancelling` SSE. Resolves simulation OQ1. |
| P2 | Active-tab state for annotation-create lives in `BookDetailView` local component state | (a) lift to `readerSettings` Pinia store, (b) keep local + prop-drill, (c) route meta | (b) — `BookDetailView` already owns the Original/Summary toggle as local state; the annotation-create handler is in the same view. No need to elevate to Pinia for a single consumer. Resolves simulation OQ2. |
| P3 | `Book.default_summary_id` already exists in models; no DB migration | (a) reuse existing FK, (b) add new field | (a) — code study confirmed `Book.default_summary_id: int \| None → Summary` exists with `ondelete=SET NULL`. `GET /books/{id}` already returns `default_summary` object. T5 is verification, not implementation. |
| P4 | Book-summary 409 idempotency partially exists; T4 is verification + payload tightening | (a) audit existing 409, only patch payload if needed, (b) rewrite the check | (a) — `default_summary.py:flow step 4` already returns 409 on active job. Need to confirm it returns `active_job_id` per § 7.5; if not, surgical patch only. |
| P5 | Tasks ordered by surface, not strictly by dependency graph | (a) surface-grouped (W1/W4/W6/...), (b) backend-first then frontend, (c) FR-ID order | (a) — keeps reviewer context coherent (Book Detail tasks read together) and matches the spec's workstream taxonomy. The few real cross-task dependencies (T5→T13, T6→T18/T19, T11→T12/T13, T2→T3) are explicit in the execution order. |
| P6 | TDD for backend tasks (T1, T2, T3) and a subset of frontend tasks (T7, T8, T9, T10, T11) | (a) TDD on backend + new components; light tests on cosmetic-only frontend tasks (T16, T17, T18, T20), (b) full TDD everywhere | (a) — pure CSS/template tweaks (alt-row stripe removal, router-link wrapping, dark: → CSS-var migration) gain little from a unit test; manual + Playwright verification is more useful. New behavior (formatter logic, footer nav, tab routing, BookSummaryTab states, preset CRUD) gets red→green TDD. |
| P7 | Preset facet validation source = filesystem-derived cache built once on `PresetService` init (per SD15) | (a) cache on init, (b) re-read on every call, (c) cache + invalidate-on-write | (a) — SD15 chose this; matches existing `_validate_facets` constants pattern. Stale until restart is acceptable for a single-user tool. |
| P8 | "Read Section Summaries" CTA navigates to `BookSection.order_index = MIN()` (smallest order_index) for the book — i.e., the first section by reading order | (a) min(order_index), (b) sections[0] from API response, (c) special "first chapter" classification | (a) — `BookSection.order_index` is the canonical reading-order column. Resolves SD16 destination ambiguity. |
| P9 | LlmSettings restyle = exhaustive grep gate (no `dark:` left); CSS-variable substitution table inline in T20 | (a) grep gate + per-class substitution map, (b) full rewrite of the file | (a) — the file's structure is fine; only the styling vocabulary is wrong. Substitution map keeps the diff focused. |
| P10 | E10 redirect: legacy route uses Vue Router's `redirect` config (not a runtime check) | (a) `redirect: to => '/books/' + to.params.id + '?tab=summary'`, (b) rewrite `BookSummaryView` to call router.replace, (c) leave route, add link from new tab | (a) — redirect at the router level is cheaper, leaves no runtime cost, and removes `BookSummaryView.vue` from the active tree. /plan task: `git rm` the legacy view file once the redirect lands and grep confirms no other references. |

---

## Code Study Notes

**Backend conventions:**
- Services receive deps via constructor (no globals). Async methods. Test fixtures: `db_session` (rolled back), `test_settings`.
- `SettingsService` exists at `backend/app/services/settings_service.py`. Constructor accepts `Settings | None`, no AsyncEngine today — T1 will need to pass `AsyncEngine` (or use `app.state.engine`).
- `PresetService` lives at `backend/app/services/preset_service.py` (not under summarizer/). Has `load`, `list_all`, `create`, `delete`, `resolve_facets`. Missing `update`, `get_template_source`, malformed-YAML graceful-skip. `list_all` already swallows errors per file but doesn't surface warnings.
- Preset YAML directory: `backend/app/services/summarizer/prompts/presets/` (system + user co-located; `system: bool` field in YAML distinguishes). Fragments: `backend/app/services/summarizer/prompts/fragments/{dimension}/*.txt`.
- Alembic config: `backend/app/migrations/alembic.ini` + `env.py` (async engine, batch mode for SQLite).
- `default_summary.py` pattern: route returns 202 with job_id; background task fires via `asyncio.create_task(_run(...))`; SSE events `processing_completed` / `processing_failed`.
- `processing.py:259-337`: `POST /api/v1/processing/{job_id}/cancel` handles PENDING (atomic delete) and RUNNING (SIGTERM via worker); emits `job_cancelling`.
- Models: `Book.default_summary_id: int | None`, `Summary.content_type` enum includes `book`, `ProcessingJob.status` enum, partial unique index `one_active_per_book WHERE status IN ('PENDING', 'RUNNING')`.

**Frontend conventions:**
- Vue 3 SFC + `<script setup>` + Pinia. `frontend/src/components/__tests__/` siblings or top-level `__tests__/` for views.
- CSS uses `var(--color-*)` custom properties; only `LlmSettings.vue` uses Tailwind `dark:` classes (~18 occurrences) — outlier.
- `MarkdownRenderer.vue` (63 LOC) has no `<style>` block; renders raw HTML via `v-html` after `applyHighlights()`. Adding scoped styles requires adding `class="markdown-body"` on the root and a `<style scoped>` block.
- `ReadingArea.vue` (92 LOC) has props `hasPrev`/`hasNext` and emits `navigate('prev'|'next')` on arrow-key. No existing footer slot — need to add one (or render footer inside the component).
- `ContextSidebar.vue` (60 LOC) and `AIChatTab.vue` (73 LOC) use `var(--color-bg)`/`var(--color-text-*)` with hardcoded fallbacks; they're outside the reader-theme `data-theme` scope, so theme switches don't affect them.
- `ThemeCard.vue` lives at `components/settings/ThemeCard.vue` (106 LOC), used by `ThemeGrid.vue`. Has its own `__tests__/ThemeCard.spec.ts`.
- `TopBar.vue:36` has the dynamic title; route name fallback `'Book Companion'`. Currently a plain `<h1>` (or similar) element — wrap in `<router-link to="/">`.
- `IconRail.vue:16` has the BC logo as a plain `<span class="text-lg font-bold">BC</span>` — wrap in `<router-link to="/">`.
- `BookOverviewView.vue` (499 LOC): single-page layout with cover/meta/sections; **no tab strip exists**. Adding tabs is a real template refactor.
- `BookDetailView.vue` (380 LOC): owns the Summary/Original toggle (local state) and the annotation loader at lines 43-47 / 98-115 — annotation loader currently filters `content_type='section_content'`.
- Routes (`router/index.ts` lines 18-57): `/books/:id` → `BookOverviewView`, `/books/:id/summary` → `BookSummaryView` (LEGACY — will be redirected by T21), `/books/:id/sections/:sectionId` → `BookDetailView`.

**Pipeline trace** (Generate book-summary): `BookSummaryTab.vue` → `POST /api/v1/books/{id}/book-summary` → `book_summary.py` queues `ProcessingJob(step=SUMMARIZE, status=PENDING)` + fires `_run()` → `SummarizerService.summarize_book_level()` → on completion, `Book.default_summary_id` updated + SSE `processing_completed` → `BookSummaryTab` subscribed to `/api/v1/processing/{job_id}/stream` refreshes.

---

## Prerequisites

- Repo at `/Users/maneeshdhabria/Desktop/Projects/personal/book-companion`, branch `main` clean.
- Backend deps installed: `cd backend && uv sync --dev`.
- Frontend deps installed: `cd frontend && npm install`.
- At least one book with summarized sections in the local DB for live verification (per CLAUDE.md "Interactive verification" workflow). Confirm via:
  ```bash
  sqlite3 ~/Library/Application\ Support/bookcompanion/library.db \
    "SELECT b.id, b.title, COUNT(s.id) FROM books b LEFT JOIN summaries s ON s.book_id=b.id AND s.content_type='section' GROUP BY b.id"
  ```
  If empty, run `cd backend && uv run python tests/fixtures/download_fixtures.py && uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub`.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/services/settings_service.py:253-287` | Replace `uv run alembic` subprocess with programmatic `MigrationContext` + `ScriptDirectory` API; add structured `error` field |
| Modify | `backend/app/services/preset_service.py` | Add `update()`, `get_template_source()`, malformed-YAML resilience with `warnings[]` accumulator |
| Modify | `backend/app/api/routes/summarize_presets.py` | Add POST/PUT/DELETE/`{name}/template` endpoints; `warnings[]` field on GET list |
| Verify (no change expected) | `backend/app/api/routes/book_summary.py` | Confirm 409 response includes `active_job_id` |
| Verify (no change expected) | `backend/app/api/routes/books.py` | Confirm GET response shape includes `default_summary` (Markdown body for default_summary where `content_type='book'`) |
| Move | `frontend/src/components/settings/ThemeCard.vue` → `frontend/src/components/shared/ThemeCard.vue` | Single canonical location for theme/preset cards |
| Modify | `frontend/src/components/settings/ThemeGrid.vue:4` | Update import path to `@/components/shared/ThemeCard.vue` |
| Modify | `frontend/src/components/book/SectionListTable.vue:38-43` | Replace `compressionLabel(s)` formatter with `~N%` rounded-to-5 |
| Modify | `frontend/src/components/reader/MarkdownRenderer.vue` | Add `class="markdown-body"` on root; add `<style scoped>` block (lists + tables) |
| Modify | `frontend/src/components/reader/TOCDropdown.vue` | Pass `content_char_count` (or full Section objects with that field) into compact `SectionListTable` |
| Create | `frontend/src/components/reader/ReadingAreaFooterNav.vue` | Inline prev/next link pair with `?tab=` preservation; hides when both null |
| Modify | `frontend/src/components/reader/ReadingArea.vue` | Add `<slot name="footer">` after the article body; render in `BookDetailView` consumers |
| Create | `frontend/src/components/book/BookSummaryTab.vue` | Empty / in-progress / failed / populated states; SSE subscription for cross-tab freshness |
| Modify | `frontend/src/views/BookOverviewView.vue` | Add tab strip (Overview / Summary / Sections) driven by `?tab=` query; refactor toolbar to single Read CTA + OverflowMenu |
| Modify | `frontend/src/components/book/OverflowMenu.vue` | Add Generate/Read book summary, Customize reader, Re-import, Export Markdown, Delete; popover anchored to trigger |
| Modify | `frontend/src/components/sidebar/ContextSidebar.vue` | Read `var(--reader-bg, var(--color-bg))`, `var(--reader-text)`, `var(--reader-border)` |
| Modify | `frontend/src/components/sidebar/AIChatTab.vue` | Same theme variable substitution |
| Modify | `frontend/src/views/BookDetailView.vue:104,109` | Annotation loader broadens to `content_type IN (section_content, section_summary)`; create handler reads active tab and passes `content_type` |
| Modify | `frontend/src/components/app/IconRail.vue:14-32` | Wrap BC logo in `<router-link to="/">` with focus/hover state |
| Modify | `frontend/src/components/app/TopBar.vue:45-59` | Wrap title in `<router-link to="/">` with focus/hover state |
| Modify | `frontend/src/components/settings/DatabaseSettings.vue` | Remove `nth-child(even)` rule; render `Unknown` + tooltip when migration revision is null/non-hex |
| Modify | `frontend/src/components/settings/ReadingSettings.vue:62-69` | Replace `<div class="preset-chip">` with `<ThemeCard>` from `@/components/shared/ThemeCard.vue` |
| Modify | `frontend/src/components/settings/PresetSettings.vue` | Add New / Edit / Delete affordances; integrate `PresetCreateEditForm` + `PresetTemplateViewer` |
| Create | `frontend/src/components/settings/PresetCreateEditForm.vue` | Form with name (slug), label, description, 4 facet card grids |
| Create | `frontend/src/components/settings/PresetTemplateViewer.vue` | Read-only `<pre>` viewer for base template + fragment blocks |
| Modify | `frontend/src/components/settings/LlmSettings.vue` | Drop all `dark:` Tailwind classes; convert to scoped-style + CSS-variable pattern |
| Modify | `frontend/src/router/index.ts` | Convert `/books/:id/summary` to a `redirect` to `/books/:id?tab=summary`; remove `BookSummaryView` import + delete `frontend/src/views/BookSummaryView.vue` if unreferenced |
| Test | `backend/tests/unit/test_settings_service.py` | Add tests for migration-status programmatic API + error path |
| Test | `backend/tests/unit/test_preset_service.py` | Add tests for `update()`, `get_template_source()`, malformed-YAML skip |
| Test | `backend/tests/integration/test_preset_api.py` (new) | Integration tests for POST/PUT/DELETE/template endpoints |
| Test | `frontend/src/components/book/__tests__/SectionListTable.compression.spec.ts` (new) | Behavioral assertions on `compressionLabel` |
| Test | `frontend/src/components/reader/__tests__/MarkdownRenderer.styles.spec.ts` (new) | Mounted-component getComputedStyle on `<ul>` etc. |
| Test | `frontend/src/components/reader/__tests__/ReadingAreaFooterNav.spec.ts` (new) | Renders both / first-only / last-only / hidden-on-single |
| Test | `frontend/src/components/reader/__tests__/TOCDropdown.spec.ts` | Extend: char counts non-zero for non-empty sections |
| Test | `frontend/src/components/book/__tests__/BookSummaryTab.spec.ts` (new) | All 4 states; CTA disabled at 0 sections summarized |
| Test | `frontend/src/components/book/__tests__/OverflowMenu.spec.ts` | Extend: items list assertion (no "Customize text") |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `ScriptDirectory.from_config()` fails to resolve `script_location` when bookcompanion is pip-installed (importlib resources vs filesystem path) | Medium | Test the new `get_migration_status()` against both dev tree (`uv run`) and a pip-installed wheel before declaring T1 done. If the relative-Path approach fails in installed mode, switch to `importlib.resources.files("app.migrations")`. |
| `ContextSidebar`/`AIChatTab` style changes regress non-reader contexts (any places where these panels render outside a reader-theme scope) | Medium | Use the `var(--reader-bg, var(--color-bg))` fallback pattern (option B in spec § 9.7) — never breaks app-default rendering. |
| Tab-strip refactor on `BookOverviewView` (~499 LOC) accidentally removes existing controls (export, customize-text, etc. — many of which the spec is removing intentionally) | Medium | T11 + T12 read like a major template refactor; verify each existing CTA either lands in OverflowMenu or is explicitly dropped per spec. Don't rebuild the page; refactor in place. |
| `MarkdownRenderer` scoped styles don't apply when consumers wrap output in additional containers | Low | Use `:deep()` selectors (per spec § 9.6). Verify with mounted-component test in T8. |
| `ThemeCard` move breaks downstream consumers that import from old path | Low | Grep gate in T6 + run frontend test suite + type-check before commit. |
| Legacy `/books/:id/summary` route still has consumers we don't know about | Low | Grep `from '@/views/BookSummaryView'` and any `name: 'book-summary'` references before deletion in T21. |
| `LlmSettings` Tailwind → CSS-var migration regresses light-theme styling | Medium | Side-by-side compare in browser (light + dark) after T20; manual check is the verification gate. |
| Annotation create handler change breaks existing Original-tab highlight creation | Medium | T15 must include both forward (Original → `section_content`) and new (Summary → `section_summary`) test paths. |

---

## Tasks

### T1: Migration-status backend programmatic rewrite

**Goal:** Replace `uv run alembic` subprocess with programmatic Alembic API; eliminate `"FAILED:"` literal leak; add structured `error` field.
**Spec refs:** FR-13 (backend), SD2, § 7.1, simulation E1.

**Files:**
- Modify: `backend/app/services/settings_service.py:253-287`
- Test: `backend/tests/unit/test_settings_service.py`

**Steps:**

- [ ] **1.** Write failing test `test_get_migration_status_returns_revision_strings`:
  ```python
  # backend/tests/unit/test_settings_service.py
  import pytest
  from app.services.settings_service import SettingsService

  @pytest.mark.asyncio
  async def test_get_migration_status_returns_revision_strings(db_engine, test_settings):
      svc = SettingsService(settings=test_settings, engine=db_engine)
      result = await svc.get_migration_status()
      assert result["error"] is None
      assert result["current"] is None or len(result["current"]) >= 8  # alembic hex
      assert result["latest"] is not None and len(result["latest"]) >= 8
      assert isinstance(result["is_behind"], bool)
      # Critical guard: response must never contain alembic's error banner
      for value in (result["current"], result["latest"]):
          assert value is None or not value.startswith("FAILED")
  ```

- [ ] **2.** Write failing test `test_get_migration_status_failure_returns_structured_error`:
  ```python
  @pytest.mark.asyncio
  async def test_get_migration_status_failure_returns_structured_error(test_settings, monkeypatch):
      svc = SettingsService(settings=test_settings, engine=None)  # engine None → forces error path
      result = await svc.get_migration_status()
      assert result == {"current": None, "latest": None, "is_behind": False, "error": pytest.approx(result["error"])} \
          if False else (result["current"] is None and result["latest"] is None and result["is_behind"] is False and isinstance(result["error"], str))
  ```

- [ ] **3.** Run tests; expect FAIL (current method takes no `engine` kwarg, doesn't return `error` field):
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_settings_service.py::test_get_migration_status_returns_revision_strings tests/unit/test_settings_service.py::test_get_migration_status_failure_returns_structured_error -v
  ```
  Expected: 2 failures.

- [ ] **4.** Implement: replace `get_migration_status()` body in `settings_service.py` per spec § 7.1 implementation block. Update `__init__` signature to accept optional `engine: AsyncEngine | None = None` (constructed from `Settings().database.url` if not passed, mirroring `env.py` pattern).

  Key implementation points:
  - Use `Path(__file__).resolve().parent.parent / "migrations"` for migrations dir; assert `alembic.ini` exists at that path
  - `ScriptDirectory.from_config(cfg).get_current_head()` for `latest`
  - `await conn.run_sync(lambda sc: MigrationContext.configure(sc).get_current_revision())` for `current`
  - Wrap in try/except; on error return `{current: None, latest: None, is_behind: False, error: str(e)}`; otherwise `error: None`
  - `logger.exception("migration_status_failed")` on the error path

- [ ] **5.** Run tests; expect both PASS:
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_settings_service.py -v
  ```

- [ ] **6.** Live API check via curl (with backend running):
  ```bash
  curl -s http://localhost:8000/api/v1/settings/migration-status | python3 -m json.tool
  ```
  Expected: `{"current": "<hex>", "latest": "<hex>", "is_behind": false, "error": null}`. **Critical**: response must NOT contain `"FAILED:"`.

- [ ] **7.** Regression grep gate:
  ```bash
  grep -rn '"FAILED:' backend/app/services/settings_service.py && echo "FAIL: FAILED literal still present" && exit 1 || echo "OK"
  grep -rn "uv run alembic" backend/app/services/settings_service.py && echo "FAIL: subprocess still present" && exit 1 || echo "OK"
  ```

- [ ] **8.** Commit:
  ```bash
  git add backend/app/services/settings_service.py backend/tests/unit/test_settings_service.py
  git commit -m "fix(backend): rewrite migration-status to programmatic Alembic API (FR-13)"
  ```

**Inline verification:**
- `uv run python -m pytest backend/tests/unit/test_settings_service.py -v` — all green.
- `curl -s http://localhost:8000/api/v1/settings/migration-status` returns valid hex revisions, never `"FAILED:"`.

---

### T2: PresetService extensions (update, template viewer, malformed-YAML resilience)

**Goal:** Add `update()`, `get_template_source()` methods; harden `list_all()` to skip malformed YAML files with structured warnings.
**Spec refs:** FR-15, FR-16, SD15, SD21, simulation G4.

**Files:**
- Modify: `backend/app/services/preset_service.py`
- Test: `backend/tests/unit/test_preset_service.py`

**Steps:**

- [ ] **1.** Write failing test `test_update_existing_user_preset`:
  ```python
  def test_update_existing_user_preset(tmp_path):
      svc = PresetService(presets_dir=tmp_path)
      svc.create(name="myfoo", description="orig", facets={"style":"bullet_points","audience":"practitioner","compression":"standard","content_focus":"frameworks_examples"})
      updated = svc.update(name="myfoo", description="updated", label="Foo Updated", facets={"style":"prose","audience":"practitioner","compression":"brief","content_focus":"frameworks_examples"})
      assert updated.description == "updated"
      assert updated.facets["style"] == "prose"
      assert updated.facets["compression"] == "brief"
      reloaded = svc.load("myfoo")
      assert reloaded.facets["style"] == "prose"
  ```

- [ ] **2.** Write failing test `test_get_template_source_returns_base_and_fragments`:
  ```python
  def test_get_template_source_returns_base_and_fragments():
      svc = PresetService()
      result = svc.get_template_source("practitioner_bullets")  # known system preset
      assert result["name"] == "practitioner_bullets"
      assert result["is_system"] is True
      assert "source" in result["base_template"]
      assert len(result["base_template"]["source"]) > 0
      assert len(result["fragments"]) == 4  # 4 facet dimensions
      dims = {f["dimension"] for f in result["fragments"]}
      assert dims == {"style", "audience", "compression", "content_focus"}
      for frag in result["fragments"]:
          assert "source" in frag and len(frag["source"]) > 0
  ```

- [ ] **3.** Write failing test `test_list_all_skips_malformed_yaml_with_warnings`:
  ```python
  def test_list_all_skips_malformed_yaml_with_warnings(tmp_path):
      good = tmp_path / "good.yaml"
      good.write_text('name: good\ndescription: ok\nfacets:\n  style: bullet_points\n  audience: practitioner\n  compression: standard\n  content_focus: frameworks_examples\n')
      bad = tmp_path / "bad.yaml"
      bad.write_text("not: valid: yaml: ::: [\n")
      svc = PresetService(presets_dir=tmp_path)
      presets, warnings = svc.list_all_with_warnings()
      assert len(presets) == 1
      assert presets[0].name == "good"
      assert len(warnings) == 1
      assert "bad.yaml" in warnings[0]["file"]
      assert warnings[0]["error"]  # non-empty error string
  ```

- [ ] **4.** Run tests; expect 3 FAILs:
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_preset_service.py::test_update_existing_user_preset tests/unit/test_preset_service.py::test_get_template_source_returns_base_and_fragments tests/unit/test_preset_service.py::test_list_all_skips_malformed_yaml_with_warnings -v
  ```

- [ ] **5.** Implement:
  - `update(name, description=None, label=None, facets=None) -> Preset`: load existing; raise `PresetError` if `system=True`; merge non-None fields; validate facets via existing `_validate_facets`; write YAML atomically (`tmp_path = path.with_suffix('.yaml.tmp'); write; os.replace(tmp_path, path)`); return reloaded `Preset`.
  - `get_template_source(name) -> dict`: load preset; read `prompts/summarize_section_v1.txt` (or whichever version is current — read from `Settings.summarization.prompt_version`) into `base_template`; for each facet, read `prompts/fragments/{dim}/{value}.txt` into `fragments[i]`; return per spec § 7.2 shape.
  - `list_all_with_warnings() -> tuple[list[Preset], list[dict]]`: iterate `presets_dir.glob('*.yaml')`; for each, try `_parse_file`; on `yaml.YAMLError` or `PresetError`, append `{file: <name>, error: <str>}` to warnings list; log structured warning `log.warning("preset_skipped", file=..., error=...)`. Keep existing `list_all()` returning only the preset list (calls the new method, drops warnings — for back-compat).

- [ ] **6.** Run tests; expect all PASS:
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_preset_service.py -v
  ```

- [ ] **7.** Commit:
  ```bash
  git add backend/app/services/preset_service.py backend/tests/unit/test_preset_service.py
  git commit -m "feat(backend): preset update + template viewer + malformed-YAML resilience"
  ```

**Inline verification:**
- `uv run python -m pytest backend/tests/unit/test_preset_service.py -v` — all green.

---

### T3: Preset CRUD + template API endpoints

**Goal:** Wire HTTP endpoints to the new PresetService methods; expose `warnings[]` on list.
**Spec refs:** FR-15, FR-16, § 7.2, simulation G13, G14.

**Files:**
- Modify: `backend/app/api/routes/summarize_presets.py`
- Test: `backend/tests/integration/test_preset_api.py` (new)

**Steps:**

- [ ] **0. (Pre-flight)** Verify integration-test fixtures exist. The tests in T3, T4, T5 depend on these:
  ```bash
  cd backend
  grep -n "def client\|def tmp_presets_dir\|seeded_book_with_section_summaries\|seeded_book_with_default_summary\|seeded_book_no_summary" tests/conftest.py tests/integration/conftest.py 2>/dev/null
  ```
  - **`client`** fixture (httpx AsyncClient bound to the FastAPI app) — almost certainly already exists; if not, add a standard `pytest_asyncio.fixture` that yields `AsyncClient(app=app, base_url="http://test")`.
  - **`tmp_presets_dir`** fixture — write a `tmp_path`-backed dir, override `Settings.presets_dir`, ensure `PresetService` resolves to it.
  - **`seeded_book_with_section_summaries`** / **`seeded_book_with_default_summary`** / **`seeded_book_no_summary`** — async fixtures that insert a `Book` (and as appropriate, `BookSection` rows + `Summary` rows + set `Book.default_summary_id`) into `db_session`, return the book id.
  Add any missing fixture to `backend/tests/integration/conftest.py` (or the appropriate existing conftest) before writing the new tests below. Commit fixture additions in a separate commit:
  ```bash
  git add backend/tests/integration/conftest.py
  git commit -m "test(backend): add fixtures for preset CRUD + book-summary integration tests"
  ```

- [ ] **1.** Write failing integration test `test_preset_crud_lifecycle`:
  ```python
  # backend/tests/integration/test_preset_api.py
  import pytest

  @pytest.mark.asyncio
  async def test_preset_crud_lifecycle(client, tmp_presets_dir):
      # Create
      r = await client.post("/api/v1/summarize/presets", json={
          "name": "test_user_foo", "label": "Test Foo", "description": "ephemeral",
          "facets": {"style": "bullet_points", "audience": "practitioner",
                     "compression": "standard", "content_focus": "frameworks_examples"}
      })
      assert r.status_code == 201
      assert r.json()["name"] == "test_user_foo"

      # Update
      r = await client.put("/api/v1/summarize/presets/test_user_foo", json={
          "name": "test_user_foo", "label": "Test Foo Updated", "description": "updated",
          "facets": {"style": "prose", "audience": "practitioner",
                     "compression": "brief", "content_focus": "frameworks_examples"}
      })
      assert r.status_code == 200
      assert r.json()["facets"]["style"] == "prose"

      # Template
      r = await client.get("/api/v1/summarize/presets/test_user_foo/template")
      assert r.status_code == 200
      body = r.json()
      assert body["name"] == "test_user_foo"
      assert body["is_system"] is False
      assert "source" in body["base_template"]

      # Template not found
      r = await client.get("/api/v1/summarize/presets/nonexistent/template")
      assert r.status_code == 404

      # Delete
      r = await client.delete("/api/v1/summarize/presets/test_user_foo")
      assert r.status_code == 204

  @pytest.mark.asyncio
  async def test_preset_create_collision_returns_409(client):
      r = await client.post("/api/v1/summarize/presets", json={
          "name": "practitioner_bullets",  # known system preset
          "label": "Dup", "description": "x",
          "facets": {"style":"bullet_points","audience":"practitioner","compression":"standard","content_focus":"frameworks_examples"}
      })
      assert r.status_code == 409
      assert "already exists" in r.json()["detail"].lower()

  @pytest.mark.asyncio
  async def test_preset_delete_system_returns_403(client):
      r = await client.delete("/api/v1/summarize/presets/practitioner_bullets")
      assert r.status_code == 403

  @pytest.mark.asyncio
  async def test_preset_invalid_facet_returns_422(client):
      r = await client.post("/api/v1/summarize/presets", json={
          "name": "test_bad", "label": "Bad", "description": "x",
          "facets": {"style":"NONEXISTENT_VALUE","audience":"practitioner","compression":"standard","content_focus":"frameworks_examples"}
      })
      assert r.status_code == 422
  ```

- [ ] **2.** Run tests; expect FAILs (endpoints don't exist):
  ```bash
  cd backend && uv run python -m pytest tests/integration/test_preset_api.py -v
  ```

- [ ] **3.** Implement endpoints in `backend/app/api/routes/summarize_presets.py`:
  - `POST /api/v1/summarize/presets` → 201 + preset object. Body validated by Pydantic model (`PresetCreateRequest` with `name: constr(regex=r'^[a-z0-9_]+$')`, `label`, `description`, `facets: dict`). On collision (system or user) → 409. On invalid facet → 422.
  - `PUT /api/v1/summarize/presets/{name}` → 200 + preset object. 404 if missing. 403 if system. 422 if invalid.
  - `DELETE /api/v1/summarize/presets/{name}` → 204. 403 if system. 404 if missing.
  - `GET /api/v1/summarize/presets/{name}/template` → 200 + template payload per spec § 7.2. 404 if missing.
  - Modify `GET /api/v1/summarize/presets`: call `service.list_all_with_warnings()`; include `warnings: [...]` in response (new optional field; existing fields unchanged for back-compat).

- [ ] **4.** Run tests; expect all PASS:
  ```bash
  cd backend && uv run python -m pytest tests/integration/test_preset_api.py -v
  ```

- [ ] **5.** Live curl smoke:
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/summarize/presets \
    -H "Content-Type: application/json" \
    -d '{"name":"smoke_foo","label":"Smoke","description":"x","facets":{"style":"bullet_points","audience":"practitioner","compression":"standard","content_focus":"frameworks_examples"}}'
  # Expect: 201 + body with name=smoke_foo

  curl -s http://localhost:8000/api/v1/summarize/presets/smoke_foo/template | python3 -m json.tool
  # Expect: {name, is_system: false, base_template: {...}, fragments: [4 items]}

  curl -s -X DELETE http://localhost:8000/api/v1/summarize/presets/smoke_foo -i | head -1
  # Expect: HTTP/1.1 204
  ```

- [ ] **6.** Commit:
  ```bash
  git add backend/app/api/routes/summarize_presets.py backend/tests/integration/test_preset_api.py
  git commit -m "feat(api): preset CRUD + raw-template endpoints (FR-15, FR-16)"
  ```

**Inline verification:**
- All 4 integration tests green.
- Curl lifecycle smoke succeeds.

---

### T4: Verify book-summary 409 idempotency payload

**Goal:** Confirm `POST /books/{id}/book-summary` returns `active_job_id` in the 409 response (per § 7.5); patch only if missing.
**Spec refs:** FR-02 E11, SD17, § 7.5, simulation G1.

**Files:**
- Modify (conditional): `backend/app/api/routes/book_summary.py`
- Test: `backend/tests/integration/test_book_summary_idempotency.py` (new or extend existing)

**Steps:**

- [ ] **1.** Read current behavior:
  ```bash
  grep -n "409\|already.*progress\|active.*job" backend/app/api/routes/book_summary.py
  ```

- [ ] **2.** Write integration test:
  ```python
  # backend/tests/integration/test_book_summary_idempotency.py
  @pytest.mark.asyncio
  async def test_concurrent_default_summary_returns_409_with_active_job_id(client, seeded_book_with_section_summaries):
      book_id = seeded_book_with_section_summaries
      r1 = await client.post(f"/api/v1/books/{book_id}/book-summary", json={"preset_name": "practitioner_bullets"})
      assert r1.status_code in (201, 202)
      job_id_1 = r1.json().get("job_id") or r1.json().get("id")

      r2 = await client.post(f"/api/v1/books/{book_id}/book-summary", json={"preset_name": "practitioner_bullets"})
      assert r2.status_code == 409
      body = r2.json()
      assert "active_job_id" in body
      assert body["active_job_id"] == job_id_1
      assert "in progress" in body.get("detail", "").lower()
  ```

- [ ] **3.** Run test:
  ```bash
  cd backend && uv run python -m pytest tests/integration/test_book_summary_idempotency.py -v
  ```
  - If PASS: T4 done; skip step 4. Commit only the new test.
  - If FAIL: 409 returned but missing `active_job_id` key (or different shape).

- [ ] **4.** (Conditional) Patch the 409 branch in `book_summary.py` to include `active_job_id` in the response detail object. The active job's id is already queried for the conflict check; just propagate it to the response body.

- [ ] **5.** Re-run; expect PASS.

- [ ] **6.** Commit:
  ```bash
  git add backend/tests/integration/test_book_summary_idempotency.py backend/app/api/routes/book_summary.py
  git commit -m "test(backend): assert 409 idempotency includes active_job_id (FR-02 E11)"
  ```

**Inline verification:**
- `uv run python -m pytest backend/tests/integration/test_book_summary_idempotency.py -v` — green.

---

### T5: Verify GET /books/{id} embeds book-summary Markdown

**Goal:** Confirm `GET /api/v1/books/{id}` already returns the book-summary Markdown (via `Book.default_summary` relationship where `Summary.content_type='book'`); patch shape only if mismatch with § 7.4.
**Spec refs:** FR-02, SD22, § 7.4, simulation G5.

**Files:**
- Verify (no change expected): `backend/app/api/routes/books.py`
- Test: extend `backend/tests/integration/test_books_api.py` (or create)

**Steps:**

- [ ] **1.** Read current response shape from existing tests + route file:
  ```bash
  grep -n "default_summary\|default_summary\|summary_md" backend/app/api/routes/books.py | head -20
  ```

- [ ] **2.** Write/extend integration test:
  ```python
  @pytest.mark.asyncio
  async def test_get_book_includes_default_summary_when_present(client, seeded_book_with_default_summary):
      book_id = seeded_book_with_default_summary
      r = await client.get(f"/api/v1/books/{book_id}")
      assert r.status_code == 200
      body = r.json()
      # Canonical field name is `default_summary` (per plan decision F1)
      summary = body.get("default_summary")
      assert summary is not None
      assert "summary_md" in summary
      assert isinstance(summary["summary_md"], str) and len(summary["summary_md"]) > 0

  @pytest.mark.asyncio
  async def test_get_book_default_summary_is_null_when_absent(client, seeded_book_no_summary):
      book_id = seeded_book_no_summary
      r = await client.get(f"/api/v1/books/{book_id}")
      assert r.status_code == 200
      body = r.json()
      assert body.get("default_summary") is None
  ```

  Per plan decision F1, the canonical field name is `default_summary` (already used by `books.py`). Tests assert directly on that name.

- [ ] **3.** Run tests:
  ```bash
  cd backend && uv run python -m pytest tests/integration/test_books_api.py -v -k "default_summary"
  ```
  - If PASS: T5 done — confirms existing route satisfies SD22 with field name `default_summary`. Update spec § 7.4 in a follow-up commit to use `default_summary` instead of `book_summary`.
  - If FAIL: patch `books.py` to ensure `default_summary` is embedded. Use `selectinload(Book.default_summary)` to avoid lazy-load post-commit (CLAUDE.md gotcha 1).

- [ ] **4.** Commit:
  ```bash
  git add backend/tests/integration/test_books_api.py backend/app/api/routes/books.py
  git commit -m "test(backend): assert GET /books/{id} embeds book summary (FR-02, SD22)"
  ```

**Inline verification:**
- The 2 new tests green.
- Curl: `curl -s http://localhost:8000/api/v1/books/1 | python3 -m json.tool | grep -A3 '"default_summary"'` returns the expected shape.

---

### T6: Move ThemeCard to components/shared/

**Goal:** Relocate `ThemeCard.vue` to the shared components dir per SD7 / FR-17; update all imports.
**Spec refs:** FR-17, SD7.

**Files:**
- Move: `frontend/src/components/settings/ThemeCard.vue` → `frontend/src/components/shared/ThemeCard.vue`
- Move: `frontend/src/components/settings/__tests__/ThemeCard.spec.ts` → `frontend/src/components/shared/__tests__/ThemeCard.spec.ts`
- Modify: `frontend/src/components/settings/ThemeGrid.vue:4` (import)
- (Future): consumers added in T18, T19

**Steps:**

- [ ] **1.** `git mv` the component and its test:
  ```bash
  cd frontend
  mkdir -p src/components/shared/__tests__
  git mv src/components/settings/ThemeCard.vue src/components/shared/ThemeCard.vue
  git mv src/components/settings/__tests__/ThemeCard.spec.ts src/components/shared/__tests__/ThemeCard.spec.ts
  ```

- [ ] **2.** Grep all consumers and update imports:
  ```bash
  grep -rln "components/settings/ThemeCard" src/
  # Edit each: replace 'settings/ThemeCard' with 'shared/ThemeCard'
  ```

- [ ] **3.** Update import path inside the moved test file (the relative import `../ThemeCard.vue` may need to become `../ThemeCard.vue` — verify it resolves; tests are in the sibling `__tests__/` so it should be unchanged).

- [ ] **4.** Build + type-check + run the moved test:
  ```bash
  cd frontend
  npm run type-check
  npm run test:unit -- ThemeCard
  npm run test:unit -- ThemeGrid  # downstream consumer regression
  ```
  Expected: all green.

- [ ] **5.** Grep gate (no consumer left on the old path):
  ```bash
  grep -rln "components/settings/ThemeCard" src/ && echo "FAIL: stale import" && exit 1 || echo "OK"
  ```

- [ ] **6.** Commit:
  ```bash
  cd .. && git add -A && git commit -m "refactor(frontend): relocate ThemeCard to components/shared/ (FR-17 SD7)"
  ```

**Inline verification:**
- `npm run type-check` clean.
- `npm run test:unit -- ThemeCard ThemeGrid` green.
- Grep gate passes.

---

### T7: Compression formatter `~N%`

**Goal:** Replace `value.toFixed(1) + '%'` with `~N%` rounded to nearest 5 across full range.
**Spec refs:** FR-05, SD5, simulation S2 (boundary).

**Files:**
- Modify: `frontend/src/components/book/SectionListTable.vue:38-43`
- Test: `frontend/src/components/book/__tests__/SectionListTable.compression.spec.ts` (new)

**Steps:**

- [ ] **1.** Write failing test:
  ```ts
  // frontend/src/components/book/__tests__/SectionListTable.compression.spec.ts
  import { describe, it, expect } from 'vitest';
  import { formatCompression } from '../SectionListTable.formatters';  // export the formatter

  describe('formatCompression', () => {
    it('rounds 15.5 to ~15%', () => expect(formatCompression(15.5)).toBe('~15%'));
    it('rounds 47.8 to ~50%', () => expect(formatCompression(47.8)).toBe('~50%'));
    it('rounds 3.1 to ~5%', () => expect(formatCompression(3.1)).toBe('~5%'));
    it('rounds 0 to ~0%', () => expect(formatCompression(0)).toBe('~0%'));
    it('rounds 62 to ~60%', () => expect(formatCompression(62)).toBe('~60%'));
    it('rounds 2.4 to ~0%', () => expect(formatCompression(2.4)).toBe('~0%'));
    it('returns em-dash for null/undefined', () => {
      expect(formatCompression(null)).toBe('—');
      expect(formatCompression(undefined)).toBe('—');
    });
  });
  ```

- [ ] **2.** Run test; expect FAIL (no `formatCompression` export):
  ```bash
  cd frontend && npm run test:unit -- SectionListTable.compression
  ```

- [ ] **3.** Implement:
  - Create `frontend/src/components/book/SectionListTable.formatters.ts` exporting:
    ```ts
    export const formatCompression = (raw: number | null | undefined): string => {
      if (raw === null || raw === undefined) return '—';
      const bucketed = Math.round(raw / 5) * 5;
      return `~${bucketed}%`;
    };
    ```
  - In `SectionListTable.vue`, replace the existing `compressionLabel(s)` body around line 38-43 to call `formatCompression(s.compression_ratio_percent)` (or whatever field name the existing code uses — read first).

- [ ] **4.** Run test; expect PASS. Run full file's existing tests for regression:
  ```bash
  npm run test:unit -- SectionListTable
  ```

- [ ] **5.** Live verification (Playwright MCP or browser): navigate to `/books/3`, observe compression column on Sections list — values render as `~15%`, `~25%`, etc. (no `15.5%` or similar).

- [ ] **6.** Commit:
  ```bash
  git add frontend/src/components/book/SectionListTable.formatters.ts frontend/src/components/book/SectionListTable.vue frontend/src/components/book/__tests__/SectionListTable.compression.spec.ts
  git commit -m "feat(frontend): compression formatter ~N% rounded to 5 (FR-05)"
  ```

**Inline verification:**
- New `compression.spec.ts` green; existing `SectionListTable.spec.ts` still green.

---

### T8: MarkdownRenderer scoped styles for bullets and tables

**Goal:** Add scoped `.markdown-body` styles so `<ul>`/`<ol>`/`<table>` render with visible markers + borders.
**Spec refs:** FR-06, FR-10, SD10.

**Files:**
- Modify: `frontend/src/components/reader/MarkdownRenderer.vue`
- Test: `frontend/src/components/reader/__tests__/MarkdownRenderer.styles.spec.ts` (new)

**Steps:**

- [ ] **1.** Write failing test:
  ```ts
  // MarkdownRenderer.styles.spec.ts
  import { mount } from '@vue/test-utils';
  import { describe, it, expect } from 'vitest';
  import MarkdownRenderer from '../MarkdownRenderer.vue';

  describe('MarkdownRenderer scoped styles', () => {
    it('renders root with markdown-body class', () => {
      const wrapper = mount(MarkdownRenderer, { props: { content: '- a\n- b\n' } });
      expect(wrapper.element.classList.contains('markdown-body')).toBe(true);
    });
    it('renders ul with disc list style after styles applied', () => {
      const wrapper = mount(MarkdownRenderer, { props: { content: '- a\n- b\n' }, attachTo: document.body });
      const ul = wrapper.element.querySelector('ul');
      expect(ul).toBeTruthy();
      expect(getComputedStyle(ul!).listStyleType).toBe('disc');
      wrapper.unmount();
    });
    it('renders nested ul with circle', () => {
      const md = '- a\n  - b\n';
      const wrapper = mount(MarkdownRenderer, { props: { content: md }, attachTo: document.body });
      const nested = wrapper.element.querySelector('ul ul');
      expect(nested).toBeTruthy();
      expect(getComputedStyle(nested!).listStyleType).toBe('circle');
      wrapper.unmount();
    });
    it('renders table with collapsed borders', () => {
      const md = '| a | b |\n|---|---|\n| 1 | 2 |\n';
      const wrapper = mount(MarkdownRenderer, { props: { content: md }, attachTo: document.body });
      const tbl = wrapper.element.querySelector('table');
      expect(tbl).toBeTruthy();
      expect(getComputedStyle(tbl!).borderCollapse).toBe('collapse');
      wrapper.unmount();
    });
  });
  ```

- [ ] **2.** Run test; expect 4 FAILs:
  ```bash
  cd frontend && npm run test:unit -- MarkdownRenderer.styles
  ```

- [ ] **3.** Implement: in `MarkdownRenderer.vue`:
  - Add `class="markdown-body"` to the root `<div v-html="renderedHtml">`.
  - Add `<style scoped>` block per spec § 9.6 (uses `:deep()` selectors for ul/ol/li/table/th/td/thead).

- [ ] **4.** Run test; expect all PASS.

- [ ] **5.** Live verification: navigate to a section with a Markdown summary that contains bullets + a table (e.g. `/books/1/sections/6?tab=summary`). DOM check via browser devtools or Playwright MCP `evaluate`:
  ```js
  getComputedStyle(document.querySelector('.markdown-body ul')).listStyleType
  // Expected: "disc"
  ```

- [ ] **6.** Commit:
  ```bash
  git add frontend/src/components/reader/MarkdownRenderer.vue frontend/src/components/reader/__tests__/MarkdownRenderer.styles.spec.ts
  git commit -m "fix(frontend): MarkdownRenderer scoped styles for bullets and tables (FR-06 FR-10)"
  ```

**Inline verification:**
- `npm run test:unit -- MarkdownRenderer` all green (existing + new file).
- Browser computed style check returns `disc` / `circle` / `collapse`.

---

### T9: TocDropdown char-count fix

**Goal:** TOC dropdown shows correct per-section character count matching Book Detail Sections table.
**Spec refs:** FR-08, SD8.

**Files:**
- Modify: `frontend/src/components/reader/TOCDropdown.vue`
- Modify (possibly): `frontend/src/components/book/SectionListTable.vue` — confirm compact-mode prop names
- Test: extend `frontend/src/components/reader/__tests__/TOCDropdown.spec.ts`

**Steps:**

- [ ] **1.** Read `TOCDropdown.vue` to identify how it builds the section list passed to `<SectionListTable :sections="..." compact />`. Confirm whether `content_char_count` is preserved or dropped during the mapping. Most likely cause: TOC fetches a lighter-weight `Section` shape that omits `content_char_count`.

- [ ] **2.** Write/extend failing test:
  ```ts
  it('renders content_char_count for non-empty sections', async () => {
    const sections = [
      { id: 1, title: 'Ch 1', content_char_count: 1234, order_index: 0, depth: 0 },
      { id: 2, title: 'Ch 2', content_char_count: 5678, order_index: 1, depth: 0 },
    ];
    const wrapper = mount(TOCDropdown, { props: { sections, currentSectionId: 1 } });
    await wrapper.find('.toc-trigger').trigger('click');
    const text = wrapper.text();
    // Allow either "1,234" or "1234" formatting
    expect(text).toMatch(/1[,]?234/);
    expect(text).toMatch(/5[,]?678/);
  });
  ```

- [ ] **3.** Run; expect FAIL.

- [ ] **4.** Implement: ensure `content_char_count` flows through to compact-mode rows. Two likely paths:
  - **Path A (preferred per SD8):** TOC's `sections` prop already contains `content_char_count` (from `SectionBrief` API shape). Verify the compact-mode template in `SectionListTable.vue` renders it (it should — the same column works in non-compact mode). If compact mode hides the column, add a `:show-char-count="true"` prop or remove the column-hiding logic for compact mode.
  - **Path B:** TOC builds a stripped-down section object internally; map `content_char_count` through.

- [ ] **5.** Run test; expect PASS. Run full TOC test file for regression.

- [ ] **6.** Live verification: navigate to `/books/3/sections/<any>`, click TOC dropdown trigger, observe non-zero chars per section.

- [ ] **7.** Commit:
  ```bash
  git add frontend/src/components/reader/TOCDropdown.vue frontend/src/components/book/SectionListTable.vue frontend/src/components/reader/__tests__/TOCDropdown.spec.ts
  git commit -m "fix(frontend): TOC dropdown shows real per-section char counts (FR-08 SD8)"
  ```

**Inline verification:**
- TOCDropdown.spec.ts all green.
- Browser TOC dropdown shows non-zero counts on a real book.

---

### T10: ReadingArea footer prev/next nav

**Goal:** Inline `← Previous: <title>` / `Next: <title> →` link pair at the end of reader content. Preserves `?tab=`. Hides on single-section book.
**Spec refs:** FR-07, SD6, SD14, simulation G16.

**Files:**
- Create: `frontend/src/components/reader/ReadingAreaFooterNav.vue`
- Modify: `frontend/src/components/reader/ReadingArea.vue` — add `<slot name="footer">` after the article body
- Modify: `frontend/src/views/BookDetailView.vue` — pass the footer-nav into the slot for both Summary and Original tab usages
- Test: `frontend/src/components/reader/__tests__/ReadingAreaFooterNav.spec.ts` (new)

**Steps:**

- [ ] **1.** Write failing tests:
  ```ts
  describe('ReadingAreaFooterNav', () => {
    const prev = { id: 5, title: 'Prev Section' };
    const next = { id: 7, title: 'Next Section' };

    it('renders both links when both prev and next exist', () => {
      const wrapper = mount(ReadingAreaFooterNav, { props: { bookId: 3, prev, next, currentTab: 'summary' } });
      const text = wrapper.text();
      expect(text).toContain('← Previous: Prev Section');
      expect(text).toContain('Next: Next Section →');
      const links = wrapper.findAll('a');
      expect(links.length).toBe(2);
      expect(links[0].attributes('href')).toContain('/books/3/sections/5');
      expect(links[0].attributes('href')).toContain('tab=summary');
      expect(links[1].attributes('href')).toContain('/books/3/sections/7');
      expect(links[1].attributes('href')).toContain('tab=summary');
    });

    it('renders only Next on first section', () => {
      const wrapper = mount(ReadingAreaFooterNav, { props: { bookId: 3, prev: null, next, currentTab: 'original' } });
      expect(wrapper.text()).not.toContain('Previous');
      expect(wrapper.text()).toContain('Next: Next Section →');
      expect(wrapper.findAll('a').length).toBe(1);
    });

    it('renders only Previous on last section', () => {
      const wrapper = mount(ReadingAreaFooterNav, { props: { bookId: 3, prev, next: null, currentTab: 'summary' } });
      expect(wrapper.text()).toContain('← Previous: Prev Section');
      expect(wrapper.text()).not.toContain('Next:');
    });

    it('renders nothing when both prev and next are null', () => {
      const wrapper = mount(ReadingAreaFooterNav, { props: { bookId: 3, prev: null, next: null, currentTab: 'summary' } });
      expect(wrapper.findAll('a').length).toBe(0);
      // Component returns nothing visible
      expect(wrapper.text().trim()).toBe('');
    });

    it('preserves currentTab=original in hrefs', () => {
      const wrapper = mount(ReadingAreaFooterNav, { props: { bookId: 3, prev, next, currentTab: 'original' } });
      const links = wrapper.findAll('a');
      links.forEach(link => expect(link.attributes('href')).toContain('tab=original'));
    });
  });
  ```

- [ ] **2.** Run; expect 5 FAILs (component doesn't exist).

- [ ] **3.** Implement `ReadingAreaFooterNav.vue` per spec § 9.4:
  ```vue
  <script setup lang="ts">
  import { computed } from 'vue';
  defineProps<{
    bookId: number;
    prev: { id: number; title: string } | null;
    next: { id: number; title: string } | null;
    currentTab: 'summary' | 'original';
  }>();
  </script>

  <template>
    <footer v-if="prev || next" class="reading-area__footer-nav">
      <router-link v-if="prev" :to="{ path: `/books/${bookId}/sections/${prev.id}`, query: { tab: currentTab } }" class="footer-nav__prev">
        ← Previous: {{ prev.title }}
      </router-link>
      <span v-else></span>
      <router-link v-if="next" :to="{ path: `/books/${bookId}/sections/${next.id}`, query: { tab: currentTab } }" class="footer-nav__next">
        Next: {{ next.title }} →
      </router-link>
      <span v-else></span>
    </footer>
  </template>

  <style scoped>
  .reading-area__footer-nav {
    display: flex;
    justify-content: space-between;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--color-border);
    color: var(--color-text-secondary);
    opacity: 0.7;
  }
  .reading-area__footer-nav a { color: inherit; text-decoration: none; }
  .reading-area__footer-nav a:hover { text-decoration: underline; opacity: 1; }
  </style>
  ```
  (Tests assert plain `<a>`, but `<router-link>` renders as `<a>` — both pass.)

- [ ] **4.** Modify `ReadingArea.vue`: add `<slot name="footer" />` after the `<MarkdownRenderer>` element inside `<article>`.

- [ ] **5.** Modify `BookDetailView.vue`: in both the Summary and Original `<ReadingArea>` usages (~lines 238-261), add the footer-nav into the slot:
  ```vue
  <ReadingArea ... >
    <template #footer>
      <ReadingAreaFooterNav :book-id="reader.bookId" :prev="reader.prevSection" :next="reader.nextSection" :current-tab="activeTab" />
    </template>
  </ReadingArea>
  ```
  Use the existing `reader.prevSection` / `reader.nextSection` (or whatever the store exposes — read first).

- [ ] **6.** Run tests; expect PASS.

- [ ] **7.** Live verification: navigate to `/books/3/sections/<middle>?tab=summary`, scroll to bottom — see both links. Navigate to first section — see only Next. Navigate to last section — see only Previous. Click Next on a Summary tab — lands on next section's Summary tab.

- [ ] **8.** Commit:
  ```bash
  git add frontend/src/components/reader/ReadingAreaFooterNav.vue frontend/src/components/reader/ReadingArea.vue frontend/src/views/BookDetailView.vue frontend/src/components/reader/__tests__/ReadingAreaFooterNav.spec.ts
  git commit -m "feat(frontend): inline prev/next footer nav on reader (FR-07 SD6 SD14)"
  ```

**Inline verification:**
- 5 ReadingAreaFooterNav tests green.
- Browser walkthrough: middle / first / last / single-section all behave per spec.

---

### T11: BookDetailTabs strip + ?tab= routing

**Goal:** Add Overview / Summary / Sections tab strip on `BookOverviewView`. Active tab driven by `route.query.tab`. Switching tabs uses `router.replace`.
**Spec refs:** FR-01 (parts), FR-02 (tab presence), SD1, simulation S24.

**Files:**
- Modify: `frontend/src/views/BookOverviewView.vue` (~499 LOC; major template change)
- Test: `frontend/src/views/__tests__/BookOverviewView.tabs.spec.ts` (new)

**Steps:**

- [ ] **1.** Write failing test:
  ```ts
  describe('BookOverviewView tab strip', () => {
    it('renders three tab buttons: Overview, Summary, Sections', async () => {
      const wrapper = mountWithRouter(BookOverviewView, { route: '/books/3' });
      const tabs = wrapper.findAll('[role="tab"]');
      expect(tabs.length).toBe(3);
      expect(tabs.map(t => t.text())).toEqual(['Overview', 'Summary', 'Sections']);
    });
    it('defaults to overview tab when ?tab= is absent', () => {
      const wrapper = mountWithRouter(BookOverviewView, { route: '/books/3' });
      const active = wrapper.find('[role="tab"][aria-selected="true"]');
      expect(active.text()).toBe('Overview');
    });
    it('respects ?tab=summary on initial mount', () => {
      const wrapper = mountWithRouter(BookOverviewView, { route: '/books/3?tab=summary' });
      const active = wrapper.find('[role="tab"][aria-selected="true"]');
      expect(active.text()).toBe('Summary');
    });
    it('updates URL via router.replace when a tab is clicked', async () => {
      const { wrapper, router } = mountWithRouter(BookOverviewView, { route: '/books/3' });
      const replaceSpy = vi.spyOn(router, 'replace');
      await wrapper.findAll('[role="tab"]')[1].trigger('click');
      expect(replaceSpy).toHaveBeenCalledWith(expect.objectContaining({ query: expect.objectContaining({ tab: 'summary' }) }));
    });
  });
  ```

- [ ] **2.** Run; expect FAILs.

- [ ] **3.** Implement: refactor `BookOverviewView.vue` template:
  - Above the existing main content, add a tab strip (3 buttons with `role="tab"`, `aria-selected` on active) bound to a computed `activeTab` derived from `route.query.tab` (default `'overview'`).
  - Wrap the existing Overview content (cover, meta, status, suggested tags, etc.) in a panel rendered when `activeTab === 'overview'`.
  - Render `<BookSummaryTab :book="book" />` (component from T13) when `activeTab === 'summary'` — for now during T11, render a placeholder `<div>Summary tab placeholder</div>` and leave the real component for T13.
  - Render `<SectionListTable :sections="book.sections" />` when `activeTab === 'sections'` (move existing rendering).
  - Tab click handler: `router.replace({ query: { ...route.query, tab: <new> } })`.

- [ ] **4.** Run tests; expect PASS for all 4. Run existing `BookOverviewView.spec.ts` for regression.

- [ ] **5.** Live verification: navigate to `/books/3` → Overview tab active. Click Sections → URL becomes `/books/3?tab=sections` and table renders. Click Summary → `/books/3?tab=summary` (placeholder for now). Reload `/books/3?tab=summary` directly → Summary tab active on initial render (no flash of Overview).

- [ ] **6.** Commit:
  ```bash
  git add frontend/src/views/BookOverviewView.vue frontend/src/views/__tests__/BookOverviewView.tabs.spec.ts
  git commit -m "feat(frontend): add Book Detail tab strip with ?tab= routing (FR-02 SD1)"
  ```

**Inline verification:**
- 4 new tab-strip tests green; existing BookOverviewView tests pass.
- Browser walkthrough: tab clicks update URL; deep link respects `?tab=`.

---

### T12: OverflowMenu reshape + toolbar to single CTA

**Goal:** Single primary `Read` CTA + overflow with `Generate/Read book summary`, `Customize reader…`, `Edit structure`, `Re-import`, `Export Markdown`, `Delete`. No "Customize text" anywhere. Popover anchored to overflow trigger. Customize-reader applies to global reader defaults (no scope-switching).
**Spec refs:** FR-01, FR-03, FR-04, SD3, SD4, SD11.

**Files:**
- Modify: `frontend/src/views/BookOverviewView.vue` — toolbar refactor (lines 76-95)
- Modify: `frontend/src/components/book/OverflowMenu.vue`
- Test: extend `frontend/src/components/book/__tests__/OverflowMenu.spec.ts`

**Steps:**

- [ ] **1.** Extend OverflowMenu.spec.ts:
  ```ts
  it('renders the canonical menu items', async () => {
    const wrapper = mount(OverflowMenu, { props: { hasBookSummary: false, /* other props */ } });
    await wrapper.find('.overflow-trigger').trigger('click');
    const items = wrapper.findAll('[role="menuitem"]').map(i => i.text());
    expect(items).toContain('Generate book summary');
    expect(items).toContain('Customize reader…');
    expect(items).toContain('Edit structure');
    expect(items).toContain('Re-import');
    expect(items).toContain('Export Markdown');
    expect(items).toContain('Delete book');
    // negative assertions
    expect(items).not.toContain('Customize text');
    expect(items).not.toContain('Customize text…');
  });

  it('shows Read book summary when book has a summary', async () => {
    const wrapper = mount(OverflowMenu, { props: { hasBookSummary: true } });
    await wrapper.find('.overflow-trigger').trigger('click');
    const items = wrapper.findAll('[role="menuitem"]').map(i => i.text());
    expect(items).toContain('Read book summary');
    expect(items).not.toContain('Generate book summary');
  });
  ```

- [ ] **2.** Run; expect FAIL.

- [ ] **3.** Implement OverflowMenu changes:
  - Accept `hasBookSummary: boolean` prop.
  - First menu item conditional: `Generate book summary` when `!hasBookSummary`, else `Read book summary`.
  - Add menu items: Re-import, Export Markdown, Delete book (likely already exist on the surrounding view; move them into the menu).
  - Remove any "Customize text" item.
  - Customize reader handler emits `open-reader-settings` (existing). The popover's anchor is the trigger button; verify it's positioned via CSS `top: calc(100% + 4px); right: 0` already in place (per code study, it is).

- [ ] **4.** Implement BookOverviewView toolbar changes (lines 76-95 area):
  - Keep one primary `Read` CTA (routes to `/books/:id/sections/<first>?tab=original`).
  - Remove the disabled "Read Summary" button.
  - Remove the floating "Customize…" link outside the menu.
  - Remove the legacy "Export Markdown" button if it's currently a sibling of overflow (move into menu).
  - Pass `:has-book-summary="!!book.default_summary"` (or whatever field name from T5) to `<OverflowMenu>`.

- [ ] **5.** Run tests; expect PASS.

- [ ] **6.** Live verification: navigate to `/books/3`. Toolbar shows only one Read CTA + overflow `⋯`. Click overflow → menu has the canonical items, no "Customize text". Click Customize reader → popover opens anchored to the trigger (not detached at random coords). Themes load (no "Couldn't load themes" error per simulation E10/AC#4). Popover closes via Esc and outside-click.

- [ ] **7.** Commit:
  ```bash
  git add frontend/src/views/BookOverviewView.vue frontend/src/components/book/OverflowMenu.vue frontend/src/components/book/__tests__/OverflowMenu.spec.ts
  git commit -m "feat(frontend): single Read CTA + reshaped overflow menu (FR-01 FR-03 FR-04)"
  ```

**Inline verification:**
- Extended OverflowMenu.spec.ts green.
- Browser walkthrough: toolbar correct; Customize reader opens anchored popover with themes loaded.

---

### T13: BookSummaryTab component (empty / in-progress / failed / populated)

**Goal:** New `BookSummaryTab.vue` component renders 4 distinct states. Generate CTA hits POST `/books/{id}/book-summary`; handles 409 by attaching to existing job. Subscribes to existing SSE channel for cross-tab freshness.
**Spec refs:** FR-02, SD17–SD22, simulation E11–E15.

**Files:**
- Create: `frontend/src/components/book/BookSummaryTab.vue`
- Modify: `frontend/src/views/BookOverviewView.vue` — replace the placeholder from T11 with `<BookSummaryTab>`
- Test: `frontend/src/components/book/__tests__/BookSummaryTab.spec.ts` (new)

**Steps:**

- [ ] **1.** Write failing tests:
  ```ts
  describe('BookSummaryTab', () => {
    const baseBook = (overrides = {}) => ({ id: 3, sections: [{id:1, summary_id: 10}, {id:2, summary_id: null}], default_summary: null, last_summary_failure: null, ...overrides });

    it('Empty state with N>=1 sections summarized: shows progress text and enabled Generate CTA', () => {
      const book = baseBook();
      const wrapper = mount(BookSummaryTab, { props: { book } });
      expect(wrapper.text()).toMatch(/1 of 2 sections summarized/);
      const cta = wrapper.find('button.generate-cta');
      expect(cta.attributes('disabled')).toBeUndefined();
    });

    it('Empty state with 0 sections summarized: Generate CTA disabled', () => {
      const book = baseBook({ sections: [{id:1, summary_id: null}] });
      const wrapper = mount(BookSummaryTab, { props: { book } });
      const cta = wrapper.find('button.generate-cta');
      expect(cta.attributes('disabled')).toBeDefined();
      expect(wrapper.text()).toMatch(/at least one section/i);
    });

    it('Populated state: renders Markdown body and Read Section Summaries action', () => {
      const book = baseBook({ default_summary: { summary_md: '# Title\n\nBody.', generated_at: '2026-05-01T00:00:00Z' } });
      const wrapper = mount(BookSummaryTab, { props: { book } });
      expect(wrapper.find('.markdown-body').exists()).toBe(true);
      expect(wrapper.text()).toContain('Read Section Summaries');
      expect(wrapper.text()).toContain('Regenerate');
    });

    it('Failed state: shows error and Retry CTA when last job failed and no summary exists', () => {
      const book = baseBook({ last_summary_failure: { code: 'LLM_TIMEOUT', stderr: 'Provider timeout', at: '2026-05-01T00:00:00Z' } });
      const wrapper = mount(BookSummaryTab, { props: { book } });
      expect(wrapper.text()).toContain('Provider timeout');
      expect(wrapper.find('button.retry-cta').exists()).toBe(true);
    });
  });
  ```

- [ ] **2.** Run; expect FAILs (component doesn't exist).

- [ ] **3.** Implement `BookSummaryTab.vue`:
  - Props: `book` (the full Book object from `GET /books/{id}` response, including `default_summary` per T5 and `last_summary_failure`).
  - Compute counts: `summarizedCount = book.sections.filter(s => s.summary_id !== null).length`, `totalCount = book.sections.length`.
  - Compute current state machine:
    - `populated` when `book.default_summary !== null`
    - `inProgress` when an active processing-job exists for this book (poll/SSE-driven; component holds a local `activeJob` ref)
    - `failed` when `book.last_summary_failure !== null && !book.default_summary` (and no active job)
    - `empty` otherwise
  - Render branch per state. Wireframe `02_book-detail-summary-tab_desktop-web.html` is the visual reference.
  - Generate CTA: `POST /api/v1/books/{id}/book-summary`. On 202/201: extract `job_id`, set `activeJob`, subscribe to SSE `/api/v1/processing/{job_id}/stream`. On 409: extract `active_job_id` from body, attach SSE to that. On other error: surface a toast.
  - Cancel button: `POST /api/v1/processing/{job_id}/cancel`; on success, clear `activeJob` and emit a `book-refetch` event for parent to re-fetch.
  - Retry button (Failed state): same path as Generate.
  - Read Section Summaries action: routes to `/books/{book.id}/sections/{firstSection.id}?tab=summary` where `firstSection = book.sections.find(s => s.order_index === Math.min(...book.sections.map(s => s.order_index)))` — or simply `book.sections[0]` if the API returns them ordered (it does per code study).
  - SSE event handlers: on `processing_completed` → emit `book-refetch`; on `processing_failed` → emit `book-refetch` and switch to Failed state.

- [ ] **4.** Replace T11's placeholder in `BookOverviewView.vue`: `<BookSummaryTab :book="book" @book-refetch="loadBook" />`.

- [ ] **5.** Run tests; expect PASS.

- [ ] **6.** Live verification (Playwright MCP):
  - Empty state: book with no `default_summary`, ≥1 section summarized → progress text + enabled Generate.
  - 0-summarized: zero section summaries → Generate disabled.
  - Click Generate → in-progress state → wait for completion → populated state with Markdown.
  - Open the same book in another tab → Click Generate in tab A → tab B receives SSE event → refreshes (or remains stable). Verify cross-tab idempotency: tab B click also fires Generate → 409 → attaches to active job → both tabs render the same in-progress state.
  - Cancel: kick off a Generate, click Cancel → returns to Empty state.

- [ ] **7.** Commit:
  ```bash
  git add frontend/src/components/book/BookSummaryTab.vue frontend/src/views/BookOverviewView.vue frontend/src/components/book/__tests__/BookSummaryTab.spec.ts
  git commit -m "feat(frontend): BookSummaryTab with empty/in-progress/failed/populated states (FR-02)"
  ```

**Inline verification:**
- BookSummaryTab.spec.ts all green.
- Manual cross-tab idempotency walkthrough succeeds without duplicate jobs.

---

### T14: Side panels read reader-theme variables

**Goal:** `ContextSidebar` and `AIChatTab` adopt the active reader theme; with reader on Dark, sidebar bg is no longer `rgb(255,255,255)`.
**Spec refs:** FR-09, SD10 (option B from spec § 9.7 — substitute variables, not move scope).

**Files:**
- Modify: `frontend/src/components/sidebar/ContextSidebar.vue` (style block)
- Modify: `frontend/src/components/sidebar/AIChatTab.vue` (style block)

**Steps:**

- [ ] **1.** Patch the scoped style blocks. Replace `var(--color-bg)` → `var(--reader-bg, var(--color-bg))`, `var(--color-text-primary)` → `var(--reader-text, var(--color-text-primary))`, `var(--color-border)` → `var(--reader-border, var(--color-border))`. (Confirm exact existing variable names by reading the file first; the substitution pattern is "fall back to app default when reader var is unset.")

- [ ] **2.** Live verification (Playwright MCP):
  ```js
  // 1. Switch reader to Dark theme
  // 2. Open Annotations or AI Chat tab in sidebar
  // 3. Evaluate:
  getComputedStyle(document.querySelector('.context-sidebar')).backgroundColor
  // Expected: NOT "rgb(255, 255, 255)". Should match the reader's --reader-bg value.
  ```

- [ ] **3.** No-regression check: switch reader to default light theme. Sidebar should render with the app's normal background (not transparent).

- [ ] **4.** Commit:
  ```bash
  git add frontend/src/components/sidebar/ContextSidebar.vue frontend/src/components/sidebar/AIChatTab.vue
  git commit -m "fix(frontend): side panels follow reader-theme scope (FR-09)"
  ```

**Inline verification:**
- Browser computed style under Dark theme: `.context-sidebar` background ≠ white.
- Light theme regression: sidebar still readable.

---

### T15: Annotation Summary-tab filter + content_type wiring

**Goal:** Load annotations of both `content_type='section_content'` and `'section_summary'`. Render the right subset on each tab. New highlights created on Summary tab persist with `content_type='section_summary'`.
**Spec refs:** FR-12, SD9, SD12, P2 (active-tab in BookDetailView local state).

**Files:**
- Modify: `frontend/src/views/BookDetailView.vue:104,109` (annotation loader) and the highlight-create handler
- Test: `frontend/src/views/__tests__/BookDetailView.annotations.spec.ts` (new) — unit test for the create handler's `content_type` selection

**Steps:**

- [ ] **1.** Read current annotation loader and create handler in `BookDetailView.vue`. Identify where the active tab (Original vs Summary) is stored locally. Per P2, this is local state — likely a ref like `contentMode` or `activeTab`. To make the create logic unit-testable, extract the `content_type` selection into a small pure helper in the same file (or in `frontend/src/utils/annotationContentType.ts`):
  ```ts
  export const annotationContentTypeFor = (activeTab: 'summary' | 'original'): 'section_summary' | 'section_content' =>
    activeTab === 'summary' ? 'section_summary' : 'section_content';
  ```

- [ ] **2.** Write failing unit test:
  ```ts
  // frontend/src/views/__tests__/BookDetailView.annotations.spec.ts (or utils/__tests__/annotationContentType.spec.ts)
  import { describe, it, expect } from 'vitest';
  import { annotationContentTypeFor } from '@/utils/annotationContentType';

  describe('annotationContentTypeFor', () => {
    it('returns section_summary on summary tab', () => {
      expect(annotationContentTypeFor('summary')).toBe('section_summary');
    });
    it('returns section_content on original tab', () => {
      expect(annotationContentTypeFor('original')).toBe('section_content');
    });
  });
  ```
  Run: `npm run test:unit -- annotationContentType`. Expected: FAIL (helper does not exist yet).

- [ ] **4.** Implement the `annotationContentTypeFor` helper at the path imported above. Run the test; expect PASS.

- [ ] **5.** Patch the loader:
  - If the API call has a `content_type=section_content` query param: change to omit the filter (load both) OR pass an array `content_type[]=section_content&content_type[]=section_summary`. Verify backend accepts the chosen shape (per code study, `routes/annotations.py` already enriches both types; API contract supports the broadened request).
  - Split the result client-side: `contentAnnotations = all.filter(a => a.content_type === 'section_content')`, `summaryAnnotations = all.filter(a => a.content_type === 'section_summary')`.
  - Pass `contentAnnotations` to the Original-tab `<ReadingArea>` and `summaryAnnotations` to the Summary-tab `<ReadingArea>`.

- [ ] **6.** Patch the highlight-create handler:
  - Read the active tab from local state.
  - Pass `content_type: annotationContentTypeFor(activeTab)` in the `POST /api/v1/annotations` payload.

- [ ] **7.** Live verification (Playwright MCP — this AC has a verified failure mode in the spec):
  - Pre-fix verified failure (must reproduce): navigate to `/books/1/sections/6?tab=summary`. Currently API returns 2 highlight annotations on `section_content`; Summary tab DOM has 0 `<span class="highlight">`.
  - Post-fix:
    - Navigate to `/books/1/sections/6?tab=original` → 2 `<span class="highlight">` (regression check: Original tab still works).
    - Switch to `/books/1/sections/6?tab=summary` → 0 highlights initially (no `section_summary` annotations yet).
    - Select text on the Summary tab and create a highlight via the floating toolbar.
    - Reload `?tab=summary` → 1 `<span class="highlight">` rendered.
    - Switch to `?tab=original` → still 2 highlights (the `section_summary` one isn't projected onto original, per spec § Non-goals).
  - DOM check via `document.querySelectorAll('.markdown-body span.highlight').length`.

- [ ] **8.** Commit:
  ```bash
  git add frontend/src/views/BookDetailView.vue frontend/src/utils/annotationContentType.ts frontend/src/views/__tests__/BookDetailView.annotations.spec.ts
  git commit -m "fix(frontend): annotations render on Summary tab; create handler honors active tab (FR-12)"
  ```

**Inline verification:**
- `npm run test:unit -- annotationContentType` green (2 cases).
- Manual: `/books/1/sections/6?tab=summary` no longer renders 0 highlights when the user creates one.
- Regression: Original tab highlight count unchanged.

---

### T16: App shell — IconRail + TopBar router-link

**Goal:** BC icon and app-bar title are clickable router-links to `/`.
**Spec refs:** FR-11.

**Files:**
- Modify: `frontend/src/components/app/IconRail.vue:14-32`
- Modify: `frontend/src/components/app/TopBar.vue:45-59`

**Steps:**

- [ ] **1.** `IconRail.vue`: wrap the BC `<span>` (or its parent block) in `<router-link to="/">`. Add CSS so the link inherits color, has a focus ring, and shows `cursor: pointer`.

- [ ] **2.** `TopBar.vue`: locate the title element rendered from the computed page-title (line ~36/45). Wrap in `<router-link to="/">`. Same CSS treatment.

- [ ] **3.** Live verification:
  - Navigate to `/books/3`. Click BC icon → URL becomes `/`. Hover BC → cursor pointer visible.
  - Tab into BC icon → focus ring visible.
  - Click app-bar title → also `/`.

- [ ] **4.** Commit:
  ```bash
  git add frontend/src/components/app/IconRail.vue frontend/src/components/app/TopBar.vue
  git commit -m "fix(frontend): app-shell logo and title route to / (FR-11)"
  ```

**Inline verification:**
- Manual: both clickable, focus rings visible, cursor pointer.

---

### T17: DatabaseSettings — remove stripes + Unknown rendering

**Goal:** Remove alt-row stripes; render `Unknown` + tooltip when migration revision is null/non-hex.
**Spec refs:** FR-13 (frontend), FR-14, simulation E1.

**Files:**
- Modify: `frontend/src/components/settings/DatabaseSettings.vue`

**Steps:**

- [ ] **1.** Remove the `nth-child(even)` rule at lines 188-190. Keep all other styling.

- [ ] **2.** Add a defensive renderer for `current` and `latest`:
  ```vue
  <script setup>
  const isHexRevision = (v) => typeof v === 'string' && /^[a-f0-9]{8,}$/.test(v);
  const display = (v) => isHexRevision(v) ? v : 'Unknown';
  </script>
  ```
  Use `{{ display(store.migrationStatus.current) }}` etc. If `store.migrationStatus.error` is non-null, render a tooltip (`title="..."`) on the Unknown badge.

- [ ] **3.** Live verification:
  - Healthy backend: navigate to `/settings/database` → revisions render as 12-char hex; no row stripes.
  - Force error path: temporarily break `alembic.ini` path or stop the engine — refresh → Unknown + tooltip with error.

- [ ] **4.** Commit:
  ```bash
  git add frontend/src/components/settings/DatabaseSettings.vue
  git commit -m "fix(frontend): DatabaseSettings remove stripes + render Unknown defensively (FR-13 FR-14)"
  ```

**Inline verification:**
- Browser: no alt-row striping; revisions render correctly; Unknown tooltip shows error detail.

---

### T18: ReadingSettings preset chips → shared ThemeCard

**Goal:** Replace `<div class="preset-chip">` (lines 62-69) with `<ThemeCard>` from `@/components/shared/ThemeCard.vue` so reading-preset pills get button semantics, hover/cursor, focus ring.
**Spec refs:** FR-17, SD13, depends on T6.

**Files:**
- Modify: `frontend/src/components/settings/ReadingSettings.vue:62-69`

**Steps:**

- [ ] **1.** Read existing template (lines 62-69): mapping iteration over `presets`, rendering a `<div class="preset-chip">{{ preset.name }}</div>`.

- [ ] **2.** Replace with `<ThemeCard>` per preset, mapping props sensibly: `:label="preset.name"`, `:bg="preset.bg ?? 'var(--color-bg)'"`, `:fg="preset.fg ?? 'var(--color-text-primary)'"`, `:active="preset.id === activePresetId"`, click handler to set active preset (existing logic).

- [ ] **3.** Remove the old `.preset-chip` CSS rules (lines ~141-149 per code study).

- [ ] **4.** Live verification:
  - Navigate to `/settings/reading` (or wherever ReadingSettings renders) → preset pills now look like the reader settings popover ThemeCards (consistent look).
  - Tab into a pill → focus ring visible.
  - Hover → cursor pointer.

- [ ] **5.** Commit:
  ```bash
  git add frontend/src/components/settings/ReadingSettings.vue
  git commit -m "fix(frontend): ReadingSettings uses shared ThemeCard for preset pills (FR-17)"
  ```

**Inline verification:**
- Manual: pills look like ReaderSettingsPopover cards; focus + hover work.

---

### T19a: PresetCreateEditForm component

**Goal:** Standalone form component with name/label/description inputs + 4 facet card grids; emits `save`/`cancel`.
**Spec refs:** FR-15, SD13, depends on T6 (ThemeCard for cards — optional; cards may use a lighter local component).

**Files:**
- Create: `frontend/src/components/settings/PresetCreateEditForm.vue`
- Test: `frontend/src/components/settings/__tests__/PresetCreateEditForm.spec.ts` (new)

**Steps:**

- [ ] **1.** Write failing test:
  ```ts
  describe('PresetCreateEditForm', () => {
    const facetOptions = {
      style: ['bullet_points', 'prose'],
      audience: ['practitioner', 'academic'],
      compression: ['brief', 'standard', 'detailed'],
      content_focus: ['frameworks_examples', 'concepts'],
    };

    it('disables Save when name is empty', () => {
      const wrapper = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } });
      expect(wrapper.find('button.save').attributes('disabled')).toBeDefined();
    });
    it('disables Save when name has invalid chars', async () => {
      const wrapper = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } });
      await wrapper.find('input[name="name"]').setValue('Invalid Name!');
      expect(wrapper.text()).toMatch(/lowercase|a-z0-9_/i);
      expect(wrapper.find('button.save').attributes('disabled')).toBeDefined();
    });
    it('disables Save when label is empty even if name is valid', async () => {
      const wrapper = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } });
      await wrapper.find('input[name="name"]').setValue('valid_name');
      expect(wrapper.find('button.save').attributes('disabled')).toBeDefined();
    });
    it('emits save with full payload when all fields valid', async () => {
      const wrapper = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } });
      await wrapper.find('input[name="name"]').setValue('my_preset');
      await wrapper.find('input[name="label"]').setValue('My Preset');
      // Select first card in each facet grid
      const grids = wrapper.findAll('.facet-grid');
      for (const grid of grids) {
        await grid.find('button.facet-card').trigger('click');
      }
      await wrapper.find('button.save').trigger('click');
      const emitted = wrapper.emitted('save');
      expect(emitted).toBeTruthy();
      const payload = emitted![0][0] as any;
      expect(payload.name).toBe('my_preset');
      expect(payload.label).toBe('My Preset');
      expect(payload.facets).toHaveProperty('style');
      expect(payload.facets).toHaveProperty('audience');
      expect(payload.facets).toHaveProperty('compression');
      expect(payload.facets).toHaveProperty('content_focus');
    });
    it('emits cancel when cancel clicked', async () => {
      const wrapper = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } });
      await wrapper.find('button.cancel').trigger('click');
      expect(wrapper.emitted('cancel')).toBeTruthy();
    });
    it('mode=edit prefills from initial prop', () => {
      const initial = { name: 'foo', label: 'Foo', description: 'desc',
        facets: { style: 'prose', audience: 'practitioner', compression: 'brief', content_focus: 'concepts' } };
      const wrapper = mount(PresetCreateEditForm, { props: { mode: 'edit', facetOptions, initial } });
      expect((wrapper.find('input[name="name"]').element as HTMLInputElement).value).toBe('foo');
      // name field is read-only in edit mode
      expect(wrapper.find('input[name="name"]').attributes('readonly')).toBeDefined();
    });
  });
  ```

- [ ] **2.** Run; expect 6 FAILs.

- [ ] **3.** Implement `PresetCreateEditForm.vue` per the test contract:
  - Props: `mode: 'create' | 'edit'`, `facetOptions: Record<string, string[]>`, `initial?: PresetPayload`.
  - Inputs: name (text, slug-validated, readonly when `mode==='edit'`), label, description (textarea).
  - Per-facet card grid: for each dimension in `facetOptions`, render a row of `<button class="facet-card">` with the value + a plain-language subhead (small lookup map keyed by `{dimension}.{value}`; embed inline).
  - Save button disabled until: name non-empty AND name matches `^[a-z0-9_]+$` AND label non-empty AND all 4 facets selected.
  - Inline error text under name input when invalid: e.g., "Use lowercase letters, digits, and underscores only".
  - Emits `save` with `{name, label, description, facets}` and `cancel`.

- [ ] **4.** Run tests; expect all PASS.

- [ ] **5.** Commit:
  ```bash
  git add frontend/src/components/settings/PresetCreateEditForm.vue frontend/src/components/settings/__tests__/PresetCreateEditForm.spec.ts
  git commit -m "feat(frontend): PresetCreateEditForm component (FR-15)"
  ```

**Inline verification:**
- 6 form tests green.

---

### T19b: PresetTemplateViewer component

**Goal:** Read-only Jinja viewer that fetches `/template` and renders base + fragments as `<pre>` blocks.
**Spec refs:** FR-16, depends on T3 (template endpoint exists).

**Files:**
- Create: `frontend/src/components/settings/PresetTemplateViewer.vue`
- Test: `frontend/src/components/settings/__tests__/PresetTemplateViewer.spec.ts` (new)

**Steps:**

- [ ] **1.** Write failing test (mocks the fetch):
  ```ts
  describe('PresetTemplateViewer', () => {
    it('renders base template + fragments after fetch resolves', async () => {
      const mockResp = {
        name: 'practitioner_bullets',
        is_system: true,
        base_template: { path: 'summarize_section_v1.txt', source: '## Base prompt template body' },
        fragments: [
          { dimension: 'style', value: 'bullet_points', path: 'fragments/style/bullet_points.txt', source: 'Use bullets.' },
          { dimension: 'audience', value: 'practitioner', path: 'fragments/audience/practitioner.txt', source: 'Practitioners.' },
          { dimension: 'compression', value: 'standard', path: 'fragments/compression/standard.txt', source: '20%.' },
          { dimension: 'content_focus', value: 'frameworks_examples', path: 'fragments/content_focus/frameworks_examples.txt', source: 'Frameworks.' },
        ],
      };
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(mockResp) });
      vi.stubGlobal('fetch', fetchMock);

      const wrapper = mount(PresetTemplateViewer, { props: { name: 'practitioner_bullets' } });
      await flushPromises();

      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/v1/summarize/presets/practitioner_bullets/template'));
      const pres = wrapper.findAll('pre');
      expect(pres.length).toBe(5);  // 1 base + 4 fragments
      expect(pres[0].text()).toContain('Base prompt template body');
      expect(wrapper.text()).toContain('style: bullet_points');
      expect(wrapper.text()).toContain('audience: practitioner');
    });
    it('renders an error state when fetch returns 404', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }));
      const wrapper = mount(PresetTemplateViewer, { props: { name: 'missing' } });
      await flushPromises();
      expect(wrapper.text()).toMatch(/not found/i);
    });
  });
  ```

- [ ] **2.** Run; expect 2 FAILs.

- [ ] **3.** Implement `PresetTemplateViewer.vue`:
  - Prop `name: string`.
  - On mount (and on `watch(name)`), fetch `GET /api/v1/summarize/presets/{name}/template`. On 404, render error state.
  - Layout: heading per block (`<h4>` with filename + dimension/value), `<pre>` with raw `source`. Mono font + scoped styles using `var(--color-bg-muted)` background.
  - Optional copy-to-clipboard button per block (small, top-right corner).

- [ ] **4.** Run tests; expect PASS.

- [ ] **5.** Commit:
  ```bash
  git add frontend/src/components/settings/PresetTemplateViewer.vue frontend/src/components/settings/__tests__/PresetTemplateViewer.spec.ts
  git commit -m "feat(frontend): PresetTemplateViewer component (FR-16)"
  ```

**Inline verification:**
- 2 viewer tests green.

---

### T19c: PresetSettings rewrite — wire CRUD + viewer

**Goal:** Compose T19a + T19b into a full preset management page. New / Edit / Delete affordances; system presets read-only; warnings banner.
**Spec refs:** FR-15, FR-16, depends on T19a + T19b + T3.

**Files:**
- Modify: `frontend/src/components/settings/PresetSettings.vue` (~173 LOC; major rewrite)

**Steps:**

- [ ] **1.** Rewrite `PresetSettings.vue`:
  - Header bar with `New preset` button.
  - On mount, `GET /api/v1/summarize/presets` (already an existing call). Capture `warnings: [...]` from response if non-empty.
  - If `warnings.length > 0`, render a small banner above the list: "N preset files were skipped due to errors. Click to view." (expand to show file/error pairs.)
  - Two-column layout: list (left) + selected preset detail (right).
  - List row: name + (system badge) OR (Edit + Delete buttons for user presets).
  - Detail panel: description, facets table, then `<PresetTemplateViewer :name="selectedPreset.name" />`.
  - `New preset` button opens an inline modal containing `<PresetCreateEditForm mode="create" :facet-options="facetOptions" @save="handleCreate" @cancel="closeModal" />`.
    - `handleCreate`: POST to `/api/v1/summarize/presets`. On 201: refetch list, close modal, select the new preset. On 409: surface inline error in form ("A preset with this name already exists"). On 422: surface field-level error.
  - `Edit` opens the same modal in `mode="edit"` with `:initial="selectedPreset"`. On save: PUT, refetch.
  - `Delete`: two-step confirmation. First click → button transforms to "Confirm delete" with a 5-second timeout. Second click within window → DELETE → refetch.
  - `facetOptions` prop value: derive from a new lightweight API or hardcode the 4 dimensions client-side (acceptable for personal tool — read the keys from any existing system preset's `facets` shape returned by the list endpoint, union over all presets).

- [ ] **2.** Live verification:
  - `/settings/presets`: `New preset` → form opens → fill all fields → save → new preset appears in list with Edit + Delete; selected automatically.
  - Click Edit → form opens prefilled (name field readonly) → change description → save → list updates.
  - Click Delete → button shows "Confirm delete" → click → preset gone.
  - Click a system preset (e.g., `practitioner_bullets`) → detail shows description + facets + template viewer with base + 4 fragment blocks. No Edit/Delete buttons; "system" badge visible.
  - Manually corrupt a user preset YAML on disk (`echo "::: bad" > <preset_dir>/myfoo.yaml`) → reload `/settings/presets` → list renders without `myfoo` + warning banner shows the bad file.
  - Try to create a preset named `practitioner_bullets` → inline form error "A preset with this name already exists".
  - Try to create with empty label → Save disabled.
  - Try to create with name `Has Caps!` → inline error + Save disabled.

- [ ] **3.** Commit:
  ```bash
  git add frontend/src/components/settings/PresetSettings.vue
  git commit -m "feat(frontend): PresetSettings full CRUD wiring + warnings banner (FR-15 FR-16)"
  ```

**Inline verification:**
- Manual CRUD walkthrough end-to-end.
- Malformed-YAML warning surfaces in the list view.
- Collision and slug validation surface inline.

---

### T20: LlmSettings restyle — drop Tailwind dark:

**Goal:** Convert all `dark:` Tailwind utility classes to scoped-style + CSS-variable pattern matching sibling settings pages.
**Spec refs:** FR-18, P9.

**Files:**
- Modify: `frontend/src/components/settings/LlmSettings.vue` (~300 LOC)

**Steps:**

- [ ] **1.** Inventory current `dark:` usage:
  ```bash
  grep -n "dark:" frontend/src/components/settings/LlmSettings.vue | head -40
  ```
  Map each Tailwind class to its CSS-variable equivalent. Substitution table:

  | Tailwind | CSS-variable replacement |
  |----------|--------------------------|
  | `text-gray-900 dark:text-gray-100` | `var(--color-text-primary)` |
  | `text-gray-500 dark:text-gray-400` | `var(--color-text-secondary)` |
  | `bg-white dark:bg-gray-800` | `var(--color-bg-primary)` |
  | `bg-gray-50 dark:bg-gray-900` | `var(--color-bg-muted)` |
  | `border-gray-300 dark:border-gray-600` | `var(--color-border)` |
  | `bg-red-50 dark:bg-red-900/30` | `var(--color-bg-error)` (or a scoped class with both light + dark fallback values) |
  | `text-red-800 dark:text-red-200` | `var(--color-text-error)` |
  | `border-red-300 dark:border-red-700` | `var(--color-border-error)` |
  | `dark:bg-gray-800 dark:text-gray-100` (form inputs) | inputs styled with `var(--color-bg-input)` + `var(--color-text-primary)` |

  If any of the listed CSS variables don't exist, find them in another settings file (e.g. `DatabaseSettings.vue`) and reuse the same name.

- [ ] **2.** Migrate the file in one pass:
  - Replace every `class="..."` Tailwind block with semantic class names (e.g., `class="settings-heading"`, `class="error-banner"`, `class="form-input"`).
  - Move all styling into a single `<style scoped>` block at the bottom of the file using the CSS-variable pattern.
  - Mirror the visual structure of `DatabaseSettings.vue` (similar headings, banners, inputs).

- [ ] **3.** Grep gate (must return zero matches):
  ```bash
  grep -n "dark:" frontend/src/components/settings/LlmSettings.vue && echo "FAIL" && exit 1 || echo "OK"
  ```

- [ ] **4.** Live verification (side-by-side comparison):
  - Default light theme: visit `/settings/llm` and `/settings/database` in two browser tabs at the same width. Headings, inputs, banners, borders, and spacing should match closely.
  - Switch the app to dark theme (if global dark mode exists) → same comparison; LlmSettings should track the same theme as DatabaseSettings.
  - Functional regression: form fields still accept input, save button still posts, error banner still appears on validation failure.

- [ ] **5.** Commit:
  ```bash
  git add frontend/src/components/settings/LlmSettings.vue
  git commit -m "refactor(frontend): LlmSettings to scoped-style + CSS-vars (FR-18)"
  ```

**Inline verification:**
- Grep gate: zero `dark:` matches.
- Visual side-by-side parity with DatabaseSettings.
- Form save and validation paths still work.

---

### T21: Legacy /books/:id/summary route → redirect

**Goal:** Convert the legacy standalone book-summary route to a redirect to `?tab=summary`. Delete `BookSummaryView.vue` if no other consumer references it.
**Spec refs:** Edge case E10, P10.

**Files:**
- Modify: `frontend/src/router/index.ts`
- Delete (conditional): `frontend/src/views/BookSummaryView.vue`

**Steps:**

- [ ] **1.** Read current routes; locate the `/books/:id/summary` entry.

- [ ] **2.** Replace with a `redirect`:
  ```ts
  {
    path: '/books/:id/summary',
    redirect: to => ({ path: `/books/${to.params.id}`, query: { tab: 'summary' } }),
  },
  ```

- [ ] **3.** Grep for other consumers of `BookSummaryView`:
  ```bash
  grep -rln "BookSummaryView\|name: 'book-summary'" frontend/src/
  ```

- [ ] **4.** If only the router referenced it: `git rm frontend/src/views/BookSummaryView.vue` and remove its import in `router/index.ts`.

- [ ] **5.** Live verification:
  - Visit `/books/3/summary` → URL replaces to `/books/3?tab=summary` → Summary tab active.
  - Reload at `/books/3?tab=summary` → still works (verifies T11 deep-link).

- [ ] **6.** Commit:
  ```bash
  git add frontend/src/router/index.ts
  git rm frontend/src/views/BookSummaryView.vue 2>/dev/null || true
  git commit -m "refactor(frontend): redirect legacy /books/:id/summary to ?tab=summary (E10)"
  ```

**Inline verification:**
- Visit legacy URL → 302 to new URL → Summary tab renders.

---

### T22: Final verification

**Goal:** Verify the entire bundle works end-to-end against the 18 ACs.

- [ ] **Lint & format:**
  ```bash
  cd backend && uv run ruff check . && uv run ruff format --check .
  cd ../frontend && npm run lint && npm run format -- --check
  ```

- [ ] **Type check:**
  ```bash
  cd frontend && npm run type-check
  ```

- [ ] **Backend test suite:**
  ```bash
  cd backend && uv run python -m pytest -q
  ```
  Expected: no regressions vs. main; T1, T2, T3, T4, T5 added tests all green.

- [ ] **Frontend unit tests:**
  ```bash
  cd frontend && npm run test:unit
  ```
  Expected: all green including the new specs (BookSummaryTab, ReadingAreaFooterNav, MarkdownRenderer.styles, SectionListTable.compression, PresetCreateEditForm, PresetTemplateViewer, annotationContentType, OverflowMenu extended, BookOverviewView.tabs, TOCDropdown extended).

- [ ] **No-regression grep gates:**
  ```bash
  # No FAILED literal in backend
  grep -rn '"FAILED:' backend/app/services/ && exit 1 || echo "OK"
  # No subprocess alembic call
  grep -rn "uv run alembic" backend/app/services/settings_service.py && exit 1 || echo "OK"
  # No Tailwind dark: in settings
  grep -rn "dark:" frontend/src/components/settings/LlmSettings.vue && exit 1 || echo "OK"
  # No "Customize text" string in BookOverviewView or OverflowMenu
  grep -rn "Customize text" frontend/src/views/BookOverviewView.vue frontend/src/components/book/OverflowMenu.vue && exit 1 || echo "OK"
  # No stale ThemeCard import
  grep -rn "components/settings/ThemeCard" frontend/src && exit 1 || echo "OK"
  ```

- [ ] **Live verification setup** (per CLAUDE.md "Interactive verification"):
  ```bash
  cd frontend && npm run build
  rm -rf ../backend/app/static && cp -R dist ../backend/app/static
  cd ../backend && uv run bookcompanion serve --port 8765 &
  curl -sf http://localhost:8765/api/v1/health
  ```

- [ ] **Per-AC Playwright MCP gate** (drive each via `browser_navigate`/`browser_evaluate`/`browser_snapshot`):

  | AC | Failure mode (must NOT reproduce) | Verification |
  |----|------------------------------------|--------------|
  | 1 | Disabled "Read Summary" button on Book Detail | `document.querySelectorAll('button[disabled]').length` for Read Summary = 0; only one Read CTA visible |
  | 2 | No Summary tab on Book Detail | `document.querySelectorAll('[role="tab"]').length === 3`; clicking Summary on a book without default_summary shows empty state with Generate CTA |
  | 3 | "Customize text" floating link | `document.body.innerText.includes('Customize text') === false` |
  | 4 | Popover detached at `top:682,left:800` with "Couldn't load themes" error | Click overflow → Customize reader; popover anchored to trigger; `themeColors` API returns 200; close via Esc works |
  | 5 | `15.5%` style compression | First few rows of Sections table show `~15%`, `~25%` etc. — match `^~\d+%$` |
  | 6 | Bullet markers absent | `getComputedStyle(document.querySelector('.markdown-body ul')).listStyleType === 'disc'` |
  | 7 | No prev/next footer | Footer renders both links on a middle section; only Next on first; only Previous on last |
  | 8 | TOC shows `0` chars on `/books/3` | TOC dropdown chars match Sections-table chars |
  | 9 | `.context-sidebar` bg `rgb(255,255,255)` under Dark theme | Switch reader to Dark; computed bg ≠ white |
  | 10 | Markdown tables unstyled | `getComputedStyle(table).borderCollapse === 'collapse'` |
  | 11 | BC icon and title not interactive | Both clickable; both navigate to `/`; both have visible focus ring |
  | 12 | Summary tab renders 0 highlights when section_summary annotations exist | After creating a Summary-tab highlight, reload → DOM has the highlight span |
  | 13 | `current/latest === "FAILED:"` | `curl -s :8765/api/v1/settings/migration-status` returns hex revisions, never `FAILED:` |
  | 14 | Database settings stripes alternate | DOM check: no `:nth-child(even)` background applied to `.stat-row` |
  | 15 | Cannot create user preset from UI | New preset workflow completes; preset persists; Edit + Delete work |
  | 16 | No template viewer for system preset | Click `practitioner_bullets`; viewer shows base template + 4 fragments with raw source |
  | 17 | Reading-Settings preset chips are `<div>` (no hover/cursor) | Pills are `<button>`; tab navigation works; visual matches ReaderSettingsPopover ThemeCards |
  | 18 | LlmSettings has Tailwind `dark:` classes | `grep dark: frontend/src/components/settings/LlmSettings.vue` empty; visual matches DatabaseSettings |

- [ ] **Concurrency smoke** (cross-tab idempotency from simulation E11):
  - Open `/books/3?tab=summary` in two tabs.
  - In tab A click Generate → in-progress.
  - In tab B click Generate → backend returns 409 → tab B attaches to same job → both tabs reflect in-progress.
  - Wait for completion → both tabs render populated state.

- [ ] **Cleanup:**
  - Stop the verification server: `kill $(lsof -ti:8765)`.
  - Remove any tmp preset YAMLs created during malformed-YAML manual testing.
  - Verify `git status` is clean (or contains only intentional changes for the next task).

- [ ] **Update changelog:** add a `2026-05-01` bundle entry to `docs/changelog.md` summarizing the 18 fixes (or run `/pmos-toolkit:changelog` after merge).

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | (F1) Spec used `book_summary` field name but `GET /books/{id}` already returns `default_summary`. (F3) T19 was ~2hr of work in one task. (F4) T15 had no automated test for the active-tab → content_type wiring. (F5) T3/T4/T5 assumed integration fixtures (`client`, `tmp_presets_dir`, `seeded_book_with_*`) without verifying they exist. | (F1) Pinned `default_summary` as canonical across plan (T5 verifies, T13 props use it); spec § 7.4 to be updated post-merge. (F3) Split T19 into T19a (form) + T19b (viewer) + T19c (PresetSettings wrap-up); each ~30–45 min. (F4) Extracted `annotationContentTypeFor` helper in T15 step 1; added unit test in step 2; commit includes the new `frontend/src/utils/annotationContentType.ts`. (F5) Added T3 step 0 pre-flight that greps `conftest.py` for required fixtures and adds them in a separate commit if missing. |
