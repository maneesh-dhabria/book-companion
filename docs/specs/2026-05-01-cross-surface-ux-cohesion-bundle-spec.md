# Cross-Surface UX Cohesion Bundle — Spec

**Date:** 2026-05-01
**Status:** Draft
**Tier:** 2 — Enhancement bundle
**Requirements:** `docs/requirements/2026-05-01-cross-surface-ux-cohesion-bundle.md`
**Wireframes:** `docs/wireframes/2026-05-01-cross-surface-ux-cohesion-bundle/`

---

## 1. Problem Statement

Eighteen cross-surface UX defects (Book Detail, Section Reader, app shell, four Settings pages) erode product polish: dead controls, lying read-outs (`0` char counts, literal `"FAILED:"` migration revisions), divergent component vocabularies (Tailwind `dark:` classes vs. scoped-style + CSS-variables), and a missing IA home for the book-level summary. This spec converts the 18 acceptance criteria from the requirements doc into prescriptive file-level changes, API contract changes, and verification commands.

**Primary success metric:** all 18 ACs verifiable, every defect's verified failure mode (`FAILED:` string, sidebar staying white on Dark theme, 0 highlights on Summary tab, TOC `0` chars) no longer reproducible on `localhost`.

---

## 2. Goals

| # | Goal | Success Metric |
|---|------|----------------|
| G1 | Every interactive control on affected surfaces does what its label promises (or is removed) | Zero buttons/links that are disabled-but-look-clickable; zero menu items missing handlers |
| G2 | Book Detail is the single home for reading **and** reading the book summary | `/books/:id?tab=summary` renders the Markdown book summary OR an empty state with a single Generate CTA |
| G3 | Settings pages share one visual vocabulary | Zero `dark:` Tailwind utility classes in `frontend/src/components/settings/`; all pages use scoped-style + CSS variables |
| G4 | Backend never leaks alembic error banners into API responses | `GET /api/v1/settings/migration-status` returns `null` (or structured error) instead of `"FAILED:"` |
| G5 | User can manage user presets (CRUD) and inspect system preset templates without a terminal | New/Edit/Delete affordances on user presets; raw Jinja viewer on any preset |

---

## 3. Non-Goals

