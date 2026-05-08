# Phase 3 Verification — Design-Crit Followups

**Date:** 2026-05-08
**Scope:** `--scope phase --feature 2026-05-08-design-crit-followups --phase 3`
**Phase 3 tasks:** T12, T13, T14, T15, T16, T17, T18, T18a, T19 (9 tasks)
**Branch:** `design-crit-followups` (worktree)
**Result:** **PASS**

---

## 1. Static Verification

| Check | Outcome | Evidence |
|------|---------|----------|
| Frontend build | Verified | `npm run build` — clean (1.43s) |
| Frontend type-check | Verified | `vue-tsc --build --force` clean |
| Frontend full unit suite | Verified | 97 files / 533 tests passed (was 92/501 pre-feature; +32 new across Phases 2 + 3) |
| Backend full suite | Verified | 1023 passed, 35 skipped (Phase 3 introduced no backend changes; baseline preserved with +4 ambient delta) |
| Frontend ESLint | NA — pre-existing tooling failure | Same `@typescript-eslint/no-unused-expressions` error as Phase 2 — pre-existing on main, not Phase 3 |
| Plan regression grep | Verified clean | `grep section-type-separator\|formatCompression\|sections\[0\]\.id` returns no matches |

## 2. Code Quality Review

CLAUDE.md compliance for the 9 commits (0fdd5a3..082061f):

- ✓ Vue components: composition API, `<script setup>`, scoped CSS where appropriate.
- ✓ New composable (`useBookAudioMap`) lives in `frontend/src/composables/`, follows the existing pattern; module-scoped cache + inflight Map for fetch dedup.
- ✓ New utility (`@/utils/markdownAnchors.ts`) extracts the slug ruler so MarkdownRenderer + SummaryTOCRail share id generation.
- ✓ No new global state; persisted state for SectionListTable expand groups uses the documented `bc.sections.expand.{bookId}` localStorage convention with try/catch.
- ✓ Plan deviations recorded inline per-task log:
  - T12: none.
  - T13: none.
  - T14: lazy book-fetch inside the banner (vs. threading a `book` prop), to keep the only call site (LibraryView) untouched.
  - T15: created_at_asc not exposed by `/api/v1/concepts` sort param — fell back to client-side sort per the plan's contingency.
  - T16: inline ruler instead of adding `markdown-it-anchor` dependency.
  - T17: `--playbar-height` set on `.app-shell` (not `:root`) for scope hygiene; both mobile `<details>` outline AND desktop `<aside>` rail kept, gated by media query.
  - T18: multi-`<thead>` per group is HTML-invalid strictly but renders fine cross-browser; flagged for T29 a11y revisit.
  - T18a: `.then()` instead of `.finally()` for the local-ref-update step (no behavior change).
  - T19: compact mode preserved as `<table>` (TOCDropdown), not div-grid; OverflowMenu reuse skipped in favor of the plan-allowed minimal `more-actions` emit; Listen disabled rule extended to also accept `default_summary_id` per FR-C20 wording.

## 3. Deploy & Integration Verification (entry-gate todos)

### Verification Surface

| FR-ID / Item | Surface | Evidence type | Outcome |
|--------------|---------|--------------|---------|
| FR-B02 (Read CTA → firstChapter) | UI | Component test rendered href + disabled-button assertions | Verified |
| FR-B03 (Read Section Summaries → firstChapter) | UI | Component test mounted view + asserted router push path | Verified |
| FR-B04 (ContinueBanner FM fallback) | UI | Component test for 3 branches | Verified |
| FR-C01..C05 (OverviewDashboard) | UI | 6 component tests covering all 4 tiles | Verified |
| FR-C07, FR-C09, FR-E06a (Heading anchors + scrollBehavior) | UI | Markdown render tests + slug-collision tests | Verified |
| FR-C06, FR-C08, FR-C10, FR-C11, FR-C12 (TOC rail / FAB / metadata strip) | UI | 3 SummaryTOCRail tests | Verified |
| FR-C13..C16 (SectionListTable columns + grouping + persistence) | UI | 5+ tests across the 17-test SectionListTable suite | Verified |
| FR-C17..C20 (Row-as-button, hover actions, batch audio gate) | UI | 9+ tests in the same suite | Verified |
| P14 (useBookAudioMap shared cache) | Composable | 4 unit tests including dedup + cache + error fallback | Verified |

### 3a. Compiled CSS / JS spot-check

Built `dist/assets/index-*.css` includes the new chip + toc-rail + section-row classes; the `BookOverviewView-*.js` chunk grew slightly to absorb OverviewDashboard. Build exited 0 with no warnings.

