---
task_number: 25
task_name: "T25: ResumeAffordance mounting"
task_goal_hash: afcaca622ce45074a4023269e99d1d85f5c1bfde1bf49b496cf96cb8a9385ae2
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T21:10:00Z
completed_at: 2026-05-08T21:18:00Z
files_touched:
  - frontend/src/api/audio.ts
  - frontend/src/views/BookOverviewView.vue
  - frontend/src/views/BookDetailView.vue
  - frontend/src/views/__tests__/BookOverviewView.spec.ts
---

# T25: ResumeAffordance mounting (FR-E07, FR-E07a, FR-E08)

## Outcome
- **`audioApi.positionsByBook(bookId)`:** New typed API client method targeting `/api/v1/audio/positions/by-book/{book_id}`. Returns `AudioPositionByBook | null` — `null` on 404 (no position yet). Other HTTP errors re-throw.
- **`BookOverviewView` (`/books/:id`):** Calls `positionsByBook` on mount. Mounts `<ResumeAffordance>` at the top of the book-overview main when the position exists AND is not the same content as the active Playbar (FR-E08). Hardened `showResume` to require both `content_id` and `content_type` so a stub `{}` response from a generic test fetch fallback doesn't false-positive.
- **`BookDetailView` (`/books/:id/sections/:sectionId`):** Mounts `<ResumeAffordance>` for the current section when not the same content as the active Playbar. ResumeAffordance internally fetches its own `/audio_position?content_type=section_summary&content_id={id}` and 404-degrades silently.
- Library view (`/`) is wired by **T28** in the same phase.

## Plan deviations
- Plan §T25 step 4 said `totalSentences` — the prop exists on ResumeAffordance but the view doesn't have that count yet. Passed `0` as a placeholder; ResumeAffordance currently uses it only in the resume label, not for any gating. A follow-up could thread the count through `audio_position` lookups when the backend adds it to the response.
- Plan §T25 step 2 prescribed positioning the dock unobtrusively. Mounted at the top of `<main class="book-overview">` before the header — visible on first paint without competing with the cover. Same placement convention in BookDetailView (above ReaderHeader).

## Verification
- Full frontend unit suite: 552/552 pass (was 550 at T24 close; +2 new BookOverviewView gating tests).
- `npm run type-check` clean.
- `npm run build` clean (1.47s).

## Runtime evidence
The 2 new BookOverviewView tests cover:
1. Position present (200 with full payload) → `[data-testid="book-resume-affordance"]` mounts.
2. Position absent (404) → affordance not mounted (stays gated).

The BookDetailView mount path is symmetric; relies on ResumeAffordance's own internal 404-handling via `audioPositionApi.get`. Adding a Vue Router-driven mount test for it would require setting up the full reader store with a real section, which is more invasive than the gate logic warrants — T29's e2e sweep will exercise the real path.
