---
task_number: 13
task_name: "T13: firstChapter into BookSummaryTab"
task_goal_hash: 09463e1114c74d40563326fd15a22c1081ddcb34dcb1b6e17b927bf34b6e80d5
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T17:32:00Z
completed_at: 2026-05-08T17:38:00Z
files_touched:
  - frontend/src/components/book/BookSummaryTab.vue
  - frontend/src/components/book/__tests__/BookSummaryTab.spec.ts
---

# T13: firstChapter into BookSummaryTab "Read Section Summaries" (FR-B03)

## Outcome
- `BookSummaryTab.vue` `readSectionSummaries()` now uses `firstChapter(sections, book.status)` after sorting by `order_index`. When no chapter exists, the function shows a `'No chapter to open yet'` info toast via `useUiStore().showToast()` and skips navigation.
- `SectionLike` interface widened with optional `section_type`. `BookLike` widened with optional `status` so `firstChapter`'s PARSED-fallback path is reachable.
- The cast `sections as unknown as ReadonlyArray<Section>` bridges the local `SectionLike` shape and the `Section` type from `@/types`. The fields actually consumed by `firstChapter` (`section_type`, runtime presence) are now on `SectionLike`, so the cast is sound.

## Verification
- `npm run test:unit -- --run src/components/book/__tests__/BookSummaryTab.spec.ts` — 5/5 pass (4 prior + 1 new for FR-B03).
- Full frontend unit suite: 507/507 pass (+1 vs T12).
- `npm run type-check` clean.

## Runtime evidence
The new component test mounts `BookSummaryTab` with sections[0]=copyright, sections[1]=chapter, real `vue-router` memory history, populated `default_summary` (so the populated state with the CTA renders), then clicks the "Read Section Summaries" button and asserts `router.currentRoute.value.path === '/books/3/sections/51'`. The disabled-empty-state test continues to gate the empty path.

## No deviations.
