# Reader + Book Detail UX Fixes — Implementation Plan

**Date:** 2026-04-30
**Spec:** `docs/specs/2026-04-30-reader-and-book-detail-ux-fixes-spec.md`
**Requirements:** `docs/requirements/2026-04-30-reader-and-book-detail-ux-fixes.md`

---

## Overview

Bundled UX-fix plan covering 8 confirmed bugs and 5 gaps across the post-summarization workflow. The work touches the backend processing guard (stale-job sweep with `BEGIN IMMEDIATE`), a markdown image-URL rewrite path (helper + Alembic data migration + prompt update), a new `/jobs/{id}` deep-link API + view, and a Vue-side overhaul of the reader-section URL tab state, the book-detail action row, the shared section-list table, theme + preset migrations, and a bundled-webfont story with an ARIA-compliant font picker.

Backend lands first (the Vue components consume new schema fields and the new `/api/v1/processing/{job_id}` endpoint), then frontend infra (webfonts + theme CSS), then leaf components, then views, then final verification.

**Done when:** Every spec FR-ID has a passing test, all 8 bug verifications in spec §12.6 produce green output, the Playwright session in spec §12.5 completes without console errors, the lint + type-check + full pytest + vitest suites are green, and `/jobs/{id}` paints correctly for a deleted/active/completed/failed job from a cold reload.

**Execution order:**

```
Backend infra (sequential within track, parallel across tracks):
  Track A — Processing guard:    B1 → B2
  Track B — Image rewrite:       B3 → B4 → B5
  Track C — Jobs API:            B6
  Track D — TOC plumbing:        B7
  Track E — Preset migration:    B8 (depends on F2 theme work — see notes)

Frontend infra (parallelizable):
  F1 (webfonts)  [P]
  F2 (theme CSS) [P]

Frontend leaf components (after F1+F2):
  F3 (SectionListTable, depends on B7)  [P]
  F4 (FontListbox + CustomEditor wiring, depends on F1) [P]
  F5 (ExportSplitButton + OverflowMenu) [P]
  F6 (ThemeGrid preview, depends on F1+F2) [P]
  F7 (ContentToggle styling) [P]

Frontend views/stores (after components):
  F8 (reader store URL tabs)
  F9a (BookOverviewView action row + section list + popover, depends on F3, F5)
  F9b (Export 250ms loader + clipboard fallback, depends on F9a)
  F10 (JobProgressView + /jobs/:id route + indicator link, depends on B6)

Final:
  TN (full verification)
```

---

## Decision Log

> Inherits all 17 architecture decisions D1-D17 from the spec. Entries below are implementation-specific decisions made during planning.

| #  | Decision | Options Considered | Rationale |
|----|----------|--------------------|-----------|
| P1 | Reuse the existing `POST /api/v1/processing/{job_id}/cancel` route from JobProgressView's [Cancel] button. Do NOT introduce `DELETE /api/v1/processing/{job_id}` despite spec FR-12 wording. | (a) Reuse existing POST `/cancel`; (b) add a DELETE alias; (c) replace POST with DELETE | (a) — the existing endpoint already implements the best-effort cancel semantics chosen for OQ4 (PENDING atomic-delete, RUNNING flag-and-signal). Adding a DELETE alias creates two truths; replacing breaks the persistent indicator's existing wire-up. Spec text was loose; the route name is the only divergence. |
| P2 | Extract `is_stale(job: ProcessingJob, *, now: datetime, max_age: timedelta) -> bool` from `orphan_sweep.py:41-58` into a top-level module function (still in `orphan_sweep.py`, not a new file). | (a) Same file, top-level fn; (b) new `staleness.py`; (c) classmethod on ProcessingJob | (a) — minimum churn. Both callers (startup orphan sweep + on-demand guard) live in `app/services/summarizer/` and `app/api/routes/`; one shared import is cleaner than a new module. |
| P3 | `from_image_id_scheme()` lives in the existing `app/services/parser/image_url_rewrite.py` next to `from_placeholder()`, mirroring the latter's signature shape `(md, filename_to_image_id, on_missing)`. Image existence check uses the same `filename_to_image_id` dict the caller already builds; missing → strip-with-link-fallback per FR-09. | (a) Same file, sibling fn; (b) new module; (c) inline in summarizer | (a) — symmetry with the existing rewriter. The summarizer already constructs the image map for `from_placeholder`; passing the same dict avoids a second DB round-trip. |
| P4 | `content_char_count` is exposed as a `column_property` on `BookSection` using `func.length(BookSection.content_md)`, not a stored column or a Python `len()`. Materialized via `selectinload` in the books route. | (a) `column_property`; (b) eager-load full `content_md` and `len()` in serializer; (c) stored column with trigger | (a) — keeps the calc visible and avoids fetching potentially 100KB+ markdown over the wire when only the length is needed. SQLite's `LENGTH()` on TEXT counts characters, matching Python's `len()` for UTF-8 strings (within MMC). |
| P5 | Theme palettes for `paper` and `contrast` derived in this plan, not deferred. Values locked in §11 of this doc. | (a) Lock now; (b) defer to /execute | (a) — OQ1 was resolved during /plan intake. Locked values let the Phase 14 Playwright check assert specific computed colors. |
| P6 | Mobile is in scope for `SectionListTable` compact mode at <640px (per OQ2 resolution). One task adds the responsive verification; the broader UI is desktop-first. | (a) Include compact-mobile check; (b) skip mobile | (a) — OQ2 was resolved. The compact path already exists for the TOC dropdown (~360px); mobile is a smaller delta. |
| P7 | Orphan-image telemetry is structured-log only (per OQ3 resolution). No counter, no DB column. | (a) Log only; (b) counter | (a) — OQ3 resolved. Personal-scale tool; structlog is the existing observability surface. |
| P8 | `SectionListTable` SSE subscription (FR-33a) reuses the existing `useSummarizationJobStore` rather than opening a fresh `EventSource`. The store already manages the global stream; the table reads `summarizationJob.sectionEvents` and reacts. | (a) Reuse store; (b) per-component EventSource | (a) — avoids two SSE consumers per browser session for the same job, and keeps the lifecycle (open/close on terminal status) centralized. |
| P9 | Buffered SSE-seeding race in JobProgressView (FR-11a) implemented as a small composable `useBufferedJobStream(jobId)` returning `{state, error, isLoading}`. Component logic stays declarative. | (a) Composable; (b) inline in setup() | (a) — testable in isolation; the buffer-then-drain logic is the single most error-prone part of the plan. A composable lets one Vitest spec assert ordering without mounting the view. |
| P10 | `ExportSplitButton` and `OverflowMenu` are two separate components, not one parameterized menu, because their ARIA roles differ (split-button vs menu-button) and their default-action semantics differ (Export has a default click; ⋯ does not). | (a) Two components; (b) one component with `role` prop | (a) — ARIA Menu Button vs Split Button are distinct W3C patterns. Conflating them via prop forces conditional ARIA wiring that's hard to test. |
| P11 | TDD ordering for backend tasks: write the unit test in `backend/tests/unit/`, run to confirm RED, write the implementation, run to confirm GREEN. Frontend Vitest tasks follow the same pattern. New routes additionally get an integration test that hits the FastAPI app via `httpx.AsyncClient`. | (a) Strict TDD per task; (b) batch tests at end | (a) — matches CLAUDE.md project convention and prior plans in `docs/plans/`. Catches signature drift early. |
| P12 | Both data migrations (image-rewrite + preset-typography) are committed as separate Alembic revisions, in this order: image-rewrite first (B5), preset-typography second (B8). They share no FK constraints; ordering is for log-readability. | (a) Two revisions; (b) one combined revision | (a) — independent rollback windows. If preset-typography needs revert, image-rewrite stays applied. |
| P13 | The `summarize_section.txt` prompt update (FR-08) is committed in the same task as the runtime rewriter wiring (B4) so the LLM and the rewriter agree at the same git SHA. The Alembic migration (B5) is committed separately so its revert window is independent. | (a) Prompt + wiring same task, migration separate; (b) all three together | (a) — prompt + rewriter form a runtime contract (agree on output shape); the migration is a one-shot data fix. Splitting matches deploy-vs-data-migration boundary. |
| P14 | Final verification (TN) launches the verification server on **port 8765** per CLAUDE.md "Interactive verification" guidance. The user's likely-running `:8000` server stays untouched. Frontend build is copied into `backend/app/static/` for same-origin serving. | (a) Port 8765 + static copy; (b) reuse :8000; (c) Vite dev :5173 + proxy | (a) — matches CLAUDE.md exact pattern. Avoids the dev-vs-prod proxy ambiguity. |

---

## Code Study Notes

**Backend insertion points** (verified by file reads, not skim):

- `backend/app/api/routes/processing.py:113-127` — current 409 guard is a single `select().where(book_id, status IN ('PENDING','RUNNING'))` followed by `raise HTTPException(409)`. New code wraps this in `BEGIN IMMEDIATE` and runs `is_stale()` between SELECT and HTTPException. Cancel route is at `processing.py:228-306` (POST `/cancel`).
- `backend/app/db/models.py:282-321` — `ProcessingJob` already has `pid`, `started_at`, `request_params` (JSON), `status` enum. No schema change needed for Phase B1/B2. Partial UNIQUE index `one_active_per_book` at lines 313-318 stays untouched (D17 / Non-Goal).
- `backend/app/services/parser/image_url_rewrite.py` — `from_placeholder(md, filename_to_image_id, on_missing="keep")` at lines 58-98. `OnMissing = Literal["keep", "strip"]` at line 12. `from_image_id_scheme()` mirrors this shape but matches `image:NNN` directly (no filename indirection); the existence check uses `filename_to_image_id.values()` (image_id integers).
- `backend/app/services/summarizer/summarizer_service.py:484, 584, 646` — three `from_placeholder()` call sites. New `from_image_id_scheme()` insertion goes immediately after each.
- `backend/app/services/summarizer/orphan_sweep.py:41-58` — `_pid_is_alive(pid)` and `_job_is_too_old(job, now, max_age)`. The plan extracts a single `is_stale(job, *, now, max_age)` predicate that combines both.
- `backend/app/api/schemas.py:62-70` — `SectionBriefResponse` currently has `id, title, order_index, section_type, content_token_count, has_summary`. Add `content_char_count: int` (default 0). The route at `routes/books.py:_book_to_response()` line 64 builds it.
- `backend/app/migrations/versions/c9d0e1f2a3b4_v1_5a_summary_image_rewrite.py:32-66` — exact pattern to mirror for B5: query summaries, build per-book image map, rewrite, UPDATE if changed, log count.
- `backend/app/migrations/versions/a5459240fea0_v1_5_1_collapse_reading_presets.py:53-93` — pattern for B8: idempotent guard via `PRAGMA table_info`, UPDATE with WHERE clause matching original tuple (so re-running is no-op).
- `backend/app/api/sse.py:15-54` — EventBus exposes `subscribe/unsubscribe/publish/close`. Event types are ad-hoc strings ("section_started", "section_completed", "processing_completed", etc.). No new event types needed; B6 only consumes them via SSE-stream replay.

**Frontend insertion points:**

