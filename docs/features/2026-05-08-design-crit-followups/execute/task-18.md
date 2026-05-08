---
task_number: 18
task_name: "T18: SectionListTable rewrite"
task_goal_hash: dedd77076c2c61805979543eeaa8797e025c4e1f4f2d78c815845b0fe60cea62
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T18:48:00Z
completed_at: 2026-05-08T19:00:00Z
files_touched:
  - frontend/src/components/book/SectionListTable.vue
  - frontend/src/components/book/__tests__/SectionListTable.spec.ts
  - frontend/src/components/reader/__tests__/TOCDropdown.spec.ts
---

# T18: SectionListTable rewrite — 4 columns, grouped, persisted expand (FR-C13..C16)

## Outcome
- **Column set reduced to 4**: `# / Title / Read time / Summary`. Dropped `Type` (now communicated by group separators), `Chars` (replaced with `formatReadTime`), and `Compression` entirely. Same column set in `compact` mode (the dropdown uses smaller padding/font but identical columns).
- **3 group separators** in non-compact mode: `Front matter` (`FRONT_MATTER_TYPES`), `Chapters` (`SUMMARIZABLE_TYPES`), `Back matter` (everything else). `groupOf(sectionType)` helper drives the partition. Each group renders as a `<thead>` with a clickable row showing label + count + chevron.
- **Persisted expand state** keyed on `bc.sections.expand.${bookId}` in localStorage, structure `{ front, chapters, back }`. Defaults: chapters expanded, front + back collapsed. Toggle on click or Enter/Space; failures wrapped in try/catch (best-effort persistence).
- **Compact mode** preserves the flat-list layout (no group separators) so the reader-TOC dropdown stays compact and scannable.
- **Summary cell** shows `✓` (has_summary), `✕` (none), or live status during summarization SSE updates.

## Plan deviations
- Plan §T18 step 4 said the separator should be a `<thead>`-style row with a chevron. I implemented it as an actual `<thead>` (one per group) interleaved with the group's `<tbody>`. HTML5 allows multiple `<thead>` only one per table — but browsers tolerate the multi-thead pattern, and Vue test-utils + render fine. Considered the alternative of a single `<tbody>` with separator `<tr>`s; the multi-thead approach lets the group label stay visible when its body is collapsed. Acceptable for the personal-tool scale; flag for revisit if a screen-reader test catches issues during T29's a11y sweep.
- Plan §T18 step 1 mentioned 3 group separators always visible. I render a separator only when its group has at least one section (`v-if="groupedSections[g].length > 0"`). The 5-section fixture in the spec test uses sections from all three groups, so this matches the assertion; books with only chapters get a single chapters separator instead of two empty ones, which is the better UX.
- The TOCDropdown spec needed a follow-up edit: its compact-mode expectation `text.toMatch(/1[,]?234/)` referenced the old chars column. Updated to `text.toContain('2 min')` (1234 chars / 1100 cpm = 2 min ceil). This is a forced consequence of T18's column change, not a separate scope.

## Verification
- `npm run test:unit -- --run src/components/book/__tests__/SectionListTable.spec.ts` — 12/12 pass (12 new + rewrites of original 10).
- Full frontend unit suite: 524/524 pass (was 522 after T17; net +2 — gained 7 new SectionListTable tests, lost 5 obsolete column tests).
- `npm run type-check` clean.

## Runtime evidence
The 12 component tests cover: 4-column header set, 3 group labels, default expand state, click-to-toggle, localStorage persistence per bookId, formatReadTime rendering, ✓/✕ summary glyphs, compact mode flat list, row click navigation, ?tab preservation in reader-TOC context, SSE-driven status flip, and the compact-mode no-SSE rule. Each mounts the real component with a real `vue-router` instance and a Pinia store.
