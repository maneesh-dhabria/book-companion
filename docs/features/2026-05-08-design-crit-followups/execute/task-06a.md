---
task_number: 6.5
task_name: "T6a: /reading-state/by-book"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T15:54:00Z
completed_at: 2026-05-08T15:56:00Z
files_touched:
  - backend/app/db/repositories/reading_state_repo.py
  - backend/app/api/routes/reading_state.py
  - backend/tests/unit/repositories/test_reading_state_repo.py
---

# T6a: GET /reading-state/by-book/{book_id} (P13)

## Outcome
- New `ReadingStateRepository.get_for_device_and_book(user_agent, book_id)` returns the matching row or None.
- New route `GET /api/v1/reading-state/by-book/{book_id}` returning the existing `ReadingStateResponse` schema; all-null fields when no row exists (200, not 404).

## Verification
- Repo unit test passes: matching device+book returns row; mismatched device or book returns None.
- Full backend test suite: 1019 passed (vs 1001 baseline, +18 new).
