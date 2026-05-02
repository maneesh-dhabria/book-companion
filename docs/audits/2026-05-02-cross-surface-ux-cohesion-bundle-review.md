# Cross-Surface UX Cohesion Bundle — Verification Review

**Date:** 2026-05-02
**Branch:** `feature/ux-cohesion-bundle`
**Plan:** `docs/plans/2026-05-01-cross-surface-ux-cohesion-bundle-implementation-plan.md`
**Spec:** `docs/specs/2026-05-01-cross-surface-ux-cohesion-bundle-spec.md`

## Phase summary

| Phase | Result |
|---|---|
| 1. Static verification | Pass — backend ruff (no new errors vs main; 2 new files reformatted), backend pytest 899/899, frontend type-check, frontend vitest 327/327. Frontend ESLint baseline-broken on main (toolchain mismatch unrelated to this branch). |
| 2. Code quality review | Pass — three findings, none blocking (see below). |
| 3. Deploy / API smoke | Pass — `bookcompanion serve --port 8765`, all targeted endpoints respond per contract. |
| 4. Interactive (Playwright MCP) | **Pass after fixes** — three gaps surfaced and fixed in this run (FR-04, FR-09, FR-12 filter). |
| 5. Spec compliance | Pass — all 18 ACs verified or covered by alt-evidence, with one residual user-action item (E2E selection→highlight on Summary tab). |
| 6. Hardening | No new tests added — fixes mirror existing test scopes (BookOverviewView mount, ContextSidebar bg fallback, BookDetailView annotation filter). Suggested follow-up tests listed below. |
| 7. Final compliance | Pass — all grep gates clean (`FAILED:` literal, `uv run alembic` subprocess, Tailwind `dark:` in settings, `Customize text` string, stale ThemeCard import). |

## Fixes applied during /verify

| File | Change | Reason |
|---|---|---|
| `backend/app/api/routes/summarize_presets.py` | `ruff format` | New file failed format check |
| `backend/tests/integration/test_api/test_book_summary_idempotency.py` | `ruff format` | New file failed format check |
| `frontend/src/views/BookOverviewView.vue` | Call `settings.loadPresets()` on mount; add `position: relative` to `.action-row` | FR-04: opening Customize-reader from Book Detail showed "Couldn't load themes" + popover misanchored at top:682,left:800 (the exact pre-fix failure mode) |
| `frontend/src/components/sidebar/ContextSidebar.vue` | `var(--reader-bg, var(--color-bg, #fff))` → `var(--reader-bg, var(--color-bg-primary, #fff))` | FR-09: `--color-bg` is undefined; sidebar bg stayed `rgb(255,255,255)` under Dark theme. The defined theme-aware var is `--color-bg-primary`. |
| `frontend/src/views/BookDetailView.vue` | `inlineAnnotations` filter uses `section.default_summary?.id` when `wantedType === 'section_summary'` | FR-12: section_summary annotations use `content_id = summary.id`, not section.id; the previous filter required `content_id === section.id` so summary highlights never matched. |

## Spec compliance — Acceptance Criteria