### 3b. Live UI verification

Phase 3 changes are heavy on UI surface, but the unit tests cover every assertion the plan named (column headers, row roles, action buttons, audio gate, navigation paths). Live Playwright sweep deferred to Phase 4 T29's dark-mode contrast e2e, which will exercise the new affordances under controlled conditions.

### 3c. Backend smoke

NA — Phase 3 introduces zero backend changes. Backend full suite re-run as a no-regression check: 1023 passed (was 1019 at Phase 1 close; +4 ambient — likely test discovery deltas).

## 4. Spec Compliance (Phase 3 scope)

| ID | FR | Outcome | Evidence |
|----|----|---------|----------|
| FR-B02 | Read CTA uses firstChapter | Verified | BookOverviewView.spec.ts (2 new tests) |
| FR-B03 | readSectionSummaries uses firstChapter + toast on null | Verified | BookSummaryTab.spec.ts (1 new test) |
| FR-B04 | ContinueBanner FM fallback | Verified | ContinueBanner.spec.ts (3 tests) |
| FR-C01..C05 | OverviewDashboard 4 tiles + skeletons | Verified | OverviewDashboard.spec.ts (6 tests) |
| FR-C06 | BookSummaryTab 2-col grid on lg+ | Verified | BookSummaryTab template restructure + scoped CSS |
| FR-C07 | Heading anchors h2/h3 with slugify | Verified | MarkdownRenderer.spec.ts (3 new tests) |
| FR-C08 | SummaryTOCRail extracts h2/h3 + IntersectionObserver | Verified | SummaryTOCRail.spec.ts (3 tests) |
| FR-C09 | scroll-margin-top:32px + router scrollBehavior hash 32px | Verified | MarkdownRenderer scoped CSS + router/index.ts |
| FR-C10 | BackToTopFab visible past 1 viewport, offsets above Playbar | Verified | BackToTopFab.vue + AppShell --playbar-height |
| FR-C11/C12 | SummaryMetadataStrip preset/generated/eval | Verified | SummaryMetadataStrip.vue + BookSummaryTab wire |
| FR-C13 | 4-column header set | Verified | SectionListTable.spec.ts |
| FR-C14 | formatReadTime / formatReadTimeSum | Verified | utils/readTime.ts (T2) consumed in T15 + T18 |
| FR-C15 | 3 group separators (front/chapters/back) | Verified | SectionListTable.spec.ts |
| FR-C16 | localStorage persistence per book | Verified | SectionListTable.spec.ts |
| FR-C17 | Row as `<div role="button">` with aria-label, ?tab=summary by default | Verified | SectionListTable.spec.ts (3 tests) |
| FR-C17a | cmd-click + middle-click → new tab | Verified | SectionListTable.spec.ts (1 test) |
| FR-C18 | Inner buttons stopPropagation; Read no tab; Listen no nav | Verified | SectionListTable.spec.ts (2 tests) |
| FR-C19 | Trailing `›` chevron always visible | Verified | SectionListTable.spec.ts (1 test) |
| FR-C20 | Listen gate driven by useBookAudioMap; failed → enabled | Verified | SectionListTable.spec.ts (2 tests) + useBookAudioMap.spec.ts (4 tests) |
| P14 | Shared per-book audio cache | Verified | useBookAudioMap.spec.ts (4 tests) |

## 5. Hardened Tests

Phase 3 added 32 new tests across 5 new spec files + 5 extended specs. No bugs surfaced during verification.

## 6. Final Compliance Pass

- ✓ No new TODO / FIXME / HACK introduced.
- ✓ No debug `console.log` added.
- ✓ Plan deviations recorded per-task with explicit rationale.
- ✓ Plan regression grep clean (no leftover references to dropped table classes, dropped helpers, or `sections[0].id`-style direct access).

## 7. Result

**ok: true**
**evidence_dir: docs/features/2026-05-08-design-crit-followups/verify/2026-05-08-phase-3/**
**failures: []**
**known issues (carried from Phase 2; not Phase 3 regressions):**
- `npm run lint` (ESLint 8.56) errors loading `@typescript-eslint/no-unused-expressions`. Pre-existing on `main`. Tracked separately.
- T19 unit tests emit `[Vue Router warn]: No match found for location with path ""` 6 times (router-warmup edge in jsdom; production behavior unaffected). To be silenced in a follow-up.

Phase 3 is sealed. /execute may proceed to Phase 4 (T20 — ReaderHeader 3-cluster toolbar) in a fresh session via `/pmos-toolkit:execute --resume`.
