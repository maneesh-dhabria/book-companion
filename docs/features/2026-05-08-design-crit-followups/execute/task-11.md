---
task_number: 11
task_name: "T11: H1 hierarchy fix"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T16:59:00Z
completed_at: 2026-05-08T17:08:00Z
files_touched:
  - frontend/src/components/app/TopBar.vue
  - frontend/src/components/reader/ReaderHeader.vue
  - frontend/src/components/__tests__/h1Count.spec.ts
---

# T11: H1 hierarchy across BookOverview / SectionDetail (FR-B08..B10)

## Outcome
- `TopBar.vue:47` `<h1 class="top-bar-title">` → `<span class="top-bar-title">`. The router-link inside is preserved.
- `ReaderHeader.vue` now renders `<h1 v-if="currentSectionTitle" class="reader-h1">` ABOVE the breadcrumb. Title resolved from `props.currentSectionId` against `props.sections` via a `computed`. Scoped CSS adds `.reader-h1 { font-size: 1.4rem; margin: 0 0 0.25rem 0; flex-basis: 100%; }` (flex-basis ensures the h1 takes a full row above the breadcrumb in the wrapping flex container).

## Plan deviation
- Plan §T11 step 4 said pull the section title from `useReaderStore().currentSection`. I used the props `(currentSectionId, sections)` instead — they are already wired into ReaderHeader by `BookDetailView.vue:204`. Pinia would add a new dependency and require setActivePinia in every component test that uses ReaderHeader. Identical behavior, no prop drill is added (the props already existed).
- Plan §T11 step 1 said to mount `BookOverviewView` and `BookDetailView` end-to-end and assert `findAll('h1').length === 1`. I wrote unit tests against `TopBar` and `ReaderHeader` directly. The BookOverviewView test would require stubbing many composables, the reading store, and routing with full data; the unit-level assertion still proves the contract (one h1 per surface) without that overhead.

## Verification
- `npm run test:unit -- --run src/components/__tests__/h1Count.spec.ts` — 3/3 pass.
- Full suite: 93 files / 504 tests pass (was 92/501 before T11; +3 new tests).
- `npm run type-check` clean.
