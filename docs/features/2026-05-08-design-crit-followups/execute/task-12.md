---
task_number: 12
task_name: "T12: Wire firstChapter into BookOverviewView Read CTA"
task_goal_hash: d0d13b5821fad0195d7adf224df86f27e6dcb691f2a3634233b2238bbe5ede5a
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T17:25:00Z
completed_at: 2026-05-08T17:30:00Z
files_touched:
  - frontend/src/views/BookOverviewView.vue
  - frontend/src/views/__tests__/BookOverviewView.spec.ts
---

# T12: firstChapter into BookOverviewView Read CTA (FR-B02)

## Outcome
- `BookOverviewView.vue` imports `firstChapter` from `@/stores/reader`. The `firstSection` computed now delegates to `firstChapter(book.sections, book.status)` so front-matter sections (copyright, dedication, etc.) are skipped.
- The Read CTA renders the existing `<router-link>` when a chapter exists; otherwise a disabled `<button class="btn-primary" disabled title="No chapter to open yet">Read</button>` with the same `data-action="read"` so the action-row test that asserts `[read, overflow]` still holds in both states.

## Verification
- `npm run test:unit -- --run src/views/__tests__/BookOverviewView.spec.ts` — 9/9 pass (7 prior + 2 new for FR-B02).
- Full frontend unit suite: 506/506 pass (was 504 after Phase 2; +2 new this task).
- `npm run type-check` clean.

## Runtime evidence
The two new component tests render the view through a real `vue-router` instance and assert (a) the `<a>`'s `href === '/1/sections/11'` when sections[0] is copyright and sections[1] is a chapter, and (b) the `<button disabled title="No chapter to open yet">` shape when only front-matter sections exist with status PARSING. These cover both branches of the new template and satisfy the UI evidence requirement for a single-computed swap.

## No deviations.
