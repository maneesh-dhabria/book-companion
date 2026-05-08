---
task_number: 14
task_name: "T14: ContinueBanner FM fallback"
task_goal_hash: 200bdad1b6bea33538ba7680934740dbea74f8a37d176e4be12e31771518a0af
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T17:42:00Z
completed_at: 2026-05-08T17:48:00Z
files_touched:
  - frontend/src/components/reader/ContinueBanner.vue
  - frontend/src/components/reader/__tests__/ContinueBanner.spec.ts
---

# T14: ContinueBanner front-matter fallback (FR-B04)

## Outcome
- After `fetchContinueReading()` resolves, `ContinueBanner.vue` now lazily fetches `/api/v1/books/{bookId}` to obtain `book.sections` + `book.status`. The banner uses this to detect whether the recorded `last_section_id` points to a `FRONT_MATTER_TYPES` section (or is null).
- When fallback is needed: target = `firstChapter(book.sections, book.status)`, button label = "Start reading", body shows just the book + chapter title (no "You were reading…" framing).
- When fallback is NOT needed: existing "You were reading **Book**, **Section**" + "Continue" UX is preserved.
- When no chapter exists at all (book has only front-matter and is still parsing), the banner hides itself instead of routing to the cover page.
- Banner remains hidden during the brief window between `fetchContinueReading()` and the book-detail fetch when fallback is needed — no flash of "Continue → cover page".

## Plan deviation
- Plan §T14 step 1 said "mount the component with a populated book (sections array)". I added an internal `fetch('/api/v1/books/{id}')` rather than threading a `book` prop through the only call site (`LibraryView.vue:64 <ContinueBanner />`). Tests mock the fetch instead. This avoids a breaking-prop change in the LibraryView call site and keeps the banner self-contained, which matches the plan's `Files:` constraint of touching only `ContinueBanner.vue`.

## Verification
- `npm run test:unit -- --run src/components/reader/__tests__/ContinueBanner.spec.ts` — 3/3 pass.
- Full frontend unit suite: 510/510 pass (was 507 after T13; +3 new).
- `npm run type-check` clean.

## Runtime evidence
The 3 new tests cover the three branches: (1) section_id points to front-matter → "Start reading" + click navigates to first chapter; (2) section_id is a chapter → "Continue" + click navigates to recorded section; (3) no chapter at all → banner does not render. Each mounts a real `vue-router` + Pinia store, mocks both fetches, and asserts both DOM text and `router.currentRoute.value.path` after click.
