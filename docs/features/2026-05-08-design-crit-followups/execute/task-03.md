---
task_number: 3
task_name: "T3: /continue front-matter filter"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T15:42:00Z
completed_at: 2026-05-08T15:48:00Z
files_touched:
  - backend/app/db/repositories/reading_state_repo.py
  - backend/tests/unit/repositories/test_reading_state_repo.py
---

# T3: /continue front-matter filter (FR-B05a)

## Outcome
`ReadingStateRepository.get_latest_other_device` now `outerjoin`s `BookSection` and excludes rows whose `section_type ∈ FRONT_MATTER_TYPES`. Rows with `section_id IS NULL` (book-level resume) still pass through.

## Verification
- `pytest tests/unit/repositories/test_reading_state_repo.py -v` → 3/3 pass.
- `pytest tests/integration/test_api/test_reading_state_api.py -v` → 1 pass, 3 skipped (need seeded books, unaffected).
- `ruff check` clean; `ruff format` clean.

## Notes / Deviation
- Plan said test file `tests/unit/api/test_reading_state.py`; I wrote `tests/unit/repositories/test_reading_state_repo.py` — matches the existing `tests/unit/repositories/` directory convention used by `test_audio_position_repo.py`. The route delegates to the repo, so testing the repo directly is the precise unit.
- Test uses `asyncio.sleep(1.1)` between upserts — SQLite `CURRENT_TIMESTAMP` resolves to seconds; sub-second sleeps left ordering ambiguous and the "skips_front_matter" test passed accidentally via id-tiebreak.
- Used `outerjoin(BookSection)` + `or_(section_id IS NULL, section_type NOT IN FRONT_MATTER_TYPES)` for null-safety.
