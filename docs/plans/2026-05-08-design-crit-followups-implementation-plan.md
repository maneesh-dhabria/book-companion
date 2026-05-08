# Design-Crit Followups (Library, Book, Section, Audio) — Implementation Plan

**Date:** 2026-05-08
**Spec:** `docs/specs/2026-05-08-design-crit-followups-spec.md`
**Requirements:** `docs/requirements/2026-05-08-design-crit-followups.md`
**Simulation:** `docs/simulations/2026-05-08-design-crit-followups-simulation.md`

---

## Overview

This plan implements the 6-cluster bundle from the spec: dark-mode chip tokens (A), read-position correctness + h1 hierarchy (B), BookSummaryPage IA rebuild (C), SectionDetail toolbar rebuild (D), Audio Playbar/empty-state polish (E), and Library polish (F). No DB schema changes; three new backend endpoints; one extended endpoint; significant frontend rework on `BookOverviewView` (the spec calls it "BookSummaryPage"), `SectionListTable`, `BookSummaryTab`, `Playbar`, `AudioTab`, `ReaderHeader`, `FilterRow`, plus several new components (`OverviewDashboard`, `SummaryTOCRail`, `BackToTopFab`, `SentenceProgressBar`, `DifferencePopover`, `KeyboardShortcutsOverlay`, `resumeBannerStore`).

**Done when:**
- Backend has 3 new routes + extended `/continue`; all backend unit/integration tests pass.
- Frontend Vitest covers `firstChapter`, `readTime`, `resumeBanner` resolver, `SectionListTable`, `SummaryTOCRail`, `OverviewDashboard`, `Playbar` engine branches, `h1Count`.
- Playwright e2e suite (8 new specs) green; axe-core `color-contrast` zero violations on `/`, `/books/1`, `/books/1/sections/1`, `/concepts`, `/annotations` in light + dark.
- Manual /verify ladder spot-check passes: Read CTA on a book whose `sections[0].section_type === 'copyright'` lands on a real chapter; dark-mode chips legible; each `/books/:id` and `/books/:id/sections/:id` page has exactly one `<h1>`.
- `npm run lint`, `npm run type-check`, `npm run build`, `uv run ruff check .` all clean.

**Execution order:**

```
Phase 1 (Backend + helpers)         Phase 2 (Tokens + h1)
    T1  firstChapter helper             T7   Chip token CSS
    T2  readTime util         [P]       T8   First-class chip rewrites
    T3  /continue FM filter             T9   Chip site sweep (17 sites)
    T4  /resume-banner route            T10  Decorative non-text audit
    T5  /audio/sections/by-book         T11  H1 hierarchy fix
    T6  /audio/positions/by-book
    T6a /reading-state/by-book

Phase 3 (BookSummaryPage IA)        Phase 4 (Cluster D + E + F + final)
    T12 firstChapter at Overview        T20  3-cluster toolbar
    T13 firstChapter at SummaryTab      T21  Drop drawer + TOCDropdown chips
    T14 ContinueBanner FM fallback      T22  Playbar timestamp + tooltip badge
    T15 OverviewDashboard (4 tiles)     T23  SentenceProgressBar
    T16 Heading anchors + scroll        T24  AudioTab empty state + popover
    T17 TOC rail + FAB + metadata       T25  ResumeAffordance mounting
    T18 SectionListTable rewrite        T26  KeyboardShortcutsOverlay
    T18a useBookAudioMap composable     T27  Library view toggle + bulk gate
    T19 Section row UX + batch audio    T28  resumeBannerStore coordination
                                        T29  Dark-mode contrast e2e + grep gate
                                        T30  Final verification
```

`[P]` denotes a task that can run in parallel with the previous one. Otherwise execute sequentially.

---

## Decision Log

> Inherits architecture decisions D1–D22 from the spec. Entries below are implementation-specific decisions made during code study.