- **NOT** introducing a new design system or component library — converging on the existing scoped-style + CSS-variable pattern (used by 5/6 settings pages) is cheaper.
- **NOT** redesigning IA beyond the Book Detail tab strip and overflow menu reshape.
- **NOT** building preset import/export/sharing — out of scope per requirements (item #15 is local CRUD only).
- **NOT** extending annotation rendering to **cross-project** highlights from `section_content` onto summary text — different text, no offset mapping.
- **NOT** changing how summaries are generated, evaluated, or stored — every defect here is a presentation/control bug.

---

## 4. Decision Log

Decisions D1–D12 from the requirements doc carry forward. Spec adds the following implementation-level decisions:

| # | Decision | Options Considered | Rationale |
|---|----------|--------------------|-----------|
| SD1 | Book Detail tab routing = query param `?tab=overview\|summary\|sections` | (a) query param, (b) nested path routes `/books/:id/summary`, (c) keep standalone `/books/:id/summary` as primary | (a) — matches existing reader pattern (`/books/:id/sections/:sid?tab=summary`); zero router-config change; tabs swap content within `BookOverviewView`. If a standalone book-summary route already exists, it 301-redirects to `?tab=summary`. (User decision) |
| SD2 | Migration-status backend = programmatic Alembic API | (a) `MigrationContext.get_current_revision()` + `ScriptDirectory.get_current_head()` in-process, (b) keep `uv run alembic` subprocess and sanitize, (c) structured error response only | (a) — root cause: in pip-installed mode `uv` is not on `PATH` and the subprocess fails; alembic's stderr banner leaks into `current`/`latest`. Programmatic API uses the existing `AsyncEngine`, has no `PATH` dependency, and cannot leak banners. (User decision) |
| SD3 | "Customize text" overflow item is **removed**, not split | (a) drop entirely (single "Customize reader…"), (b) keep both as distinct surfaces, (c) rename to one clearer label | (a) — there is only one customization surface today (reader settings popover); "Customize text" is a duplicate label. (User decision, OQ#3) |
| SD4 | Customize-reader entry point from Book Detail = global reader defaults | (a) book-scoped defaults, (b) global reader defaults, (c) book defaults + apply to last-read section | (b) — single source of truth (the existing `readerSettings` Pinia store); no new persistence shape; matches the gear-icon entry point in the reader. (User decision, OQ#4) |
| SD5 | Compression bucketing = uniform 5-pt rounding across full range | (a) uniform 5-pt, (b) cap at `~50%+`, (c) wider buckets at extremes | (a) — simplest formatter, sortable, no special cases. `Math.round(value/5)*5`. (User decision, OQ#2) |
| SD6 | Section reader footer prev/next = subtle inline link pair | (a) inline links, (b) bordered cards, (c) sticky bottom bar | (a) — minimal chrome; matches Notion/Substack docs aesthetic; keyboard arrows already work, footer is purely a discoverability fix. (User decision) |
| SD7 | `ThemeCard.vue` location = move from `components/settings/` to `components/shared/` | (a) move to shared/, (b) re-export from settings/, (c) leave + add a sibling | (a) — the requirements explicitly direct `frontend/src/components/shared/ThemeCard.vue` (D11, AC #17) so both `ReaderSettingsPopover` (via `ThemeGrid`), `ReadingSettings`, and `PresetSettings` (for future preset cards if needed) import from a single canonical path. Update imports in two callers. |
| SD8 | TOC char count source = pass `content_char_count` through `TocDropdown` to `SectionListTable` compact mode | (a) pass through existing field, (b) new API field, (c) compute client-side | (a) — `SectionBrief.content_char_count` is already returned by the API and rendered correctly in the full Sections table on Book Detail. Bug is that `TocDropdown` doesn't propagate the field into the compact-mode rows. (D8) |
| SD9 | Annotation Summary-tab highlights = broaden frontend filter, not new backend | (a) load both `section_content` AND `section_summary` annotations, render the right set per tab, (b) new backend join | (a) — `routes/annotations.py` already accepts and returns both `content_type` values. Hardcoded filter `content_type='section_content'` in the BookDetailView annotation loader is the single point of failure. Loader must also include `content_type='section_summary'`; the rendering side passes the right subset to `applyHighlights()` per active tab. New annotations created on the Summary tab persist with `content_type='section_summary'`. |
| SD10 | Markdown bullet/table styles = new scoped style block on `MarkdownRenderer.vue` (or `.markdown-body` global) | (a) scoped styles on the renderer component, (b) `.prose` Tailwind plugin, (c) global stylesheet | (a) — `MarkdownRenderer.vue` has no `<style>` block today; global Tailwind preflight wins and zeros out `list-style`. Adding a scoped `.markdown-body` class on the rendered root with explicit `list-style: disc/circle` + table styling is the smallest surgical fix. |
| SD11 | Customize-reader popover positioning = anchored to overflow trigger only (drop "centered modal" alternative) | (a) anchored only, (b) centered modal only, (c) responsive (anchor on desktop, modal on narrow viewports) | (a) — matches the reader's gear-icon pattern and wireframe `03_reader-settings-popover_desktop-web.html`. Removes the AC #4 "or centered modal" branch; one code path. (User decision) |
| SD12 | Annotation-create on Summary tab = pass active tab as content_type parameter | (a) read active tab from reader state in the create handler and pass content_type, (b) infer from selection target via data-attribute, (c) defer to /plan | (a) — single touch in the create handler; the active tab is already in reader state. (User decision) |
| SD13 | Preset facet pickers = card grids with plain-language subheads | (a) card grids per facet, (b) dropdowns, (c) mixed | (a) — matches wireframe 05; PSYCH J3 friction was specifically about facet vocabulary jargon, fixed inline by plain-language subheads. (User decision) |
| SD14 | Footer prev/next preserves the current `?tab` value | (a) preserve current tab, (b) always Summary, (c) Original on first visit | (a) — predictable; if the user is reading summaries they want the next summary. (User decision) |
| SD15 | Preset facet validation source = filesystem-derived from `prompts/fragments/{dim}/*.txt` | (a) filesystem-derived (cache on init), (b) static enum, (c) keep current source | (a) — adding a new fragment file extends allowed values without code change; matches the same convention `PresetService` already uses to compose prompts. (User decision) |
| SD16 | "Read Section Summaries" replaces "Read in reader" as the populated-state action label | (a) "Read Section Summaries" (clearer about destination — section-level summaries, not the book summary the user is already on), (b) "Read in reader" (generic) | (a) — disambiguates from the book-level summary already shown on the Summary tab. (User decision) |
| SD17 | Generate book-summary idempotency = backend rejects duplicate active job with 409 | (a) backend 409 + return active job_id, (b) frontend disable only, (c) accept as risk | (a) — covers cross-tab races and double-clicks; the frontend then attaches to the existing job_id and renders the in-progress state. (Simulation gap G1) |
| SD18 | Cancel button reuses existing processing-job cancel endpoint; cancellation leaves `summary_md` null | (a) reuse existing endpoint, (b) drop Cancel from FR-02, (c) defer to future bundle | (a) — minimal new surface; aligns with how section-summary jobs are cancelled today. (Simulation gap G2) |
| SD19 | Add a **Failed** state to BookSummaryTab — shows last error + Retry CTA | (a) explicit failed state, (b) silent fall-back to empty, (c) defer | (a) — keeps the failure visible so the user can decide; reads `processing_jobs.error_message` from the last terminal job for this book. (Simulation gap G3) |
| SD20 | BookSummaryTab subscribes to existing book-summary SSE channel for cross-tab freshness | (a) SSE subscribe, (b) manual refresh only, (c) accept staleness | (a) — reuses existing SSE infrastructure; covers the "regenerate in another tab" case at no new infra cost. (Simulation gap G7) |
| SD21 | `GET /api/v1/summarize/presets` skips malformed user-preset YAML files with a structured warning | (a) skip-with-warning, (b) 500 the whole endpoint, (c) best-effort partial parse | (a) — single bad file shouldn't break the whole UI; warning surfaces in logs and optionally in a `warnings: [...]` array on the response. (Simulation gap G4) |
| SD22 | `book_summary` is embedded in `GET /api/v1/books/{id}` response (not a separate endpoint) | (a) embed in book payload, (b) separate endpoint, (c) defer | (a) — one round-trip, matches how SectionBrief embeds default_summary; backend joins Book → default_summary (Summary table). (Simulation gap G5) |

---

## 5. User Journeys

The 7 journeys in the requirements doc (§ User Journeys) are authoritative. No new journeys added by the spec.

---

## 6. Functional Requirements

FR-XX numbering matches AC #N from the requirements doc § Acceptance Criteria so the plan can reference both.

### 6.1 Book Detail (FR-01, FR-02, FR-03, FR-04, FR-05)

| ID | Requirement | Files (primary) |
|----|-------------|-----------------|
| FR-01 | One primary `Read` CTA on Book Detail toolbar; no "Read Summary" button outside overflow; no disabled-link controls | `frontend/src/views/BookOverviewView.vue` |
| FR-02 | New `Summary` tab on Book Detail. **Empty state** (no book summary yet, no active job): banner text `"X of Y sections summarized so far — the book summary will reflect those."` + `Generate book summary` CTA. CTA is **enabled when ≥1 section summary exists**, disabled otherwise. **In-progress state**: progress indicator + Cancel button (Cancel calls the existing job-cancel endpoint per SD18; on success the tab returns to the Empty state, `book.summary_md` stays null). **Failed state** (last book-summary job ended with an error and no successful summary exists): error message from `processing_jobs.error_message` + `Retry` CTA (per SD19). **Populated state**: rendered Markdown of the book summary + `Regenerate` + `Read Section Summaries` actions. The `Read Section Summaries` action routes to `/books/:id/sections/<first_section_id>?tab=summary` (first section in the book, summary tab). The tab subscribes to the existing book-summary SSE channel so completions in another tab/session refresh the view automatically (per SD20); SSE reconnect uses the existing pattern. | `frontend/src/views/BookOverviewView.vue`, `frontend/src/components/book/BookSummaryTab.vue` (new) |
| FR-03 | "Customize text" never appears as a floating control. The overflow menu's `Customize reader…` is the only customization entry point. | `frontend/src/views/BookOverviewView.vue`, `frontend/src/components/book/OverflowMenu.vue` |
| FR-04 | Clicking `Customize reader…` opens the reader settings popover **anchored to the overflow menu trigger button** (no centered-modal fallback — SD11). Themes load successfully, Esc + outside-click both close. Settings affect **global reader defaults** (per SD4). | `frontend/src/components/book/OverflowMenu.vue`, `frontend/src/components/settings/ReaderSettingsPopover.vue` |
| FR-05 | Compression renders as `~N%` where `N = Math.round(raw/5)*5`. Sortable. | `frontend/src/components/book/SectionListTable.vue:39` |

### 6.2 Section Reader (FR-06, FR-07, FR-08, FR-09, FR-10, FR-12)

| ID | Requirement | Files (primary) |
|----|-------------|-----------------|
| FR-06 | Bullets in summary content render with `list-style: disc` (top) / `circle` (nested) and consistent indentation. Numbered lists render with default decimal markers. | `frontend/src/components/reader/MarkdownRenderer.vue` (new `<style scoped>` block) |
| FR-07 | Both Summary and Original tabs render an inline footer at end of content: `← Previous: <prev section title>` and `Next: <next section title> →` as plain underlined-on-hover text links. First section: only `Next: …`. Last section: only `← Previous: …`. Footer routes preserve the active `?tab` query param. | `frontend/src/views/BookDetailView.vue` (around lines 238–261; `<template #footer>` slot on `<ReadingArea>`), `frontend/src/components/reader/ReadingAreaFooterNav.vue` (new) |
| FR-08 | TOC dropdown shows correct per-section character count (matches Book Detail Sections table). Source: `SectionBrief.content_char_count`. | `frontend/src/components/reader/TOCDropdown.vue`, `frontend/src/components/book/SectionListTable.vue` (compact-mode prop) |
| FR-09 | `ContextSidebar` and `AIChatTab` background, text, and border colors read from reader-theme CSS variables. With reader Dark theme active, `.context-sidebar` background MUST NOT be `rgb(255,255,255)` — it MUST resolve to `var(--reader-bg)` (or equivalent in-scope var). Verified failure mode: switching to Dark leaves the sidebar pure white. Fix: apply the reader-theme scope (`data-theme` attribute) to the parent of the sidebar/chat panels OR change the sidebar/chat CSS to read `--reader-bg`/`--reader-text`/`--reader-border` directly. | `frontend/src/components/sidebar/ContextSidebar.vue`, `frontend/src/components/sidebar/AIChatTab.vue`, `frontend/src/stores/readerSettings.ts` |
| FR-10 | Tables in summary content render with `border`, header-row distinction (`<thead>` background or font-weight), and cell padding. | `frontend/src/components/reader/MarkdownRenderer.vue` (same `<style scoped>` block as FR-06) |
| FR-12 | Annotations with `content_type='section_summary'` render on the Summary tab using the existing `applyHighlights()` engine. **New highlights created while the active tab is Summary persist with `content_type='section_summary'`**; created on Original tab persist with `content_type='section_content'`. Wiring: the annotation-create handler reads the active tab from reader state and passes it as the `content_type` parameter to the create call (per SD12). **Out of scope**: cross-projecting `section_content` highlights onto summary text. Verified failure mode (`/books/1/sections/6`): API returns 2 highlight annotations, Original tab renders 2 `<span class="highlight">`, Summary tab renders 0. After fix: Summary tab renders highlights for any `section_summary` annotations. | `frontend/src/views/BookDetailView.vue:104,109` (annotation loader broadens filter), annotation-create handler in same view (read active tab, pass `content_type`), `frontend/src/utils/highlightInjector.ts` (no change) |

### 6.3 App Shell (FR-11)

| ID | Requirement | Files (primary) |
|----|-------------|-----------------|
| FR-11 | The dynamic title in the app bar AND the `BC` icon in the side rail are clickable router-links to `/`. Both have `cursor: pointer`, hover state, focus ring. The app-bar title element is the `<h1>` (or equivalent) rendered using the computed value from `TopBar.vue:36` (falls back to `"Book Companion"`); wrap it in `<router-link to="/">`. | `frontend/src/components/app/IconRail.vue:16-17`, `frontend/src/components/app/TopBar.vue:36` (and the title rendering site in the same file) |

### 6.4 Settings (FR-13, FR-14, FR-17, FR-18)

| ID | Requirement | Files (primary) |
|----|-------------|-----------------|
| FR-13 | **Backend:** `GET /api/v1/settings/migration-status` MUST never embed alembic error banners (e.g., `"FAILED:"`) into `current`/`latest`. On error, response is `{current: null, latest: null, is_behind: false, error: "<message>"}`. **Frontend:** renders any null/non-revision value as `Unknown` with a tooltip surfacing `error` when present. | `backend/app/services/settings_service.py:253-287`, `frontend/src/components/settings/DatabaseSettings.vue:39-48` |
| FR-14 | Database settings stats table: no alternating row stripes; uses the same neutral-row visual as other settings pages (no `nth-child(even)` rule). | `frontend/src/components/settings/DatabaseSettings.vue:188-190` |
| FR-17 | `ThemeCard.vue` lives at `frontend/src/components/shared/ThemeCard.vue` (moved from `components/settings/`). Both `ThemeGrid.vue` (used by `ReaderSettingsPopover`) and `ReadingSettings.vue` import from this shared path. Reading-preset pills are `<button>` with `cursor: pointer`, hover state, focus ring, and ARIA-correct semantics. | `frontend/src/components/shared/ThemeCard.vue` (new path), `frontend/src/components/settings/ThemeGrid.vue`, `frontend/src/components/settings/ReadingSettings.vue:63-69` |
| FR-18 | `LlmSettings.vue` uses scoped-style + CSS-variable pattern; zero `dark:` Tailwind utility classes. Visual parity with sibling settings pages side-by-side. | `frontend/src/components/settings/LlmSettings.vue:161-293` |

### 6.5 Preset Management (FR-15, FR-16)

| ID | Requirement | Files (primary) |
|----|-------------|-----------------|
| FR-15 | A `New preset` button opens a form: name, label, description, **and one card grid per facet** (style / audience / compression / content_focus). Each facet card shows the value name + a one-line plain-language subhead (per PSYCH J3 fix in the requirements doc § Wireframes). Layout matches `docs/wireframes/2026-05-01-cross-surface-ux-cohesion-bundle/05_preset-create-edit-form_desktop-web.html`. Save creates a user preset on disk via `POST /api/v1/summarize/presets`. User presets render inline `Edit` and `Delete` actions. System presets render neither. Name collision shows inline validation: `"A preset with this name already exists"`. Delete uses two-step confirm. | `frontend/src/components/settings/PresetSettings.vue`, `frontend/src/components/settings/PresetCreateEditForm.vue` (new), `backend/app/services/preset_service.py`, `backend/app/api/routes/summarize_presets.py` |
| FR-16 | Selecting any preset shows: description, facets, and the **raw Jinja prompt template source** — the unrendered base template + the fragment files it composes (one block per fragment, labeled by dimension). System presets are read-only (no Edit/Delete; template is read-only). Rendering with sample data is **out of scope**. | `frontend/src/components/settings/PresetSettings.vue`, `backend/app/api/routes/summarize_presets.py` (new template endpoint) |

---

## 7. API Changes

### 7.1 `GET /api/v1/settings/migration-status` (modified)

**Request:** unchanged.

**Response (200):**
```json
{
  "current": "string|null — current alembic revision ID, null on error",
  "latest": "string|null — head revision ID, null on error",
  "is_behind": "boolean",
  "error": "string|null — optional error detail (omitted/null when healthy)"
}
```

**Implementation (replaces subprocess):**
```python
# backend/app/services/settings_service.py
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

# Paths confirmed to exist: backend/app/migrations/alembic.ini and ./env.py
_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
_ALEMBIC_INI = _MIGRATIONS_DIR / "alembic.ini"

async def get_migration_status(self) -> dict:
    try:
        # 1. Read head from migration scripts (sync, no DB)
        cfg = Config(str(_ALEMBIC_INI))
        cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
        script = ScriptDirectory.from_config(cfg)
        latest = script.get_current_head()

        # 2. Read current from DB via the existing AsyncEngine on the service
        async with self._engine.connect() as conn:
            current = await conn.run_sync(
                lambda sync_conn: MigrationContext.configure(sync_conn).get_current_revision()
            )

        return {
            "current": current,
            "latest": latest,
            "is_behind": bool(current and latest and current != latest),
            "error": None,
        }
    except Exception as e:
        logger.exception("migration_status_failed")
        return {"current": None, "latest": None, "is_behind": False, "error": str(e)}
```

**Plan-time validation tasks:**
- Confirm `SettingsService` already holds an `AsyncEngine` reference; if not, inject from `app.state` during /plan.
- Confirm `alembic.ini`'s `script_location` resolves correctly when `bookcompanion` is installed via `pip` (importlib resources may be needed instead of `Path(__file__)` if the package is zipped).

**Defensive frontend rule:** any `current`/`latest` value that isn't a 12-character hex revision (or null) renders as `Unknown`.

### 7.2 Preset CRUD (new)

The existing `GET /api/v1/summarize/presets` returns the list. Per SD21, this endpoint must skip malformed user-preset YAML files (catch parse errors per file, log a structured warning, exclude from response, optionally surface in a `warnings: [{file, error}, ...]` field on the response). Add:

| Method | Path | Purpose | Success response |
|--------|------|---------|-----------------|
| `POST` | `/api/v1/summarize/presets` | Create user preset | `201 Created` + the created preset object (same shape as a list-item) |
| `PUT` | `/api/v1/summarize/presets/{name}` | Update user preset | `200 OK` + the updated preset object |
| `DELETE` | `/api/v1/summarize/presets/{name}` | Delete user preset | `204 No Content` |
| `GET` | `/api/v1/summarize/presets/{name}/template` | Return raw Jinja sources | `200 OK` + template payload (§ below). `404 Not Found` if `name` does not match any system or user preset. |

**`POST` / `PUT` request body:**
```json
{
  "name": "string — slug, [a-z0-9_], unique across system+user; PUT keeps name from URL",
  "label": "string — display name",
  "description": "string|null",
  "facets": {
    "style": "one of: bullet_points|prose|outline|...",
    "audience": "one of: practitioner|academic|...",
    "compression": "one of: brief|standard|detailed",
    "content_focus": "one of: frameworks_examples|concepts|..."
  }
}
```

Validation: facet values are **filesystem-derived** (per SD15) — valid values for each dimension are the basenames (without `.txt`) of files in `backend/app/services/summarizer/prompts/fragments/{dimension}/`. `PresetService` caches this mapping on init; **adding a new fragment file requires a process restart for the new value to be accepted** (acceptable for a single-user tool). Invalid facet → `422 Unprocessable Entity` with the offending dimension/value in the error body.

Frontend form validation (FR-15): name MUST be non-empty and match `[a-z0-9_]+`; label MUST be non-empty. Empty fields render an inline error before submission; an invalid slug renders an inline error and disables Save. Name collision (system OR user) → `409 Conflict` with `{detail: "A preset with this name already exists"}`. Deleting a system preset → `403 Forbidden`. Updating/deleting a user preset that doesn't exist → `404`.

**`GET /presets/{name}/template` response:**
```json
{
  "name": "string",
  "is_system": "boolean",
  "base_template": {
    "path": "summarize_section_v1.txt",
    "source": "string — raw Jinja template content"
  },
  "fragments": [
    {
      "dimension": "style",
      "value": "bullet_points",
      "path": "fragments/style/bullet_points.txt",
      "source": "string — raw fragment content"
    }
  ]
}
```

### 7.3 Annotations (no contract change)

`GET /api/v1/annotations` already supports both `content_type` values. Frontend loader must request both (or omit the filter and split client-side).

### 7.4 `GET /api/v1/books/{id}` (modified — embed book_summary, per SD22)

The existing book-detail endpoint MUST embed the current default book summary so BookSummaryTab renders in one round-trip.

**Response (200) — added field:**
```json
{
  "book": {
    "...": "existing fields",
    "book_summary": {
      "summary_id": "int",
      "markdown": "string — Summary.summary_md",
      "generated_at": "ISO8601",
      "preset_name": "string — preset used for this summary"
    }
  }
}
```
- `book_summary` is `null` when the book has no `default_summary` row at the book level.
- Backend resolves via `Book.default_summary` (Summary table relationship) using `selectinload()` to avoid lazy-load post-commit (CLAUDE.md gotcha 1).

### 7.5 `POST /api/v1/books/{id}/book-summary` (modified — idempotency, per SD17)

The existing endpoint queues the job. Add idempotency:

**Error response (409 Conflict):**
```json
{
  "detail": "A book-summary job is already in progress for this book",
  "active_job_id": "int — the running processing_jobs.id"
}
```
- Triggered when an active (non-terminal) `processing_jobs` row exists with this book_id and job_type='book_summary'.
- Frontend treats 409 as a non-error: extracts `active_job_id`, attaches to the SSE channel, renders In-progress state.

### 7.6 Cancel job (existing endpoint, no contract change)

Cancel reuses the existing processing-job cancel endpoint. /plan task: confirm exact path (likely `DELETE /api/v1/processing/{job_id}` or `POST /api/v1/processing/{job_id}/cancel`) and pin in the plan doc.

---

## 8. Database Design

**No schema changes.** All affected behavior is presentation-layer or service-layer.

User presets continue to persist as YAML files under the data directory's preset folder (existing `PresetService` convention). System presets remain read-only files in the package at `backend/app/services/summarizer/prompts/presets/`.

---

## 9. Frontend Design

### 9.1 New components

| Path | Purpose |
|------|---------|
| `frontend/src/components/shared/ThemeCard.vue` | Moved from `components/settings/`. Single source of truth for theme/preset cards. |
| `frontend/src/components/book/BookSummaryTab.vue` | Renders the Book Detail Summary tab — empty/in-progress/populated states. |
| `frontend/src/components/book/BookDetailTabs.vue` | Tab strip wrapper for Book Detail (Overview/Summary/Sections). May be implemented inline in `BookOverviewView.vue` if simple enough. |
| `frontend/src/components/reader/ReadingAreaFooterNav.vue` | Inline prev/next link pair rendered in `<ReadingArea>` footer slot. |
| `frontend/src/components/settings/PresetCreateEditForm.vue` | New/Edit form (name, label, description, 4 facet pickers). |
| `frontend/src/components/settings/PresetTemplateViewer.vue` | Read-only Jinja source viewer (base template + fragment blocks). Code-styled `<pre>` with copy-to-clipboard. |

### 9.2 Tab strip (Book Detail)

`BookOverviewView.vue` renders a tab strip at the top with three buttons: `Overview`, `Summary`, `Sections`. Active tab driven by `route.query.tab` (default `overview`). Switching emits `router.replace({ query: { ...route.query, tab: <new> } })`. The Overview tab keeps its current content unchanged (cover, metadata, authors, parsing/summarization status, quality score). The Sections tab renders the existing `SectionListTable`. The Summary tab renders `BookSummaryTab.vue`.

### 9.3 State management

- **Reader settings:** existing `readerSettings` Pinia store. Customize-reader from Book Detail overflow writes to the same store (SD4).
- **Presets:** new methods on the existing presets store: `createPreset(payload)`, `updatePreset(name, payload)`, `deletePreset(name)`, `fetchTemplate(name)`. Optimistic-UI is **not** required — wait for response.
- **Annotations:** `BookDetailView.vue` annotation loader broadens to `content_type IN (section_content, section_summary)`. Each tab passes its own subset to `applyHighlights()`.

### 9.4 Footer prev/next pattern

```html
<footer class="reading-area__footer-nav">
  <a v-if="prev" :href="prevHref" class="footer-nav__prev">← Previous: {{ prev.title }}</a>
  <span v-else></span>
  <a v-if="next" :href="nextHref" class="footer-nav__next">Next: {{ next.title }} →</a>
</footer>
```
- Plain text links, underline on hover, `color: var(--reader-text)` muted at 0.7 opacity.
- Both `prevHref` and `nextHref` preserve the current `?tab=` value (Summary→Summary, Original→Original; SD14).
- Layout: flex `justify-content: space-between`. First section: empty `<span>` placeholder on left. Last section: empty `<span>` on right. **Single-section book** (both `prev` and `next` are null): footer does not render at all.

### 9.5 Compression formatter (FR-05)

```ts
// frontend/src/components/book/SectionListTable.vue
const formatCompression = (raw: number): string => {
  const bucketed = Math.round(raw / 5) * 5;
  return `~${bucketed}%`;
};
```
Replace `value.toFixed(1) + '%'` at line 39.

### 9.6 MarkdownRenderer scoped styles (FR-06, FR-10)

```vue
<style scoped>
.markdown-body :deep(ul) { list-style: disc; padding-left: 1.5rem; }
.markdown-body :deep(ul ul) { list-style: circle; }
.markdown-body :deep(ol) { list-style: decimal; padding-left: 1.5rem; }
.markdown-body :deep(li) { margin-block: 0.25rem; }
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; margin-block: 1rem; }
.markdown-body :deep(th), .markdown-body :deep(td) {
  border: 1px solid var(--color-border);
  padding: 0.5rem 0.75rem;
  text-align: left;
}
.markdown-body :deep(thead) { background: var(--color-bg-muted); font-weight: 600; }
</style>
```
Apply class `markdown-body` on the renderer's root `<div>`.

### 9.7 Theme scope on side panels (FR-09)

Two acceptable options; pick whichever lands cleanly during /execute:

**Option A (smaller diff):** add a `data-theme` attribute on the parent of `ContextSidebar` + `AIChatTab` so existing reader-theme variables (`--reader-bg`, `--reader-text`, `--reader-border`) cascade in.

**Option B (most explicit):** change `ContextSidebar.vue` and `AIChatTab.vue` styles from `var(--color-bg)` etc. to `var(--reader-bg, var(--color-bg))` so they participate in the reader-theme scope but fall back to app defaults when rendered outside it.

Verification (must pass under both options): with the reader on Dark theme, `.context-sidebar` `background-color` MUST NOT be `rgb(255,255,255)`.

---

## 10. Edge Cases

The 11 cases in the requirements doc § Edge / Error Cases are authoritative. Spec-specific clarifications:

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Migration check fails (e.g., DB locked) | API returns `{current: null, latest: null, is_behind: false, error: "<msg>"}`; UI shows `Unknown` + tooltip with `error`. |
| E2 | User creates preset with reserved/system name | `409 Conflict`, inline form error `"A preset with this name already exists"`. |
| E3 | Preset name with non-slug chars | Frontend sanitizes to `[a-z0-9_]`; backend rejects with `400` if invalid. |
| E4 | Generate book summary clicked when 0 sections summarized | CTA disabled; banner explains `"Summarize at least one section first."` |
| E5 | Annotation created on Summary tab | Persists with `content_type='section_summary'`; re-renders on subsequent visits to that tab. |
| E6 | Section reader on first section | Footer: only `Next: …`; left side empty. |
| E7 | Section reader on last section | Footer: only `← Previous: …`; right side empty. |
| E8 | TOC for very long books | List remains scrollable; char count rendered for every row. |
| E9 | LlmSettings rendered in Dark theme | All controls visible with adequate contrast (matches sibling pages); no Tailwind `dark:` classes remain. |
| E10 | Standalone `/books/:id/summary` route hit | If such a route currently exists in `frontend/src/router/`, replace it with a redirect to `/books/:id?tab=summary`. /plan task: `grep -rn "summary" frontend/src/router/` to confirm presence/absence; if absent, no work required. |
| E11 | User clicks Generate book summary while a job is already active for that book (cross-tab or double-click) | Backend returns `409 Conflict` with `{detail: "A book-summary job is already in progress for this book", active_job_id: <int>}`. Frontend swallows the 409, attaches to the existing `active_job_id`, and renders the In-progress state. (SD17) |
| E12 | User clicks Cancel during in-progress generation | Calls existing job-cancel endpoint with the active job_id. On `204`, tab returns to Empty state; `book.summary_md` and book Summary row stay null. (SD18) |
| E13 | Last book-summary job ended in failure (terminal `error_message` non-null) and book has no summary yet | Tab renders Failed state: shows `processing_jobs.error_message` + Retry CTA. Retry calls the same POST endpoint as Generate. (SD19) |
| E14 | Another browser tab regenerates the book summary while this tab is on the Summary tab | SSE event arrives; tab refetches `GET /api/v1/books/{id}` and re-renders the populated state. (SD20) |
| E15 | A user-preset YAML file on disk is malformed (manual edit corrupted it) | `GET /presets` skips the bad file, logs a structured warning, optionally surfaces it in `warnings: [...]` on the response. UI renders the rest of the list. (SD21) |

---

## 11. Configuration & Feature Flags

**No new configuration variables.** No feature flags required — these are bug fixes and presentation changes. Land per-PR per-workstream; each PR independently shippable.

**Viewport scope:** desktop-web only. Tab strip and footer prev/next use flex/wrap so they degrade gracefully at narrow widths, but no responsive QA gate; iPad/mobile tuning is deferred to a separate bundle (per simulation gap G9 disposition).

---

## 12. Testing & Verification Strategy

### 12.1 Unit tests (frontend, Vitest)

| Test | Asserts |
|------|---------|
| `SectionListTable.compression.spec.ts` | `formatCompression(15.5)` → `"~15%"`; `formatCompression(47.8)` → `"~50%"`; `formatCompression(3.1)` → `"~5%"`; `formatCompression(0)` → `"~0%"`. |
| `BookSummaryTab.spec.ts` | Empty state shows banner + Generate button; CTA disabled when 0 sections summarized; CTA enabled when ≥1. |
| `OverflowMenu.spec.ts` | Menu items present: Generate/Read book summary, Customize reader, Edit structure, Re-import, Export Markdown, Delete. No "Customize text" item. |
| `ReadingAreaFooterNav.spec.ts` | Renders both links when prev+next present; only Next when first; only Previous when last; preserves `?tab` query param. |
| `TOCDropdown.spec.ts` | Compact rows render `content_char_count` when given; never renders `0` for non-empty sections. |
| `MarkdownRenderer.styles.spec.ts` | After mount with markdown containing `<ul><li>`, computed style of `<ul>` is `list-style: disc`. |

### 12.2 Unit tests (backend, pytest)

| Test | Asserts |
|------|---------|
| `test_settings_service.py::test_get_migration_status_happy_path` | Returns 12-char hex revisions, `error: None`. |
| `test_settings_service.py::test_get_migration_status_failure` | When `MigrationContext.get_current_revision()` raises, response is `{current: null, latest: null, is_behind: false, error: <str>}`. |
| `test_settings_service.py::test_no_failed_string_in_response` | Under any failure mode, no field's value starts with `"FAILED"`. |
| `test_preset_service.py::test_create_user_preset` | Writes YAML to data dir; round-trip via `load()` returns the same facets. |
| `test_preset_service.py::test_create_collision` | Creating a preset with a system name raises; API returns 409. |
| `test_preset_service.py::test_delete_system_forbidden` | `DELETE /presets/practitioner_bullets` → 403. |
| `test_preset_service.py::test_get_template_source` | Returns base template + N fragments, each with a `source` string. |

### 12.3 Integration / E2E

| Test | Asserts |
|------|---------|
| `tests/integration/test_migration_status_endpoint.py` | `GET /api/v1/settings/migration-status` against a healthy test DB returns `is_behind=False, error=None`, both revs are non-null hex. |
| `tests/e2e/test_preset_crud.py` | Create → Read → Update → Delete a user preset via the API; system preset DELETE returns 403. |

### 12.4 Manual verification (Playwright MCP)

Per CLAUDE.md "Interactive verification" workflow — run a fresh build into `backend/app/static`, start `bookcompanion serve --port 8765`, drive via Playwright MCP. **Each AC has a verifiable failure mode in the requirements doc; reproducing the pre-fix failure and confirming it no longer occurs is the gate.**

| AC | Pre-fix failure mode | Post-fix verification |
|----|----------------------|------------------------|
| 1 | "Read Summary" button visible+disabled on `/books/3` | Only one "Read" CTA visible; no button labeled "Read Summary" outside overflow. |
| 2 | No Summary tab on `/books/3` | Tab strip has Overview/Summary/Sections; clicking Summary on a book without `summary_md` shows empty state + Generate CTA. |
| 4 | Popover renders detached at `top:682,left:800` with "Couldn't load themes" error | Popover anchored to overflow trigger; `themes` API returns 200; close (Esc + outside-click) works. |
| 6 | Bullets render without markers | `getComputedStyle($0).listStyleType === "disc"`. |
| 8 | TOC shows `0` chars for every section on `/books/3` | TOC chars match Sections-table chars. |
| 9 | `getComputedStyle(document.querySelector(".context-sidebar")).backgroundColor === "rgb(255, 255, 255)"` under Dark theme | After theme switch, sidebar bg matches `var(--reader-bg)` (non-white). |
| 11 | BC icon and title not interactive | Both navigate to `/`; both have `cursor: pointer` and visible focus ring. |
| 12 | `/books/1/sections/6` Summary tab DOM has 0 `<span class="highlight">` | Summary tab DOM has highlight spans matching `section_summary` annotation count. |
| 13 | `GET /api/v1/settings/migration-status` returns `{"current":"FAILED:","latest":"FAILED:",...}` | Response is either healthy revs or `{current: null, latest: null, error: "<msg>"}` — never `"FAILED:"`. |
| 18 | LlmSettings has `dark:` Tailwind classes | `grep -r "dark:" frontend/src/components/settings/LlmSettings.vue` returns nothing. |

### 12.5 Verification commands

```bash
# Backend
cd backend
uv run python -m pytest tests/unit/test_settings_service.py tests/unit/test_preset_service.py -v
uv run python -m pytest tests/integration/test_migration_status_endpoint.py -v
uv run python -m pytest tests/e2e/test_preset_crud.py -v
uv run ruff check .

# Frontend
cd frontend
npm run test:unit -- SectionListTable.compression BookSummaryTab OverflowMenu ReadingAreaFooterNav TOCDropdown MarkdownRenderer.styles
npm run type-check
npm run lint

# No-regression grep gates
grep -r "dark:" frontend/src/components/settings/LlmSettings.vue && exit 1 || echo "OK: no dark: classes"
grep -rn '"FAILED:' backend/app/services/settings_service.py && exit 1 || echo "OK: no FAILED literal"

# Live verification (after build + serve --port 8765)
curl -s http://localhost:8765/api/v1/settings/migration-status | jq '. | select(.current=="FAILED:" or .latest=="FAILED:")' \
  | grep -q . && exit 1 || echo "OK: no FAILED leak"

# Playwright MCP — see § 12.4 table for the per-AC checks
```

---

## 13. Rollout Strategy

- **Per-workstream PRs**, in any order. Each workstream is independently shippable; no inter-PR dependency on a feature flag.
- **Suggested sequence** (intentionally not enforced — left to /plan):
  1. **Workstream 6** (Settings cohesion) and **Workstream 5** (App shell nav) first — pure cosmetic/wiring, lowest risk.
  2. **Workstream 1** (Book Detail toolbar) and **Workstream 2** (compression formatter) — small, isolated.
  3. **Workstream 4** (Section Reader polish) — touches MarkdownRenderer + side panels + TOC + footer + annotation filter; biggest surface in this bundle.
  4. **Workstream 3** (Book Summary tab) — depends on toolbar reshape (W1) for the Generate CTA placement parity.
  5. **Workstream 7** (Preset management) — independent of the rest; can run in parallel.
- **Rollback:** any PR can be reverted independently. No data migrations. User-preset YAML files persist across rollback (forward-compatible YAML).
- **Graceful degradation:** if the new `/presets/{name}/template` endpoint fails, PresetSettings falls back to current-state behavior (description + facets only, no template viewer).

---

## 14. Research Sources

| Source | Type | Key Takeaway |
|--------|------|--------------|
| `frontend/src/views/BookOverviewView.vue:76-95` | Existing code | Two adjacent CTAs + floating Customize link outside overflow |
| `frontend/src/components/book/OverflowMenu.vue:46-49,103-113,138-139` | Existing code | Customize-reader handler exists; popover uses absolute positioning |
| `frontend/src/views/BookDetailView.vue:104,109,238-261` | Existing code | Annotation loader hardcodes `content_type=section_content`; `<ReadingArea>` exposes prev/next props |
| `frontend/src/components/reader/MarkdownRenderer.vue` | Existing code | No scoped style block — global Tailwind preflight wins, zeros `list-style` |
| `frontend/src/components/reader/TOCDropdown.vue` | Existing code | Wraps `SectionListTable` in compact mode; `content_char_count` not propagated |
| `frontend/src/utils/highlightInjector.ts:259` | Existing code | `applyHighlights()` is content-type-agnostic — works for both tabs once correct annotations are passed |
| `frontend/src/components/sidebar/ContextSidebar.vue`, `AIChatTab.vue` | Existing code | Use `var(--color-bg)` not `var(--reader-bg)`; not in reader-theme scope |
| `frontend/src/components/app/IconRail.vue:16-17` | Existing code | BC logo is plain `<span>`, not a router-link |
| `frontend/src/components/settings/DatabaseSettings.vue:39-48,188-190` | Existing code | Renders backend literal directly; alt-row stripes via `nth-child(even)` |
| `backend/app/services/settings_service.py:253-287` | Existing code | `get_migration_status()` shells out to `uv run alembic` — fragile in installed mode |
| `backend/app/api/routes/annotations.py:38,60` | Existing code | API already filters/returns both `SECTION_CONTENT` and `SECTION_SUMMARY` |
| `backend/app/services/preset_service.py:71-76,118-139` | Existing code | `load()`, `resolve_facets()` exist; create/update/delete missing |
| `backend/app/services/summarizer/prompts/{presets,fragments}/` | Existing code | System presets + fragments live as YAML/txt files in package |
| `frontend/src/components/settings/ThemeCard.vue` | Existing code | Already extracted (in `settings/`); needs to move to `shared/` and be reused by `ReadingSettings`/`PresetSettings` |
| `frontend/src/components/settings/LlmSettings.vue:163-278` | Existing code | Uses Tailwind `dark:` classes throughout — outlier |
| Live API: `GET /api/v1/settings/migration-status` (2026-05-01) | Live response | `{"current":"FAILED:","latest":"FAILED:","is_behind":false}` — confirms backend-side leak |
| `docs/wireframes/2026-05-01-cross-surface-ux-cohesion-bundle/` | Wireframes | 6 wireframes covering the 6 IA/flow items; 12 polish items skip wireframes per /wireframes Phase 2 |
| `docs/requirements/2026-05-01-cross-surface-ux-cohesion-bundle.md` | Requirements | Authoritative AC table, edge cases, decision log |

---

## 15. Open Questions

None at spec time. All four open questions from the requirements doc were resolved during multi-role interview (see SD3, SD4, SD5, SD1).

---

## 16. Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | (a) FR-12 silent on how Summary-tab annotation-create knows to use `content_type='section_summary'`. (b) FR-04 carried forward AC's "or centered modal" alternative — needed a single canonical anchoring decision. (c) FR-11 handed off file location to /plan ("locate via grep"). (d) FR-15 said "4 facet pickers" without specifying the UX — wireframe shows card grids. (e) § 7.1 implementation block referenced `ALEMBIC_INI_PATH`/`MIGRATIONS_DIR` constants that don't exist. (f) E10 conditional ("if such a route exists") had no /plan task. | (a) Added SD12 + tightened FR-12 wiring (read active tab from reader state, pass as `content_type`). (b) Added SD11 (anchored only) + tightened FR-04 (no centered-modal fallback). (c) Pinned `TopBar.vue:36` as the title source after grep. (d) Added SD13 + tightened FR-15 (card grids per facet, plain-language subheads, ref wireframe 05). (e) Replaced placeholder constants with `Path(__file__).resolve().parent.parent / "migrations"` and confirmed `alembic.ini` exists; added two plan-time validation tasks. (f) Added explicit /plan grep task to E10. |
| 2 | (a) FR-02 mentioned a `Read in reader` action without a destination route or label clarity (user noted "Read in reader" is confusing on a Summary tab). (b) Footer prev/next href construction said "preserve current `?tab`" without pinning the rule. (c) § 7.2 facet validation referenced `PresetService.FACET_DIMENSIONS` without specifying whether values are static-enum or filesystem-derived. | (a) Renamed action to `Read Section Summaries`; pinned destination `/books/:id/sections/<first_section_id>?tab=summary`; added SD16. (b) Added SD14 making preserve-current-tab explicit. (c) Added SD15 (filesystem-derived from `prompts/fragments/{dim}/*.txt`, cached on init); changed validation error to `422` with offending dimension/value in body. |
| 3 (simulation) | 16 gaps surfaced from /simulate-spec: 5 significant (concurrent Generate idempotency, Cancel state machine, Failed UI state, malformed-YAML resilience, book_summary data-access path) + 11 minor (network drop, cross-tab freshness, footer fallback semantics, narrow-viewport scope, import-path migration, facet-cache restart semantics, active-tab state location, preset-CRUD response codes, template 404, form validation, single-section footer). | Added SD17–SD22 (idempotency 409, cancel reuse, failed state, SSE for cross-tab freshness, malformed-YAML skip, embed book_summary in `/books/{id}`). Added §§ 7.4–7.6 (book_summary embed, 409 idempotency contract, cancel-endpoint /plan task). Tightened FR-02 with explicit Failed state + SSE subscription. Added E11–E15 edge cases. Added desktop-first viewport scope note. Documented facet-cache restart semantics. Captured remaining minors in the simulation trace's Accepted Risks / Plan-time judgment sections. |