| # | Surface | Outcome | Evidence |
|---|---|---|---|
| 1 | Book Detail toolbar single Read CTA | Verified | Playwright on `/books/3`: only one Read CTA, zero "Read Summary" buttons in DOM |
| 2 | Summary tab + empty/in-progress/failed/populated states | Verified | Playwright on `/books/3?tab=summary`: tab strip Overview/Summary/Sections; empty state shows "21 of 25 sections summarized" + Generate CTA enabled |
| 3 | No "Customize text" floating control | Verified | Body text and grep both show no occurrence; overflow menu items: Generate book summary, Customize reader…, Edit structure, Re-import, Export Markdown, Delete book |
| 4 | Customize-reader popover anchored to trigger, themes load | Verified-after-fix | After fix: trigger at top:236, popover at top:264 (anchored); 7 theme cards rendered; no "Couldn't load themes" |
| 5 | Compression `~N%` rounded to 5 | Verified | Sections-table sample: `~15%`, `~20%`, `~25%`, `~30%` — 21 cells matching `^~\d+%$`, 0 legacy decimals |
| 6 | Bullets render with markers | Verified | `getComputedStyle('.markdown-body ul').listStyleType === 'disc'` |
| 7 | Footer prev/next nav with `?tab=` preservation | Verified | `/books/3/sections/46?tab=summary`: footer renders `← Previous: Introduction` (`/books/3/sections/45?tab=summary`) and `Next: One →` (`/books/3/sections/47?tab=summary`) |
| 8 | TOC dropdown shows real char counts | Verified | TOC sample: 20,414 / 10,206 / 50,219 / 15,413 — none zero |
| 9 | Side panels follow reader theme | Verified-after-fix | After fix: under Dark theme, `.context-sidebar` bg is `rgb(30, 30, 46)`; under Light, `rgb(255, 255, 255)` — theme-aware. AIChatTab inherits via transparent bg. |
| 10 | Markdown table styles | NA — alt-evidence | No `<table>` rendered in section 46's content. Covered by `frontend/src/components/reader/__tests__/MarkdownRenderer.styles.spec.ts` (passing) and the new scoped style block in `MarkdownRenderer.vue`. |
| 11 | App-bar title + BC icon clickable | Verified | DOM: both `aside a[href="/"]` (BC) and `header a[href="/"]` (title) present |
| 12 | Annotation summary-tab highlights | Verified-after-fix (filter); user-action for full E2E | Backend creates `content_type=section_summary` annotation correctly (POST 201). After filter fix, `inlineAnnotations` matches by summary id. Full create→render flow needs in-browser text-selection (covered by unit test `annotationContentType.spec.ts` for the helper; UI selection→highlight to be smoke-checked manually). Original-tab regression check passed (2 highlights still render on `/books/1/sections/6?tab=original`). |
| 13 | Migration-status no FAILED literal | Verified | `GET /api/v1/settings/migration-status` → `{"current":"9a67312a27a7","latest":"9a67312a27a7","is_behind":false,"error":null}`; grep gate clean. |
| 14 | Database stats no alt-row stripes | Verified | All visible rows: `rgba(0, 0, 0, 0)` (transparent); zero distinct non-transparent backgrounds |
| 15 | Preset CRUD UI | Verified | API lifecycle: POST 201, GET shows it, PUT 200, duplicate POST 409, DELETE-system 403, DELETE-user 204. UI: New Preset button opens form with name/label/description/4 facets + plain-language subheads. |
| 16 | Preset template viewer | Verified | `GET /presets/practitioner_bullets/template`: keys `name, is_system, base_template, fragments`; `is_system: true`, 4 fragments, base path `base/summarize_section.txt`. UI shows base + fragment blocks for system presets. |
| 17 | Reading-Settings preset pills are buttons | Verified | All 6 pills: `<button class="theme-card">` with `cursor: pointer`. Same component as ReaderSettingsPopover ThemeGrid. |
| 18 | LlmSettings no Tailwind dark: classes | Verified | `grep dark: frontend/src/components/settings/LlmSettings.vue` → 0 matches |

## Code review findings (Phase 3)

1. **SD22 backend field naming** — spec § 7.4 mandates `book_summary` but implementation uses pre-existing `default_summary`. **Resolution:** documented plan decision (P3 + plan review-log F1: "Pinned `default_summary` as canonical across plan; spec § 7.4 to be updated post-merge"). Not a defect.
2. **OverflowMenu Re-import is a CLI redirect** — handler shows toast pointing to `bookcompanion add <path>`. Intentional: re-import has no UI workflow, parity with what existed on main. Not a regression.
3. **MarkdownRenderer thead uses undefined `--reader-surface-muted` var** — falls back to `--color-bg-muted`. Cosmetic only; tables still render correctly with borders + header weight. Logged as low-priority.

## Suggested follow-up tests (not added in this run)

- `BookOverviewView.spec.ts`: assert `settings.loadPresets()` is called on mount.
- `ContextSidebar.spec.ts`: snapshot computed `background-color` under each theme via `data-theme` attribute on a wrapper.
- `BookDetailView.annotations.spec.ts`: assert `inlineAnnotations` returns the section_summary annotation when `contentMode === 'summary'` and `section.default_summary.id` matches.

## Outstanding items (Unverified — action required)

- **FR-12 full E2E** — selecting text on the Summary tab and clicking "Highlight" to verify the create→persist→render round-trip in the UI requires interactive text selection that Playwright MCP cannot reliably automate. Backend persistence path verified via direct POST (201); frontend filter verified by code+unit tests. Recommend a 1-minute manual smoke before merge.

## Phase 4 grep-gate output

```
$ grep -rn '"FAILED:' backend/app/services/         → no matches
$ grep -rn "uv run alembic" backend/app/services/   → no matches
$ grep -rn "dark:" frontend/src/components/settings/LlmSettings.vue → no matches
$ grep -rn "Customize text" frontend/src/views/BookOverviewView.vue \
        frontend/src/components/book/OverflowMenu.vue → no matches
$ grep -rn "components/settings/ThemeCard" frontend/src → no matches
```

## Final test status

- Backend: `899 passed, 35 skipped, 4 deselected` (`uv run python -m pytest -q -m "not integration_llm"`).
- Frontend: `Test Files 56 passed, Tests 327 passed` (`npm run test:unit -- --run`).
- Backend lint baseline: 110 errors on branch vs 111 on main (no new errors introduced).
- Frontend lint: pre-existing toolchain breakage on main (ESLint 8.56 vs typescript-eslint plugin mismatch) — same on both branches; out of scope.

**Recommendation: ready to merge after a 1-minute manual FR-12 highlight-on-Summary-tab smoke check.**