| #   | Decision | Options Considered | Rationale |
|-----|----------|--------------------|-----------|
| P1  | "HomeView" in spec = `frontend/src/views/LibraryView.vue` (route `/`). The plan uses `LibraryView` everywhere the spec says HomeView. | (a) rename file; (b) treat as alias. | (b) — renaming the file is out-of-scope churn and changes routing. The view is mounted at `/` per `router/index.ts:9-13`. |
| P2  | "BookSummaryPage" in spec = `frontend/src/views/BookOverviewView.vue` (route `/books/:id`, name `book-overview`). The plan uses the actual file name. | (a) rename file; (b) treat as alias. | (b) — file already exists with the IA the spec assumes; renaming would touch unrelated tests, router meta, and the redirect alias at `router/index.ts:53-58`. |
| P3  | TopBar lives at `frontend/src/components/app/TopBar.vue`, NOT `components/layout/`. The spec line refs are otherwise correct (the `<h1>` is at `app/TopBar.vue:47-49`). | (a) follow spec path verbatim; (b) follow code reality. | (b) — `components/layout/` does not exist in this repo. |
| P4  | The existing audio-position lookup route is `GET /api/v1/audio_position?content_type=...&content_id=...&browser_id=...` (NOT `/api/v1/audio/positions/lookup` as the spec hedged at FR-E07b). This is what `frontend/src/api/audioPosition.ts` already calls. | (a) follow spec hedge; (b) reuse the actual endpoint. | (b) — FR-E07b explicitly said "verify at /plan time and adapt." Reuse the existing route; no new lookup endpoint needed for per-section detection. |
| P5  | Library `displayMode` values stay `'grid' \| 'list' \| 'table'` (current code in `stores/books.ts:19`). Spec FR-F02 listed `compact`; the existing third value is `table`. | (a) rename to `compact`; (b) keep `table`; (c) introduce a fourth value. | (b) — renaming touches `stores/books.ts`, `BookTable.vue`, server view-state persistence (`store.loadViews`), and existing localStorage keys. The spec's `compact` label is a UI label only; the storage value is irrelevant to UX. The `Lucide` icon swap (FR-F01) gives the visual change the spec asked for. |
| P6  | Use the existing `localStorage` key `bc.library.view` (FR-F02) AND ALSO continue calling `store.setDisplayMode(mode)` (which already persists to the backend `library-views` view system). Two-write durability. | (a) replace server-side persistence with local; (b) replace local with server; (c) write both. | (c) — server-side `loadViews()` already exists and is consumed by the store; localStorage adds resilience for offline / first-paint. Cheap and additive. |
| P7  | Section-row "More" overflow menu reuses the existing `frontend/src/components/book/OverflowMenu.vue` rather than introducing a new component. | (a) new component; (b) reuse + extend. | (b) — `OverflowMenu` already supports edit/regenerate/export actions used in `BookOverviewView`. Section context is a thinner subset; pass props or add a `mode="section"` variant. Verify in T19; if API is too book-scoped to fit, fall back to a small section-specific menu. |
| P8  | The new `dark-mode-contrast.spec.ts` slots into the verification ladder via `frontend/package.json`'s `test:e2e` script. Add a `Makefile` target `test-e2e-contrast` that calls `npx playwright test tests/e2e/dark-mode-contrast.spec.ts` so /verify can invoke it deterministically. test.sh does not currently invoke Playwright (verified via `grep test:e2e test.sh` returning none); verification ladder addition is one Makefile line. | (a) add to test.sh; (b) Makefile target; (c) inline in /verify. | (b) — Makefile is the documented dev-loop entrypoint per CLAUDE.md "front door". |
| P9  | Concept Overview tile (FR-C04) sort by `Concept.created_at ASC`. The spec acknowledged `Concept.score` does not exist (review-loop 3 finding). Verify at T15 that `/api/v1/concepts?book_id=N&sort=created_at_asc` (or equivalent) is callable; if not, fetch all concepts and sort client-side. | (a) backend support needed; (b) client-side sort. | Investigate at T15; default to (b) (client-side `.slice(0,5)` after `.sort`) since concept counts per book are typically <50. |
| P10 | `BookOverviewView.vue` `firstSection` computed at line 199 is the BUG site (D2). Replacement uses `firstChapter(sections, book.value?.status)`. The view also has a separate `<h1>{{ book.title }}</h1>` at line 19, which becomes the route's sole h1 once TopBar's h1 is demoted (FR-B10 verified). | (a) leave existing logic; (b) replace at single site. | (b) — surgical, clearly testable. |
| P11 | Sections-tab grouping is computed in the component (FR-C15) — no `BACK_MATTER_TYPES` constant. The mapping function `groupOf(sectionType)` returns `'front' | 'chapters' | 'back'` and lives in `SectionListTable.vue` (or a small adjacent helper) so the contract test on the existing FE/BE constants stays intact (D22). | (a) new constant; (b) computed mapping. | (b) — preserves the contract test guarantee. |
| P12 | `audio_positions` "by book" join (FR-E07a) is implemented in the existing `AudioPositionRepository` rather than ad-hoc in the route. Adds method `get_latest_for_book(book_id)` returning the most-recent matching row. | (a) inline in route; (b) repo method. | (b) — repo layer is where `audio_positions` SQL belongs per CLAUDE.md "Repositories: thin query builders only". |
| P13 | OverviewDashboard's Continue tile needs an honest "has reading position for THIS book" signal to switch label between "Continue reading" and "Start reading" (FR-C02). Add a small backend route `GET /api/v1/reading-state/by-book/{book_id}` returning the most-recent reader_position for the current device + book (404 if none). New T6a. | (a) honest backend signal; (b) reuse a denormalized `scroll_position` field; (c) drop the conditional. | (a) — keeps the label honest with no client-side guessing. Cost is one tiny route + repo method. |
| P14 | Sections-tab + TOCDropdown audio-availability lookup (T19, T21) share a per-book audio map. Add a `useBookAudioMap(bookId)` composable with simple in-memory cache so a single fetch serves both surfaces in one render of `BookOverviewView`. New T18a. | (a) duplicate fetch per surface; (b) shared composable. | (b) — saves redundant fetches when navigating Sections → SectionDetail breadcrumb dropdown; ~20 LOC composable. |
| P15 | ReaderHeader reads `currentSection.title` from `useReaderStore()` directly instead of prop-drilling from `BookDetailView` (T11). | (a) explicit prop; (b) read from store. | (b) — ReaderHeader is already store-coupled (the breadcrumb's section list comes from the store via the parent). Avoids a prop contract change for a single string. |
| P16 | `LibraryView` renders no banner while `resumeBannerStore.chosen` is loading; banner appears post-fetch. Avoids a flash of `<ContinueBanner>` when the user actually wants `<ResumeAffordance>`. | (a) optimistic render; (b) wait. | (b) — `chosen === null` semantically covers both "still loading" and "no activity". Single-source-of-truth conditional. |
| P17 | `/reading-state/resume-banner` response schema is extended beyond spec §9.1 with `last_audio_total_sentences: int \| None`. Spec §9.1 omitted it; `<ResumeAffordance>` requires it for honest "X of Y" copy. Backend reads it from the matching `audio_files` row. | (a) extend backend response; (b) suppress "of Y" client-side; (c) extra FE round-trip. | (a) — single round-trip, honest UX, no schema mutation. |

---

## Code Study Notes

- **Section-type constants** are mirrored at `backend/app/services/parser/section_classifier.py:84` (`FRONT_MATTER_TYPES`) and `:98` (`SUMMARIZABLE_TYPES`) and at `frontend/src/stores/reader.ts:10-29`. A contract test at `backend/tests/unit/test_section_type_sets_contract.py` enforces equality. Plan additions must NOT re-declare these.
- **Bug sites confirmed** (verified by reading code):
  - `frontend/src/views/BookOverviewView.vue:199` — `firstSection = computed(() => (book.value?.sections || [])[0] ?? null)` ✓ exists.
  - `frontend/src/components/book/BookSummaryTab.vue:164-173` — `readSectionSummaries()` sorts by `order_index` and picks `[0]` ✓ exists.
  - `frontend/src/components/app/TopBar.vue:47-49` — `<h1 class="top-bar-title"><router-link ...>` ✓ exists.
  - `frontend/src/components/audio/Playbar.vue:117-130` — Limited-controls badge at 117–123, timestamp at 128–130 ✓ exists.
  - `frontend/src/components/library/FilterRow.vue:53-77` — display-mode buttons with `▦ ☰ ▤` glyphs ✓ exists.
  - `frontend/src/components/audio/AudioTab.vue:95-105` — current "no-audio" empty state ✓ exists.
- **`BookOverviewView` already has `<h1>{{ book.title }}</h1>`** at line 19, so post-FR-B08 (TopBar demote) the route lands on exactly one h1. No additional change needed for FR-B10 beyond verification.
- **`ReaderHeader.vue` has NO `<h1>`** today — only a breadcrumb dropdown. FR-B09 must promote the section title to a new `<h1 class="reader-h1">` while keeping the breadcrumb context as a sibling (no heading semantics).
- **`ResumeAffordance.vue` (`frontend/src/components/audio/ResumeAffordance.vue`) is functional**: `resume()` and `startFromBeginning()` are implemented at lines 39–54 and call `useTtsPlayerStore().open()`. D12 scope is purely mounting. The component is currently referenced ONLY by its test (`__tests__/ResumeAffordance.spec.ts`) — confirmed via repo-wide grep.
- **`LibraryView.vue` already mounts `<ContinueBanner />`** at line 64. T28 must keep this but gate it on `resumeBannerStore.chosen === 'reading'` (or `null` while loading), and add `<ResumeAffordance>` for `chosen === 'listening'`.
- **`audio_positions` schema** (`backend/app/db/models.py:678+`): PK = `(content_type, content_id, browser_id)`; `updated_at` is the recency column (NO `last_played_at` — confirmed). `book_id` is NOT a column; the join through `book_sections` per FR-E07a is necessary.
- **`reading_state_repo.get_latest_other_device`** at `backend/app/db/repositories/reading_state_repo.py:54-64` does NOT join `book_sections`; FR-B05a must add a join + `WHERE bs.section_type NOT IN (...)`.
- **Existing audio position route**: `GET /api/v1/audio_position` (path: `backend/app/api/routes/audio_position.py:23`). NOT under `/api/v1/audio/positions/lookup`. Decision P4 above.
- **Verify ladder hook**: `test.sh` has no e2e wiring (verified `grep test:e2e test.sh` returns none). The Makefile is the front door per CLAUDE.md; T29 adds a target. /verify Phase 4 already runs Playwright via the manual ladder; T29 wires the new spec into the deterministic gate.
- **Data flow pipeline trace (resume coordination)**: Audio write entry (`AudioPositionService.update`) → `audio_positions.updated_at` ✓. Reader write entry (`reader.ts` route guard / `PUT /reading-state`) → `reader_position.updated_at` ✓. Storage tables exist ✓. Read entry for home banner = `GET /reading-state/resume-banner` ❌ TO BUILD (T4). FE consumer = `useResumeBannerStore` ❌ TO BUILD (T28). All write-end and storage links exist; only read-end + FE consumer are gaps — exactly as the spec data-flow trace promised in §6.2.

---

## Prerequisites

- `git status` clean on a branch named `design-crit-followups` (or equivalent).
- `cd backend && uv sync --dev` succeeds.
- `cd frontend && npm install` succeeds.
- A book with at least one front-matter section AND at least one chapter exists in the dev DB (for manual spot checks). If absent: `cd backend && uv run python tests/fixtures/download_fixtures.py && uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub`.

---

## File Map

### Backend

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/app/api/schemas.py` (extend) | Add `ResumeBannerResponse`, `AudioByBookResponse`, `AudioPositionByBookResponse` Pydantic schemas. |
| Modify | `backend/app/api/routes/reading_state.py` | Add `GET /resume-banner`; extend `/continue` callsite to use new repo signature. |
| Modify | `backend/app/db/repositories/reading_state_repo.py` | Add `get_latest_other_device(user_agent, exclude_section_types)`; add `get_latest_resume_banner(exclude_section_types)`. |
| Modify | `backend/app/db/repositories/audio_position_repo.py` | Add `get_latest_for_book(book_id)`. |
| Create | `backend/app/api/routes/audio.py` (extend or new sub-route file) | Add `GET /audio/sections/by-book/{book_id}` and `GET /audio/positions/by-book/{book_id}`. (If `audio.py` has no router for sections, add a new `audio_by_book.py` and include it in `app/api/main.py`.) |
| Test | `backend/tests/unit/api/test_reading_state.py` (extend) | New tests for FM filter on /continue + new /resume-banner. |
| Test | `backend/tests/integration/test_reading_state_continue.py` (NEW) | End-to-end test seeding reader_position pointing at copyright; assert next valid row is returned. |
| Test | `backend/tests/unit/api/test_audio_by_book.py` (NEW) | Tests for both new audio batch endpoints. |

### Frontend

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `frontend/src/utils/readTime.ts` | `formatReadTime(chars)` + `formatReadTimeSum(chars[])`. |
| Modify | `frontend/src/stores/reader.ts` | Export `firstChapter(sections, bookStatus)` helper. |
| Create | `frontend/src/stores/resumeBanner.ts` | Pinia store: fetches `/reading-state/resume-banner`; exposes `chosen: 'reading'\|'listening'\|null`. |
| Create | `frontend/src/composables/useBookAudioMap.ts` | Shared audio-map cache by bookId (consumed by SectionListTable + TOCDropdown). |
| Modify | `frontend/src/assets/main.css` | Add `.chip`, `.chip--accent`, `.chip--info`, `.chip--warn`, `.chip--neutral` + `.dark` variants. |
| Modify | `frontend/src/components/common/TagChip.vue` | Use chip tokens (drop scoped color rules). |
| Modify | `frontend/src/components/audio/EngineChip.vue` | Use `.chip--info` / `.chip--neutral`. |
| Modify | `frontend/src/components/audio/Playbar.vue` | Limited-controls → `.chip--warn`; timestamp gated by engine; tooltip + sentence progress mount. |
| Modify | 17 chip-using components (see FR-A05) | Single-file token swaps. |
| Modify | `frontend/src/components/app/TopBar.vue` | `<h1>` → `<span>`. |
| Modify | `frontend/src/components/reader/ReaderHeader.vue` | 3-cluster toolbar; promote section title to `<h1 class="reader-h1">`; drop drawer; pass enriched chips to TOCDropdown. |
| Modify | `frontend/src/components/reader/TOCDropdown.vue` | Add status chips per row. |
| Modify | `frontend/src/components/reader/ContinueBanner.vue` | Front-matter fallback via `firstChapter`. |
| Modify | `frontend/src/views/BookOverviewView.vue` | Replace `firstSection` with `firstChapter`; mount `OverviewDashboard` for the Overview tab; mount `ResumeAffordance` (gated). |
| Modify | `frontend/src/components/book/BookSummaryTab.vue` | `readSectionSummaries` uses `firstChapter`; integrate TOC rail + FAB + metadata strip. |
| Modify | `frontend/src/components/book/SectionListTable.vue` | 4 columns, grouped, persisted expand, row-as-button, hover icons. |
| Modify | `frontend/src/components/audio/AudioTab.vue` | Empty-state rewrite. |
| Modify | `frontend/src/components/library/FilterRow.vue` | Lucide icons + Select-mode toggle. |
| Modify | `frontend/src/components/library/BookCard.vue`, `BookList.vue`, `BookTable.vue` | Hide checkboxes outside bulk-select mode. |
| Modify | `frontend/src/views/LibraryView.vue` | Resume coordination: use `resumeBannerStore` to choose between `<ContinueBanner>` and `<ResumeAffordance>`. |
| Modify | `frontend/src/views/SettingsView.vue` | Add `id="audio"` anchor on the engine settings section. |
| Modify | `frontend/src/router/index.ts` | Add/verify `scrollBehavior` honoring `to.hash`. |
| Modify | `frontend/src/stores/ui.ts` | Add `bulkSelectMode` boolean state. |
| Create | `frontend/src/components/book/OverviewDashboard.vue` | 4-tile dashboard with skeletons. |
| Create | `frontend/src/components/book/SummaryTOCRail.vue` | Sticky right-rail TOC. |
| Create | `frontend/src/components/book/BackToTopFab.vue` | FAB visible after first viewport. |
| Create | `frontend/src/components/book/SummaryMetadataStrip.vue` | Metadata strip above markdown. |
| Create | `frontend/src/components/audio/SentenceProgressBar.vue` | Segmented bar above Playbar. |
| Create | `frontend/src/components/audio/DifferencePopover.vue` | Anchored popover for engine difference. |
| Create | `frontend/src/components/app/KeyboardShortcutsOverlay.vue` | `?`-toggled shortcuts overlay. |
| Test | `frontend/src/stores/__tests__/firstChapter.spec.ts` (NEW) | Helper unit tests. |
| Test | `frontend/src/utils/__tests__/readTime.spec.ts` (NEW) | Read-time tests. |
| Test | `frontend/src/stores/__tests__/resumeBanner.spec.ts` (NEW) | Resolver tests. |
| Test | `frontend/src/components/book/__tests__/SectionListTable.spec.ts` (extend) | DOM-structural tests for 4 columns + grouping. |
| Test | `frontend/src/components/book/__tests__/SummaryTOCRail.spec.ts` (NEW) | Anchor + collision tests. |
| Test | `frontend/src/components/book/__tests__/OverviewDashboard.spec.ts` (NEW) | 4-tile rendering tests. |
| Test | `frontend/src/components/audio/__tests__/Playbar.spec.ts` (extend) | Engine-branch tests. |
| Test | `frontend/src/components/__tests__/h1Count.spec.ts` (NEW) | h1-singleton on BookOverviewView + BookDetailView. |
| Test | `frontend/tests/e2e/dark-mode-contrast.spec.ts` (NEW) | Axe-core sweep. |
| Test | `frontend/tests/e2e/read-cta-routes-to-chapter.spec.ts` (NEW) | Read CTA never copyright. |
| Test | `frontend/tests/e2e/summary-toc-anchors.spec.ts` (NEW) | TOC click → heading at viewport top. |
| Test | `frontend/tests/e2e/h1-singleton.spec.ts` (NEW) | Exactly one `<h1>` per route. |
| Test | `frontend/tests/e2e/sections-grouping.spec.ts` (NEW) | Front+back collapsed; chapters expanded; localStorage round-trip. |
| Test | `frontend/tests/e2e/audio-empty-state.spec.ts` (NEW) | Empty state + popover open/close. |
| Test | `frontend/tests/e2e/playbar-timestamp.spec.ts` (NEW) | Engine-gated timestamp DOM presence. |
| Test | `frontend/tests/e2e/resume-coordination.spec.ts` (NEW) | Most-recent-wins banner choice. |

### Project root

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `Makefile` | Add `test-e2e-contrast` target wrapping the new Playwright spec. |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Chip-token sweep accidentally regresses an unrelated badge | Medium | T9 lists exact `file:line` per site; commit per file; final regression grep gates `bg-(indigo\|amber\|...)-(100\|200) + rounded-full`. |
| Section-row keyboard semantics break (`<div role="button">`) | Medium | T19 adds Vitest cases for Enter/Space activation, `cmd+click` open-in-new-tab, middle-click. |
| Sections tab batch-audio endpoint absent in dev DB | Low | T19 fallback path enables Listen rows when endpoint 404s; per-click `audio_position` lookup still works. |
| `BookOverviewView.vue` rewrite (Overview tab) breaks the existing Overview text | Low | T15 explicitly REPLACES the existing `.overview-meta` block; behavior change is intentional and asserted by `OverviewDashboard.spec.ts`. |
| Markdown-it heading anchor plugin name/version mismatch | Medium | T16 verifies the plugin during the failing-test step; if absent, falls back to render-rule override. |
| `@floating-ui/vue` not installed | Medium | T24 starts with `npm ls @floating-ui/vue`; if missing, falls back to a manual absolutely-positioned div as the spec FR-E05 allows. |
| `ResumeAffordance` requires audioStatus prop that the new mount sites cannot supply | Low | Code study confirmed `audioStatus: 'complete' | 'partial' | 'none'` — pass `'complete'` when the new `/audio/positions/by-book/{id}` returns 200; `'none'` on 404. |
| Cross-device parity between `/continue` and `/resume-banner` confuses callers | Low | Spec D21 + FR-B05 explicitly note both endpoints; tests in T3 + T4 cover the semantic divide. |

---

## Tasks

## Phase 1: Backend foundations + helpers

Phase rationale: build the backend endpoints and FE helpers that everything else consumes. Each task ships a thin slice that can be tested in isolation. After Phase 1, we have a deployable, tested backend surface and the two FE utilities that other phases depend on.

---

### T1: `firstChapter` helper

**Goal:** Add a tested `firstChapter(sections, bookStatus)` helper to `frontend/src/stores/reader.ts`.
**Spec refs:** FR-B01, D2.

**Files:**
- Modify: `frontend/src/stores/reader.ts`
- Test: `frontend/src/stores/__tests__/firstChapter.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Write the failing test at `frontend/src/stores/__tests__/firstChapter.spec.ts`. Cover: empty array → null; only `copyright` + status `'PARSING'` → null; only `copyright` + status `'PARSED'` → `sections[0]`; mix of `copyright` + `chapter` → first `chapter`; `introduction` qualifies; `glossary` does NOT qualify; `null`/`undefined` sections → null.
- [ ] Step 2: `cd frontend && npm run test:unit -- src/stores/__tests__/firstChapter.spec.ts` — expected FAIL: `firstChapter is not a function`.
- [ ] Step 3: Implement `export function firstChapter(sections, bookStatus)` in `frontend/src/stores/reader.ts`. Return: first section whose `section_type ∈ SUMMARIZABLE_TYPES`; else `sections[0]` when `bookStatus === 'PARSED'`; else null. Treat null/undefined inputs as null.
- [ ] Step 4: `npm run test:unit -- src/stores/__tests__/firstChapter.spec.ts` — expected PASS.
- [ ] Step 5: `git add frontend/src/stores/reader.ts frontend/src/stores/__tests__/firstChapter.spec.ts && git commit -m "feat(reader): firstChapter helper for FR-B01"`.

**Inline verification:**
- `cd frontend && npm run type-check` — clean.
- `npm run test:unit -- src/stores/__tests__/firstChapter.spec.ts` — N passed.

---

### T2: `readTime` utility [P with T1]

**Goal:** Add `formatReadTime` and `formatReadTimeSum` helpers.
**Spec refs:** FR-C14, G7.

**Files:**
- Create: `frontend/src/utils/readTime.ts`
- Test: `frontend/src/utils/__tests__/readTime.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Write the failing tests in `readTime.spec.ts`. `formatReadTime`: 0 → `'<1 min'`; -1 → `'<1 min'`; 1 → `'1 min'`; 1100 → `'1 min'`; 1101 → `'2 min'`; 6600 → `'6 min'`. `formatReadTimeSum`: `[]` → `'<1 min'`; `[60001]` → `'1h'`; `[60001, 60001]` → `'2h'` (120002 chars / 1100 = 109.09 → ceil = 110 min → `'1h 50m'`); `[3300, 3300]` → `'6 min'`. Verify the 110-min math; the spec sketch said `'1h 50m'` for `[60001, 60001]`.
- [ ] Step 2: `npm run test:unit -- src/utils/__tests__/readTime.spec.ts` — expected FAIL.
- [ ] Step 3: Implement per the spec §11.4 code block. CHARS_PER_MINUTE = 1100.
- [ ] Step 4: `npm run test:unit -- src/utils/__tests__/readTime.spec.ts` — expected PASS.
- [ ] Step 5: `git commit -m "feat(utils): readTime formatters for FR-C14"`.

**Inline verification:**
- All tests pass.

---

### T3: `/reading-state/continue` front-matter filter (FR-B05a)

**Goal:** Server-side skip front-matter rows in `get_latest_other_device`.
**Spec refs:** FR-B05a, D20, §10.

**Files:**
- Modify: `backend/app/db/repositories/reading_state_repo.py`
- Modify: `backend/app/api/routes/reading_state.py` (no behavior change but verify wiring)
- Test: `backend/tests/unit/api/test_reading_state.py` (extend)

**Steps:**

- [ ] Step 1: Add a failing pytest in `test_reading_state.py::test_continue_skips_front_matter`: seed two `reader_position` rows (different `user_agent`s), one pointing at a `copyright` section, one at a `chapter` section, copyright more recent. Call `GET /reading-state/continue` with a third user_agent. Assert response `last_section_id` matches the chapter row.
- [ ] Step 2: `cd backend && uv run python -m pytest tests/unit/api/test_reading_state.py::test_continue_skips_front_matter -v` — expected FAIL (returns the copyright row).
- [ ] Step 3: Modify `reading_state_repo.get_latest_other_device(current_user_agent)` to add `JOIN BookSection ON BookSection.id == ReadingState.section_id`, `WHERE BookSection.section_type.notin_(FRONT_MATTER_TYPES)`. Import `FRONT_MATTER_TYPES` from `app.services.parser.section_classifier`. Use `select(ReadingState).join(BookSection, ReadingState.section_id == BookSection.id)` and existing `selectinload` options. Note: `section_id` may be null on some rows; use `.where(ReadingState.section_id.is_not(None))` to make the join safe, OR use `outerjoin` and filter only when section is non-null.
- [ ] Step 4: Pytest passes.
- [ ] Step 5: Add second test `test_continue_returns_empty_when_only_front_matter_exists`: only a copyright row across all devices → `ReadingStateResponse()` defaults.
- [ ] Step 6: `uv run ruff check . && uv run ruff format --check .` — clean.
- [ ] Step 7: `git commit -m "feat(reading-state): server-side front-matter filter on /continue (FR-B05a)"`.

**Inline verification:**
- `uv run python -m pytest tests/unit/api/test_reading_state.py -v` — all pass.
- `curl -sf http://localhost:8000/api/v1/reading-state/continue` (after seeding) returns a non-front-matter row.

---

### T4: New `GET /reading-state/resume-banner`

**Goal:** New endpoint exposing most-recent reading + audio positions across all browsers.
**Spec refs:** FR-B05, D21, §9.1.

**Files:**
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/db/repositories/reading_state_repo.py`
- Modify: `backend/app/db/repositories/audio_position_repo.py`
- Modify: `backend/app/api/routes/reading_state.py`
- Test: `backend/tests/unit/api/test_reading_state.py` (extend)

**Steps:**

- [ ] Step 1: Pydantic schema `ResumeBannerResponse` with all 11 fields per spec §9.1, PLUS `last_audio_total_sentences: int | None = None` (plan-level extension P17 — needed by the home-page `<ResumeAffordance>` so its "of Y" copy is correct). All fields Optional. Add to `app/api/schemas.py`.
- [ ] Step 2: Failing test `test_resume_banner_returns_most_recent_reading_and_audio`: seed a non-front-matter `reader_position` and an `audio_positions` row pointing at a `section_summary` content_id matching a known `book_sections.id`; both for different browser_ids. Call new endpoint; assert all reading + audio fields populated; ts ordering correct.
- [ ] Step 3: Run pytest — FAIL (route doesn't exist).
- [ ] Step 4: Add `ReadingStateRepository.get_latest_resume_banner_reading()` returning the most-recent `ReadingState` whose joined `BookSection.section_type ∉ FRONT_MATTER_TYPES`. NO `user_agent` exclusion (cross-device most-recent). Eager-load `book` + `section`.
- [ ] Step 5: Add `AudioPositionRepository.get_latest_resume_banner()` returning the most-recent `AudioPosition` row WHERE `content_type IN ('section_summary', 'section_content', 'book_summary')` ordered by `updated_at DESC`. For section types, eager-load (or join + select) the parent `BookSection` and its `Book`. For `book_summary`, look up `Book` by `audio_positions.content_id`. Return a NamedTuple or dict with `(content_type, content_id, updated_at, book_id, book_title, section_title, total_sentences)`. The `total_sentences` is read from the matching `audio_files` row by joining on `(book_id, content_type, content_id)`; null if no audio_files row exists.
- [ ] Step 6: Add route `@router.get("/resume-banner")` in `reading_state.py`. Compose the two repo calls; build the response. All-null fields when neither row exists.
- [ ] Step 7: Tests for: both null → all-null response, 200; reading-only → reading fields populated, audio fields null; audio-only with `annotations_playlist` → audio fields null (filtered at SQL); both → both populated.
- [ ] Step 8: `git commit -m "feat(reading-state): new /resume-banner endpoint (FR-B05, D21)"`.

**Inline verification:**
- `uv run python -m pytest tests/unit/api/test_reading_state.py -v` — all pass.
- `curl -sf http://localhost:8000/api/v1/reading-state/resume-banner | python3 -m json.tool` returns shape from §9.1.

---

### T5: New `GET /audio/sections/by-book/{book_id}`

**Goal:** Batch audio-availability lookup for the Sections tab.
**Spec refs:** FR-C20, §9.4.

**Files:**
- Modify: `backend/app/db/repositories/audio_file_repo.py`
- Create or modify: `backend/app/api/routes/audio.py` (add route in same module)
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/unit/api/test_audio_by_book.py` (NEW)

**Steps:**

- [ ] Step 0: Inspect `backend/app/api/routes/audio.py`. If its `APIRouter` already uses prefix `/api/v1/audio`, add the new routes there. Otherwise create `backend/app/api/routes/audio_by_book.py` with `APIRouter(prefix="/api/v1/audio", tags=["audio"])` and register it from `app/api/main.py` via `app.include_router(audio_by_book.router)`. Document the choice in the commit message.
- [ ] Step 1: Pydantic schemas: `AudioByBookEntry { section_id: int, has_mp3: bool, engine: str | None }` and `AudioByBookResponse { book_id: int, sections: list[AudioByBookEntry] }`.
- [ ] Step 2: Failing test: seed 3 sections in a book; create 1 `audio_files` row with `status='ready'` for one section; call endpoint; assert 3 entries returned, exactly 1 with `has_mp3=true`.
- [ ] Step 3: Add `AudioFileRepository.list_ready_for_book(book_id)` returning rows with `book_id == :id AND content_type IN ('section_summary','section_content') AND status == 'ready'`.
- [ ] Step 4: Add route `@router.get("/api/v1/audio/sections/by-book/{book_id}")`. Fetch sections via `SectionRepository.list_for_book(book_id)`; fetch audio rows; map by `content_id`. Return ALL sections with `has_mp3` derived from the map. 404 if book absent.
- [ ] Step 5: Pytest passes.
- [ ] Step 6: `git commit -m "feat(audio): batch /audio/sections/by-book route (FR-C20)"`.

**Inline verification:**
- `curl -sf http://localhost:8000/api/v1/audio/sections/by-book/1 | python3 -m json.tool` returns the schema.

---

### T6: New `GET /audio/positions/by-book/{book_id}`

**Goal:** Detect "audio position exists for this book" (used by `BookOverviewView` ResumeAffordance gate).
**Spec refs:** FR-E07a, §9.4.

**Files:**
- Modify: `backend/app/db/repositories/audio_position_repo.py`
- Modify: `backend/app/api/routes/audio.py` (or new sub-route)
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/unit/api/test_audio_by_book.py` (extend)

**Steps:**

- [ ] Step 1: Failing test: seed 2 audio_positions, one for `book_summary` of book 1 (content_id=1), one for `section_summary` of section in book 2; call endpoint with book_id=1; assert returns the `book_summary` row. Then seed an `annotations_playlist` row for book 1 with newer ts; assert it is NOT returned.
- [ ] Step 2: Pytest FAIL — endpoint missing.
- [ ] Step 3: Add `AudioPositionRepository.get_latest_for_book(book_id)`. SQL composes a UNION of:
  - section types: `SELECT * FROM audio_positions ap JOIN book_sections bs ON bs.id = ap.content_id WHERE ap.content_type IN ('section_summary','section_content') AND bs.book_id = :book_id`.
  - book summary: `SELECT * FROM audio_positions WHERE content_type='book_summary' AND content_id = :book_id`.
  Order by `updated_at DESC`, limit 1. Annotations-playlist excluded by SELECT clauses.
- [ ] Step 4: Add route `@router.get("/api/v1/audio/positions/by-book/{book_id}")`. 200 with shape from spec §9.4 if found; 404 if none.
- [ ] Step 5: Pytest passes.
- [ ] Step 6: `git commit -m "feat(audio): /audio/positions/by-book route (FR-E07a)"`.

**Inline verification:**
- `curl -sf -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/audio/positions/by-book/1` returns 200 or 404 deterministically based on seed state.

---

### T6a: New `GET /reading-state/by-book/{book_id}`

**Goal:** Per-book + per-device reading-state lookup so the Continue tile in OverviewDashboard can pick the honest "Continue reading" / "Start reading" label.
**Spec refs:** FR-C02 (the honest signal it implies). Plan-level decision P13.

**Files:**
- Modify: `backend/app/db/repositories/reading_state_repo.py`
- Modify: `backend/app/api/routes/reading_state.py`
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/unit/api/test_reading_state.py` (extend)

**Steps:**

- [ ] Step 1: Failing test `test_by_book_returns_latest_for_device_and_book`: seed two reader_position rows for the same device, different books; call endpoint with `book_id` matching the older row's book; assert `last_section_id` matches the older row.
- [ ] Step 2: Add `ReadingStateRepository.get_for_device_and_book(user_agent, book_id)` returning the matching row (or None) with `selectinload(ReadingState.section)`.
- [ ] Step 3: Add route `@router.get("/by-book/{book_id}")`. Returns the existing `ReadingStateResponse` schema; 200 with all-null fields when no row exists (NOT 404 — keeps the FE consumer simple).
- [ ] Step 4: Tests pass.
- [ ] Step 5: `git commit -m "feat(reading-state): /by-book route for OverviewDashboard Continue tile (P13)"`.

**Inline verification:**
- `curl -sf http://localhost:8000/api/v1/reading-state/by-book/1 | python3 -m json.tool` returns the schema.

---

## Phase 2: Tokens + h1 hierarchy

Phase rationale: ship the dark-mode chip token + h1 demote/promote together. Each is small, but the combined visual change is what unblocks the cluster-A and cluster-B regression tests in Phase 3+.

---

### T7: Chip token CSS

**Goal:** Add `.chip*` classes with light + dark variants to `main.css`.
**Spec refs:** FR-A01, §11.1.
**Wireframe refs:** none — global token addition; no specific screen.

**Files:**
- Modify: `frontend/src/assets/main.css`

**Steps:**

- [ ] Step 1: Append the CSS block from spec §11.1 verbatim (5 base classes + 4 dark variants). Place it near other global tokens (search for an existing `.btn-primary` rule and put it adjacent).
- [ ] Step 2: Manual verification: open the browser DevTools, apply `<span class="chip chip--accent">test</span>` to a temporary element in `BookOverviewView`; confirm both light + dark themes render.
- [ ] Step 3: `git commit -m "feat(css): add chip tokens with dark variants (FR-A01)"`.

**Inline verification:**
- `npm run build` — no CSS parse errors.
- Apply tokens manually in DevTools console; verify computed background/text matches the spec values.

---

### T8: First-class chip rewrites (TagChip, EngineChip, Limited-controls)

**Goal:** Rewrite the three "headline" chip components onto the tokens.
**Spec refs:** FR-A02, FR-A03, FR-A04.
**Wireframe refs:** none — this is a token swap; visual style unchanged.

**Files:**
- Modify: `frontend/src/components/common/TagChip.vue`
- Modify: `frontend/src/components/audio/EngineChip.vue`
- Modify: `frontend/src/components/audio/Playbar.vue` (Limited-controls span only)

**Steps:**

- [ ] Step 1: `TagChip.vue` — drop hardcoded color rules in `<style scoped>`; bind class `.chip` + a tone class chosen by prop or default `.chip--neutral`. If `color` prop drives a specific tone, keep an inline-style fallback for user-defined hex tags. Update existing TagChip tests if they assert on specific bg/text classes.
- [ ] Step 2: `EngineChip.vue:32` — replace `bg-indigo-100 text-indigo-700` (or the current hex) with `:class="['chip', engine === 'kokoro' ? 'chip--info' : 'chip--neutral']"`. Drop the corresponding scoped style if present. Run the existing `EngineChip` test if any.
- [ ] Step 3: `Playbar.vue:120` — change `class="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800"` to `class="chip chip--warn"`. Keep `data-testid="limited-controls"`.
- [ ] Step 4: `npm run test:unit` — all existing tests pass.
- [ ] Step 5: `git commit -m "feat(chips): port TagChip/EngineChip/Limited-controls to chip tokens (FR-A02..A04)"`.

**Inline verification:**
- Manual: open `/books/1` in dark mode; tag chips legible; Engine chip in Playbar legible; Limited-controls badge legible.

---

### T9: Chip site sweep (17 remaining text-bearing sites)

**Goal:** Token-swap the remaining 17 text-bearing chip/badge sites listed in FR-A05.
**Spec refs:** FR-A05.
**Wireframe refs:** none.

**Files:** (one commit per file is encouraged; one task because the work is mechanical)
- `frontend/src/components/reader/EvalBadge.vue:29`
- `frontend/src/components/common/ContrastBadge.vue:35`
- `frontend/src/components/sidebar/ChatScopeSelector.vue:50`
- `frontend/src/components/audio/GenerateAudioModal.vue:127`
- `frontend/src/components/settings/LlmSettings.vue:212`
- `frontend/src/components/audio/SectionsAudioRow.vue:63`
- `frontend/src/components/sidebar/AnnotationCard.vue:67`
- `frontend/src/components/library/BookCard.vue:33`
- `frontend/src/components/library/BookList.vue:36`
- `frontend/src/components/library/BookTable.vue:77`
- `frontend/src/components/settings/DatabaseSettings.vue:48`
- `frontend/src/components/settings/PresetSettings.vue:176`
- `frontend/src/components/settings/ReadingSettings.vue:148`
- `frontend/src/components/concepts/ConceptList.vue:46`
- `frontend/src/components/concepts/ConceptDetail.vue:39, :79`
- `frontend/src/components/upload/StructureReview.vue:39`

**Steps:**

- [ ] Step 1: For EACH file above: read the chip/badge element at the cited line, identify the current background/text classes, swap to `class="chip chip--<tone>"` where `<tone>` is `accent` (success/positive), `info` (informational), `warn` (warning/amber), or `neutral` (slate/grey). For `ConceptDetail.vue:79` (related-concept chips), use `.chip--accent` (interactive).
- [ ] Step 2: After each swap, eye-test the component in light + dark mode if any test fixture renders it.
- [ ] Step 3: Run `npm run test:unit` after the full sweep — all tests pass.
- [ ] Step 4: `npm run lint` — clean.
- [ ] Step 5: Run the regression grep:
  ```bash
  grep -rn 'rounded-full' frontend/src/components frontend/src/views \
    | grep -E 'bg-(indigo|amber|slate|blue|green|red|yellow)-(100|200)'
  ```
  Expected: NO output (or only matches in files we INTENTIONALLY left alone — none should remain after sweep). If matches remain, decide per-site whether to fold into `.chip--*` or keep (e.g., progress-bar fills).
- [ ] Step 6: `git commit -m "feat(chips): sweep 17 text-bearing chip sites onto tokens (FR-A05)"`.

**Inline verification:**
- Regression grep above returns no chip-shaped hits.
- `npm run build && npm run test:unit` — clean.

---

### T10: Decorative non-text chip audit (FR-A05a)

**Goal:** Confirm 7 decorative dot/pill sites meet WCAG SC 1.4.11 (≥ 3:1) in both themes; swap any that fail.
**Spec refs:** FR-A05a.
**Wireframe refs:** none.

**Files (READ first, swap only if failing):**
- `frontend/src/components/audio/KokoroStatusIndicator.vue:60, :65, :70`
- `frontend/src/components/sidebar/PersistentProcessingIndicator.vue:62`
- `frontend/src/components/book/SummarizationProgress.vue:55, :59`
- `frontend/src/components/common/BottomSheet.vue:121`

**Steps:**

- [ ] Step 1: For each site, read the current background color and the surrounding container's background; compute the contrast ratio (use a tool like [WebAIM contrast checker](https://webaim.org/resources/contrastchecker/) or the `axe` CLI). Document any failing pair in a checklist below.
- [ ] Step 2: For any failing pair, choose a darker/lighter token shade (e.g., bump `bg-emerald-300` → `bg-emerald-500`) that achieves ≥ 3:1 in both themes.
- [ ] Step 3: If all 7 sites pass: commit a no-op note in `docs/audits/2026-05-08-non-text-contrast-audit.md` recording the audit. If any fail: `git commit -m "fix(a11y): non-text contrast on decorative indicators (FR-A05a)"`.

**Inline verification:**
- Manual contrast check; results recorded.

---

### T11: H1 hierarchy fix

**Goal:** Demote TopBar `<h1>` to `<span>`; promote SectionDetail section title to `<h1>`; verify BookOverviewView retains exactly one `<h1>`.
**Spec refs:** FR-B08, FR-B09, FR-B10, G6, NFR-02.
**Wireframe refs:** none — this is a semantic-HTML fix, not a visual change.

**Files:**
- Modify: `frontend/src/components/app/TopBar.vue`
- Modify: `frontend/src/components/reader/ReaderHeader.vue`
- Test: `frontend/src/components/__tests__/h1Count.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Failing component test `h1Count.spec.ts`: mount `BookOverviewView` with a stubbed router + a fake book; assert `wrapper.findAll('h1').length === 1`. Mount `BookDetailView` (the section view) with a fake section; assert `=== 1`. Currently fails because TopBar adds a second h1.
- [ ] Step 2: `npm run test:unit -- src/components/__tests__/h1Count.spec.ts` — expected FAIL.
- [ ] Step 3: `TopBar.vue:47-49` — change `<h1 class="top-bar-title">` to `<span class="top-bar-title">`. Keep the inner `<router-link>`. Verify the existing `.top-bar-title` CSS still renders identically (it's flagged as a `font-size: 16px; font-weight: 600` rule so no h1-specific styles).
- [ ] Step 4: `ReaderHeader.vue` — read the section title from `useReaderStore()` (per P15, no prop drill). Add an import `import { useReaderStore } from '@/stores/reader'`, instantiate `const reader = useReaderStore()`, and render a new `<h1 class="reader-h1">{{ reader.currentSection?.title ?? '' }}</h1>` element ABOVE the `.reader-breadcrumb`. The breadcrumb keeps Library/Book context as plain `<router-link>`s with no heading semantics. Add scoped CSS:
  ```css
  .reader-h1 {
    font-size: 1.4rem;
    margin: 0 0 0.25rem 0;
  }
  ```
- [ ] Step 5: Test passes. Re-run `npm run test:unit` to ensure no broader regressions (pageTitle in TopBar still computes, etc.).
- [ ] Step 6: Manual spot-check via Playwright MCP after Phase 2 (or step 7 below): hard-reload `/books/1` and `/books/1/sections/1`; in DevTools console run `document.querySelectorAll('h1').length`; expect `1` on each.
- [ ] Step 7: `git commit -m "fix(a11y): h1 hierarchy across BookOverview / SectionDetail (FR-B08..B10)"`.

**Inline verification:**
- `npm run test:unit -- src/components/__tests__/h1Count.spec.ts` — PASS.
- `npm run type-check` — clean.

---

## Phase 3: BookSummaryPage IA

Phase rationale: 8 tasks rebuilding the dominant book-detail surface. Each task is independently committable but depends on Phase 1's helpers (`firstChapter`, `readTime`) and Phase 2's tokens (`.chip--*`). After Phase 3, the BookSummaryPage Overview, Summary, and Sections tabs match the spec.

---

### T12: Wire `firstChapter` into BookOverviewView Read CTA

**Goal:** Replace `firstSection = sections[0]` with `firstChapter(...)` at `BookOverviewView.vue:199`. Disable + tooltip when null.
**Spec refs:** FR-B02, G2, D2.
**Wireframe refs:** none — surgical replacement at a single computed.

**Files:**
- Modify: `frontend/src/views/BookOverviewView.vue`

**Steps:**

- [ ] Step 1: Failing component test (extend an existing spec or add `BookOverviewView.spec.ts`): mount with a book whose `sections[0].section_type === 'copyright'` and `sections[1].section_type === 'chapter'`; assert the Read button's `to.params.sectionId === sections[1].id.toString()`. Currently fails because `firstSection` returns sections[0].
- [ ] Step 2: At `BookOverviewView.vue:1`-ish import block, add `import { firstChapter } from '@/stores/reader'`. Replace line 199 with:
  ```ts
  const firstSection = computed(() =>
    firstChapter(book.value?.sections ?? null, book.value?.status ?? null)
  )
  ```
- [ ] Step 3: Update the Read `<router-link>` block (currently at lines 52–62) to render a disabled `<button>` with `title="No chapter to open yet"` when `firstSection.value === null`, else the existing router-link. Pseudocode:
  ```vue
  <router-link v-if="firstSection" class="btn-primary" ... />
  <button v-else type="button" class="btn-primary" disabled
    title="No chapter to open yet">Read</button>
  ```
- [ ] Step 4: Test passes; existing tests for BookOverviewView remain green.
- [ ] Step 5: `git commit -m "fix(book): Read CTA uses firstChapter (FR-B02)"`.

**Inline verification:**
- Manual: visit a book whose sections[0] is copyright; Read CTA navigates to the first chapter.

---

### T13: Wire `firstChapter` into BookSummaryTab "Read Section Summaries"

**Goal:** Replace `BookSummaryTab.vue:164-173` `readSectionSummaries` with `firstChapter`.
**Spec refs:** FR-B03.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/book/BookSummaryTab.vue`

**Steps:**

- [ ] Step 1: Failing test: mount `BookSummaryTab` with a book whose first section is `copyright`; click the "Read Section Summaries" button; assert router push goes to the first SUMMARIZABLE section.
- [ ] Step 2: Replace lines 164–173 to call `firstChapter(props.book.sections, props.book.status)`. If null, show toast `'No chapter to open yet'` (use the existing `useUiStore().showToast`).
- [ ] Step 3: Test passes.
- [ ] Step 4: `git commit -m "fix(book): readSectionSummaries uses firstChapter (FR-B03)"`.

**Inline verification:** unit tests pass.

---

### T14: ContinueBanner front-matter fallback

**Goal:** Defensive front-matter fallback in `ContinueBanner.vue` (FR-B04). If API returns null `section_id` or a front-matter section, fall back to `firstChapter`; banner becomes "Start reading".
**Spec refs:** FR-B04.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/reader/ContinueBanner.vue`

**Steps:**

- [ ] Step 1: Failing test: mock the API to return a front-matter section_id; mount the component with a populated book (`sections` array); assert banner text is `'Start reading'` and the link's section param is the first chapter.
- [ ] Step 2: Implement: when the resolved `section.section_type ∈ FRONT_MATTER_TYPES` OR `section_id` is null, compute `target = firstChapter(book.sections, book.status)`; if `target` non-null, render with `'Start reading'` label routing to `target.id`; else render no banner.
- [ ] Step 3: Test passes.
- [ ] Step 4: `git commit -m "fix(banner): ContinueBanner front-matter fallback (FR-B04)"`.

**Inline verification:** unit tests pass.

---

### T15: OverviewDashboard component (4 tiles + skeletons)

**Goal:** New component rendering the Continue / Book summary / Top concepts / Sections tiles with skeleton placeholders.
**Spec refs:** FR-C01, FR-C01a, FR-C02, FR-C03, FR-C04, FR-C05, G1.
**Wireframe refs:** none — component composition follows spec §11.2.

**Files:**
- Create: `frontend/src/components/book/OverviewDashboard.vue`
- Modify: `frontend/src/views/BookOverviewView.vue` (replace the Overview tab body lines 103-112 with `<OverviewDashboard :book="book" />`)
- Test: `frontend/src/components/book/__tests__/OverviewDashboard.spec.ts` (NEW)

**Steps:**

- [ ] Step 0: Verify `GET /api/v1/concepts` supports `?book_id=` filter: read `backend/app/api/routes/concepts.py` and inspect the route signature. If supported, plan the call as `/api/v1/concepts?book_id={bookId}&sort=created_at_asc&limit=5`; if NOT supported, fall back to `GET /api/v1/concepts?limit=200` + client-side filter `c.book_id === bookId` + client sort by `created_at` asc + slice 0..5. Document the discovered shape in the commit message.
- [ ] Step 1: Plan the data inputs: `book` prop (with `sections[]`, `status`, `default_summary`); fetched `concepts` (per Step 0 decision); per-book reading-state via `GET /api/v1/reading-state/by-book/{bookId}` (T6a) for the Continue tile label.
- [ ] Step 2: Failing test: mount with a fully-loaded book; assert exactly 4 tiles by data-testid (`tile-continue`, `tile-summary`, `tile-concepts`, `tile-sections`). Continue tile uses `firstChapter` (mock the helper). Sections tile renders the `formatReadTimeSum` of section char counts.
- [ ] Step 3: Build the component. Layout = CSS Grid (`grid-cols-1 md:grid-cols-2 gap-4`). Each tile is a `<router-link>` (or `<button>` for generative CTAs), focus ring, hover bg.
  - Continue: `firstChapter` for target; title is "Continue reading" if `GET /reading-state/by-book/{bookId}` (T6a) returns a non-null `last_section_id`, else "Start reading"; subtitle `§{order_index} · {section.title}`. Disabled state when target is null.
  - Book summary: subtitle from `book.default_summary` (preset + relativeTime).
  - Top concepts: fetch concepts client-side (await mounted), sort by `created_at ASC`, slice to 5 chips.
  - Sections: `formatReadTimeSum(book.sections.map(s => s.content_char_count ?? 0))`.
- [ ] Step 4: Add per-tile skeleton `<div class="skeleton">` blocks visible while data is loading. Use `bg-slate-200 dark:bg-slate-700 animate-pulse`. Three lines per tile, varying widths.
- [ ] Step 5: Replace the existing `<section v-if="activeTab === 'overview'">` block in `BookOverviewView.vue` (lines 103-112) with `<OverviewDashboard :book="book" />`.
- [ ] Step 6: Tests pass. Visual sanity check via Playwright MCP at `/books/1`.
- [ ] Step 7: `git commit -m "feat(book): OverviewDashboard 4-tile component (FR-C01..C05)"`.

**Inline verification:**
- Manual `/books/1` → 4 tiles visible; each routes correctly.

---

### T16: Markdown heading anchors + scrollBehavior

**Goal:** Markdown renderer emits stable `id="<slug>"` on every H2/H3; router scrollBehavior honors `to.hash` with 32px offset.
**Spec refs:** FR-C07, FR-C09, FR-E06a, §11.7.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/reader/MarkdownRenderer.vue` (or wherever `markdown-it` is configured)
- Modify: `frontend/src/router/index.ts`

**Steps:**

- [ ] Step 1: Open `MarkdownRenderer.vue` and identify the `markdown-it` setup. Run `npm ls markdown-it-anchor` — if installed, configure it; if not, add a render-rule override that walks tokens and sets `attrSet('id', slugify(...))` on `heading_open` tokens for h2/h3.
- [ ] Step 2: Implement the slugify per §11.7 verbatim. Threading: instantiate `taken: Set<string>` per `render()` call. Use the heading's index (token position among heading_open tokens) as `fallbackOrdinal`.
- [ ] Step 3: Add CSS to the markdown root: `:where(h2, h3) { scroll-margin-top: 32px; }`.
- [ ] Step 4: Failing test (in `SummaryTOCRail.spec.ts` later, or a small inline test now): render markdown `## Foo\n## Foo`; assert the rendered HTML contains `id="foo"` and `id="foo-1"`.
- [ ] Step 5: `router/index.ts` — add `scrollBehavior(to, from, savedPosition)`:
  ```ts
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, behavior: 'smooth', top: 32 }
    return { top: 0 }
  }
  ```
- [ ] Step 6: `git commit -m "feat(markdown): heading anchors + router scrollBehavior (FR-C07, FR-E06a)"`.

**Inline verification:**
- Render a summary with H2s; inspect DOM for `id` attrs; click a link `/books/1?tab=summary#chapter-3` → scrolls within ±32px.

---

### T17: SummaryTOCRail + BackToTopFab + SummaryMetadataStrip

**Goal:** Add the sticky TOC rail, Back-to-top FAB, and metadata strip to BookSummaryTab.
**Spec refs:** FR-C06, FR-C08, FR-C10, FR-C11, FR-C12, G4, D7, §11.2.
**Wireframe refs:** none.

**Files:**
- Create: `frontend/src/components/book/SummaryTOCRail.vue`
- Create: `frontend/src/components/book/BackToTopFab.vue`
- Create: `frontend/src/components/book/SummaryMetadataStrip.vue`
- Modify: `frontend/src/components/book/BookSummaryTab.vue` (template reorganized to 2-column grid on `lg+`)
- Modify: `frontend/src/components/app/AppShell.vue` (set `--playbar-height` CSS custom property when Playbar is mounted)
- Test: `frontend/src/components/book/__tests__/SummaryTOCRail.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Failing TOC tests: (a) render markdown with 3 H2s and 2 H3s; assert the TOC component emits a sticky `<nav>` with 5 anchor links matching the slugs; empty markdown → single "Top" entry. (b) Active-entry highlight: stub `IntersectionObserver` (Vitest `vi.stubGlobal('IntersectionObserver', ...)`); fire an `IntersectionObserverEntry` for the second heading; assert that anchor's element gets `class*="active"` and other anchors do not.
- [ ] Step 2: Build `SummaryTOCRail.vue`. Strategy: accept the rendered HTML string as a prop (or accept the markdown source and parse with the same `markdown-it` instance). Walk the parsed tree (DOMParser on the HTML string) to extract `(level, text, id)` for h2/h3. Render `<nav class="toc-rail sticky top-16">`. Use IntersectionObserver on heading IDs to highlight the active entry.
- [ ] Step 3: Build `BackToTopFab.vue`. Visible when `window.scrollY > window.innerHeight`. Style: `position: fixed; right: 1.5rem; bottom: calc(var(--playbar-height, 0px) + 1.5rem);` with `.chip--accent` class for color. Click handler: `window.scrollTo({ top: 0, behavior: 'smooth' })`.
- [ ] Step 4: AppShell (or wherever Playbar is mounted at app root) — set `--playbar-height: 84px` on `:root` via inline style binding `:style="{ '--playbar-height': playbarVisible ? '84px' : '0px' }"`. Verify by opening DevTools after Playbar mounts.
- [ ] Step 5: Build `SummaryMetadataStrip.vue`. Props: `preset`, `generatedAt`, `evalPassed`, `evalTotal`. Render `Preset: {preset} · Generated: {relativeTime} · Eval: {pass}/{total} ({pct}%)`.
- [ ] Step 6: Reorganize `BookSummaryTab.vue` template into a 2-column grid (`grid lg:grid-cols-[1fr,16rem] gap-6`). Markdown column wraps the existing `<MarkdownRenderer>`; TOC column wraps the new rail. Below `lg`, render TOC inside a `<details>` "Outline" expander above the markdown. Mount `<SummaryMetadataStrip>` above the markdown body. Mount `<BackToTopFab>` inside the markdown column.
- [ ] Step 7: Tests pass.
- [ ] Step 8: `git commit -m "feat(summary): TOC rail + back-to-top FAB + metadata strip (FR-C06..C12)"`.

**Inline verification:**
- Manual: visit a book with a long Book Summary; TOC visible on `lg+`; click → scrolls. Scroll past first viewport → FAB appears.

---

### T18: SectionListTable rewrite — 4 columns, grouped, persisted expand

**Goal:** Replace SectionListTable's column set and grouping per spec.
**Spec refs:** FR-C13, FR-C14, FR-C15, FR-C16, G5, G7, D5, D18.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/book/SectionListTable.vue`
- Modify: `frontend/src/components/book/__tests__/SectionListTable.spec.ts` (extend existing if present)

**Steps:**

- [ ] Step 1: Failing test: mount with mixed section types (1 copyright, 3 chapters, 1 glossary); assert column headers in order `['#', 'Title', 'Read time', 'Summary']`; assert 3 group separators (`'Front matter'`, `'Chapters'`, `'Back matter'`); chapters group expanded by default; front + back collapsed.
- [ ] Step 2: Define a small helper in the component:
  ```ts
  function groupOf(sectionType: string): 'front' | 'chapters' | 'back' {
    if (FRONT_MATTER_TYPES.has(sectionType)) return 'front'
    if (SUMMARIZABLE_TYPES.has(sectionType)) return 'chapters'
    return 'back'
  }
  ```
- [ ] Step 3: Drop the `compression` column logic. Add a `formatReadTime(s.content_char_count ?? 0)` rendering for each row. Summary column shows `'✓'` if `s.has_summary` else `'✕'`.
- [ ] Step 4: Render 3 group separators with collapsible state. Each separator is a `<thead>`-style row with a chevron. Click toggles expand. Persistence via `localStorage.getItem('bc.sections.expand.' + bookId)` on mount; write on toggle, wrapped in try/catch.
- [ ] Step 5: Tests pass.
- [ ] Step 6: `git commit -m "feat(sections): 4-column grouped section list (FR-C13..C16)"`.

**Inline verification:** Manual visit `/books/1?tab=sections`; verify columns + grouping + expand state survives reload.

---

### T18a: `useBookAudioMap(bookId)` composable

**Goal:** Shared in-memory cache of the per-book audio-availability map so SectionListTable (T19) and TOCDropdown (T21) reuse one fetch.
**Spec refs:** Plan-level decision P14; supports FR-C20, FR-D04.

**Files:**
- Create: `frontend/src/composables/useBookAudioMap.ts`
- Modify: `frontend/src/api/audio.ts` (add `audioApi.sectionsByBook(bookId)` if not added in T19's planning)
- Test: `frontend/src/composables/__tests__/useBookAudioMap.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Failing test: call the composable twice for the same `bookId`; assert `audioApi.sectionsByBook` is called only once (mock the API). Call for a different `bookId`; assert two total calls. On API 404 / error, `map.value === {}` and a `failed: true` flag exposed.
- [ ] Step 2: Implement (~30 LOC):
  ```ts
  // frontend/src/composables/useBookAudioMap.ts
  import { ref } from 'vue'
  import { audioApi } from '@/api/audio'

  type AudioMap = Record<number, { has_mp3: boolean; engine: string | null }>
  const cache = new Map<number, { map: AudioMap; failed: boolean }>()
  const inflight = new Map<number, Promise<void>>()

  export function useBookAudioMap(bookId: number) {
    const map = ref<AudioMap>(cache.get(bookId)?.map ?? {})
    const failed = ref(cache.get(bookId)?.failed ?? false)
    const ready = ref(cache.has(bookId))

    if (!cache.has(bookId)) {
      let p = inflight.get(bookId)
      if (!p) {
        p = audioApi.sectionsByBook(bookId).then(
          (res) => {
            const m: AudioMap = {}
            for (const e of res.sections) m[e.section_id] = { has_mp3: e.has_mp3, engine: e.engine }
            cache.set(bookId, { map: m, failed: false })
          },
          () => { cache.set(bookId, { map: {}, failed: true }) },
        ).finally(() => {
          map.value = cache.get(bookId)!.map
          failed.value = cache.get(bookId)!.failed
          ready.value = true
          inflight.delete(bookId)
        })
        inflight.set(bookId, p)
      } else {
        p.finally(() => {
          map.value = cache.get(bookId)?.map ?? {}
          failed.value = cache.get(bookId)?.failed ?? false
          ready.value = true
        })
      }
    }
    return { map, failed, ready }
  }
  ```
- [ ] Step 3: `audioApi.sectionsByBook(bookId)` lives in `frontend/src/api/audio.ts` calling `GET /api/v1/audio/sections/by-book/{bookId}`.
- [ ] Step 4: Tests pass.
- [ ] Step 5: `git commit -m "feat(audio): useBookAudioMap composable (P14)"`.

**Inline verification:**
- Tests assert single fetch per bookId.

---

### T19: Section row UX — div-role-button, hover icons, batch audio lookup

**Goal:** Each section row becomes a `<div role="button">` wrapper with nested action buttons revealed on hover; batch audio lookup gates Listen.
**Spec refs:** FR-C17, FR-C17a, FR-C18, FR-C19, FR-C20, D6, §11.6.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/book/SectionListTable.vue`
- Modify (or create) `frontend/src/api/audio.ts` to add `audioApi.sectionsByBook(bookId)`.

**Steps:**

- [ ] Step 1: Failing test: render a row; click the row → router push to `/books/:id/sections/:id?tab=summary`. Click the inner Read button → push to `/books/:id/sections/:id` (no tab). Click the inner Listen → does NOT navigate. Middle-click opens a new tab. Cmd-click opens a new tab. Listen disabled when no MP3 + no summary.
- [ ] Step 2: Drop the `<table>`/`<tr>` structure entirely (per spec §11.6). Restructure the section list as a stack of `<div role="button" tabindex="0">` rows in a CSS Grid (`grid-template-columns: 3rem 1fr 5rem 4rem 1.5rem` for `# | title | read time | summary | chevron`). The table headers become a single non-interactive grid row above. Each row binds `@click`, `@keydown.enter`, `@keydown.space.prevent`, `@click.middle`, plus `@click` checks `event.metaKey || event.ctrlKey` to open in a new tab via `window.open`. Add `aria-label="Open summary of {section.title}"`. The group separators remain (front/chapters/back) as `<div>` rows with their own click handlers for collapse.
- [ ] Step 3: Inner action buttons (visible on row hover via Tailwind `group` + `group-hover:opacity-100`):
  - ▶ Listen → calls existing TtsPlayButton flow (re-use `<TtsPlayButton>` component or its underlying handler).
  - 📖 Read → `router.push({ name: 'section-detail', params: { ... } })` — NO `?tab=summary`.
  - ⋯ More → opens an `OverflowMenu` instance (per P7, reuse if compatible; else inline minimal menu).
  Each `<button>` calls `event.stopPropagation()`. Add `@click.middle.stop` and `@auxclick.stop` per FR-C17a.
- [ ] Step 4: Batch audio lookup via the shared composable from T18a: `const { map: audioMap, failed } = useBookAudioMap(props.bookId)`. Wire `Listen` disabled state: `disabled = !audioMap[s.id]?.has_mp3 && !s.has_summary`. When `failed === true`, render Listen rows enabled (degraded fallback per FR-C20).
- [ ] Step 5: Add a trailing `›` chevron always visible at row right.
- [ ] Step 6: Tests pass.
- [ ] Step 7: `git commit -m "feat(sections): row-as-button + hover actions + batch audio (FR-C17..C20)"`.

**Inline verification:**
- Manual: hover a section row → action icons appear; click row → opens summary; click ▶ → starts audio without navigating; cmd-click row → opens new tab.

---

## Phase 4: SectionDetail + Audio + Library + Resume + verify

Phase rationale: 11 tasks. The remaining clusters (D, E, F) plus the home-page resume coordination glue. After this phase the entire spec is implemented and the verification gate is wired. Tasks are mostly independent so order is opportunistic.

---

### T20: ReaderHeader 3-cluster toolbar

**Goal:** Reorganize ReaderHeader controls into Nav | Mode | Actions clusters with vertical dividers.
**Spec refs:** FR-D01, FR-D02, FR-D05, D8.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/reader/ReaderHeader.vue`

**Steps:**

- [ ] Step 1: Update the `.reader-controls` block. Wrap into 3 inner divs with vertical 1px divider classes (`border-l border-slate-200 dark:border-slate-700 pl-2 ml-2`). Cluster A: prev/next nav buttons. Cluster B: `<ContentToggle>`. Cluster C: a `<slot name="actions">` plus a Listen button + Reader settings cog (existing components).
- [ ] Step 2: Set `min-width: 40px; min-height: 40px;` on `.nav-btn`. Add `aria-label="Previous section: {prevSection?.title ?? ''}"` / `"Next section: ..."`.
- [ ] Step 3: Add Listen button with `aria-label="Listen to this section"` `title="Play audio"` if not already in the slot.
- [ ] Step 4: Manual verification (Playwright MCP): tab order is left-to-right within each cluster; nav buttons are 40×40.
- [ ] Step 5: `git commit -m "feat(reader): 3-cluster toolbar (FR-D01, FR-D02, FR-D05)"`.

**Inline verification:** Manual hit-test; existing reader tests pass.

---

### T21: Drop drawer; enrich TOCDropdown

**Goal:** Remove the ☰ drawer button (if present); enrich TOCDropdown rows with status chips.
**Spec refs:** FR-D03, FR-D04, D8.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/reader/ReaderHeader.vue` (drop drawer trigger if present)
- Modify: `frontend/src/components/reader/TOCDropdown.vue`

**Steps:**

- [ ] Step 1: Read `ReaderHeader.vue` for any `<button>` that toggles a drawer (the spec said it's there; current code in T11's read shows breadcrumb + ContentToggle + nav + slot only — drawer may already be removed. If absent, this step is a no-op).
- [ ] Step 2: In `TOCDropdown.vue`, render per-row chips: read mode (📖 Original / 📋 Summary based on `section.has_summary`), summary status (✓/✕), audio status (🎧 if `audioMap[s.id]?.has_mp3` for this section, else nothing). Use the `.chip chip--*` tokens. Audio status comes from `useBookAudioMap(bookId)` (T18a) — a second call within the same component tree is a cache hit; no double fetch.
- [ ] Step 3: Existing tests pass.
- [ ] Step 4: `git commit -m "feat(reader): TOCDropdown status chips + drawer drop (FR-D03, FR-D04)"`.

**Inline verification:** Manual: open the breadcrumb dropdown on a section page; rows show chips.

---

### T22: Playbar timestamp gate + Limited-controls tooltip

**Goal:** Hide the `0:00 / 0:00` element on Web Speech; wrap Limited-controls in a tooltip with link to `/settings#audio`.
**Spec refs:** FR-E01, FR-E03, G8, D10, D11.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/audio/Playbar.vue`
- Test: `frontend/src/components/audio/__tests__/Playbar.spec.ts` (extend)

**Steps:**

- [ ] Step 1: Failing test: stub `useTtsPlayerStore` with `engine === 'web-speech'`; mount Playbar; assert `wrapper.find('[data-testid="timestamp"]').exists() === false`. Then with `engine === 'kokoro'`; assert it exists.
- [ ] Step 2: Add `data-testid="timestamp"` to the existing timestamp `<span>` (line 128–130). Add `v-if="store.engine === 'kokoro'"`.
- [ ] Step 3: Wrap the Limited-controls span in a tooltip-on-hover/focus showing `Web Speech can't seek/scrub. Install Kokoro for full controls →` linking to `/settings#audio`. Reuse the `TtsPlayButton`'s tooltip pattern (search `frontend/src/components/audio/TtsPlayButton.vue` for the tooltip implementation).
- [ ] Step 4: Tests pass.
- [ ] Step 5: `git commit -m "feat(playbar): engine-gated timestamp + tooltip badge (FR-E01, FR-E03)"`.

**Inline verification:** Manual on a Web Speech session: timestamp absent. Hover Limited-controls: tooltip + link.

---

### T23: SentenceProgressBar

**Goal:** Segmented progress strip above the Playbar, on both engines.
**Spec refs:** FR-E02, D15.
**Wireframe refs:** none.

**Files:**
- Create: `frontend/src/components/audio/SentenceProgressBar.vue`
- Modify: `frontend/src/components/audio/Playbar.vue` (mount the new component just above the controls row)
- Test: `frontend/src/components/audio/__tests__/Playbar.spec.ts` (extend)

**Steps:**

- [ ] Step 1: Failing test: mount Playbar with `totalSentences=5, sentenceIndex=2`; assert 5 segments rendered; segments 0-1 have `bg-indigo-500` class; segment 2 has `border-indigo-500 bg-transparent`; segments 3-4 have `bg-slate-200`.
- [ ] Step 2: Build the component (~30 lines). `<div class="flex gap-px h-1 mb-1">` containing `v-for="i in totalSentences"` segments. Class binding: `i < currentIndex ? 'bg-indigo-500 dark:bg-indigo-400' : i === currentIndex ? 'border border-indigo-500 bg-transparent' : 'bg-slate-200 dark:bg-slate-700'` plus `flex-1 min-w-[2px]`.
- [ ] Step 3: Mount inside Playbar template above the controls row.
- [ ] Step 4: Tests pass.
- [ ] Step 5: `git commit -m "feat(audio): SentenceProgressBar above Playbar (FR-E02)"`.

**Inline verification:** Manual: start audio; bar advances by sentence on both engines.

---

### T24: AudioTab empty state + DifferencePopover

**Goal:** Replace the "no-audio" empty state with engine chip + estimate + scope + popover.
**Spec refs:** FR-E04, FR-E05, FR-E06, D9, D19.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/audio/AudioTab.vue`
- Create: `frontend/src/components/audio/DifferencePopover.vue`
- Modify: `frontend/src/views/SettingsView.vue` (add `id="audio"` to the relevant section)

**Steps:**

- [ ] Step 1: Run `npm ls @floating-ui/vue` — note availability.
- [ ] Step 2: Build `DifferencePopover.vue`. Props: `open: boolean`, `triggerEl: HTMLElement`. Emit `close`. Content per FR-E04 wireframe: 2 paragraphs comparing engines + a CTA `<router-link to="/settings#audio">Open audio settings →</router-link>`. Implement focus trap (use `useFocusTrap` from `@vueuse/integrations/useFocusTrap` if installed; else minimal manual trap with `tabindex="-1"` first-focus + Tab/Shift+Tab cycling listener). Close on outside-click + Esc; on close, return focus to `triggerEl`.
- [ ] Step 3: Modify the `<div v-else-if="state === 'no-audio'">` block (lines 95-105) of `AudioTab.vue` to render: `<EngineChip>` of the default engine, paragraph "Generate audio for this book.", paragraph with engine label + estimate (`≈ X min on Kokoro` derived from `total_units * ~30s` or instant on Web Speech) + scope `{N chapter summaries}`, primary `Generate` button (existing `onGenerate` handler), link button "What's the difference?" toggling `showDiff`.
- [ ] Step 4: `SettingsView.vue` — find the audio engine section and add `id="audio"` on its container.
- [ ] Step 5: Tests: a small Vitest mounting AudioTab in `state==='no-audio'`; assert the new elements present. A Playwright e2e is added in T29 (audio-empty-state spec).
- [ ] Step 6: `git commit -m "feat(audio): empty-state + DifferencePopover (FR-E04..E06)"`.

**Inline verification:** Manual: visit `/books/1?tab=audio` for a book with no audio; new empty state visible; popover opens/closes; CTA scrolls to `/settings#audio`.

---

### T25: ResumeAffordance mounting on 3 reading-context routes

**Goal:** Mount `<ResumeAffordance>` on `/`, `/books/:id`, `/books/:id/sections/:id`. Gate per-route via the appropriate audio_position lookup.
**Spec refs:** FR-E07, FR-E07a, FR-E07b, FR-E08, G9, D12, §11.5.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/views/BookOverviewView.vue` (mount with per-book gate)
- Modify: `frontend/src/views/BookDetailView.vue` (mount with per-section gate)
- Modify: `frontend/src/views/LibraryView.vue` (mount under `chosen === 'listening'` — handled by T28)
- Modify: `frontend/src/api/audio.ts` (add `positionsByBook(bookId)` calling new endpoint)

**Steps:**

- [ ] Step 1: Add `positionsByBook(bookId): Promise<{ content_type, content_id, sentence_index, updated_at } | null>`; the API returns 404 for "no position", treat as `null`.
- [ ] Step 2: In `BookOverviewView.vue`, on mount call `positionsByBook(bookId)`. Store as `audioPosition` ref. If non-null AND not equal to the active Playbar content (FR-E08 detection: `ttsPlayer.isActive && ttsPlayer.contentId === audioPosition.contentId && ttsPlayer.contentType === audioPosition.contentType`), render `<ResumeAffordance :content-type="..." :content-id="..." :total-sentences="..." audio-status="complete" />`. Position the dock unobtrusively (e.g., at the top of the `book-overview` main).
- [ ] Step 3: In `BookDetailView.vue` (`SectionDetail`), on section change call existing `GET /api/v1/audio_position?content_type=section_summary&content_id=:sectionId&browser_id=:browserId` (the route confirmed in P4). If 200, mount `<ResumeAffordance>` with same FR-E08 gate. If 404 or error, do not mount.
- [ ] Step 4: Verify `<ResumeAffordance>` props: `contentType`, `contentId`, `audioStatus`, `totalSentences`. Pass `audioStatus="complete"` in both contexts (presence of the position implies completion).
- [ ] Step 5: Tests: small mount tests assert presence under different `audioPosition` states.
- [ ] Step 6: `git commit -m "feat(resume): mount ResumeAffordance on book + section routes (FR-E07)"`.

**Inline verification:** Manual: pause audio mid-listen; navigate to `/books/:id`; dock appears.

---

### T26: KeyboardShortcutsOverlay + Playbar tooltip shortcuts

**Goal:** Add the `?`-toggled overlay and per-button title shortcuts.
**Spec refs:** FR-E09.
**Wireframe refs:** none.

**Files:**
- Create: `frontend/src/components/app/KeyboardShortcutsOverlay.vue`
- Modify: `frontend/src/components/app/AppShell.vue` (mount the overlay)
- Modify: `frontend/src/components/audio/Playbar.vue` (add `title` attrs to buttons)

**Steps:**

- [ ] Step 1: Build the overlay. Listens to `keydown` at the document level; if key is `?` and no input is focused, toggle visibility. Modal-style overlay listing: Space (play/pause), → (next sentence), ← (prev sentence), Esc (close).
- [ ] Step 2: Mount in AppShell.
- [ ] Step 3: Playbar buttons: add `title="Play (Space)"` / `title="Pause (Space)"`, `title="Next sentence (→)"`, `title="Previous sentence (←)"`.
- [ ] Step 4: `git commit -m "feat(audio): keyboard shortcuts overlay + tooltips (FR-E09)"`.

**Inline verification:** Press `?` in the app → overlay visible.

---

### T27: Library view-toggle Lucide + bulk-select gate

**Goal:** Replace `▦ ☰ ▤` with Lucide icons; add Select-mode toggle; hide bulk checkboxes outside Select mode.
**Spec refs:** FR-F01, FR-F02, FR-F03, FR-F04, D13, D14.
**Wireframe refs:** none.

**Files:**
- Modify: `frontend/src/components/library/FilterRow.vue`
- Modify: `frontend/src/stores/ui.ts` (add `bulkSelectMode`)
- Modify: `frontend/src/components/library/BookCard.vue` / `BookList.vue` / `BookTable.vue` (gate the checkbox `v-if="ui.bulkSelectMode"`)
- Modify: `frontend/src/stores/books.ts` (clear `selectedIds` when bulkSelectMode toggles off)

**Steps:**

- [ ] Step 1: Run `npm ls lucide-vue-next`. If installed, import `LayoutGrid`, `List`, `Rows3`. If absent, install: `npm i lucide-vue-next`.
- [ ] Step 2: Replace the 3 buttons in `FilterRow.vue:53-77` with Lucide icon components. Add `aria-label="{Grid|List|Table} view"` to each. Add visible labels at `md+` via Tailwind `hidden md:inline`.
- [ ] Step 3: Persist selection: on `setDisplayMode(mode)`, also call `localStorage.setItem('bc.library.view', mode)` wrapped in try/catch with a one-shot toast on quota error. On store init, hydrate via `localStorage.getItem('bc.library.view')` BEFORE `loadViews()`.
- [ ] Step 4: Add `bulkSelectMode: ref(false)` to `useUiStore`. Add a Select toolbar button to FilterRow's right side that toggles `ui.bulkSelectMode`. Clear `selectedIds` when toggling off.
- [ ] Step 5: In each of `BookCard.vue`, `BookList.vue`, `BookTable.vue`, find the checkbox column/element and wrap with `v-if="ui.bulkSelectMode"`. Drop the DOM, not just hide.
- [ ] Step 6: Tests: extend any existing Library tests; add one assertion that the checkbox is absent when `bulkSelectMode === false`.
- [ ] Step 7: `git commit -m "feat(library): Lucide view toggle + bulk-select gate (FR-F01..F04)"`.

**Inline verification:** Manual `/`: Lucide icons; click Select → checkboxes appear; deselect → empty bulk bar.

---

### T28: resumeBannerStore + LibraryView coordination

**Goal:** New Pinia store fetching `/reading-state/resume-banner`; LibraryView renders one of `<ContinueBanner>` (icon 📖), `<ResumeAffordance>` (icon 🎧), or neither.
**Spec refs:** FR-B06, FR-B07, FR-B07a, D16, §6.3.2.
**Wireframe refs:** none.

**Files:**
- Create: `frontend/src/stores/resumeBanner.ts`
- Modify: `frontend/src/views/LibraryView.vue`
- Modify: `frontend/src/components/reader/ContinueBanner.vue` (add a 📖 leading icon)
- Test: `frontend/src/stores/__tests__/resumeBanner.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Failing test: store starts with `chosen === null`. Hydrate with both null → null. Reading-only → `'reading'`. Audio-only → `'listening'`. Audio more recent → `'listening'`. Reading more recent → `'reading'`. Equal timestamps → `'reading'` (deterministic tie-break per FR-B06). API throws → `chosen === null` (no toast). Build the test before the store.
- [ ] Step 2: Build `resumeBanner.ts`. State: `lastViewedAt`, `lastAudioAt`, plus all the book/section/audio fields from §9.1. Actions: `load()` calls `fetch('/api/v1/reading-state/resume-banner')`; on success, sets fields; on failure, calls `console.warn('resume-banner-fetch-failed', err)` and leaves all fields null. `chosen` = computed: both null → null; one null → the other; ts equal → `'reading'`; otherwise newer wins.
- [ ] Step 3: In `LibraryView.vue`, on mount call `resumeBanner.load()`. Per P16, render nothing while `chosen === null` (loading and "no activity" share the same conditional). Replace the existing `<ContinueBanner />` line 64 with:
  ```vue
  <ContinueBanner v-if="resumeBanner.chosen === 'reading'" />
  <ResumeAffordance
    v-else-if="resumeBanner.chosen === 'listening'"
    :content-type="resumeBanner.lastAudioContentType"
    :content-id="resumeBanner.lastAudioContentId"
    :total-sentences="resumeBanner.lastAudioTotalSentences ?? 0"
    audio-status="complete"
  />
  ```
- [ ] Step 4: `ContinueBanner.vue` — add a 📖 leading icon span. `ResumeAffordance` already has a 🎧-style aesthetic; add the emoji per spec FR-B07.
- [ ] Step 5: Tests pass.
- [ ] Step 6: `git commit -m "feat(home): resume coordination via resumeBannerStore (FR-B06, FR-B07)"`.

**Inline verification:** Manual: pause audio mid-listen on a book; navigate to `/`; ResumeAffordance dock visible; ContinueBanner not.

---

### T29: Dark-mode contrast e2e + regression grep

**Goal:** Add the axe-core sweep Playwright spec; wire into Makefile; add the chip-regression grep as a CI/verify gate.
**Spec refs:** FR-A06, FR-A07, NFR-01, G3.
**Wireframe refs:** none.

**Files:**
- Create: `frontend/tests/e2e/dark-mode-contrast.spec.ts`
- Modify: `Makefile`

**Steps:**

- [ ] Step 1: Verify axe-core for Playwright is installed: `cd frontend && npm ls @axe-core/playwright`. If missing, `npm i -D @axe-core/playwright`.
- [ ] Step 2: Build the spec. For each route in `['/', '/books/1', '/books/1/sections/1', '/concepts', '/annotations']`, for each theme in `['light', 'dark']` (toggle theme by setting `localStorage.theme` or the `dark` class on `<html>`), navigate, then run a whole-page axe sweep: `new AxeBuilder({ page }).withTags(['wcag2aa']).analyze()`. Assert that violations filtered to `rule.id === 'color-contrast'` is an empty array. Whole-page scope (per Loop-2 disposition) catches non-chip text contrast issues; chip-only filtering is a debug-time helper only.
- [ ] Step 3: `Makefile` — add a target:
  ```
  test-e2e-contrast:
  	cd frontend && npx playwright test tests/e2e/dark-mode-contrast.spec.ts
  ```
- [ ] Step 4: Run `make test-e2e-contrast` against a running dev server. Expected: zero violations. If violations: triage per chip site; either fix the token or document an exception.
- [ ] Step 5: `git commit -m "test(a11y): dark-mode-contrast e2e gate (FR-A06, FR-A07)"`.

**Inline verification:** `make test-e2e-contrast` exits 0.

---

### T30: Final Verification

**Goal:** Verify the entire implementation works end-to-end.

- [ ] **Lint & format:**
  - `cd frontend && npm run lint && npm run type-check`
  - `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] **Backend tests:**
  ```
  cd backend && uv run python -m pytest \
    tests/unit/api/test_reading_state.py \
    tests/integration/test_reading_state_continue.py \
    tests/unit/api/test_audio_by_book.py -v
  ```
  Expected: all pass.
- [ ] **Backend full suite (regression):** `cd backend && uv run python -m pytest -m "not integration_llm"` — no regressions.
- [ ] **Frontend unit + component tests:**
  ```
  cd frontend && npm run test:unit -- \
    src/stores/__tests__/firstChapter.spec.ts \
    src/utils/__tests__/readTime.spec.ts \
    src/stores/__tests__/resumeBanner.spec.ts \
    src/components/book/__tests__/SectionListTable.spec.ts \
    src/components/book/__tests__/SummaryTOCRail.spec.ts \
    src/components/book/__tests__/OverviewDashboard.spec.ts \
    src/components/audio/__tests__/Playbar.spec.ts \
    src/components/__tests__/h1Count.spec.ts
  ```
  Expected: all pass.
- [ ] **Frontend full unit suite:** `npm run test:unit` — no regressions.
- [ ] **Frontend build:** `npm run build` — clean.
- [ ] **Database migrations:** N/A (no schema changes per spec §10).
- [ ] **Deploy/serve for interactive verification:**
  ```
  cd backend && uv run bookcompanion serve --port 8765 &
  curl -sf http://localhost:8765/api/v1/health
  cd frontend && npm run build && rm -rf ../backend/app/static && cp -R dist ../backend/app/static
  ```
- [ ] **API smoke tests (curl):**
  ```
  curl -sf http://localhost:8765/api/v1/reading-state/continue | python3 -m json.tool
  curl -sf http://localhost:8765/api/v1/reading-state/resume-banner | python3 -m json.tool
  curl -sf http://localhost:8765/api/v1/audio/sections/by-book/1 | python3 -m json.tool
  curl -sf -o /dev/null -w "%{http_code}\n" http://localhost:8765/api/v1/audio/positions/by-book/1
  ```
  Expected shapes match spec §9.1, §9.4.
- [ ] **E2E suite:**
  ```
  cd frontend && npm run test:e2e -- \
    tests/e2e/dark-mode-contrast.spec.ts \
    tests/e2e/read-cta-routes-to-chapter.spec.ts \
    tests/e2e/summary-toc-anchors.spec.ts \
    tests/e2e/h1-singleton.spec.ts \
    tests/e2e/sections-grouping.spec.ts \
    tests/e2e/audio-empty-state.spec.ts \
    tests/e2e/playbar-timestamp.spec.ts \
    tests/e2e/resume-coordination.spec.ts
  ```
- [ ] **Frontend smoke test (Playwright MCP):**
  1. (No auth.)
  2. Navigate to `http://localhost:8765/`.
  3. Verify `<ContinueBanner>` OR `<ResumeAffordance>` (depending on seeded state); confirm exactly one renders.
  4. Walk: `/` → click any book card → `/books/:id` (Overview tab → 4 tiles render → click "Read" tile → lands on a real chapter).
  5. Take a screenshot of `/books/:id` Overview tab.
  6. **Hard-reload every parameterized route the change touches:**
     - Open `/books/1` in a fresh tab; confirm the requested book renders, not the library list.
     - Open `/books/1/sections/3` in a fresh tab; confirm the requested section renders (NOT section 1 / the index).
     - Open `/books/1?tab=summary#chapter-3` in a fresh tab; confirm the heading is at viewport top ±32px.
     - Open `/settings#audio` in a fresh tab; confirm the audio settings section is scrolled into view.
  7. **Force at least one error path:**
     - Stop the backend; navigate to `/`; confirm `resumeBannerStore` errors silently (no toast, banner absent — per FR-B07a).
     - Restart backend; navigate to `/books/9999` (non-existent); confirm "Book not found" error displays cleanly with a recoverable nav option (already-existing behavior — verify).
- [ ] **UX polish checklist:**
  - `document.title` set per route (existing `router.afterEach` handles this).
  - No internal IDs/enum keys leaked into copy (verify chip labels read "Web Speech" / "Kokoro", not raw enum values).
  - Casing/date-format consistency (relative times in Continue tile, Book summary tile, Sections tile).
  - Meaningful image `alt` (cover image already has `alt="Cover for {title}"`).
  - No dead disabled affordances (Read button disabled state has tooltip; bulk-select button when no rows selected — verify).
  - Zero uncaught console errors during the full journey (open DevTools console, walk every route, confirm clean).
  - Navigation labels match destination titles (sidebar / breadcrumb).
- [ ] **Wireframe diff:** N/A (no wireframes folder for this feature; spec design references are textual).
- [ ] **Manual spot checks:**
  - Read CTA on a book whose `sections[0].section_type === 'copyright'` lands on a real chapter (regression for the dominant defect).
  - Toggle to dark mode; visit `/`, `/books/1`, `/books/1/sections/1`, `/concepts`, `/annotations`; chips legible everywhere.
  - Sections tab: front + back collapsed by default; toggle; reload; state preserved.
  - Audio tab on a book with no audio: empty state shows engine chip + estimate; click "What's the difference?" → popover; click outside → closes; focus returns to trigger.
  - Playbar on Web Speech: no `0:00 / 0:00` element; sentence-progress bar visible.
  - Playbar on Kokoro: timestamp + sentence-progress bar visible.
  - Library: Lucide icons; click Select → checkboxes appear; pick books; bulk toolbar slides up; click off Select → checkboxes disappear and selection clears.
- [ ] **Regression grep (chip token discipline):**
  ```
  cd frontend && grep -rn 'rounded-full' src/components src/views \
    | grep -E 'bg-(indigo|amber|slate|blue|green|red|yellow)-(100|200)' \
    && echo "FAIL: chip with hardcoded color found" || echo "PASS"
  ```
  Expected: PASS.

**Cleanup:**
- [ ] Stop the dev server: `kill $(lsof -ti:8765)`.
- [ ] Update `docs/changelog.md` (if invoked from /verify it will run /changelog separately; otherwise add an entry).

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1    | (a) T19/T21 each fetched the per-book audio map independently. (b) T15 OverviewDashboard's Continue tile had no honest signal for "Continue reading" vs "Start reading". (c) T11 promoted the section title to `<h1>` via prop drill, changing ReaderHeader's contract. (d) T28 left the loading-state branch ambiguous (could flash). | (a) Added T18a `useBookAudioMap` composable; T19 + T21 consume it; decision P14 logged. (b) Added T6a backend `GET /reading-state/by-book/{book_id}`; decision P13 logged; T15 wired to it. (c) ReaderHeader now reads from `useReaderStore()` directly; decision P15 logged. (d) Render-nothing-while-loading made explicit in T28 step 3; decision P16 logged. |
| 2    | (a) T19 hedged on `<tr role="button">` vs `<div role="button">` — spec §11.6 picked the `<div>`; hedge contradicted spec. (b) T29 axe sweep narrowed to chip selectors only; FR-A06 wants whole-page color-contrast clean. (c) T17 promised an active-entry highlight via IntersectionObserver but had no test asserting it. (d) T5/T6 hedged on `audio.py` vs new file. | (a) T19 step 2 rewritten to a CSS-grid `<div role="button">` row stack — table semantics dropped entirely. (b) T29 step 2 rewritten to whole-page `AxeBuilder` sweep, filter on `rule.id === 'color-contrast'`. (c) T17 step 1 split into two failing tests including IntersectionObserver-stubbed active-state assertion. (d) T5 step 0 added: inspect existing `audio.py` and pick router placement deterministically; commit message documents the choice. |
