---
task_number: 14
task_name: "Drop UA filter on /reading-state/by-book/{id}"
task_goal_hash: 1e5716a25405acbea9f26c8801330349b13bdd6475276486f9057625bc9cd722
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T02:00:00Z
completed_at: 2026-05-09T02:10:00Z
files_touched:
  - backend/app/api/routes/reading_state.py
  - backend/app/db/repositories/reading_state_repo.py
  - backend/app/api/schemas.py
  - backend/tests/integration/test_api/test_reading_state_by_book.py
---

## Summary

- Bug-fix TDD: 4 regression tests written FIRST and proven to fail on the current code (KeyError on `most_recent_section_ids`). Then implemented the fix and re-verified — all 4 pass.
- Added `ReadingStateRepository.get_all_devices_for_book(book_id, *, since=None)` returning newest-first list (FR-17).
- Rewrote `GET /api/v1/reading-state/by-book/{id}`: dropped the `user_agent` Header dep, applies `since=now-48h` window, builds `most_recent_section_ids` by deduplicating section ids in newest-first order (cap 10).
- Extended `ReadingStateResponse` Pydantic model with `most_recent_section_ids: list[int] = []` (default empty so existing PUT/continue/resume-banner serialization keeps the same shape with the new field defaulted).

## Verification

- `uv run python -m pytest tests/integration/test_api/test_reading_state_by_book.py -v` → 4 passed.
- `uv run python -m pytest tests/ -k reading_state -v` → 16 passed, 3 skipped (skips are pre-existing — book-list dependency).
- Confirmed `/reading-state/continue` contract unchanged: `test_continue_endpoint_still_filters_by_device` passes — DeviceA's own row does NOT come back from `/continue` when DeviceA queries (CLAUDE.md gotcha #27 preserved).
- Ruff: clean on all 4 files. Format: clean.

## Notes

- Test seeding for the 48-hour window: ORM insert (not raw SQL) was required because SQLAlchemy's SQLite DateTime(timezone=True) bind processor formats values differently than `datetime.isoformat()` would produce in raw `:updated_at` parameters; with the raw path the comparison `updated_at >= since` returned all rows. Using ORM insert + assignment lets the dialect normalize binding.
- `selectinload(ReadingState.section)` is included in the new repo query so the route can read `head.section.title` without lazy-loading after commit.
- The 48-hour window is hardcoded in the route (matches the plan); not pulled into Settings since this endpoint has only one caller.
