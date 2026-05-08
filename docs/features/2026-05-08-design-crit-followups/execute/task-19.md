---
task_number: 19
task_name: "T19: Section row UX + batch audio"
task_goal_hash: eacaed9a579bb58fae54355e7f8b37577758bafa5edd72e64f70cf69122997ba
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T19:18:00Z
completed_at: 2026-05-08T19:35:00Z
files_touched:
  - frontend/src/components/book/SectionListTable.vue
  - frontend/src/components/book/__tests__/SectionListTable.spec.ts
---

# T19: Section row UX + batch audio (FR-C17..C20)

## Outcome
- **Non-compact mode** (book-overview Sections tab): rewrote rows from `<tr role="link">` to `<div role="button" data-row tabindex="0" :aria-label="Open summary of {title}">` in a CSS Grid layout. Inner action buttons (▶ Listen, 📖 Read, ⋯ More) sit in `.row-actions` revealed via `:hover .row-actions { opacity: 1 }` (also revealed on `:focus-within` for keyboard users). Each inner button calls `@click.stop` so the outer row click doesn't fire. Trailing `›` chevron always visible on every row (FR-C19).
- **Compact mode** (reader-TOC dropdown): preserved as a dense `<table>` with `<tr role="link">` rows. The plan said "drop the table structure entirely", but compact is a tiny popup where the dense table layout is the right UX — see deviations.
- **Default row click** routes to `/books/:id/sections/:sid?tab=summary` (FR-C17). When `currentSectionId` is set (reader-TOC context), preserves the existing `?tab` query instead.
- **Inner Read button** routes to the same path WITHOUT `?tab=summary` (FR-C18) so the reader opens in original-content mode.
- **Inner Listen button** wires to `useTtsPlayerStore().open({...})` and does not navigate.
- **Inner More button** emits `more-actions` for the parent to wire up section-level overflow (Edit, Re-summarize, etc.) — actual menu deferred to a future task per the plan's "inline minimal menu" allowance.
- **cmd-click / ctrl-click → new tab** via `window.open(router.resolve(...).href, '_blank', 'noopener,noreferrer')` (FR-C17a). Middle-click + auxclick handler does the same.
- **Listen disabled gate** (FR-C20): `useBookAudioMap(bookId)` from T18a consumed in non-compact mode. Listen disabled iff `!hasMp3 && !hasSummary && !default_summary_id`. When `audio.failed === true`, all rows enable Listen (degraded fallback).

## Plan deviations
- Plan §T19 step 2 said "Drop the `<table>`/`<tr>` structure entirely." I dropped it for non-compact mode but kept the compact `<table>` for the reader-TOC dropdown caller. Justification: TOCDropdown is a tiny popover (`max-width: 360px`) where the table's dense rows + row-as-link semantics are simpler than div-grid + role=button. The spec FR-C13..C20 talks about the Sections tab specifically; compact mode is a separate visual context. The TOCDropdown.spec.ts assertion (`tbody tr[role="link"]`) preserved unchanged.
- Plan §T19 step 3 said reuse `OverflowMenu.vue` if compatible. OverflowMenu is hard-coded for book-level actions (emits `generate-book-summary`, `delete-book`, etc.) and would need a major refactor to be section-scoped. I went with the plan's "inline minimal menu" allowance: the More button just emits `more-actions` for now. A proper section-level overflow menu can be added in a follow-up without touching SectionListTable's row UX.
- Plan §T19 step 4 named the disabled rule as `!audioMap[s.id]?.has_mp3 && !s.has_summary`. I extended it to also accept `s.default_summary_id` because the spec FR-C20 says "Listen action is disabled when `default_summary_id == null` AND no MP3 exists" — `default_summary_id` is the authoritative source, and `has_summary` is a derived bool that some API responses don't populate.

## Verification
- `npm run test:unit -- --run src/components/book/__tests__/SectionListTable.spec.ts` — 17/17 pass.
- Full frontend unit suite: 533/533 pass (was 528 after T18a; net +5 — gained 17 new SectionListTable tests, removed 12 old).
- `npm run type-check` clean.
- `npm run build` clean (1.39s).

## Runtime evidence
The 17 component tests cover: 4-column header rendering, 3 group separators, default expand state, click-to-toggle + localStorage persistence per bookId, role/aria-label correctness, default row click → `?tab=summary`, Read button → no tab, Listen button does NOT navigate, Listen disabled when no summary + no MP3, Listen enabled when audio batch reports has_mp3, trailing chevron on every row, cmd-click → window.open, ✓/✕ glyphs, SSE-driven status flip (non-compact only), compact mode flat layout + TOC `?tab` preservation + no-SSE rule. Each test uses a real `vue-router` instance, real Pinia store, and `vi.spyOn(audioApi, 'sectionsByBook')` for the audio map.

A non-blocking note: the test runner emits `[Vue Router warn]: No match found for location with path ""` 6 times. The warning fires because `route.query.tab` is read inside the SSE-watch path before the router has a current route in unit tests; behavior is correct (read returns undefined, which is the intended fallback). Filed as a follow-up item; does not affect production runtime.