- `frontend/src/assets/theme.css` — light/sepia/dark blocks each declare 17 vars. `night`, `paper`, `contrast` are referenced by `themeColors.ts` but have NO CSS blocks → clicks are no-op (root cause of bug #10).
- `frontend/src/stores/reader.ts:34, 85-97, 99-119, 121-123` — `contentMode` ref, `loadSection()`, `navigateSection()`, `toggleContent()`. Router is dynamically imported at lines 109-113 inside navigate; loadSection has no router access. F8 must add `router.replace()` to `toggleContent()` and parse `route.query.tab` in `loadSection()`.
- `frontend/src/components/reader/ContentToggle.vue:51-54` — exact `:disabled` opacity rule to remove. Active styles at lines 56-59 stay.
- `frontend/src/views/BookOverviewView.vue:44-49` — static "Summaries: X of Y" counter (delete in F9). `BookOverviewView.vue:51-104` — current action row layout. `BookOverviewView.vue:115-118` — inline book summary block (preserved per Non-Goal). `BookOverviewView.vue:120-136` — inline section list (replaced by `<SectionListTable>` in F9). `BookOverviewView.vue:206-281` — `onExportClick` and `onCopyClick` with existing fallback path; F9 wraps these with the 250ms floor and the new clipboard text-only fallback.
- `frontend/src/components/reader/TOCDropdown.vue:53-83` — current section list inside a `<details>`. F9 replaces with `<SectionListTable :compact="true">`.
- `frontend/src/components/job/PersistentProcessingIndicator.vue:54-108` — running-job row + queued list. F10 inserts a "View details" `<router-link to="/jobs/${job_id}">` next to the existing Open button (lines 68-75).
- `frontend/src/components/settings/CustomEditor.vue:84-90` — native `<select>` for fonts. F4 replaces with `<FontListbox>`.
- `frontend/src/components/settings/ThemeGrid.vue:128-140` — `<ThemeCard>` loop. F6 adds a `:previewFont` prop to the card props.
- `frontend/src/router/index.ts` — snake-case route names, no `/jobs/:id` yet. F10 adds it.
- `frontend/src/main.ts` — currently 15 lines, only `./assets/main.css` import + Pinia + router. F1 adds `@fontsource/*` imports here.

**No drift between spec and code beyond P1 (cancel route name).** All other FR insertion points exist as the spec says.

**Test scaffolding observed:**
- Backend: `backend/tests/unit/`, `backend/tests/integration/test_api/`, fixtures in `backend/tests/fixtures/`. AsyncClient is the standard for integration tests.
- Frontend: `frontend/src/{views,components,stores}/__tests__/*.spec.ts` co-located. Vitest 2.1.4, Vue Test Utils 2.4.6.

---

## Prerequisites

1. Working tree clean on `main` (or a feature branch off main).
2. Backend deps installed: `cd backend && uv sync --dev`.
3. Frontend deps installed: `cd frontend && npm install`.
4. SQLite library DB exists with at least one fully-summarized book + one image-bearing summary. If empty, run `cd backend && uv run python tests/fixtures/download_fixtures.py && uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub`.
5. **Baseline lint/test capture** — first command of T1 (so any subsequent regression is comparable).
6. No active `bookcompanion serve` on port 8765 (final verification claims that port).

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/services/summarizer/orphan_sweep.py:41-87` | Extract `is_stale()` top-level predicate; refactor existing sweep to call it. |
| Create | `backend/tests/unit/test_orphan_sweep_predicate.py` | Unit-test the extracted `is_stale()` predicate in isolation. |
| Modify | `backend/app/api/routes/processing.py:113-127` | Wrap active-job guard in `BEGIN IMMEDIATE`; on stale → mark FAILED + INSERT. Return enriched 409 body when truly active. |
| Create | `backend/tests/integration/test_api/test_processing_stale_guard.py` | Two AsyncClient tests: stale RUNNING with dead PID → 202; live PID + recent → 409 with `active_job` payload. |
| Modify | `backend/app/services/parser/image_url_rewrite.py` | Add `from_image_id_scheme(md, filename_to_image_id, on_missing) -> str` next to `from_placeholder`. |
| Create | `backend/tests/unit/test_image_url_rewrite_id_scheme.py` | Unit tests for the new helper: existing id, orphan id, malformed (`image:abc`), idempotent re-run. |
| Modify | `backend/app/services/summarizer/summarizer_service.py:484, 584, 646` | Insert `from_image_id_scheme()` call after each `from_placeholder()`. |
| Modify | `backend/app/services/summarizer/prompts/base/summarize_section.txt:14-20` | Update prompt to instruct LLM to emit `/api/v1/images/{img.image_id}` directly. |
| Create | `backend/tests/unit/test_summarizer_image_rewrite.py` | Stub LLM emits both legacy and new schemes; verify persisted summary contains absolute URLs. |
| Create | `backend/app/migrations/versions/<slug>_v1_5b_legacy_image_id_rewrite.py` | One-shot Alembic data migration applying `from_image_id_scheme(..., on_missing="strip")` to all summaries. Idempotent. |
| Create | `backend/tests/integration/test_migration_image_id_rewrite.py` | Seed legacy summary; run migration; verify rewrite. Re-run; verify no-op. |
| Create | `backend/app/api/routes/processing.py` (new endpoint method) | `GET /api/v1/processing/{job_id}` returning the spec's response shape. |
| Create | `backend/tests/integration/test_api/test_processing_get_endpoint.py` | 4×200 (PENDING/RUNNING/COMPLETED/FAILED) + 1×404 cases. |
| Modify | `backend/app/db/models.py:186-235` | Add `column_property("content_char_count", func.length(content_md))` to `BookSection`. |
| Modify | `backend/app/api/schemas.py:62-70` | Add `content_char_count: int = 0` to `SectionBriefResponse`. |
| Modify | `backend/app/api/routes/books.py:64-74` | Pass `s.content_char_count` into `SectionBriefResponse(...)`. |
| Create | `backend/tests/integration/test_api/test_book_detail_char_count.py` | GET /books/{id} → response.json()["sections"][0]["content_char_count"] equals `len(content_md)`. |
| Create | `backend/app/migrations/versions/<slug>_v1_5b_preset_typography.py` | Alembic data migration updating 6 system presets to spec §11.3 values. Idempotent. |
| Create | `backend/tests/integration/test_migration_preset_typography.py` | Seed default presets; run; verify updated values; re-run; verify no-op. |
| Modify | `frontend/package.json` | Add `@fontsource/*` deps for Inter, Merriweather, Lora, Fira Code, Source Serif Pro (specific weights per FR-40). |
| Modify | `frontend/src/main.ts` | Import all `@fontsource` packages so `@font-face` ships in build. |
| Modify | `frontend/src/assets/theme.css` | Add complete `[data-theme='night'|'paper'|'contrast']` blocks (17 vars each). |
| Create | `frontend/src/components/book/SectionListTable.vue` | Shared table for book-detail (full) and TOC dropdown (compact). |
| Create | `frontend/src/components/book/__tests__/SectionListTable.spec.ts` | All 6 columns render in default; compact hides Type/Compression; compression formatting; — when no summary; row keyboard nav; SSE-driven row updates. |
| Create | `frontend/src/components/settings/FontListbox.vue` | ARIA Listbox replacing native `<select>`, with per-font preview labels. |
| Create | `frontend/src/components/settings/__tests__/FontListbox.spec.ts` | Each option has `font-family` style; ↑↓ Enter Esc click-outside. |
| Modify | `frontend/src/components/settings/CustomEditor.vue:84-90` | Replace native `<select>` with `<FontListbox>`. |
| Create | `frontend/src/components/book/ExportSplitButton.vue` | Split-button with default-action body (Download) + chevron menu (Copy). ARIA Menu Button. |
| Create | `frontend/src/components/book/OverflowMenu.vue` | ⋯ trigger + ARIA Menu Button popover. Menu items: Edit Structure, Customize Reader. |
| Create | `frontend/src/components/book/__tests__/ExportSplitButton.spec.ts` | Default-click triggers `download` event; chevron opens menu; menu Item triggers `copy`; disabled state when no summaries. |
| Modify | `frontend/src/components/settings/ThemeGrid.vue:128-140` | Pass `previewFont` to `<ThemeCard>`. |
| Modify | `frontend/src/components/reader/ContentToggle.vue:51-54` | Drop the `:disabled` opacity rule; use muted-but-clickable inactive styling. Remove `:disabled` bindings on the buttons. |
| Modify | `frontend/src/stores/reader.ts:85-97, 99-119, 121-123` | URL `?tab=` sync — read on `loadSection`, `router.replace` in `toggleContent`, preserve in `navigateSection`, silently rewrite when destination has no summary. |
| Create | `frontend/src/stores/__tests__/reader.tab.spec.ts` | URL-tab read on load; toggle replaces URL; nav preserves; mismatch rewrites. |
| Modify | `frontend/src/views/BookOverviewView.vue:44-49, 51-104, 120-136, 206-281` | Delete static counter; rebuild action row (3 primaries + ⋯); replace inline section list with `<SectionListTable>`; wire 250ms loader + clipboard fallback. |
| Modify | `frontend/src/views/__tests__/BookOverviewView.spec.ts` | Update existing assertions; add action-row shape assertion; assert static counter text absent; assert export disabled-with-tooltip when no summaries. |
| Create | `frontend/src/views/JobProgressView.vue` | New view: skeleton → 200 (active/terminal) | 404. Uses `useBufferedJobStream(jobId)` composable. |
| Create | `frontend/src/composables/useBufferedJobStream.ts` | REST→SSE seeding race protection per FR-11a. |
| Create | `frontend/src/composables/__tests__/useBufferedJobStream.spec.ts` | Asserts buffer-then-drain ordering; reconnect re-seeds. |
| Modify | `frontend/src/router/index.ts` | Add `{ path: '/jobs/:id', name: 'job-detail', component: JobProgressView, props: true }`. |
| Modify | `frontend/src/components/reader/TOCDropdown.vue:53-83` | Replace inner list with `<SectionListTable :compact="true">`. |
| Modify | `frontend/src/components/job/PersistentProcessingIndicator.vue:54-108` | Add "View details" router-link to `/jobs/${job_id}` in the running-job row. |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `BEGIN IMMEDIATE` deadlocks under concurrent same-book retries | Low | SQLite serializes writers; the lock blocks (does not deadlock). Integration test asserts both requests resolve in <1s with deterministic outcomes. |
| Alembic migration on production-size DB takes >5s | Low | Personal-scale (<100 books); the migration scans only `summaries` rows matching `LIKE '%](image:%'`. Worst-case ~1k rows × <5ms rewrite = <5s. NFR-06 covers idempotency, not perf. |
| Webfont bundle exceeds NFR-05 600KB cap | Medium | Each font subset is woff2 + latin-only at 400/700. Inter+Lora+Merriweather+Fira+Source-Serif at 2 weights = ~5×80KB = 400KB. Confirm with `ls -lh frontend/dist/assets/` after F1. If over, drop a weight (e.g., Source Serif 700 → 400 only). |
| SSE seeding race in JobProgressView ships a subtle off-by-one (events processed twice or skipped) | Medium | The `useBufferedJobStream` composable is extracted exactly so it can be unit-tested with a mocked EventSource. Test cases include "event arrives between GET request and GET response" and "reconnect mid-stream". |
| ThemeCard typography preview adds layout shift in ThemeGrid | Low | Preview is a fixed-size `Aa` glyph rendered at known font_size_px in a 24px-tall slot. Visual regression caught by Playwright screenshot in TN. |
| Tab state in URL conflicts with browser back/forward expectations | Low | FR-15 mandates `router.replace()` (not push). Manual Playwright test in TN includes back-button behavior assertion. |
| Idempotent preset migration accidentally overwrites user-customized presets | Low | Per spec §11.3, the WHERE clause matches the original tuple `Georgia/16/1.6/720` — user overrides are preserved. Test asserts this. |
| Removing the `BookOverviewView` static counter breaks existing snapshot tests | Medium | FR-24 mandates a grep inventory before delete (file paths in spec). Plan task F9 makes the grep an explicit step. |

---

## Rollback

- **B5 (image-rewrite migration) bad data:** `alembic downgrade -1`. Migration has a no-op downgrade; manual restore from `~/Library/Application Support/bookcompanion/library-{ts}.db` if data was rewritten and you want it back. Recommend backup before running on prod DB.
- **B8 (preset migration) bad data:** `alembic downgrade -1`. Same — no-op downgrade; restore from backup. Or run `bookcompanion preset reset` if such a CLI exists (verify in B8).
- **B2 guard regression:** revert `processing.py` change; existing 409-on-stale behavior returns. Stale jobs need `bookcompanion init` (which runs the orphan sweep) to clear.
- **Frontend build fails post-fontsource:** `git revert` the F1 commit; remove the `@fontsource` deps from `package.json`; rebuild.
- **JobProgressView broken in prod:** unregister the route in `router/index.ts`; the view is greenfield, no dependent surfaces.

---

## Tasks

### B1: Extract `is_stale()` predicate from orphan_sweep

**Goal:** Refactor freshness logic into a top-level reusable predicate without changing existing startup-sweep behavior.
**Spec refs:** FR-04, NFR-03 (foundation).

**Files:**
- Modify: `backend/app/services/summarizer/orphan_sweep.py`
- Create: `backend/tests/unit/test_orphan_sweep_predicate.py`

**Steps:**

- [ ] Step 1: Capture baseline: `cd backend && uv run ruff check . > /tmp/lint-baseline.txt 2>&1; uv run python -m pytest tests/ -x --tb=no -q > /tmp/test-baseline.txt 2>&1`. Note pre-existing failures so they're not attributed to this work.

- [ ] Step 2: Write the failing unit test:
  ```python
  # backend/tests/unit/test_orphan_sweep_predicate.py
  import os
  from datetime import datetime, timedelta, timezone
  import pytest
  from unittest.mock import MagicMock
  from app.services.summarizer.orphan_sweep import is_stale

  NOW = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
  MAX_AGE = timedelta(hours=24)

  def _job(pid, started_at):
      j = MagicMock()
      j.pid = pid
      j.started_at = started_at
      return j

  def test_is_stale_when_pid_is_none():
      assert is_stale(_job(None, NOW), now=NOW, max_age=MAX_AGE) is True

  def test_is_stale_when_pid_dead(monkeypatch):
      def fake_kill(pid, sig):
          raise ProcessLookupError
      monkeypatch.setattr(os, "kill", fake_kill)
      assert is_stale(_job(99999, NOW), now=NOW, max_age=MAX_AGE) is True

  def test_is_stale_when_too_old(monkeypatch):
      monkeypatch.setattr(os, "kill", lambda pid, sig: None)
      old = NOW - timedelta(hours=25)
      assert is_stale(_job(os.getpid(), old), now=NOW, max_age=MAX_AGE) is True

  def test_is_fresh_when_pid_alive_and_recent(monkeypatch):
      monkeypatch.setattr(os, "kill", lambda pid, sig: None)
      recent = NOW - timedelta(minutes=5)
      assert is_stale(_job(os.getpid(), recent), now=NOW, max_age=MAX_AGE) is False
  ```

- [ ] Step 3: Run test — confirm RED.
  Run: `cd backend && uv run python -m pytest tests/unit/test_orphan_sweep_predicate.py -v`
  Expected: FAIL — `ImportError: cannot import name 'is_stale'`.

- [ ] Step 4: Implement. In `backend/app/services/summarizer/orphan_sweep.py`, extract a top-level function and refactor the existing helpers to call it:
  ```python
  def is_stale(job, *, now: datetime, max_age: timedelta) -> bool:
      """Return True if the job should be considered abandoned."""
      if job.pid is None:
          return True
      try:
          os.kill(job.pid, 0)
      except ProcessLookupError:
          return True
      except PermissionError:
          pass  # process exists but owned by other user; treat as alive
      if (now - job.started_at) > max_age:
          return True
      return False
  ```
  Update `orphan_sweep()` to call `is_stale(job, now=datetime.now(timezone.utc), max_age=timedelta(seconds=settings.processing.stale_job_age_seconds))`. Keep both private helpers (`_pid_is_alive`, `_job_is_too_old`) intact during this task to avoid touching unrelated callers; remove only if confirmed via grep that nothing imports them externally.

- [ ] Step 5: Run unit test — confirm GREEN.
  Run: `cd backend && uv run python -m pytest tests/unit/test_orphan_sweep_predicate.py -v`
  Expected: 4 passed.

- [ ] Step 6: Run the existing orphan-sweep test to confirm no regression.
  Run: `cd backend && uv run python -m pytest tests/integration/test_orphan_job_sweep.py -v`
  Expected: same number of pre-existing passes; 0 new failures.

- [ ] Step 7: Add settings field if missing. Check `backend/app/config.py` for `processing.stale_job_age_seconds`. If absent, add it with default `86400` (per spec §10).
  Verify: `cd backend && uv run python -c "from app.config import Settings; print(Settings().processing.stale_job_age_seconds)"`
  Expected: `86400`.

- [ ] Step 8: Commit.
  ```bash
  cd /Users/maneeshdhabria/Desktop/Projects/personal/book-companion
  git add backend/app/services/summarizer/orphan_sweep.py backend/app/config.py backend/tests/unit/test_orphan_sweep_predicate.py
  git commit -m "refactor: extract is_stale() predicate from orphan_sweep"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/summarizer/orphan_sweep.py` — no errors.
- `cd backend && uv run python -m pytest tests/unit/test_orphan_sweep_predicate.py tests/integration/test_orphan_job_sweep.py -v` — all green.

---

### B2: On-demand stale-job sweep in POST /summarize

**Goal:** Make per-section retry recover from stale RUNNING jobs at request time, replacing the current opaque 409.
**Spec refs:** FR-01, FR-02, FR-03, NFR-03.

**Files:**
- Modify: `backend/app/api/routes/processing.py:113-127`
- Create: `backend/tests/integration/test_api/test_processing_stale_guard.py`

**Steps:**

- [ ] Step 1: Write the failing integration tests:
  ```python
  # backend/tests/integration/test_api/test_processing_stale_guard.py
  import os
  import pytest
  from datetime import datetime, timedelta, timezone
  from httpx import AsyncClient

  @pytest.mark.asyncio
  async def test_stale_running_job_is_swept(app_client: AsyncClient, seeded_book, db_session):
      # Seed a RUNNING job with a dead pid and a recent started_at
      from app.db.models import ProcessingJob, ProcessingJobStatus
      job = ProcessingJob(
          book_id=seeded_book.id,
          status=ProcessingJobStatus.RUNNING,
          step="summarize",
          pid=99999,  # almost certainly dead
          started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
          request_params={"scope": "all"},
      )
      db_session.add(job)
      await db_session.commit()

      r = await app_client.post(f"/api/v1/books/{seeded_book.id}/summarize", json={"scope": "all"})
      assert r.status_code == 202, r.json()

      # The stale job is marked FAILED.
      await db_session.refresh(job)
      assert job.status == ProcessingJobStatus.FAILED
      assert "stale" in (job.error_message or "").lower()

  @pytest.mark.asyncio
  async def test_live_running_job_blocks_with_payload(app_client, seeded_book, db_session):
      from app.db.models import ProcessingJob, ProcessingJobStatus
      job = ProcessingJob(
          book_id=seeded_book.id,
          status=ProcessingJobStatus.RUNNING,
          step="summarize",
          pid=os.getpid(),
          started_at=datetime.now(timezone.utc) - timedelta(minutes=1),
          request_params={"scope": "all"},
          progress={"current": 12, "total": 24},
      )
      db_session.add(job)
      await db_session.commit()

      r = await app_client.post(f"/api/v1/books/{seeded_book.id}/summarize", json={"scope": "all"})
      assert r.status_code == 409
      body = r.json()
      assert "active_job" in body
      assert body["active_job"]["id"] == job.id
      assert body["active_job"]["progress"]["current"] == 12
      assert body["active_job"]["progress"]["total"] == 24
  ```
  Reuse existing `app_client`, `seeded_book`, `db_session` fixtures from `backend/tests/integration/test_api/conftest.py`. If they don't exist with these names, scaffold minimal versions following the patterns in `test_processing_api.py`.

- [ ] Step 2: Run — confirm RED.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_stale_guard.py -v`
  Expected: both fail. First with 409 (current behavior); second with a 409 body lacking `active_job`.

- [ ] Step 3: Implement the guard rewrite in `backend/app/api/routes/processing.py`. Locate the active-job guard at lines 113-127 and replace with:
  ```python
  from sqlalchemy import text
  from datetime import datetime, timedelta, timezone
  from app.services.summarizer.orphan_sweep import is_stale

  await db.execute(text("BEGIN IMMEDIATE"))
  result = await db.execute(
      select(ProcessingJob)
      .where(ProcessingJob.book_id == book_id)
      .where(ProcessingJob.status.in_([ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING]))
  )
  active = result.scalar_one_or_none()
  if active is not None:
      now = datetime.now(timezone.utc)
      max_age = timedelta(seconds=settings.processing.stale_job_age_seconds)
      if is_stale(active, now=now, max_age=max_age):
          active.status = ProcessingJobStatus.FAILED
          active.error_message = "Marked stale by on-demand sweep"
          active.completed_at = now
          # fall through to INSERT
      else:
          await db.commit()  # release write lock cleanly
          raise HTTPException(
              status_code=409,
              detail={
                  "detail": "A summarization job is already running for this book.",
                  "active_job": {
                      "id": active.id,
                      "scope": (active.request_params or {}).get("scope"),
                      "started_at": active.started_at.isoformat() if active.started_at else None,
                      "progress": active.progress or {},
                  },
              },
          )
  # ... existing INSERT new job code stays here, then commit
  ```
  Note: FastAPI's `HTTPException(status_code=409, detail=<dict>)` returns the dict as the body. The `"detail"` key inside makes the response shape match spec §7.2 verbatim.

- [ ] Step 4: Run integration tests — confirm GREEN.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_stale_guard.py -v`
  Expected: 2 passed.

- [ ] Step 5: Re-run the existing processing-api test to confirm no regression.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_api.py tests/integration/test_api/test_processing_cancel.py -v`
  Expected: same pre-existing passes; 0 new failures.

- [ ] Step 6: Verify the existing 409 callers (if any) on the frontend can still parse the new body. Grep:
  ```bash
  cd /Users/maneeshdhabria/Desktop/Projects/personal/book-companion/frontend
  grep -rn "status.*409\|409.*status" src/
  ```
  Document any consumer that destructures the 409 body — they will see the new keys but should not break (additive change). Note in commit body if any updates are needed.

- [ ] Step 7: Commit.
  ```bash
  git add backend/app/api/routes/processing.py backend/tests/integration/test_api/test_processing_stale_guard.py
  git commit -m "feat(processing): on-demand stale-job sweep with BEGIN IMMEDIATE"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_stale_guard.py tests/integration/test_orphan_job_sweep.py -v` — all green.
- `cd backend && uv run ruff check app/api/routes/processing.py` — no errors.

- [ ] Step 8: **NFR-03 timing assertion.** Add to the same test file:
  ```python
  @pytest.mark.asyncio
  async def test_stale_guard_happy_path_under_5ms_median(app_client, seeded_book):
      import time, statistics
      times_ms = []
      for _ in range(100):
          # Clear any active job between iterations to keep the path deterministic
          # (or seed once and assert per-iteration latency on the SELECT-only no-stale path)
          start = time.perf_counter_ns()
          # Issue the guard-only call. Ideally invoke the predicate path directly;
          # if route-level is the only seam, time the SELECT itself.
          r = await app_client.post(f"/api/v1/books/{seeded_book.id}/summarize", json={"scope": "all"})
          elapsed = (time.perf_counter_ns() - start) / 1e6
          times_ms.append(elapsed)
          # Reset — delete the just-created PENDING job so the next iteration's guard sees no row
          # (seam: a small DELETE via raw SQL keeps the loop deterministic)

      median = statistics.median(times_ms)
      # NFR-03: < 5ms for the predicate evaluation. The full POST includes more work
      # (route, deps, INSERT). The pragmatic bar in CI is < 50ms median for this
      # whole call; if local measurement shows the predicate alone exceeds 5ms, file an issue.
      assert median < 50.0, f"Median POST time {median:.2f}ms exceeds 50ms"
  ```
  Note: NFR-03 specifies the *guard*'s additive cost, not the full-route latency. A pure-predicate test would call `is_stale()` 1000 times and assert <5ms median — much more reliable in CI. Prefer that form if route-level timing flakes:
  ```python
  def test_is_stale_predicate_under_5ms_median(monkeypatch):
      import time, statistics
      monkeypatch.setattr(os, "kill", lambda pid, sig: None)
      job = MagicMock(); job.pid = os.getpid(); job.started_at = datetime.now(timezone.utc)
      times = []
      for _ in range(1000):
          s = time.perf_counter_ns()
          is_stale(job, now=datetime.now(timezone.utc), max_age=timedelta(hours=24))
          times.append((time.perf_counter_ns() - s) / 1e6)
      assert statistics.median(times) < 5.0
  ```

---

### B3: `from_image_id_scheme()` helper

**Goal:** Add the legacy-image-scheme rewriter beside the existing placeholder rewriter.
**Spec refs:** FR-05, FR-09.

**Files:**
- Modify: `backend/app/services/parser/image_url_rewrite.py`
- Create: `backend/tests/unit/test_image_url_rewrite_id_scheme.py`

**Steps:**

- [ ] Step 1: Write the failing tests:
  ```python
  # backend/tests/unit/test_image_url_rewrite_id_scheme.py
  from app.services.parser.image_url_rewrite import from_image_id_scheme

  def test_rewrites_existing_id():
      out = from_image_id_scheme("![cap](image:42)", {"a.jpg": 42})
      assert out == "![cap](/api/v1/images/42)"

  def test_orphan_id_strips_to_link_with_alt():
      out = from_image_id_scheme("before ![alt](image:99) after", {"a.jpg": 42}, on_missing="strip")
      assert out == "before [alt](#) after"

  def test_malformed_id_left_untouched():
      assert from_image_id_scheme("![x](image:abc)", {}) == "![x](image:abc)"
      assert from_image_id_scheme("![x](image:)", {}) == "![x](image:)"

  def test_empty_alt_handled():
      out = from_image_id_scheme("![](image:42)", {"a.jpg": 42})
      assert out == "![](/api/v1/images/42)"

  def test_idempotent():
      once = from_image_id_scheme("![x](image:42)", {"a.jpg": 42})
      twice = from_image_id_scheme(once, {"a.jpg": 42})
      assert once == twice == "![x](/api/v1/images/42)"

  def test_multiple_images_in_one_doc():
      md = "![a](image:1) text ![b](image:2)"
      out = from_image_id_scheme(md, {"x": 1, "y": 2})
      assert out == "![a](/api/v1/images/1) text ![b](/api/v1/images/2)"
  ```

- [ ] Step 2: Run — confirm RED.
  Run: `cd backend && uv run python -m pytest tests/unit/test_image_url_rewrite_id_scheme.py -v`
  Expected: ImportError on `from_image_id_scheme`.

- [ ] Step 3: Implement in `backend/app/services/parser/image_url_rewrite.py` near `from_placeholder`:
  ```python
  import re
  import structlog

  log = structlog.get_logger(__name__)
  LEGACY_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(image:(\d+)\)")

  def from_image_id_scheme(
      md: str,
      filename_to_image_id: dict[str, int],
      on_missing: OnMissing = "strip",
  ) -> str:
      """Rewrite legacy ![alt](image:NNN) into ![alt](/api/v1/images/NNN).

      If the image_id is not present in the section's image map, behavior depends
      on `on_missing`: 'strip' replaces with [alt](#) and logs a warning;
      'keep' leaves the original token untouched.
      """
      known_ids = set(filename_to_image_id.values())

      def _replace(m: re.Match) -> str:
          alt, raw_id = m.group(1), m.group(2)
          image_id = int(raw_id)
          if image_id in known_ids:
              return f"![{alt}](/api/v1/images/{image_id})"
          if on_missing == "strip":
              log.warning("legacy_image_ref_orphan", image_id=image_id)
              return f"[{alt}](#)"
          return m.group(0)

      return LEGACY_IMAGE_RE.sub(_replace, md)
  ```

- [ ] Step 4: Run — confirm GREEN.
  Run: `cd backend && uv run python -m pytest tests/unit/test_image_url_rewrite_id_scheme.py -v`
  Expected: 6 passed.

- [ ] Step 5: Commit.
  ```bash
  git add backend/app/services/parser/image_url_rewrite.py backend/tests/unit/test_image_url_rewrite_id_scheme.py
  git commit -m "feat(parser): from_image_id_scheme() rewrites legacy image:N markdown"
  ```

**Inline verification:**
- `uv run ruff check app/services/parser/image_url_rewrite.py`
- `uv run python -m pytest tests/unit/test_image_url_rewrite_id_scheme.py -v` — 6 passed.

---

### B4: Wire `from_image_id_scheme` into SummarizerService + update prompt

**Goal:** Future summaries no longer contain legacy `image:N` refs in persisted markdown.
**Spec refs:** FR-06, FR-08.

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py:484, 584, 646`
- Modify: `backend/app/services/summarizer/prompts/base/summarize_section.txt:14-20`
- Create: `backend/tests/unit/test_summarizer_image_rewrite.py`

**Steps:**

- [ ] Step 1: Write the failing test (use the existing stub-LLM scaffolding from `tests/unit/test_summarizer_*.py`):
  ```python
  # backend/tests/unit/test_summarizer_image_rewrite.py
  import pytest
  from app.services.parser.image_url_rewrite import from_image_id_scheme

  @pytest.mark.asyncio
  async def test_summarizer_rewrites_legacy_image_scheme(summarizer_service, stub_llm, sample_section_with_image):
      # Stub LLM emits the legacy scheme
      stub_llm.set_response("Here is **bold** ![diagram](image:7) caption.")
      summary = await summarizer_service._summarize_single_section(
          book_id=sample_section_with_image.book_id,
          section=sample_section_with_image,
          facets={"style": "concise", "audience": "practitioner",
                  "compression": "standard", "content_focus": "key_concepts"},
          preset_name="practitioner_bullets",
          model=None,
          cumulative_context="",
      )
      assert "image:7" not in summary.summary_md
      assert "/api/v1/images/7" in summary.summary_md
  ```
  If `summarizer_service`/`stub_llm`/`sample_section_with_image` fixtures don't exist with those names, follow the pattern from `tests/unit/test_summarizer_facets.py` (or wherever the stub LLM lives) and document the new fixture in `tests/conftest.py`.

- [ ] Step 2: Run — confirm RED.
  Run: `cd backend && uv run python -m pytest tests/unit/test_summarizer_image_rewrite.py -v`
  Expected: assert fails because `summary_md` still contains `image:7`.

- [ ] Step 3: Update prompt template `backend/app/services/summarizer/prompts/base/summarize_section.txt:14-20`. Replace:
  ```
  When referencing an image, use: ![brief description](image:ID)
  ```
  with:
  ```
  When referencing an image, use the absolute URL form: ![brief description](/api/v1/images/ID)
  where ID is the image_id provided in the captions list below.
  ```
  Update the captions loop similarly so it shows `(/api/v1/images/{{ img.image_id }})` instead of `(image:{{ img.image_id }})`.

- [ ] Step 4: Wire `from_image_id_scheme()` into `summarizer_service.py` at all three sites. After each existing `from_placeholder()` call (lines 484, 584, 646), add:
  ```python
  summary_text = from_image_id_scheme(summary_text, image_map, on_missing="strip")
  ```
  Ensure the import at top of file: `from app.services.parser.image_url_rewrite import from_placeholder, from_image_id_scheme`.

- [ ] Step 5: Run — confirm GREEN.
  Run: `cd backend && uv run python -m pytest tests/unit/test_summarizer_image_rewrite.py -v`
  Expected: passed.

- [ ] Step 6: Run existing summarizer tests — confirm no regression.
  Run: `cd backend && uv run python -m pytest tests/unit/test_summarizer*.py tests/integration/test_summarize_integration.py -v`
  Expected: same pre-existing pass/fail counts.

- [ ] Step 7: Commit.
  ```bash
  git add backend/app/services/summarizer/summarizer_service.py backend/app/services/summarizer/prompts/base/summarize_section.txt backend/tests/unit/test_summarizer_image_rewrite.py
  git commit -m "feat(summarizer): emit absolute image URLs and rewrite legacy refs"
  ```

**Inline verification:**
- `grep -n "image:" backend/app/services/summarizer/prompts/base/summarize_section.txt` — should produce no matches against the legacy scheme; only documentation/example references if any.
- `uv run python -m pytest tests/unit/test_summarizer_image_rewrite.py -v` — passed.

---

### B5: Alembic data migration for legacy image:N

**Goal:** Rewrite all existing summaries' `summary_md` to use absolute URLs. Idempotent.
**Spec refs:** FR-07, NFR-06.

**Files:**
- Create: `backend/app/migrations/versions/<auto>_v1_5b_legacy_image_id_rewrite.py`
- Create: `backend/tests/integration/test_migration_image_id_rewrite.py`

**Steps:**

- [ ] Step 1: Generate the migration scaffold.
  ```bash
  cd backend && uv run alembic -c app/migrations/alembic.ini revision -m "v1_5b_legacy_image_id_rewrite"
  ```
  Note the generated filename (e.g., `<hash>_v1_5b_legacy_image_id_rewrite.py`).

- [ ] Step 2: Write the failing integration test:
  ```python
  # backend/tests/integration/test_migration_image_id_rewrite.py
  import pytest
  from sqlalchemy import text

  @pytest.mark.asyncio
  async def test_migration_rewrites_legacy_image_refs(db_session, seeded_summary_with_legacy_image):
      # Seed must insert a Summary with summary_md='before ![x](image:5) after' and an Image row with id=5
      from app.migrations.versions import _last_revision_module  # see helper below
      await _last_revision_module().upgrade()  # or invoke via alembic API
      await db_session.refresh(seeded_summary_with_legacy_image)
      assert "image:5" not in seeded_summary_with_legacy_image.summary_md
      assert "/api/v1/images/5" in seeded_summary_with_legacy_image.summary_md

  @pytest.mark.asyncio
  async def test_migration_idempotent(db_session, seeded_summary_with_legacy_image):
      from app.migrations.versions import _last_revision_module
      await _last_revision_module().upgrade()
      first_md = seeded_summary_with_legacy_image.summary_md
      await _last_revision_module().upgrade()  # rerun
      await db_session.refresh(seeded_summary_with_legacy_image)
      assert seeded_summary_with_legacy_image.summary_md == first_md
  ```
  If invoking the migration directly in-test is awkward, use Alembic's programmatic API:
  ```python
  from alembic.config import Config
  from alembic import command
  cfg = Config("app/migrations/alembic.ini")
  command.upgrade(cfg, "head")
  ```
  Pattern this after `tests/integration/test_migration_*.py` if any exist; otherwise the v1.5a image-rewrite migration test is the closest precedent — read it before writing.

- [ ] Step 3: Run — confirm RED.
  Run: `cd backend && uv run python -m pytest tests/integration/test_migration_image_id_rewrite.py -v`
  Expected: FAIL — migration does nothing.

- [ ] Step 4: Implement the migration. Mirror `c9d0e1f2a3b4_v1_5a_summary_image_rewrite.py:32-66`:
  ```python
  """v1_5b legacy image:N rewrite

  Revision ID: <auto>
  Revises: <prev>
  Create Date: 2026-04-30 ...
  """
  from alembic import op
  import sqlalchemy as sa
  import re

  LEGACY_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(image:(\d+)\)")

  def upgrade():
      conn = op.get_bind()
      # Find candidate summaries
      rows = conn.execute(sa.text(
          "SELECT s.id, s.book_id, s.summary_md FROM summaries s "
          "WHERE s.summary_md LIKE '%](image:%'"
      )).fetchall()

      updated = 0
      for row in rows:
          # Build per-book image_id set
          ids = {r[0] for r in conn.execute(
              sa.text("SELECT id FROM images WHERE book_id = :bid"), {"bid": row.book_id}
          ).fetchall()}

          def _replace(m):
              alt, raw_id = m.group(1), m.group(2)
              image_id = int(raw_id)
              if image_id in ids:
                  return f"![{alt}](/api/v1/images/{image_id})"
              return f"[{alt}](#)"

          new_md = LEGACY_IMAGE_RE.sub(_replace, row.summary_md)
          if new_md != row.summary_md:
              conn.execute(
                  sa.text("UPDATE summaries SET summary_md = :md WHERE id = :id"),
                  {"md": new_md, "id": row.id},
              )
              updated += 1

      print(f"v1_5b_legacy_image_id_rewrite: rewrote {updated} summaries")

  def downgrade():
      pass  # forward-only data migration
  ```

- [ ] Step 5: Run — confirm GREEN.
  Run: `cd backend && uv run python -m pytest tests/integration/test_migration_image_id_rewrite.py -v`
  Expected: 2 passed.

- [ ] Step 6: Sanity-check on a fresh DB.
  ```bash
  cd backend && rm -f /tmp/spec-test.db && BOOKCOMPANION_DATABASE__URL=sqlite+aiosqlite:////tmp/spec-test.db uv run alembic -c app/migrations/alembic.ini upgrade head
  ```
  Expected: completes without error; final line includes "v1_5b_legacy_image_id_rewrite: rewrote 0 summaries" (empty DB).

- [ ] Step 7: Commit.
  ```bash
  git add backend/app/migrations/versions/<file> backend/tests/integration/test_migration_image_id_rewrite.py
  git commit -m "feat(db): one-shot migration to rewrite legacy image:N refs"
  ```

**Inline verification:**
- Fresh DB upgrades with no error.
- `uv run python -m pytest tests/integration/test_migration_image_id_rewrite.py -v` — 2 passed.

---

### B6: GET /api/v1/processing/{job_id} endpoint

**Goal:** Expose full job state for the JobProgressView deep-link.
**Spec refs:** FR-10, NFR-04.

**Files:**
- Modify: `backend/app/api/routes/processing.py`
- Create: `backend/tests/integration/test_api/test_processing_get_endpoint.py`

**Steps:**

- [ ] Step 0: Verify `ProcessingJob.book` relationship presence:
  ```bash
  cd backend && grep -nE "book.*relationship\(|book\s*:\s*Mapped\[\"Book\"\]" app/db/models.py
  ```
  Expected: a relationship line near the ProcessingJob model (lines ~282-321). If absent, the next step adds it; if present, skip the addition. Capture the result before continuing so the implementor knows which branch to take.

- [ ] Step 1: Write failing tests covering all 5 paths (PENDING, RUNNING, COMPLETED, FAILED, 404):
  ```python
  # backend/tests/integration/test_api/test_processing_get_endpoint.py
  import pytest
  from datetime import datetime, timezone
  from app.db.models import ProcessingJob, ProcessingJobStatus

  @pytest.mark.asyncio
  @pytest.mark.parametrize("status", [
      ProcessingJobStatus.PENDING,
      ProcessingJobStatus.RUNNING,
      ProcessingJobStatus.COMPLETED,
      ProcessingJobStatus.FAILED,
  ])
  async def test_get_job_returns_correct_shape(app_client, db_session, seeded_book, status):
      job = ProcessingJob(
          book_id=seeded_book.id,
          status=status,
          step="summarize",
          started_at=datetime.now(timezone.utc),
          completed_at=datetime.now(timezone.utc) if status in (ProcessingJobStatus.COMPLETED, ProcessingJobStatus.FAILED) else None,
          progress={"current": 5, "total": 10, "current_section_title": "X"},
          request_params={"scope": "all"},
          error_message="boom" if status == ProcessingJobStatus.FAILED else None,
      )
      db_session.add(job)
      await db_session.commit()

      r = await app_client.get(f"/api/v1/processing/{job.id}")
      assert r.status_code == 200
      body = r.json()
      assert body["id"] == job.id
      assert body["book_id"] == seeded_book.id
      assert body["book_title"] == seeded_book.title
      assert body["status"] == status.value
      assert body["scope"] == "all"
      assert body["section_id"] is None
      assert body["progress"]["current"] == 5
      assert body["progress"]["total"] == 10
      assert body["progress"]["current_section_title"] == "X"
      assert "started_at" in body
      if status in (ProcessingJobStatus.COMPLETED, ProcessingJobStatus.FAILED):
          assert body["completed_at"] is not None
      if status == ProcessingJobStatus.FAILED:
          assert body["error_message"] == "boom"

  @pytest.mark.asyncio
  async def test_get_job_404(app_client):
      r = await app_client.get("/api/v1/processing/9999999")
      assert r.status_code == 404
  ```

- [ ] Step 2: Run — confirm RED.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_get_endpoint.py -v`
  Expected: 404 on the GET (route doesn't exist yet); fail.

- [ ] Step 3: Implement the route in `backend/app/api/routes/processing.py`:
  ```python
  @router.get("/{job_id}")
  async def get_job(
      job_id: int,
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      result = await db.execute(
          select(ProcessingJob)
          .options(selectinload(ProcessingJob.book))
          .where(ProcessingJob.id == job_id)
      )
      job = result.scalar_one_or_none()
      if job is None:
          raise HTTPException(status_code=404, detail="Job not found")
      params = job.request_params or {}
      return {
          "id": job.id,
          "book_id": job.book_id,
          "book_title": job.book.title if job.book else None,
          "status": job.status.value,
          "scope": params.get("scope"),
          "section_id": params.get("section_id"),
          "progress": job.progress or {"current": 0, "total": 0, "current_section_title": None, "eta_seconds": None},
          "started_at": job.started_at.isoformat() if job.started_at else None,
          "completed_at": job.completed_at.isoformat() if job.completed_at else None,
          "error_message": job.error_message,
          "last_event_at": job.last_event_at.isoformat() if job.last_event_at else None,
      }
  ```
  If `ProcessingJob.book` relationship isn't defined, add it: `book: Mapped["Book"] = relationship("Book")`. Verify by running the existing migrations against a fresh DB.

  **Route ordering:** This route MUST be registered BEFORE `/api/v1/processing/{job_id}/stream` and `/api/v1/processing/{job_id}/cancel` only if FastAPI is configured with strict-mode path matching. In practice, FastAPI's matcher is path-aware, so order doesn't matter, but the new GET should sit next to the existing GET-stream block for readability.

- [ ] Step 4: Run — confirm GREEN.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_processing_get_endpoint.py -v`
  Expected: 5 passed (4 status × 1 + 1 404).

- [ ] Step 5: Performance check.
  ```bash
  cd backend && uv run python -c "
  import asyncio, time
  from httpx import AsyncClient
  from app.api.main import create_app
  async def go():
      app = create_app()
      async with AsyncClient(app=app, base_url='http://test') as c:
          await c.post('/api/v1/init')  # if needed
          # seed via db directly...
          start = time.perf_counter_ns()
          r = await c.get('/api/v1/processing/1')
          print(f'{(time.perf_counter_ns()-start)/1e6:.2f}ms', r.status_code)
  asyncio.run(go())
  "
  ```
  Expected: < 50ms per NFR-04. If it exceeds, check whether `selectinload` is firing.

- [ ] Step 6: Commit.
  ```bash
  git add backend/app/api/routes/processing.py backend/tests/integration/test_api/test_processing_get_endpoint.py
  git commit -m "feat(api): GET /api/v1/processing/{job_id} for deep-link view"
  ```

**Inline verification:**
- `uv run python -m pytest tests/integration/test_api/test_processing_get_endpoint.py -v` — 5 passed.
- Manual: spin up server, `curl -s http://localhost:8000/api/v1/processing/1 | python3 -m json.tool` — shows expected keys.

---

### B7: Add `content_char_count` to SectionBrief

**Goal:** Expose character count via the books endpoint without fetching full markdown bodies.
**Spec refs:** FR-32, NFR-03.

**Files:**
- Modify: `backend/app/db/models.py:186-235`
- Modify: `backend/app/api/schemas.py:62-70`
- Modify: `backend/app/api/routes/books.py:64-74`
- Create: `backend/tests/integration/test_api/test_book_detail_char_count.py`

**Steps:**

- [ ] Step 1: Write the failing integration test:
  ```python
  # backend/tests/integration/test_api/test_book_detail_char_count.py
  import pytest

  @pytest.mark.asyncio
  async def test_section_brief_includes_content_char_count(app_client, seeded_book_with_sections):
      r = await app_client.get(f"/api/v1/books/{seeded_book_with_sections.id}")
      assert r.status_code == 200
      body = r.json()
      sections = body["sections"]
      assert len(sections) > 0
      # Compare to actual content_md length on the seeded data
      for s in sections:
          assert "content_char_count" in s
          assert isinstance(s["content_char_count"], int)
          assert s["content_char_count"] >= 0

  @pytest.mark.asyncio
  async def test_section_with_null_content_md_has_zero_char_count(app_client, db_session, seeded_book):
      from app.db.models import BookSection
      s = BookSection(book_id=seeded_book.id, title="Empty", order_index=99, section_type="chapter", content_md=None)
      db_session.add(s)
      await db_session.commit()
      r = await app_client.get(f"/api/v1/books/{seeded_book.id}")
      brief = next(x for x in r.json()["sections"] if x["title"] == "Empty")
      assert brief["content_char_count"] == 0
  ```

- [ ] Step 2: Run — confirm RED (`KeyError: 'content_char_count'`).

- [ ] Step 3: Add `column_property` to `BookSection` in `backend/app/db/models.py`:
  ```python
  from sqlalchemy.orm import column_property
  from sqlalchemy import func

  class BookSection(Base):
      # ... existing fields ...
      content_char_count = column_property(
          func.coalesce(func.length(content_md), 0)
      )
  ```
  Note: `column_property` references the column attribute, so define it AFTER the `content_md` mapped_column.

- [ ] Step 4: Add field to schema in `backend/app/api/schemas.py`:
  ```python
  class SectionBriefResponse(BaseModel):
      # ... existing fields ...
      content_char_count: int = 0
  ```

- [ ] Step 5: Update `_book_to_response()` in `backend/app/api/routes/books.py:64-74`:
  ```python
  SectionBriefResponse(
      id=s.id,
      title=s.title,
      order_index=s.order_index,
      section_type=s.section_type,
      content_token_count=s.content_token_count,
      has_summary=s.default_summary_id is not None,
      content_char_count=s.content_char_count or 0,
  )
  ```

- [ ] Step 6: Run — confirm GREEN.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_book_detail_char_count.py -v`
  Expected: 2 passed.

- [ ] Step 7: Run full books-route suite.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_books*.py -v`
  Expected: pre-existing pass count + 2 new passes; 0 regressions.

- [ ] Step 8: **Perf-regression check** — `column_property` could change the SQL emitted by existing `selectinload(Book.sections)` queries. Capture the SQL emitted by GET /books/{id} via the `before_cursor_execute` event listener and assert `content_md` is NOT in the projection (only `LENGTH(content_md)`):
  ```python
  # backend/tests/integration/test_api/test_book_detail_char_count.py — additional test
  import pytest
  from sqlalchemy import event

  @pytest.mark.asyncio
  async def test_book_detail_query_does_not_select_full_content_md(app_client, seeded_book_with_sections, db_engine):
      captured = []

      def listener(conn, cursor, statement, *_):
          captured.append(statement)

      event.listen(db_engine.sync_engine, "before_cursor_execute", listener)
      try:
          r = await app_client.get(f"/api/v1/books/{seeded_book_with_sections.id}")
          assert r.status_code == 200
      finally:
          event.remove(db_engine.sync_engine, "before_cursor_execute", listener)

      # Find the query that selected from book_sections
      section_queries = [q for q in captured if "book_sections" in q.lower() and "select" in q.lower()]
      assert section_queries, "Expected a SELECT against book_sections"
      for q in section_queries:
          # content_md must appear ONLY inside LENGTH(...) — not as a bare projection column
          # Strict check: the bare token "book_sections.content_md" should not appear
          # (LENGTH(book_sections.content_md) is fine)
          stripped = q.replace("LENGTH(book_sections.content_md)", "").replace("length(book_sections.content_md)", "")
          assert "book_sections.content_md" not in stripped, f"Full content_md selected: {q}"
  ```
  If this fails (i.e., `content_md` is being eager-loaded), confirm in `models.py` that the column is `deferred(mapped_column(...))` — the existing model may already mark it deferred for parser-pipeline reasons. If not, add `deferred=True` or use `defer(BookSection.content_md)` in the books-route query.

- [ ] Step 9: Verify the SQL projection — `column_property` should NOT cause `content_md` itself to be loaded:
  ```bash
  cd backend && uv run python -c "
  import asyncio
  from sqlalchemy import select
  from app.db.session import get_session_factory
  from app.db.models import BookSection
  async def go():
      sf = get_session_factory()
      async with sf() as s:
          q = select(BookSection.id, BookSection.content_char_count).limit(1)
          print(str(q.compile(compile_kwargs={'literal_binds': True})))
  asyncio.run(go())
  "
  ```
  Expected: SQL contains `LENGTH(book_sections.content_md)` projection, not the full column.

- [ ] Step 10: Commit.
  ```bash
  git add backend/app/db/models.py backend/app/api/schemas.py backend/app/api/routes/books.py backend/tests/integration/test_api/test_book_detail_char_count.py
  git commit -m "feat(api): expose content_char_count on SectionBrief"
  ```

**Inline verification:**
- `uv run python -m pytest tests/integration/test_api/test_book_detail_char_count.py -v` — 2 passed.
- `uv run python -m pytest tests/integration/test_api/test_books*.py` — pre-existing passes preserved.

---

### B8: Alembic migration for preset typography

**Goal:** Apply spec §11.3 typography combinations to the 6 system presets, idempotently.
**Spec refs:** FR-34, NFR-06.

**Files:**
- Create: `backend/app/migrations/versions/<auto>_v1_5b_preset_typography.py`
- Create: `backend/tests/integration/test_migration_preset_typography.py`

**Steps:**

- [ ] Step 1: Generate scaffold.
  ```bash
  cd backend && uv run alembic -c app/migrations/alembic.ini revision -m "v1_5b_preset_typography"
  ```

- [ ] Step 2: Write failing test:
  ```python
  # backend/tests/integration/test_migration_preset_typography.py
  import pytest
  from sqlalchemy import text
  from alembic.config import Config
  from alembic import command

  EXPECTED = {
      "Light":         ("Georgia", 16, 1.6, 720, "light"),
      "Sepia":         ("Georgia", 17, 1.7, 680, "sepia"),
      "Dark":          ("Inter",   16, 1.6, 720, "dark"),
      "Night":         ("Inter",   18, 1.7, 680, "night"),
      "Paper":         ("Lora",    17, 1.8, 640, "paper"),
      "High Contrast": ("Inter",   18, 1.7, 700, "contrast"),
  }

  @pytest.mark.asyncio
  async def test_migration_updates_presets_to_spec_values(db_session):
      cfg = Config("app/migrations/alembic.ini")
      command.upgrade(cfg, "head")
      rows = (await db_session.execute(text("SELECT name, font_family, font_size_px, line_spacing, content_width_px, theme FROM reading_presets"))).all()
      by_name = {r.name: r for r in rows}
      for name, (font, size, lh, width, theme) in EXPECTED.items():
          row = by_name[name]
          assert row.font_family == font, f"{name}: font {row.font_family} != {font}"
          assert row.font_size_px == size
          assert row.line_spacing == lh
          assert row.content_width_px == width
          assert row.theme == theme

  @pytest.mark.asyncio
  async def test_migration_idempotent(db_session):
      cfg = Config("app/migrations/alembic.ini")
      command.upgrade(cfg, "head")
      first = (await db_session.execute(text("SELECT * FROM reading_presets ORDER BY name"))).all()
      command.upgrade(cfg, "head")  # rerun
      second = (await db_session.execute(text("SELECT * FROM reading_presets ORDER BY name"))).all()
      assert [tuple(r) for r in first] == [tuple(r) for r in second]
  ```

- [ ] Step 3: Run — confirm RED.

- [ ] Step 4: Implement migration. Mirror `a5459240fea0_v1_5_1_collapse_reading_presets.py:53-93` for the idempotent guard pattern:
  ```python
  from alembic import op
  import sqlalchemy as sa

  PRESETS = [
      ("Light",         "Georgia", 16, 1.6, 720, "light"),
      ("Sepia",         "Georgia", 17, 1.7, 680, "sepia"),
      ("Dark",          "Inter",   16, 1.6, 720, "dark"),
      ("Night",         "Inter",   18, 1.7, 680, "night"),
      ("Paper",         "Lora",    17, 1.8, 640, "paper"),
      ("High Contrast", "Inter",   18, 1.7, 700, "contrast"),
  ]

  def upgrade():
      conn = op.get_bind()
      for name, font, size, lh, width, theme in PRESETS:
          # Idempotent guard: only update if current values match the original tuple.
          # Preserves user customizations.
          conn.execute(
              sa.text(
                  "UPDATE reading_presets "
                  "SET font_family=:font, font_size_px=:size, line_spacing=:lh, content_width_px=:width, theme=:theme "
                  "WHERE name=:name "
                  "AND font_family='Georgia' AND font_size_px=16 AND line_spacing=1.6 AND content_width_px=720"
              ),
              {"name": name, "font": font, "size": size, "lh": lh, "width": width, "theme": theme},
          )

  def downgrade():
      pass
  ```
  Note: per spec §11.3, the WHERE guard locks against the ORIGINAL tuple, not the per-preset target. So Light's row is updated only if it currently equals Georgia/16/1.6/720; if a user already changed Light to e.g. Inter/14/1.5, the migration leaves it.

- [ ] Step 5: Run — confirm GREEN.

- [ ] Step 6: Commit.
  ```bash
  git add backend/app/migrations/versions/<file> backend/tests/integration/test_migration_preset_typography.py
  git commit -m "feat(db): preset typography migration to spec §11.3 values"
  ```

**Inline verification:**
- `uv run python -m pytest tests/integration/test_migration_preset_typography.py -v` — 2 passed.
- Fresh DB: `rm -f /tmp/spec-test.db && BOOKCOMPANION_DATABASE__URL=sqlite+aiosqlite:////tmp/spec-test.db uv run alembic -c app/migrations/alembic.ini upgrade head` — completes; presets show new values.

---

### F1: Bundle webfonts via @fontsource

**Goal:** Ship Inter, Merriweather, Lora, Fira Code, Source Serif Pro in the build so reader presets render with intended typography on any machine.
**Spec refs:** FR-39, FR-39a, FR-40, NFR-05.

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.ts`
- Create: `frontend/src/assets/fonts.ts` (or inline in main.ts; D below)
- Modify: `frontend/src/assets/theme.css` (font fallback chains documented in CSS comments)

**Steps:**

- [ ] Step 1: Install packages.
  ```bash
  cd frontend && npm install @fontsource/inter @fontsource/merriweather @fontsource/lora @fontsource/fira-code @fontsource/source-serif-pro
  ```

- [ ] Step 2: Verify bundle size baseline (so we can confirm NFR-05 after).
  ```bash
  cd frontend && npm run build
  du -sh dist/assets/ | tee /tmp/bundle-baseline.txt
  ```
  Note the size.

- [ ] Step 3: Create `frontend/src/assets/fonts.ts` with selective weight imports per FR-40:
  ```ts
  // Inter: 400 + 700
  import '@fontsource/inter/400.css'
  import '@fontsource/inter/700.css'
  // Merriweather: 400 + 700
  import '@fontsource/merriweather/400.css'
  import '@fontsource/merriweather/700.css'
  // Lora: 400 + 600
  import '@fontsource/lora/400.css'
  import '@fontsource/lora/600.css'
  // Fira Code: 400
  import '@fontsource/fira-code/400.css'
  // Source Serif Pro: 400 + 700
  import '@fontsource/source-serif-pro/400.css'
  import '@fontsource/source-serif-pro/700.css'
  ```

- [ ] Step 4: Import `./assets/fonts` in `frontend/src/main.ts` near the top (after `./assets/main.css`).

- [ ] Step 5: Verify `font-display: swap` is set. `@fontsource` packages default to swap, but confirm by inspecting one of the generated CSS files in node_modules:
  ```bash
  grep -l "font-display" frontend/node_modules/@fontsource/inter/400.css
  cat frontend/node_modules/@fontsource/inter/400.css | head -10
  ```
  Expected: `font-display: swap;` present in the `@font-face` block.

- [ ] Step 5b (only if Step 5 finds `font-display: swap` ABSENT): create `frontend/src/assets/fonts.css` with explicit `@font-face` declarations pointing at the bundled woff2 paths and force swap. This bypasses the `@fontsource/*/400.css` import in favor of writing our own face rules:
  ```css
  /* fonts.css — explicit swap override when @fontsource defaults differ */
  @font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url('@fontsource/inter/files/inter-latin-400-normal.woff2') format('woff2');
  }
  /* ...repeat per font + weight per FR-40... */
  ```
  Then in `frontend/src/main.ts`, replace the `./assets/fonts` import with `./assets/fonts.css`. Document the deviation in the commit body. Confirm via DevTools Network panel that the woff2 files load with `font-display: swap` semantics (text renders in fallback immediately, swaps in within ~100ms).

- [ ] Step 6: Update reader-CSS application to include fallback chains. In `frontend/src/stores/readerSettings.ts:213-224` (or wherever font_family is applied), ensure the resolved font-family string includes a fallback:
  ```ts
  const FALLBACK_CHAINS: Record<string, string> = {
    'Georgia': "Georgia, 'Lora', 'Merriweather', serif",
    'Inter': "'Inter', system-ui, -apple-system, sans-serif",
    'Merriweather': "'Merriweather', 'Lora', Georgia, serif",
    'Fira Code': "'Fira Code', 'Source Code Pro', monospace",
    'Lora': "'Lora', 'Merriweather', Georgia, serif",
    'Source Serif Pro': "'Source Serif Pro', 'Lora', 'Merriweather', serif",
  }
  root.style.setProperty('--reader-font-family', FALLBACK_CHAINS[settings.font_family] ?? settings.font_family)
  ```

- [ ] Step 7: Build and check bundle size against NFR-05.
  ```bash
  cd frontend && npm run build
  du -sh dist/assets/ | tee /tmp/bundle-after.txt
  diff /tmp/bundle-baseline.txt /tmp/bundle-after.txt
  ls -lh dist/assets/*.woff2 2>/dev/null | head
  # Sum just the woff2 files
  ls -l dist/assets/*.woff2 2>/dev/null | awk '{s+=$5} END {printf "woff2 total: %.0f KB\n", s/1024}'
  ```
  Expected: woff2 total ≤ 600KB. If over, drop a non-essential weight (start with Source Serif Pro 700 or Merriweather 700) and re-run.

- [ ] Step 8: Run unit tests to confirm no regression.
  Run: `cd frontend && npm run test:unit`

- [ ] Step 9: Commit.
  ```bash
  git add frontend/package.json frontend/package-lock.json frontend/src/main.ts frontend/src/assets/fonts.ts frontend/src/stores/readerSettings.ts
  git commit -m "feat(fonts): bundle reader webfonts via @fontsource with fallback chains"
  ```

**Inline verification:**
- `cd frontend && npm run build` — passes; woff2 total < 600KB per `ls -l` math above.
- `npm run test:unit` — no new failures.

---

### F2: Theme CSS coverage for night/paper/contrast

**Goal:** All 6 theme presets have full CSS-variable coverage so clicking is never a no-op.
**Spec refs:** FR-35.

**Files:**
- Modify: `frontend/src/assets/theme.css`

**Steps:**

- [ ] Step 1: Read current `theme.css` to confirm light/dark/sepia variable list (17 vars per spec §11.4 / §6.3 + observed: bg primary/secondary/tertiary/muted/elevated, text primary/secondary/tertiary/inverted, border/border-strong, accent, success/warning/error, sidebar-bg, highlight-bg).

- [ ] Step 2: Append the three new theme blocks. Use the night palette from spec §11.4 verbatim. Derive paper and contrast palettes per Decision Log P5 and lock them:
  ```css
  /* Night — deep navy, low-saturation; designed for OLED + late-night */
  [data-theme='night'] {
    --color-bg-primary: #0a0e1a;
    --color-bg-secondary: #111827;
    --color-bg-tertiary: #1f2937;
    --color-bg-muted: #1a2030;
    --color-bg-elevated: #1f2937;
    --color-text-primary: #e5e7eb;
    --color-text-secondary: #9ca3af;
    --color-text-tertiary: #6b7280;
    --color-text-inverted: #0a0e1a;
    --color-border: #374151;
    --color-border-strong: #4b5563;
    --color-accent: #818cf8;
    --color-success: #34d399;
    --color-warning: #fbbf24;
    --color-error: #f87171;
    --color-sidebar-bg: #0a0e1a;
    --color-highlight-bg: #fde68a40;
  }

  /* Paper — warm cream + soft serif feel */
  [data-theme='paper'] {
    --color-bg-primary: #f7f1e3;
    --color-bg-secondary: #efe6d2;
    --color-bg-tertiary: #e8ddc6;
    --color-bg-muted: #f0e8d4;
    --color-bg-elevated: #fbf6e8;
    --color-text-primary: #2d2417;
    --color-text-secondary: #5e5340;
    --color-text-tertiary: #8a7d65;
    --color-text-inverted: #f7f1e3;
    --color-border: #d6c9aa;
    --color-border-strong: #b8a884;
    --color-accent: #8b6f3c;
    --color-success: #5a7a3a;
    --color-warning: #b07a26;
    --color-error: #a14a3a;
    --color-sidebar-bg: #efe6d2;
    --color-highlight-bg: #f5d97f60;
  }

  /* Contrast — pure black/white, blue accent; AA+ everywhere */
  [data-theme='contrast'] {
    --color-bg-primary: #000000;
    --color-bg-secondary: #0a0a0a;
    --color-bg-tertiary: #1a1a1a;
    --color-bg-muted: #111111;
    --color-bg-elevated: #1a1a1a;
    --color-text-primary: #ffffff;
    --color-text-secondary: #e0e0e0;
    --color-text-tertiary: #b0b0b0;
    --color-text-inverted: #000000;
    --color-border: #ffffff;
    --color-border-strong: #ffffff;
    --color-accent: #4da3ff;
    --color-success: #00e676;
    --color-warning: #ffd600;
    --color-error: #ff5252;
    --color-sidebar-bg: #000000;
    --color-highlight-bg: #ffd60080;
  }
  ```
  Cross-check against the existing block: if your codebase's variable names differ (e.g., `--color-text-muted` instead of `--color-text-tertiary`), unify to whatever light/sepia/dark uses. The plan's list above is the spec's; the actual file's vocabulary wins.

- [ ] Step 3: Verify all 6 themes have the same set of variable names. Run the spec's coverage command:
  ```bash
  cd frontend && grep -E "^\[data-theme='(light|sepia|dark|night|paper|contrast)'\]" src/assets/theme.css | sort -u | wc -l
  ```
  Expected: `6`.

- [ ] Step 4: Verify each block defines the same variables. Quick parity check:
  ```bash
  cd frontend && python3 -c "
  import re
  src = open('src/assets/theme.css').read()
  blocks = re.findall(r\"\[data-theme='(\w+)'\]\s*\{([^}]+)\}\", src, re.S)
  for name, body in blocks:
      vars = sorted(re.findall(r'--[\w-]+', body))
      print(name, len(vars), vars[:3], '...')
  "
  ```
  Expected: each theme reports the same count.

- [ ] Step 5: Commit.
  ```bash
  git add frontend/src/assets/theme.css
  git commit -m "feat(theme): add full CSS variables for night/paper/contrast"
  ```

**Inline verification:**
- Coverage grep returns 6.
- Variable parity Python check — equal counts per theme.
- `npm run type-check && npm run lint` — clean.

---

### F3: SectionListTable shared component

**Goal:** One component drives the book-detail table and the reader-TOC dropdown with `compact` prop.
**Spec refs:** FR-27 to FR-33, FR-33a, NFR-07, E15 (mobile per OQ2).

**Files:**
- Create: `frontend/src/components/book/SectionListTable.vue`
- Create: `frontend/src/components/book/__tests__/SectionListTable.spec.ts`

**Steps:**

- [ ] Step 1: Write failing tests:
  ```ts
  // frontend/src/components/book/__tests__/SectionListTable.spec.ts
  import { describe, it, expect } from 'vitest'
  import { mount } from '@vue/test-utils'
  import SectionListTable from '../SectionListTable.vue'
  import { createRouter, createMemoryHistory } from 'vue-router'

  const sections = [
    { id: 1, title: 'Intro',     order_index: 0, section_type: 'frontmatter', content_char_count: 1000, has_summary: true,  default_summary: { summary_char_count: 200 } },
    { id: 2, title: 'Chapter 1', order_index: 1, section_type: 'chapter',     content_char_count: 5000, has_summary: true,  default_summary: { summary_char_count: 800 } },
    { id: 3, title: 'Chapter 2', order_index: 2, section_type: 'chapter',     content_char_count: 4000, has_summary: false },
  ]

  function makeRouter() {
    return createRouter({ history: createMemoryHistory(), routes: [{ path: '/books/:id/sections/:sectionId', name: 'section-detail', component: { template: '<div/>' } }] })
  }

  describe('SectionListTable', () => {
    it('renders all 6 columns in default mode', () => {
      const wrapper = mount(SectionListTable, {
        props: { sections, bookId: 1, compact: false },
        global: { plugins: [makeRouter()] },
      })
      const headers = wrapper.findAll('th').map(h => h.text())
      expect(headers).toEqual(expect.arrayContaining(['#', 'Title', 'Type', 'Chars', 'Summary', 'Compression']))
    })

    it('hides Type and Compression in compact mode', () => {
      const wrapper = mount(SectionListTable, {
        props: { sections, bookId: 1, compact: true },
        global: { plugins: [makeRouter()] },
      })
      const headers = wrapper.findAll('th').map(h => h.text())
      expect(headers).not.toContain('Type')
      expect(headers).not.toContain('Compression')
      expect(headers).toContain('Title')
    })

    it('formats compression as percent to one decimal', () => {
      const wrapper = mount(SectionListTable, {
        props: { sections, bookId: 1, compact: false },
        global: { plugins: [makeRouter()] },
      })
      // Row 2: 800 / 5000 = 16.0%
      expect(wrapper.html()).toContain('16.0%')
    })

    it('shows em-dash when no summary', () => {
      const wrapper = mount(SectionListTable, {
        props: { sections, bookId: 1, compact: false },
        global: { plugins: [makeRouter()] },
      })
      // Row 3 has no summary — Compression cell shows —
      const rows = wrapper.findAll('tbody tr')
      expect(rows[2].text()).toMatch(/—/)
    })

    it('shows em-dash when content_char_count is 0', () => {
      const wrapper = mount(SectionListTable, {
        props: {
          sections: [{ id: 4, title: 'Empty', order_index: 0, section_type: 'chapter', content_char_count: 0, has_summary: true, default_summary: { summary_char_count: 100 } }],
          bookId: 1, compact: false,
        },
        global: { plugins: [makeRouter()] },
      })
      expect(wrapper.text()).toContain('—')
    })

    it('renders separator row between section_type changes', () => {
      const wrapper = mount(SectionListTable, {
        props: { sections, bookId: 1, compact: false },
        global: { plugins: [makeRouter()] },
      })
      // Between row 1 (frontmatter) and row 2 (chapter) there should be a separator tr
      expect(wrapper.findAll('tr.section-type-separator').length).toBe(1)
    })

    it('keyboard nav: focusing first row + ArrowDown moves to next', async () => {
      const wrapper = mount(SectionListTable, {
        props: { sections, bookId: 1, compact: false },
        attachTo: document.body,
        global: { plugins: [makeRouter()] },
      })
      const rows = wrapper.findAll('tr[role="link"]')
      ;(rows[0].element as HTMLElement).focus()
      await rows[0].trigger('keydown', { key: 'ArrowDown' })
      expect(document.activeElement).toBe(rows[1].element)
    })

    it('row click navigates with ?tab preserved when calling context provides currentSectionId', async () => {
      // calling context = reader TOC: tab preservation
      const router = makeRouter()
      const wrapper = mount(SectionListTable, {
        props: { sections, bookId: 1, compact: true, currentSectionId: 1 },
        global: { plugins: [router] },
      })
      // Simulate URL having ?tab=summary
      await router.push({ path: '/books/1/sections/1', query: { tab: 'summary' } })
      const rows = wrapper.findAll('tr[role="link"]')
      await rows[1].trigger('click')
      expect(router.currentRoute.value.fullPath).toContain('tab=summary')
    })
  })
  ```

- [ ] Step 2: Run — confirm RED.
  Run: `cd frontend && npm run test:unit -- SectionListTable`
  Expected: import-fail; component doesn't exist.

- [ ] Step 3: Implement `frontend/src/components/book/SectionListTable.vue`:
  ```vue
  <script setup lang="ts">
  import { computed, ref } from 'vue'
  import { useRouter, useRoute } from 'vue-router'
  import { useSummarizationJobStore } from '@/stores/summarizationJob'

  interface Section {
    id: number
    title: string
    order_index: number
    section_type: string
    content_char_count: number
    has_summary: boolean
    default_summary?: { summary_char_count: number } | null
    last_failure_type?: string | null
  }

  const props = withDefaults(defineProps<{
    sections: Section[]
    bookId: number
    compact?: boolean
    currentSectionId?: number
  }>(), { compact: false })

  const router = useRouter()
  const route = useRoute()
  const jobStore = useSummarizationJobStore()

  // Live updates from SSE in non-compact mode (FR-33a)
  // Compact mode does NOT subscribe — see Decision Log P8.
  // The store is shared; we just react to its events when relevant.
  const liveStatuses = ref<Record<number, 'pending' | 'completed' | 'failed' | 'retrying'>>({})

  // Watch jobStore for events targeting our book
  // (implementation details: when an event arrives for a section in our list, update liveStatuses[id])
  // Skip wiring in compact mode.

  const sortedSections = computed(() => [...props.sections].sort((a, b) => a.order_index - b.order_index))

  function compressionLabel(s: Section): string {
    if (!s.has_summary || !s.default_summary || s.content_char_count === 0) return '—'
    const pct = (s.default_summary.summary_char_count / s.content_char_count) * 100
    return `${pct.toFixed(1)}%`
  }

  function summaryStatus(s: Section): { label: string, kind: 'done' | 'pending' | 'failed' | 'stale' | 'none' } {
    const live = liveStatuses.value[s.id]
    if (live === 'completed') return { label: '✓', kind: 'done' }
    if (live === 'failed') return { label: 'failed', kind: 'failed' }
    if (live === 'retrying') return { label: 'retrying…', kind: 'pending' }
    if (live === 'pending') return { label: 'pending', kind: 'pending' }
    if (s.has_summary) return { label: '✓', kind: 'done' }
    if (s.last_failure_type) return { label: 'failed', kind: 'failed' }
    return { label: '—', kind: 'none' }
  }

  function onRowClick(s: Section) {
    const query: Record<string, string> = {}
    // Preserve ?tab only when called from reader-TOC context (currentSectionId provided)
    if (props.currentSectionId !== undefined && route.query.tab) {
      query.tab = String(route.query.tab)
    }
    router.push({ name: 'section-detail', params: { id: String(props.bookId), sectionId: String(s.id) }, query })
  }

  function onRowKeydown(e: KeyboardEvent, idx: number) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      const next = (e.currentTarget as HTMLElement).parentElement?.querySelectorAll('tr[role="link"]')?.[idx + 1]
      ;(next as HTMLElement | undefined)?.focus()
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      const prev = (e.currentTarget as HTMLElement).parentElement?.querySelectorAll('tr[role="link"]')?.[idx - 1]
      ;(prev as HTMLElement | undefined)?.focus()
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onRowClick(sortedSections.value[idx])
    }
  }

  function showSeparatorBefore(idx: number): boolean {
    if (idx === 0) return false
    return sortedSections.value[idx].section_type !== sortedSections.value[idx - 1].section_type
  }
  </script>

  <template>
    <table class="section-list-table" :class="{ compact }">
      <thead>
        <tr>
          <th>#</th>
          <th>Title</th>
          <th v-if="!compact">Type</th>
          <th>Chars</th>
          <th>Summary</th>
          <th v-if="!compact">Compression</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(s, idx) in sortedSections" :key="s.id">
          <tr v-if="showSeparatorBefore(idx)" class="section-type-separator" aria-hidden="true">
            <td :colspan="compact ? 4 : 6"></td>
          </tr>
          <tr
            role="link"
            tabindex="0"
            :class="{ 'is-current': s.id === currentSectionId }"
            @click="onRowClick(s)"
            @keydown="onRowKeydown($event, idx)"
          >
            <td>{{ s.order_index + 1 }}</td>
            <td>{{ s.title }}</td>
            <td v-if="!compact">{{ s.section_type }}</td>
            <td>{{ s.content_char_count.toLocaleString() }}</td>
            <td :data-summary-kind="summaryStatus(s).kind">{{ summaryStatus(s).label }}</td>
            <td v-if="!compact">{{ compressionLabel(s) }}</td>
          </tr>
        </template>
      </tbody>
    </table>
  </template>

  <style scoped>
  .section-list-table { width: 100%; border-collapse: collapse; }
  .section-list-table th, .section-list-table td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--color-border); }
  .section-list-table tr[role="link"] { cursor: pointer; }
  .section-list-table tr[role="link"]:focus { outline: 2px solid var(--color-accent); outline-offset: -2px; }
  .section-list-table tr[role="link"]:hover { background: var(--color-bg-muted); }
  .section-list-table tr.section-type-separator { height: 1px; }
  .section-list-table tr.section-type-separator td { padding: 0; border-bottom: 1px solid var(--color-border-strong); }
  .section-list-table.compact th, .section-list-table.compact td { padding: 4px 8px; font-size: 0.9em; }
  .section-list-table.compact { max-width: 360px; }
  /* Mobile (OQ2 / E15) */
  @media (max-width: 640px) {
    .section-list-table:not(.compact) th:nth-child(3), /* Type */
    .section-list-table:not(.compact) td:nth-child(3),
    .section-list-table:not(.compact) th:nth-child(6), /* Compression */
    .section-list-table:not(.compact) td:nth-child(6) { display: none; }
  }
  </style>
  ```

- [ ] Step 4: Wire SSE updates from the existing `summarizationJob` store. First inspect the store to confirm exposed reactive state:
  ```bash
  grep -nE "^\s*(const|let|export\s+const)\s+(lastEvent|sectionEvents|isActive|runningJob)" frontend/src/stores/summarizationJob.ts
  ```
  Expected: a reactive `lastEvent` (or equivalent — name confirmed during this step). If it doesn't exist, add a minimal getter exposing the most recent SSE event as `{ event: string, data: {section_id?: number, ...} }`.

  Then add to `SectionListTable.vue` `<script setup>`:
  ```ts
  import { watch } from 'vue'

  // Skip in compact mode (Decision Log P8)
  if (!props.compact) {
    watch(() => jobStore.lastEvent, (ev) => {
      if (!ev || !ev.data?.section_id) return
      const sid = Number(ev.data.section_id)
      // Only update if the section belongs to this table
      if (!props.sections.some(s => s.id === sid)) return
      switch (ev.event) {
        case 'section_started':
          liveStatuses.value[sid] = 'pending'
          break
        case 'section_completed':
          liveStatuses.value[sid] = 'completed'
          break
        case 'section_failed':
          liveStatuses.value[sid] = 'failed'
          break
        case 'section_retry':
          liveStatuses.value[sid] = 'retrying'
          break
        case 'processing_completed':
        case 'processing_failed':
          // Terminal — clear all transient retry indicators; canonical state from props is now authoritative
          liveStatuses.value = {}
          break
      }
    }, { deep: true })
  }
  ```

- [ ] Step 4a: Add a Vitest case to F3 covering the SSE wire-up:
  ```ts
  it('flips Summary cell to ✓ on section_completed event in non-compact mode', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const jobStore = useSummarizationJobStore()
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [pinia, makeRouter()] },
    })
    // Section 3 starts as no-summary (pending); fire SSE
    jobStore.lastEvent = { event: 'section_completed', data: { section_id: 3 } } as any
    await wrapper.vm.$nextTick()
    const row = wrapper.findAll('tbody tr[role="link"]').at(2)!
    expect(row.html()).toContain('✓')
  })

  it('compact mode does NOT subscribe to SSE updates', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const jobStore = useSummarizationJobStore()
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: true },
      global: { plugins: [pinia, makeRouter()] },
    })
    jobStore.lastEvent = { event: 'section_completed', data: { section_id: 3 } } as any
    await wrapper.vm.$nextTick()
    // Section 3 still shows — (no-summary) since compact ignores live events
    const row = wrapper.findAll('tbody tr[role="link"]').at(2)!
    expect(row.text()).toContain('—')
  })
  ```

- [ ] Step 5: Run — confirm GREEN.
  Run: `cd frontend && npm run test:unit -- SectionListTable`
  Expected: 8 passed.

- [ ] Step 6: **Swap TOCDropdown to use SectionListTable.** Modify `frontend/src/components/reader/TOCDropdown.vue:53-83`. Replace the existing `.toc-list` block (and the surrounding `<details>` wrapper if it exists) with:
  ```vue
  <SectionListTable
    :sections="sections"
    :bookId="bookId"
    :currentSectionId="currentSectionId"
    :compact="true"
  />
  ```
  Imports needed at top: `import SectionListTable from '@/components/book/SectionListTable.vue'`.
  Wire props from existing TOCDropdown props: it currently receives `sections: Section[]`; if it doesn't already get `bookId` and `currentSectionId`, add those props (the parent in `BookDetailView.vue` should pass them — read that file to confirm).

  Add a TOCDropdown test or update the existing one:
  ```ts
  // TOCDropdown.spec.ts
  it('uses SectionListTable in compact mode', () => {
    const wrapper = mount(TOCDropdown, { props: { sections, bookId: 1, currentSectionId: 1 } })
    const table = wrapper.findComponent({ name: 'SectionListTable' })
    expect(table.exists()).toBe(true)
    expect(table.props('compact')).toBe(true)
  })
  ```

- [ ] Step 7: Run the new TOCDropdown assertion + the existing reader/integration tests:
  Run: `cd frontend && npm run test:unit -- SectionListTable TOCDropdown`
  Expected: green.

- [ ] Step 8: Commit.
  ```bash
  git add frontend/src/components/book/SectionListTable.vue frontend/src/components/book/__tests__/SectionListTable.spec.ts frontend/src/components/reader/TOCDropdown.vue frontend/src/components/reader/__tests__/TOCDropdown.spec.ts
  git commit -m "feat(book): SectionListTable shared component for book-detail + reader TOC"
  ```

**Inline verification:**
- `npm run test:unit -- SectionListTable TOCDropdown` — green.
- `npm run type-check` — clean.

---

### F4: FontListbox component + CustomEditor wiring

**Goal:** Replace the native `<select>` with an ARIA-compliant Listbox that previews each font in its own face.
**Spec refs:** FR-37, FR-38, NFR-01.

**Files:**
- Create: `frontend/src/components/settings/FontListbox.vue`
- Create: `frontend/src/components/settings/__tests__/FontListbox.spec.ts`
- Modify: `frontend/src/components/settings/CustomEditor.vue:84-90`

**Steps:**

- [ ] Step 1: Write failing tests:
  ```ts
  // frontend/src/components/settings/__tests__/FontListbox.spec.ts
  import { describe, it, expect } from 'vitest'
  import { mount } from '@vue/test-utils'
  import FontListbox from '../FontListbox.vue'

  const FONTS = ['Georgia', 'Inter', 'Merriweather', 'Fira Code', 'Lora', 'Source Serif Pro']

  describe('FontListbox', () => {
    it('each option has font-family style applied to its label', async () => {
      const wrapper = mount(FontListbox, {
        props: { modelValue: 'Georgia', options: FONTS },
        attachTo: document.body,
      })
      await wrapper.find('button[aria-haspopup="listbox"]').trigger('click')
      const opts = wrapper.findAll('[role="option"]')
      expect(opts).toHaveLength(FONTS.length)
      FONTS.forEach((f, i) => {
        const style = (opts[i].element as HTMLElement).style.fontFamily
        expect(style).toContain(f)
      })
    })

    it('arrow keys move active descendant', async () => {
      const wrapper = mount(FontListbox, {
        props: { modelValue: 'Georgia', options: FONTS },
        attachTo: document.body,
      })
      const trigger = wrapper.find('button[aria-haspopup="listbox"]')
      await trigger.trigger('click')
      const listbox = wrapper.find('[role="listbox"]')
      await listbox.trigger('keydown', { key: 'ArrowDown' })
      expect(listbox.attributes('aria-activedescendant')).toMatch(/inter/i)
    })

    it('Enter selects + emits update:modelValue', async () => {
      const wrapper = mount(FontListbox, {
        props: { modelValue: 'Georgia', options: FONTS },
        attachTo: document.body,
      })
      await wrapper.find('button[aria-haspopup="listbox"]').trigger('click')
      const listbox = wrapper.find('[role="listbox"]')
      await listbox.trigger('keydown', { key: 'ArrowDown' })
      await listbox.trigger('keydown', { key: 'Enter' })
      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['Inter'])
    })

    it('Esc closes and returns focus to trigger', async () => {
      const wrapper = mount(FontListbox, {
        props: { modelValue: 'Georgia', options: FONTS },
        attachTo: document.body,
      })
      const trigger = wrapper.find('button[aria-haspopup="listbox"]')
      await trigger.trigger('click')
      const listbox = wrapper.find('[role="listbox"]')
      await listbox.trigger('keydown', { key: 'Escape' })
      expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
      expect(document.activeElement).toBe(trigger.element)
    })

    it('click outside closes', async () => {
      const wrapper = mount(FontListbox, {
        props: { modelValue: 'Georgia', options: FONTS },
        attachTo: document.body,
      })
      await wrapper.find('button[aria-haspopup="listbox"]').trigger('click')
      // Simulate document click
      document.body.click()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    })
  })
  ```

- [ ] Step 2: Run — confirm RED.

- [ ] Step 3: Implement `frontend/src/components/settings/FontListbox.vue`. ARIA Listbox pattern (W3C WAI APG):
  - Trigger button: `aria-haspopup="listbox"`, `aria-expanded`.
  - On open: focus moves into the listbox, listbox has `role="listbox"`, `aria-activedescendant` references option id.
  - Each option: `role="option"`, `aria-selected`, unique `id`.
  - Each option label gets `style="font-family: '<name>', <fallback>"`.
  - Keyboard: ArrowUp/Down move `aria-activedescendant`; Enter selects + closes; Esc closes + restores focus to trigger; Tab moves out per spec.
  - Click-outside via `document.addEventListener('click', ..., { capture: true })` registered on open, removed on close.
  - Emit `update:modelValue`.

- [ ] Step 4: Run — confirm GREEN. `npm run test:unit -- FontListbox`. Expected: 5 passed.

- [ ] Step 5: Wire into `CustomEditor.vue:84-90`. Replace native select with:
  ```vue
  <FontListbox
    :modelValue="store.currentSettings.font_family"
    :options="FONTS"
    @update:modelValue="(v) => store.updateSetting('font_family', v)"
  />
  ```
  Import: `import FontListbox from './FontListbox.vue'`.

- [ ] Step 6: Run existing CustomEditor test to confirm wiring.
  Run: `cd frontend && npm run test:unit -- CustomEditor`
  Expected: existing assertions still pass; if any depended on the native `<select>`, update to interact via the FontListbox button.

- [ ] Step 7: Commit.
  ```bash
  git add frontend/src/components/settings/FontListbox.vue frontend/src/components/settings/__tests__/FontListbox.spec.ts frontend/src/components/settings/CustomEditor.vue frontend/src/components/settings/__tests__/CustomEditor.spec.ts
  git commit -m "feat(settings): FontListbox replaces native font select with ARIA listbox"
  ```

**Inline verification:**
- `npm run test:unit -- FontListbox CustomEditor` — green.
- Manual mount in dev build: each option label visibly rendered in its own font.

---

### F5: ExportSplitButton + OverflowMenu

**Goal:** Action-row split-button (Download default + Copy menu item) and ⋯ overflow menu, both ARIA Menu Button compliant.
**Spec refs:** FR-22, FR-22a, FR-21, NFR-02.

**Files:**
- Create: `frontend/src/components/book/ExportSplitButton.vue`
- Create: `frontend/src/components/book/OverflowMenu.vue`
- Create: `frontend/src/components/book/__tests__/ExportSplitButton.spec.ts`
- Create: `frontend/src/components/book/__tests__/OverflowMenu.spec.ts`

**Steps:**

- [ ] Step 1: Write failing tests covering the behavioral surface:
  ```ts
  // frontend/src/components/book/__tests__/ExportSplitButton.spec.ts
  import { describe, it, expect } from 'vitest'
  import { mount } from '@vue/test-utils'
  import ExportSplitButton from '../ExportSplitButton.vue'

  describe('ExportSplitButton', () => {
    it('default body click emits download', async () => {
      const w = mount(ExportSplitButton, { attachTo: document.body })
      await w.find('[data-role="body"]').trigger('click')
      expect(w.emitted('download')).toHaveLength(1)
      expect(w.emitted('copy')).toBeFalsy()
    })

    it('chevron opens menu and toggles aria-expanded', async () => {
      const w = mount(ExportSplitButton, { attachTo: document.body })
      const chev = w.find('[data-role="chevron"]')
      expect(chev.attributes('aria-expanded')).toBe('false')
      await chev.trigger('click')
      expect(chev.attributes('aria-expanded')).toBe('true')
      expect(w.find('[role="menu"]').exists()).toBe(true)
      const items = w.findAll('[role="menuitem"]')
      expect(items.map(i => i.text())).toEqual(expect.arrayContaining(['Download Markdown', 'Copy to Clipboard']))
    })

    it('Copy menu item emits copy and closes menu', async () => {
      const w = mount(ExportSplitButton, { attachTo: document.body })
      await w.find('[data-role="chevron"]').trigger('click')
      const copyItem = w.findAll('[role="menuitem"]').find(i => i.text() === 'Copy to Clipboard')!
      await copyItem.trigger('click')
      expect(w.emitted('copy')).toHaveLength(1)
      expect(w.find('[role="menu"]').exists()).toBe(false)
    })

    it('disabled state suppresses clicks and shows tooltip', async () => {
      const w = mount(ExportSplitButton, {
        props: { disabled: true, disabledReason: 'No summaries to export yet — summarize sections first.' },
        attachTo: document.body,
      })
      await w.find('[data-role="body"]').trigger('click')
      expect(w.emitted('download')).toBeFalsy()
      expect(w.find('[data-role="body"]').attributes('aria-disabled')).toBe('true')
      expect(w.find('[data-role="body"]').attributes('title')).toContain('No summaries to export yet')
    })

    it('Esc closes menu and refocuses chevron', async () => {
      const w = mount(ExportSplitButton, { attachTo: document.body })
      const chev = w.find('[data-role="chevron"]')
      await chev.trigger('click')
      await w.find('[role="menu"]').trigger('keydown', { key: 'Escape' })
      expect(w.find('[role="menu"]').exists()).toBe(false)
      expect(document.activeElement).toBe(chev.element)
    })

    it('ArrowDown moves focus to next menu item', async () => {
      const w = mount(ExportSplitButton, { attachTo: document.body })
      await w.find('[data-role="chevron"]').trigger('click')
      const menu = w.find('[role="menu"]')
      const items = w.findAll('[role="menuitem"]')
      ;(items[0].element as HTMLElement).focus()
      await menu.trigger('keydown', { key: 'ArrowDown' })
      expect(document.activeElement).toBe(items[1].element)
    })
  })
  ```
  ```ts
  // frontend/src/components/book/__tests__/OverflowMenu.spec.ts
  import { describe, it, expect } from 'vitest'
  import { mount } from '@vue/test-utils'
  import { createRouter, createMemoryHistory } from 'vue-router'
  import OverflowMenu from '../OverflowMenu.vue'

  function makeRouter() {
    return createRouter({ history: createMemoryHistory(), routes: [
      { path: '/books/:id/edit-structure', name: 'book-edit-structure', component: { template: '<div/>' } },
    ]})
  }

  describe('OverflowMenu', () => {
    it('trigger has aria-haspopup="menu"', () => {
      const w = mount(OverflowMenu, {
        props: { editRoute: { name: 'book-edit-structure', params: { id: '1' } } },
        global: { plugins: [makeRouter()] },
        attachTo: document.body,
      })
      expect(w.find('button').attributes('aria-haspopup')).toBe('menu')
    })

    it('click opens menu with both items', async () => {
      const w = mount(OverflowMenu, {
        props: { editRoute: { name: 'book-edit-structure', params: { id: '1' } } },
        global: { plugins: [makeRouter()] },
        attachTo: document.body,
      })
      await w.find('button').trigger('click')
      const items = w.findAll('[role="menuitem"]')
      expect(items.map(i => i.text())).toEqual(['Edit Structure', 'Customize Reader'])
    })

    it('Edit Structure is a router-link to editRoute', async () => {
      const w = mount(OverflowMenu, {
        props: { editRoute: { name: 'book-edit-structure', params: { id: '1' } } },
        global: { plugins: [makeRouter()] },
        attachTo: document.body,
      })
      await w.find('button').trigger('click')
      const editItem = w.findAll('[role="menuitem"]')[0]
      expect(editItem.attributes('href')).toContain('/books/1/edit-structure')
    })

    it('Customize Reader emits open-reader-settings and closes menu', async () => {
      const w = mount(OverflowMenu, {
        props: { editRoute: { name: 'book-edit-structure', params: { id: '1' } } },
        global: { plugins: [makeRouter()] },
        attachTo: document.body,
      })
      await w.find('button').trigger('click')
      const customizeItem = w.findAll('[role="menuitem"]')[1]
      await customizeItem.trigger('click')
      expect(w.emitted('open-reader-settings')).toHaveLength(1)
      expect(w.find('[role="menu"]').exists()).toBe(false)
    })

    it('Esc closes', async () => {
      const w = mount(OverflowMenu, {
        props: { editRoute: { name: 'book-edit-structure', params: { id: '1' } } },
        global: { plugins: [makeRouter()] },
        attachTo: document.body,
      })
      await w.find('button').trigger('click')
      await w.find('[role="menu"]').trigger('keydown', { key: 'Escape' })
      expect(w.find('[role="menu"]').exists()).toBe(false)
    })
  })
  ```

- [ ] Step 2: Run — confirm RED.

- [ ] Step 3: Implement both components per ARIA Menu Button (W3C WAI APG): `aria-haspopup="menu"` on trigger, `role="menu"` on popover, `role="menuitem"` on items, ↑/↓ navigate, Enter activates, Esc closes + restores focus.

  ExportSplitButton structure:
  - Two adjacent buttons inside a `<div role="group">`: the body button (default Download) and the chevron button (`aria-haspopup="menu"`, `aria-expanded`).
  - When chevron clicked, the `<ul role="menu">` becomes visible.
  - Disabled prop disables both buttons; tooltip via `title` attribute and a visible `[data-tooltip]` overlay (or the existing tooltip pattern in the codebase — read `BookOverviewView.vue:195-198` for the existing `exportDisabled` shape).

  OverflowMenu structure: single `<button aria-haspopup="menu">⋯</button>` + popover with two items.

- [ ] Step 4: Run — confirm GREEN.
  Run: `npm run test:unit -- ExportSplitButton OverflowMenu`
  Expected: all green.

- [ ] Step 5: Commit.
  ```bash
  git add frontend/src/components/book/ExportSplitButton.vue frontend/src/components/book/OverflowMenu.vue frontend/src/components/book/__tests__/ExportSplitButton.spec.ts frontend/src/components/book/__tests__/OverflowMenu.spec.ts
  git commit -m "feat(book): ExportSplitButton + OverflowMenu with ARIA menu pattern"
  ```

**Inline verification:**
- `npm run test:unit -- ExportSplitButton OverflowMenu` — all green.
- `npm run type-check` — clean.

---

### F6: ThemeGrid typography preview

**Goal:** Each preset tile shows its own font sample.
**Spec refs:** FR-36.

**Files:**
- Modify: `frontend/src/components/settings/ThemeGrid.vue:128-140`
- Modify: `frontend/src/components/settings/ThemeCard.vue` (add `previewFont` prop + `Aa` rendering)
- Modify: `frontend/src/components/settings/__tests__/ThemeGrid.spec.ts` (add typography assertion)

**Steps:**

- [ ] Step 1: Write a failing test that asserts a tile renders an "Aa" sample with its own `font-family` style.
  ```ts
  it('renders typography preview Aa in preset font', () => {
    const wrapper = mount(ThemeGrid, { /* existing setup */ })
    const lightTile = wrapper.find('[data-preset-name="Light"]')
    const sample = lightTile.find('.preview-sample')
    expect(sample.text()).toBe('Aa')
    expect((sample.element as HTMLElement).style.fontFamily).toContain('Georgia')
    expect((sample.element as HTMLElement).style.fontSize).toBe('16px')
  })
  ```
  Run: confirm RED.

- [ ] Step 2: Update `<ThemeCard>` to accept `previewFont: string`, `previewSize: number`. Render `<span class="preview-sample" :style="{ fontFamily: previewFont, fontSize: previewSize + 'px' }">Aa</span>` next to the existing color swatches.

- [ ] Step 3: In `ThemeGrid.vue`, fetch preset typography directly via the presets API on setup (per Decision Log: simpler than threading through a store, and the data is needed only in this surface):
  ```ts
  // ThemeGrid.vue <script setup>
  import { ref, onMounted, computed } from 'vue'

  const presets = ref<Array<{ name: string, font_family: string, font_size_px: number, theme: string }>>([])
  onMounted(async () => {
    const r = await fetch('/api/v1/presets')
    if (r.ok) presets.value = await r.json()
  })

  const cards = computed(() => {
    // existing color-only cards array, augmented with typography lookup
    return SYSTEM_THEMES.map(theme => {
      const preset = presets.value.find(p => p.theme === theme.name)
      return {
        ...theme,
        font_family: preset?.font_family ?? 'Georgia',
        font_size_px: preset?.font_size_px ?? 16,
      }
    })
  })
  ```
  Verify the `/api/v1/presets` endpoint exists and returns `name, font_family, font_size_px, theme` — read `backend/app/api/routes/presets.py` (or wherever) to confirm shape. If it returns only `name`, extend the route response model to include the typography fields.

  Then update the template:
  ```vue
  <ThemeCard
    v-for="card in cards"
    :key="card.label"
    :data-preset-name="card.label"
    :previewFont="card.font_family"
    :previewSize="card.font_size_px"
    ...
  />
  ```

- [ ] Step 4: Run — confirm GREEN.
- [ ] Step 5: Commit.

**Inline verification:**
- `npm run test:unit -- ThemeGrid` — green.

---

### F7: ContentToggle styling

**Goal:** Inactive tab reads as available, not disabled.
**Spec refs:** FR-18, FR-19.

**Files:**
- Modify: `frontend/src/components/reader/ContentToggle.vue:51-54`
- Modify: `frontend/src/components/__tests__/ContentToggle.spec.ts`

**Steps:**

- [ ] Step 1: Add failing test:
  ```ts
  it('inactive tab is fully clickable, not visually disabled', async () => {
    const wrapper = mount(ContentToggle, { props: { mode: 'summary', hasSummary: true } })
    const inactive = wrapper.findAll('.toggle-btn').find(b => !b.classes().includes('active'))!
    expect(inactive.attributes('disabled')).toBeUndefined()
    expect(getComputedStyle(inactive.element).opacity).toBe('1')
    await inactive.trigger('click')
    expect(wrapper.emitted('update:mode')).toBeDefined()
  })
  ```

- [ ] Step 2: Run — confirm RED (current `:disabled="mode === 'original'"` makes it disabled).

- [ ] Step 3: Modify `ContentToggle.vue`:
  - Remove `:disabled="mode === 'original'"` and `:disabled="mode === 'summary'"` from the buttons.
  - Remove the `.toggle-btn:disabled` rule (lines 51-54).
  - Add inactive style:
    ```css
    .toggle-btn:not(.active) {
      color: var(--color-text-secondary);
      cursor: pointer;
    }
    .toggle-btn:not(.active):hover {
      background: var(--color-bg-muted);
    }
    ```

- [ ] Step 4: Run — GREEN.
- [ ] Step 5: Commit.

**Inline verification:**
- `npm run test:unit -- ContentToggle` — green.

---

### F8: Reader store URL `?tab` sync

**Goal:** Tab state survives reload, prev/next, and URL share.
**Spec refs:** FR-14, FR-15, FR-16, FR-17, E6, E7.

**Files:**
- Modify: `frontend/src/stores/reader.ts:85-97, 99-119, 121-123`
- Create: `frontend/src/stores/__tests__/reader.tab.spec.ts`

**Steps:**

- [ ] Step 1: Write failing tests:
  ```ts
  // frontend/src/stores/__tests__/reader.tab.spec.ts
  import { describe, it, expect, beforeEach, vi } from 'vitest'
  import { setActivePinia, createPinia } from 'pinia'
  import { createRouter, createMemoryHistory } from 'vue-router'
  import { useReaderStore } from '@/stores/reader'

  function makeRouter() {
    const r = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/books/:id/sections/:sectionId', name: 'section-detail', component: { template: '<div/>' } },
      ],
    })
    return r
  }

  function mockFetch(book: any, sections: Record<number, any>) {
    global.fetch = vi.fn(async (url: string) => {
      if (url.match(/\/books\/\d+$/)) return new Response(JSON.stringify(book))
      const m = url.match(/\/sections\/(\d+)$/)
      if (m) return new Response(JSON.stringify(sections[Number(m[1])]))
      return new Response('{}', { status: 404 })
    }) as any
  }

  const BOOK = { id: 1, title: 'B', sections: [
    { id: 10, title: 'A', has_summary: true,  order_index: 0 },
    { id: 11, title: 'B', has_summary: false, order_index: 1 },
  ]}
  const SECTIONS = {
    10: { id: 10, title: 'A', has_summary: true,  content_md: 'orig', default_summary: { summary_md: 'sum' } },
    11: { id: 11, title: 'B', has_summary: false, content_md: 'orig', default_summary: null },
  }

  describe('reader store tab URL sync', () => {
    let router: ReturnType<typeof makeRouter>
    beforeEach(() => {
      setActivePinia(createPinia())
      mockFetch(BOOK, SECTIONS)
      router = makeRouter()
    })

    it('loadSection reads ?tab=summary from route.query', async () => {
      await router.push({ name: 'section-detail', params: { id: '1', sectionId: '10' }, query: { tab: 'summary' } })
      const store = useReaderStore()
      await store.loadSection(1, 10)
      expect(store.contentMode).toBe('summary')
    })

    it('loadSection falls back to original when has_summary is false', async () => {
      await router.push({ name: 'section-detail', params: { id: '1', sectionId: '11' } })
      const store = useReaderStore()
      await store.loadSection(1, 11)
      expect(store.contentMode).toBe('original')
    })

    it('loadSection rewrites URL to ?tab=original when ?tab=summary on no-summary section', async () => {
      await router.push({ name: 'section-detail', params: { id: '1', sectionId: '11' }, query: { tab: 'summary' } })
      const store = useReaderStore()
      await store.loadSection(1, 11)
      expect(store.contentMode).toBe('original')
      expect(router.currentRoute.value.query.tab).toBe('original')
    })

    it('toggleContent calls router.replace with new tab param', async () => {
      await router.push({ name: 'section-detail', params: { id: '1', sectionId: '10' }, query: { tab: 'original' } })
      const store = useReaderStore()
      await store.loadSection(1, 10)
      const replaceSpy = vi.spyOn(router, 'replace')
      store.toggleContent()
      expect(store.contentMode).toBe('summary')
      expect(replaceSpy).toHaveBeenCalled()
      const lastCall = replaceSpy.mock.calls.at(-1)![0] as any
      expect(lastCall.query.tab).toBe('summary')
    })

    it('navigateSection preserves tab in destination URL', async () => {
      await router.push({ name: 'section-detail', params: { id: '1', sectionId: '10' }, query: { tab: 'summary' } })
      const store = useReaderStore()
      await store.loadSection(1, 10)
      await store.navigateSection('next')
      expect(router.currentRoute.value.params.sectionId).toBe('11')
      // Section 11 has no summary; URL should rewrite to original (FR-17 inside loadSection)
      expect(router.currentRoute.value.query.tab).toBe('original')
    })

    it('navigateSection back to a section with summary keeps tab=summary when contentMode is summary', async () => {
      await router.push({ name: 'section-detail', params: { id: '1', sectionId: '11' }, query: { tab: 'original' } })
      const store = useReaderStore()
      await store.loadSection(1, 11)
      store.contentMode = 'summary'  // simulate user toggle even with no summary (won't render but state is set)
      // Actually: section 11 has no summary, so toggleContent on it should be a no-op or rewrite — the test below covers it
      await store.navigateSection('prev')
      expect(router.currentRoute.value.params.sectionId).toBe('10')
    })
  })
  ```

- [ ] Step 2: Run — confirm RED.

- [ ] Step 3: Modify `reader.ts`:
  - Inject `useRouter` and `useRoute` at the top of the store (Pinia setup-style stores allow this).
  - In `loadSection(bookId, sectionId)`:
    ```ts
    const route = useRoute()
    const router = useRouter()
    // ... after section loaded ...
    const requestedTab = route.query.tab
    if (requestedTab === 'summary' && section.has_summary) {
      contentMode.value = 'summary'
    } else if (requestedTab === 'original') {
      contentMode.value = 'original'
    } else if (section.has_summary) {
      contentMode.value = 'summary'
      // optional: write URL to lock it
    } else {
      contentMode.value = 'original'
    }
    // FR-17: if URL says summary but section has none, rewrite
    if (requestedTab === 'summary' && !section.has_summary) {
      router.replace({ query: { ...route.query, tab: 'original' } })
    }
    ```
  - In `toggleContent()`:
    ```ts
    contentMode.value = contentMode.value === 'original' ? 'summary' : 'original'
    router.replace({ query: { ...route.query, tab: contentMode.value } })
    ```
  - In `navigateSection(direction)`:
    ```ts
    router.push({
      name: 'section-detail',
      params: { id: String(book.value.id), sectionId: String(newSection.id) },
      query: { tab: contentMode.value },
    })
    // After loadSection runs on the new route, FR-17 logic handles the no-summary case.
    ```

- [ ] Step 4: Run — confirm GREEN.

- [ ] Step 5: Commit.
  ```bash
  git add frontend/src/stores/reader.ts frontend/src/stores/__tests__/reader.tab.spec.ts
  git commit -m "feat(reader): sync content tab to ?tab= URL query"
  ```

**Inline verification:**
- `npm run test:unit -- reader.tab` — all 6 green.

---

### F9a: BookOverviewView action row + section list + reader-settings popover mount

**Goal:** Action row reads as one designed group; static counter gone; section list uses the shared component; new ReaderSettingsPopover surface mounted in BookOverviewView (currently only in BookDetailView).
**Spec refs:** FR-20, FR-21, FR-22 (structure), FR-22a, FR-23, FR-24, FR-33 (book-detail half).

**Files:**
- Modify: `frontend/src/views/BookOverviewView.vue:44-49, 51-104, 120-136`
- Modify: `frontend/src/views/__tests__/BookOverviewView.spec.ts`

**Steps:**

- [ ] Step 1: **FR-24 grep inventory** before deletion:
  ```bash
  cd frontend && grep -rn "Summaries: " src/ tests/ playwright/ 2>/dev/null
  cd frontend && grep -rn "summary_progress.summarized" src/ tests/ 2>/dev/null
  cd backend && grep -rn "Summaries:" tests/ 2>/dev/null
  ```
  Update each callsite to either remove the assertion or assert the dynamic `<SummarizationProgress>` text instead.

- [ ] Step 2: Read the existing `ReaderSettingsPopover` usage at `BookDetailView.vue:9, 221` to confirm its trigger pattern (whether it's controlled by a prop, a default-open state, or a button slot).

- [ ] Step 3: Write failing tests:
  ```ts
  // BookOverviewView.spec.ts additions
  it('action row renders [Read][Read Summary][Export ▾][⋯] in order', () => {
    const wrapper = mount(BookOverviewView, { /* book with default_summary, summarized > 0 */ })
    const actions = wrapper.findAll('.action-row > *')
    expect(actions[0].attributes('data-action')).toBe('read')
    expect(actions[1].attributes('data-action')).toBe('read-summary')
    expect(actions[2].attributes('data-action')).toBe('export')
    expect(actions[3].attributes('data-action')).toBe('overflow')
  })

  it('static "Summaries: X of Y" text is gone', () => {
    const wrapper = mount(BookOverviewView, { /* ... */ })
    expect(wrapper.text()).not.toMatch(/Summaries:\s*\d+\s+of\s+\d+/)
  })

  it('Read Summary disabled when no default_summary (FR-23)', () => {
    const wrapper = mount(BookOverviewView, { /* book without default_summary */ })
    const btn = wrapper.find('[data-action="read-summary"]')
    expect(btn.attributes('aria-disabled')).toBe('true')
    expect(btn.attributes('title')).toMatch(/no book summary yet/i)
  })

  it('Export ▾ disabled when no sections summarized (FR-22a)', () => {
    const wrapper = mount(BookOverviewView, { /* summary_progress.summarized: 0 */ })
    const btn = wrapper.find('[data-action="export"] [data-role="body"]')
    expect(btn.attributes('aria-disabled')).toBe('true')
  })

  it('uses SectionListTable instead of inline ol', () => {
    const wrapper = mount(BookOverviewView, { /* ... */ })
    expect(wrapper.findComponent({ name: 'SectionListTable' }).exists()).toBe(true)
    expect(wrapper.find('ol.sections-toc').exists()).toBe(false)
  })

  it('OverflowMenu open-reader-settings event opens the popover', async () => {
    const wrapper = mount(BookOverviewView, { /* ... */ })
    const overflow = wrapper.findComponent({ name: 'OverflowMenu' })
    await overflow.vm.$emit('open-reader-settings')
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent({ name: 'ReaderSettingsPopover' }).exists()).toBe(true)
  })
  ```

- [ ] Step 4: Run — confirm RED.

- [ ] Step 5: Implement the new action row in `BookOverviewView.vue`. Replace the lines 51-104 block with:
  ```vue
  <div class="action-row">
    <router-link
      :to="{ name: 'section-detail', params: { id: String(book.id), sectionId: String(book.sections[0]?.id ?? 0) } }"
      class="btn-primary" data-action="read"
    >Read</router-link>

    <router-link
      :to="{ name: 'book-summary', params: { id: String(book.id) } }"
      class="btn-primary"
      :aria-disabled="!book.default_summary || undefined"
      :title="book.default_summary ? '' : 'No book summary yet — summarize sections first.'"
      data-action="read-summary"
    >Read Summary</router-link>

    <ExportSplitButton
      :disabled="!hasAnySummary"
      :disabled-reason="hasAnySummary ? '' : 'No summaries to export yet — summarize sections first.'"
      data-action="export"
      @download="onExportClick"
      @copy="onCopyClick"
    />

    <OverflowMenu
      data-action="overflow"
      :edit-route="{ name: 'book-edit-structure', params: { id: String(book.id) } }"
      @open-reader-settings="readerSettingsOpen = true"
    />
  </div>

  <ReaderSettingsPopover v-if="readerSettingsOpen" @close="readerSettingsOpen = false" />
  ```
  Imports + state:
  ```ts
  import { ref, computed } from 'vue'
  import SectionListTable from '@/components/book/SectionListTable.vue'
  import ExportSplitButton from '@/components/book/ExportSplitButton.vue'
  import OverflowMenu from '@/components/book/OverflowMenu.vue'
  import ReaderSettingsPopover from '@/components/settings/ReaderSettingsPopover.vue'

  const readerSettingsOpen = ref(false)
  const hasAnySummary = computed(() => (book.value?.summary_progress?.summarized ?? 0) > 0)
  ```
  If `ReaderSettingsPopover` doesn't accept a `@close` event today (verified during Step 2), wrap it in a `<dialog>` or simple click-outside handler — match the pattern used in BookDetailView. Document any deviation in the commit body.

- [ ] Step 6: Delete the static counter at lines 44-49.

- [ ] Step 7: Replace the inline section list at lines 120-136 with:
  ```vue
  <SectionListTable :sections="book.sections" :bookId="book.id" :compact="false" />
  ```
  PRESERVE the inline book-summary block at lines 115-118 (spec Non-Goal).

- [ ] Step 8: Run — confirm GREEN.

- [ ] Step 9: Commit.
  ```bash
  git add frontend/src/views/BookOverviewView.vue frontend/src/views/__tests__/BookOverviewView.spec.ts
  git commit -m "feat(book): redesign action row + shared SectionListTable + reader-settings popover surface"
  ```

**Inline verification:**
- `npm run test:unit -- BookOverviewView` — all new assertions pass; pre-existing pass count preserved (or updated per Step 1 grep).
- `npm run type-check` — clean.

---

### F9b: Export 250ms loader + clipboard text-only fallback

**Goal:** Export button gives honest feedback during real latency; copy survives clipboard.write failure via text-only fallback.
**Spec refs:** FR-25, FR-26, E13, E11, §11.2a regex.

**Files:**
- Modify: `frontend/src/views/BookOverviewView.vue:206-281`
- Modify: `frontend/src/views/__tests__/BookOverviewView.export.spec.ts`

**Steps:**

- [ ] Step 1: Write failing tests:
  ```ts
  // BookOverviewView.export.spec.ts additions
  import { describe, it, expect, vi, beforeEach } from 'vitest'
  import { flushPromises, mount } from '@vue/test-utils'

  describe('BookOverviewView export feedback', () => {
    beforeEach(() => { vi.useFakeTimers() })

    it('export click keeps spinner for >= 250ms even when fetch resolves in 50ms', async () => {
      const fetchSpy = vi.fn(async () => {
        await new Promise(r => setTimeout(r, 50))
        return new Response(new Blob(['md']), { status: 200 })
      })
      global.fetch = fetchSpy as any

      const wrapper = mount(BookOverviewView, { /* book with summaries */ })
      const exportBody = wrapper.find('[data-action="export"] [data-role="body"]')
      const click = exportBody.trigger('click')

      await vi.advanceTimersByTimeAsync(50)   // fetch resolves
      expect(wrapper.find('[data-action="export"] .spinner').exists()).toBe(true)

      await vi.advanceTimersByTimeAsync(200)  // total 250ms
      await flushPromises()
      expect(wrapper.find('[data-action="export"] .spinner').exists()).toBe(false)
      await click
    })

    it('clipboard fallback strips images when primary write fails', async () => {
      const writeSpy = vi.fn().mockRejectedValue(new Error('NotAllowed'))
      const writeTextSpy = vi.fn().mockResolvedValue(undefined)
      Object.defineProperty(navigator, 'clipboard', {
        value: { write: writeSpy, writeText: writeTextSpy }, configurable: true,
      })
      global.fetch = vi.fn(async () => new Response('Hello ![img](http://x/y.png) world')) as any

      const wrapper = mount(BookOverviewView, { /* ... */ })
      // Open Export menu and click Copy
      await wrapper.find('[data-action="export"] [data-role="chevron"]').trigger('click')
      const copy = wrapper.findAll('[role="menuitem"]').find(i => i.text() === 'Copy to Clipboard')!
      await copy.trigger('click')
      await flushPromises()

      expect(writeTextSpy).toHaveBeenCalledWith('Hello img world')
    })

    it('both clipboard paths failing surfaces toast', async () => {
      const writeSpy = vi.fn().mockRejectedValue(new Error('NotAllowed'))
      const writeTextSpy = vi.fn().mockRejectedValue(new Error('NotAllowed'))
      Object.defineProperty(navigator, 'clipboard', {
        value: { write: writeSpy, writeText: writeTextSpy }, configurable: true,
      })
      global.fetch = vi.fn(async () => new Response('any md')) as any

      const wrapper = mount(BookOverviewView, { /* ... */ })
      await wrapper.find('[data-action="export"] [data-role="chevron"]').trigger('click')
      await wrapper.findAll('[role="menuitem"]').find(i => i.text() === 'Copy to Clipboard')!.trigger('click')
      await flushPromises()

      // Existing toast component asserted via the wrapper's text or store
      expect(wrapper.text()).toMatch(/HTTPS or clipboard permission/i)
    })
  })
  ```

- [ ] Step 2: Run — confirm RED.

- [ ] Step 3: Implement `onExportClick` 250ms floor (FR-25):
  ```ts
  const exporting = ref(false)
  async function onExportClick() {
    exporting.value = true
    const exportP = exportBookSummary(book.value!.id)  // existing helper
    const minP = new Promise(r => setTimeout(r, 250))
    const [exportResult] = await Promise.allSettled([exportP, minP])
    exporting.value = false
    if (exportResult.status === 'fulfilled') {
      triggerDownload(exportResult.value as Blob, `${book.value!.title}.md`)
    } else {
      toast.error('Export failed')
    }
  }
  ```
  Wire `:loading="exporting"` (or equivalent) into `<ExportSplitButton>` so the spinner shows while `exporting === true`.

- [ ] Step 4: Implement `onCopyClick` text-only fallback (FR-26, §11.2a regex):
  ```ts
  const STRIP_IMG_RE = /!\[([^\]]*)\]\([^)]*\)/g

  async function onCopyClick() {
    try {
      // Existing primary path: clipboard.write with markdown blob
      await primaryClipboardWrite()
      toast.success('Copied to clipboard')
    } catch (err) {
      try {
        const r = await fetch(`/api/v1/export/book/${book.value!.id}?format=markdown`)
        const md = await r.text()
        const stripped = md.replace(STRIP_IMG_RE, '$1')
        await navigator.clipboard.writeText(stripped)
        toast.success('Copied to clipboard (text only)')
      } catch (err2) {
        toast.error('Copy needs HTTPS or clipboard permission. Use Download instead.')
      }
    }
  }
  ```

- [ ] Step 5: Run — confirm GREEN.

- [ ] Step 6: Commit.
  ```bash
  git add frontend/src/views/BookOverviewView.vue frontend/src/views/__tests__/BookOverviewView.export.spec.ts
  git commit -m "feat(book): 250ms export loader floor + clipboard text-only fallback"
  ```

**Inline verification:**
- `npm run test:unit -- BookOverviewView.export` — all green.
- Manual: in dev server, click Export — spinner visible briefly even on instant downloads. Force a clipboard failure via DevTools (override `navigator.clipboard.write`) and click Copy → text-only success toast.

---

### F10: JobProgressView + /jobs/:id route + indicator link

**Goal:** Deep-link view paints active/terminal/404 from cold reload; persistent indicator points users at it.
**Spec refs:** FR-11, FR-11a, FR-11b, FR-12, FR-12a, FR-13, E4, E5, E14.

**Files:**
- Create: `frontend/src/views/JobProgressView.vue`
- Create: `frontend/src/composables/useBufferedJobStream.ts`
- Create: `frontend/src/composables/__tests__/useBufferedJobStream.spec.ts`
- Create: `frontend/src/views/__tests__/JobProgressView.spec.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/job/PersistentProcessingIndicator.vue:54-108`

**Steps:**

- [ ] Step 1: Write failing tests for the composable:
  ```ts
  // frontend/src/composables/__tests__/useBufferedJobStream.spec.ts
  import { describe, it, expect, vi, beforeEach } from 'vitest'
  import { flushPromises } from '@vue/test-utils'
  import { useBufferedJobStream } from '../useBufferedJobStream'

  class MockEventSource {
    public onmessage: ((m: { data: string }) => void) | null = null
    public onerror: (() => void) | null = null
    public closed = false
    close() { this.closed = true }
    emit(payload: any) { this.onmessage?.({ data: JSON.stringify(payload) }) }
    fail() { this.onerror?.() }
  }

  function deferred<T>() {
    let resolve!: (v: T) => void, reject!: (e: any) => void
    const promise = new Promise<T>((r, j) => { resolve = r; reject = j })
    return { promise, resolve, reject }
  }

  const baseSeed = (overrides = {}) => ({
    id: 42, book_id: 1, book_title: 'B', status: 'RUNNING',
    scope: 'all', section_id: null,
    progress: { current: 5, total: 10, current_section_title: 'Five', eta_seconds: 60 },
    started_at: '2026-04-30T10:00:00Z',
    completed_at: null, error_message: null,
    last_event_at: '2026-04-30T10:00:01.500Z',
    ...overrides,
  })

  describe('useBufferedJobStream', () => {
    it('buffered events newer than GET timestamp are applied', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      const { state, isLoading } = useBufferedJobStream(42, {
        eventSourceFactory: () => es as any,
        fetcher: () => d.promise,
      })
      // Events arrive before GET response
      es.emit({ event: 'section_completed', data: { last_event_at: '2026-04-30T10:00:01.000Z', section_id: 6 } })
      es.emit({ event: 'section_completed', data: { last_event_at: '2026-04-30T10:00:02.000Z', section_id: 7 } })
      d.resolve(baseSeed())
      await flushPromises()
      expect(isLoading.value).toBe(false)
      // Only the second buffered event (10:00:02 > 10:00:01.500) is applied
      expect(state.value!.progress.current).toBe(6) // 5 + 1
    })

    it('section_started updates current_section_title', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      const { state } = useBufferedJobStream(42, { eventSourceFactory: () => es as any, fetcher: () => d.promise })
      d.resolve(baseSeed())
      await flushPromises()
      es.emit({ event: 'section_started', data: { last_event_at: '2026-04-30T10:00:03Z', section_title: 'Six' } })
      await flushPromises()
      expect(state.value!.progress.current_section_title).toBe('Six')
    })

    it('section_completed increments progress.current', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      const { state } = useBufferedJobStream(42, { eventSourceFactory: () => es as any, fetcher: () => d.promise })
      d.resolve(baseSeed({ progress: { current: 5, total: 10, current_section_title: '', eta_seconds: 60 } }))
      await flushPromises()
      es.emit({ event: 'section_completed', data: { last_event_at: '2026-04-30T10:00:03Z', section_id: 6 } })
      await flushPromises()
      expect(state.value!.progress.current).toBe(6)
    })

    it('section_failed increments failure counter', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      const { state } = useBufferedJobStream(42, { eventSourceFactory: () => es as any, fetcher: () => d.promise })
      d.resolve(baseSeed())
      await flushPromises()
      es.emit({ event: 'section_failed', data: { last_event_at: '2026-04-30T10:00:03Z', section_id: 6, error: 'boom' } })
      await flushPromises()
      expect(state.value!.failures).toBe(1)
    })

    it('section_retry surfaces retrying indicator', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      const { state } = useBufferedJobStream(42, { eventSourceFactory: () => es as any, fetcher: () => d.promise })
      d.resolve(baseSeed())
      await flushPromises()
      es.emit({ event: 'section_retry', data: { last_event_at: '2026-04-30T10:00:03Z', section_id: 6 } })
      await flushPromises()
      expect(state.value!.retrying_section_id).toBe(6)
    })

    it('processing_completed transitions status to COMPLETED and closes ES', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      const { state } = useBufferedJobStream(42, { eventSourceFactory: () => es as any, fetcher: () => d.promise })
      d.resolve(baseSeed())
      await flushPromises()
      es.emit({ event: 'processing_completed', data: { last_event_at: '2026-04-30T10:00:03Z' } })
      await flushPromises()
      expect(state.value!.status).toBe('COMPLETED')
      expect(es.closed).toBe(true)
    })

    it('processing_failed transitions status to FAILED', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      const { state } = useBufferedJobStream(42, { eventSourceFactory: () => es as any, fetcher: () => d.promise })
      d.resolve(baseSeed())
      await flushPromises()
      es.emit({ event: 'processing_failed', data: { last_event_at: '2026-04-30T10:00:03Z', error_message: 'boom' } })
      await flushPromises()
      expect(state.value!.status).toBe('FAILED')
      expect(state.value!.error_message).toBe('boom')
      expect(es.closed).toBe(true)
    })

    it('job_cancelling shows cancelling state', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      const { state } = useBufferedJobStream(42, { eventSourceFactory: () => es as any, fetcher: () => d.promise })
      d.resolve(baseSeed())
      await flushPromises()
      es.emit({ event: 'job_cancelling', data: { last_event_at: '2026-04-30T10:00:03Z' } })
      await flushPromises()
      expect(state.value!.cancelling).toBe(true)
    })

    it('terminal seed closes ES immediately (no SSE subscription needed)', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      useBufferedJobStream(42, { eventSourceFactory: () => es as any, fetcher: () => d.promise })
      d.resolve(baseSeed({ status: 'COMPLETED', completed_at: '2026-04-30T10:01:00Z' }))
      await flushPromises()
      expect(es.closed).toBe(true)
    })

    it('404 surfaces error.kind = "404"', async () => {
      const es = new MockEventSource()
      const d = deferred<any>()
      const { error, isLoading } = useBufferedJobStream(42, {
        eventSourceFactory: () => es as any,
        fetcher: () => d.promise,
      })
      d.reject({ kind: '404' })
      await flushPromises()
      expect(error.value?.kind).toBe('404')
      expect(isLoading.value).toBe(false)
    })

    it('reconnect re-seeds via fresh GET against latest applied event', async () => {
      const es1 = new MockEventSource()
      const es2 = new MockEventSource()
      let n = 0
      const d1 = deferred<any>()
      const d2 = deferred<any>()
      const { state } = useBufferedJobStream(42, {
        eventSourceFactory: () => (n++ === 0 ? (es1 as any) : (es2 as any)),
        fetcher: () => (n <= 1 ? d1.promise : d2.promise),
      })
      d1.resolve(baseSeed())
      await flushPromises()
      es1.emit({ event: 'section_completed', data: { last_event_at: '2026-04-30T10:00:05Z' } })
      await flushPromises()
      es1.fail()
      d2.resolve(baseSeed({ progress: { current: 7, total: 10, current_section_title: 'Seven', eta_seconds: 30 }, last_event_at: '2026-04-30T10:00:05Z' }))
      await flushPromises()
      expect(state.value!.progress.current).toBe(7)
    })
  })
  ```

- [ ] Step 2: Run — confirm RED.

- [ ] Step 3: Implement composable:
  ```ts
  // useBufferedJobStream.ts
  import { ref, onUnmounted } from 'vue'

  export function useBufferedJobStream(jobId: number, opts: { eventSourceFactory?: () => EventSource, fetcher?: () => Promise<JobState> } = {}) {
    const state = ref<JobState | null>(null)
    const error = ref<Error | null>(null)
    const isLoading = ref(true)
    let buffer: SseEvent[] = []
    let mode: 'buffer' | 'live' = 'buffer'
    let lastAppliedAt: string | null = null
    let es: EventSource | null = null

    function applyEvent(ev: SseEvent) {
      if (!state.value) return
      const s = state.value
      switch (ev.event) {
        case 'section_started':
          s.progress.current_section_title = ev.data.section_title ?? s.progress.current_section_title
          break
        case 'section_completed':
          s.progress.current = (s.progress.current ?? 0) + 1
          break
        case 'section_failed':
          s.failures = (s.failures ?? 0) + 1
          break
        case 'section_retry':
          s.retrying_section_id = ev.data.section_id ?? null
          break
        case 'processing_completed':
          s.status = 'COMPLETED'
          s.completed_at = ev.data.last_event_at
          es?.close()
          break
        case 'processing_failed':
          s.status = 'FAILED'
          s.error_message = ev.data.error_message ?? s.error_message
          s.completed_at = ev.data.last_event_at
          es?.close()
          break
        case 'job_cancelling':
          s.cancelling = true
          break
        case 'close':
          es?.close()
          break
        // 'job_queued' / 'job_promoted' intentionally not consumed (FR-11b)
      }
    }

    function start() {
      const esFactory = opts.eventSourceFactory ?? (() => new EventSource(`/api/v1/processing/${jobId}/stream`))
      es = esFactory()
      es.onmessage = (m) => {
        const ev = JSON.parse(m.data)
        if (mode === 'buffer') buffer.push(ev)
        else if (!lastAppliedAt || ev.data.last_event_at > lastAppliedAt) {
          applyEvent(ev)
          lastAppliedAt = ev.data.last_event_at
        }
      }
      es.onerror = () => { /* reconnect logic; on reconnect, set mode='buffer' and re-fetch */ }

      const fetcher = opts.fetcher ?? (() => fetch(`/api/v1/processing/${jobId}`).then(r => r.status === 404 ? Promise.reject({ kind: '404' }) : r.json()))
      fetcher().then((seed) => {
        state.value = seed
        lastAppliedAt = seed.last_event_at
        // Drain buffer
        for (const ev of buffer) {
          if (!lastAppliedAt || ev.data.last_event_at > lastAppliedAt) {
            applyEvent(ev)
            lastAppliedAt = ev.data.last_event_at
          }
        }
        buffer = []
        mode = 'live'
        isLoading.value = false
        // If terminal, close ES
        if (seed.status === 'COMPLETED' || seed.status === 'FAILED') es?.close()
      }).catch((e) => { error.value = e; isLoading.value = false })
    }

    onUnmounted(() => es?.close())
    start()
    return { state, error, isLoading }
  }
  ```

- [ ] Step 4: Run — composable tests GREEN.

- [ ] Step 5: Implement `JobProgressView.vue`. Cancel button uses the existing endpoint (Decision Log P1):
  ```ts
  async function onCancel() {
    if (!state.value) return
    state.value.cancelling = true
    await fetch(`/api/v1/processing/${state.value.id}/cancel`, { method: 'POST' })
    // The 'job_cancelling' SSE event will arrive via the composable; UI flips to "cancelling…" via state.cancelling
  }
  ```
  - Props: `id` (route param).
  - Setup: `const { state, error, isLoading } = useBufferedJobStream(Number(id))`.
  - Three render branches per FR-12 + FR-12a skeleton:
    - `isLoading.value === true` → skeleton (book-title placeholder, indeterminate animated bar)
    - `error.value?.kind === '404'` → "Job not found" + [Back to Library]
    - `state.value.status` in (PENDING, RUNNING) → progress bar + current section + ETA + [Open Book] router-link to `/books/{book_id}` + [Cancel] (POST `/api/v1/processing/{job_id}/cancel`)
    - `state.value.status` in (COMPLETED, FAILED) → completion card with `book_title`, `total_sections_summarized`, `total_failures`, `elapsed_time`, `error_message` (if FAILED), [Open Book] CTA.
  - Cancel transitions view to "cancelling…" state by calling the cancel endpoint then watching for `job_cancelling` SSE event.

- [ ] Step 6: Add route in `frontend/src/router/index.ts`:
  ```ts
  { path: '/jobs/:id', name: 'job-detail',
    component: () => import('@/views/JobProgressView.vue'), props: true },
  ```

- [ ] Step 7: Add indicator link in `PersistentProcessingIndicator.vue:68-75`. Next to the existing "Open" button on the running-job row, add:
  ```vue
  <router-link
    :to="{ name: 'job-detail', params: { id: String(queue.runningJob.job_id) } }"
    class="btn-link"
  >View details</router-link>
  ```

- [ ] Step 8: Write a JobProgressView test that mounts the view with a stubbed composable and asserts the four render modes.

- [ ] Step 9: Run all the new tests — GREEN.

- [ ] Step 10: Commit.
  ```bash
  git add frontend/src/views/JobProgressView.vue frontend/src/composables/ frontend/src/router/index.ts frontend/src/components/job/PersistentProcessingIndicator.vue frontend/src/views/__tests__/JobProgressView.spec.ts
  git commit -m "feat(jobs): /jobs/:id deep-link view + buffered SSE seeding"
  ```

**Inline verification:**
- `npm run test:unit -- useBufferedJobStream JobProgressView` — green.
- `npm run type-check` — clean.

---

### TN: Final Verification

**Goal:** Verify the entire implementation works end-to-end against the spec's success metrics.

- [ ] **Lint & format:**
  - `cd backend && uv run ruff check . && uv run ruff format --check .` — exit 0, or only pre-existing baseline failures (compare against `/tmp/lint-baseline.txt` from B1).
  - `cd frontend && npm run lint`

- [ ] **Type check:**
  - `cd frontend && npm run type-check`

- [ ] **Backend unit + integration:**
  ```bash
  cd backend && uv run python -m pytest \
    tests/unit/test_image_url_rewrite_id_scheme.py \
    tests/unit/test_orphan_sweep_predicate.py \
    tests/unit/test_summarizer_image_rewrite.py \
    tests/integration/test_api/test_processing_stale_guard.py \
    tests/integration/test_api/test_processing_get_endpoint.py \
    tests/integration/test_api/test_book_detail_char_count.py \
    tests/integration/test_migration_image_id_rewrite.py \
    tests/integration/test_migration_preset_typography.py \
    -v
  ```
  Expected: all green.

- [ ] **Full backend suite (regression):**
  - `cd backend && uv run python -m pytest -m "not integration_llm"` — same pre-existing pass count + the new ones.

- [ ] **Frontend unit:**
  - `cd frontend && npm run test:unit` — all green.

- [ ] **Database migration sanity (fresh DB):**
  ```bash
  cd backend && rm -f /tmp/spec-test.db && \
    BOOKCOMPANION_DATABASE__URL=sqlite+aiosqlite:////tmp/spec-test.db \
    uv run alembic -c app/migrations/alembic.ini upgrade head
  ```
  Expected: completes without error.

- [ ] **Production DB image-rewrite sanity (DRY):**
  ```bash
  sqlite3 ~/Library/Application\ Support/bookcompanion/library.db \
    "SELECT count(*) FROM summaries WHERE summary_md LIKE '%](image:%';"
  ```
  Expected: 0 (post-migration). If non-zero, the migration didn't run on the live DB — re-run `bookcompanion init`.

- [ ] **Theme CSS coverage:**
  ```bash
  cd frontend && grep -E "^\[data-theme='(light|sepia|dark|night|paper|contrast)'\]" src/assets/theme.css | sort -u | wc -l
  ```
  Expected: `6`.

- [ ] **Webfont bundle size:**
  ```bash
  cd frontend && npm run build
  ls -l dist/assets/*.woff2 2>/dev/null | awk '{s+=$5} END {printf "woff2 total: %.0f KB\n", s/1024}'
  ```
  Expected: ≤ 600KB.

- [ ] **Docker / verification server (CLAUDE.md "Interactive verification"):**
  ```bash
  cd frontend && npm run build && rm -rf ../backend/app/static && cp -R dist ../backend/app/static
  cd backend && uv run bookcompanion serve --port 8765 &
  sleep 3
  curl -sf http://localhost:8765/api/v1/health
  ```
  Expected: server up, /health returns 200.

- [ ] **API smoke tests (curl):**
  - `curl -s http://localhost:8765/api/v1/processing/9999999 -o /dev/null -w '%{http_code}'` → `404`
  - `curl -s http://localhost:8765/api/v1/books/1 | python3 -m json.tool | grep content_char_count` → present on each section
  - `curl -s -X POST http://localhost:8765/api/v1/books/1/summarize -H 'Content-Type: application/json' -d '{"scope":"all"}' -o /dev/null -w '%{http_code}'` → `202` or `409` (depending on state); if 409, body has `active_job` key.

- [ ] **Frontend smoke (Playwright MCP) — covering spec §12.5 sequence:**
  1. `browser_navigate` to `http://localhost:8765/`
  2. Pick a fully-summarized book; navigate to `/books/{id}`. Snapshot: action row has 4 elements (3 buttons + ⋯).
  3. `browser_evaluate(() => document.body.innerText.match(/Summaries:\s*\d+\s+of\s+\d+/))` → null.
  4. Click "Read Summary" → URL becomes `/books/{id}/summary`.
  5. Back. Click "Export ▾" chevron → menu opens; click "Copy to Clipboard"; `browser_evaluate(() => navigator.clipboard.readText())` → contains expected markdown.
  6. Navigate to a section. Click `Original` tab → URL has `?tab=original`. Reload page → tab still `original`. Click `Summary` → URL has `?tab=summary`. Click prev → URL of prev section has `?tab=summary`.
  7. Open a section that has an image-bearing summary. `browser_evaluate(() => Array.from(document.querySelectorAll('img')).filter(img => !img.complete || img.naturalWidth === 0).length)` → `0` (no broken).
  8. Open reader settings. Click each of 6 system presets. After each click, `browser_evaluate(() => getComputedStyle(document.body).backgroundColor)` → varies across the 6 themes; no two adjacent presets produce the same color.
  9. Open custom font dropdown. `browser_evaluate(() => Array.from(document.querySelectorAll('[role="option"]')).map(o => o.style.fontFamily))` → 6 distinct strings.
  10. Visit `/jobs/{any-completed-job-id}` → completion card with "Open Book" link visible.
  11. `browser_console_messages(level: 'error')` → 0 errors during the entire walk.
  12. **Mobile compact-mode (OQ2 / E15):** `browser_resize(375, 812)` → navigate to `/books/{id}` → assert SectionListTable Type and Compression column headers are NOT visible (e.g., `browser_evaluate(() => Array.from(document.querySelectorAll('th')).map(th => getComputedStyle(th).display).filter(d => d === 'none').length)` ≥ 2). Open a section → open TOC dropdown → confirm the table fits within the dropdown width without horizontal scroll.

- [ ] **Manual spot check — bug verifications from spec §12.6:**
  - **#1 retry guard:** stop the running job mid-way (kill the python process), reload UI, click "Retry" on a failed section → succeeds (no 409 surface).
  - **#5 tab styling:** inactive tab is muted but not at 0.5 opacity.
  - **#7 tab persistence:** reload preserves tab; share URL preserves tab.
  - **#8 progress dedup:** no static "Summaries: X of Y" anywhere on book detail.
  - **#9.1 deep link:** running job → click "View details" in indicator → lands on `/jobs/{id}`.
  - **#9.2 read-summary:** disabled-with-tooltip on a book without summary; works on one with summary.
  - **#10 themes:** all 6 presets visibly change background AND typography AND line-height.

- [ ] **Cleanup:**
  - `kill $(lsof -ti:8765)` — stop verification server.
  - `rm /tmp/spec-test.db /tmp/lint-baseline.txt /tmp/test-baseline.txt /tmp/bundle-*.txt`
  - Verify no stray `console.log` / `print(...)` left in the diff: `git diff main -- '***.ts' '***.vue' '***.py' | grep -E '^\+\s*(console\.log|print\()'` → empty.
  - Update `docs/changelog.md` with a user-facing entry (1-2 bullets) summarizing the bundle.

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1    | F8/F5/F10 had placeholder test bodies; F10 `applyEvent` was a stub; F3 SSE wire abstract; F6 preset source unspecified; F9 oversized (4 concerns); F9 `openReaderSettings` handler undefined; B7 `column_property` had no perf-regression check. | F8 tests expanded to 7 concrete cases. F5 ExportSplitButton + OverflowMenu tests fleshed out (6 + 5 cases). F10 `applyEvent` mapping written per FR-11b + 11 unit-test cases added (one per event + 404 + reconnect). F3 SSE wire-up specified with concrete `watch(() => jobStore.lastEvent, ...)` + 2 new test cases. F6 specified to fetch from `/api/v1/presets`. F9 split into F9a (action row + popover surface) + F9b (export feedback). F9a now mounts `ReaderSettingsPopover` toggled by ref (new surface). B7 added Step 8 SQL-projection assertion via `before_cursor_execute`. |
| 2    | F10 cancel call lacked explicit URL; NFR-03 had no timing assertion; F1 `font-display` fallback was a TBD; B6 had a runtime conditional for the `ProcessingJob.book` relationship. | F10 Step 5 now spells out `POST /api/v1/processing/${jobId}/cancel`. B2 Step 8 adds a 1000-iteration `is_stale()` median-timing test (<5ms) plus a route-level <50ms median sanity check. F1 Step 5b spells out the explicit `@font-face` fallback in `assets/fonts.css` to be used only when @fontsource's default isn't `swap`. B6 adds Step 0 grep to verify `ProcessingJob.book` upfront so the implementor doesn't decide mid-implementation. |
| 3 (final review)    | TOCDropdown replacement was in File Map but had no task step; mobile compact-mode (OQ2) was not in TN Playwright walk despite being in scope. | F3 Step 6 added: replace `TOCDropdown.vue:53-83` with `<SectionListTable :compact="true">` + add a TOCDropdown.spec.ts assertion. TN Playwright walk gains Step 12: `browser_resize(375, 812)` mobile check verifying Type/Compression columns hidden + TOC dropdown fits without horizontal scroll. |
