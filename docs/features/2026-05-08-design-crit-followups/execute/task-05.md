---
task_number: 5
task_name: "T5: /audio/sections/by-book"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T15:50:00Z
completed_at: 2026-05-08T15:54:00Z
files_touched:
  - backend/app/api/routes/audio.py
  - backend/tests/integration/test_api/test_audio_by_book.py
---

# T5: GET /api/v1/audio/sections/by-book/{book_id} (FR-C20)

## Outcome
Added route + Pydantic models `AudioByBookEntry` / `AudioByBookResponse` to `app/api/routes/audio.py`. Returns one entry per section with `has_mp3` boolean and `engine` (best-effort).

## Verification
- `pytest tests/integration/test_api/test_audio_by_book.py::test_sections_by_book_*` → 2/2 pass.
- 404 on unknown book; missing audio → entries with `has_mp3: false`; seeded audio → `has_mp3: true` with engine.

## Notes
- Route placed in existing `audio.py` (no new file). Decision per plan T5 step 0: existing `APIRouter` is prefix-less and uses absolute paths inline.
- `AudioFile` has no `status` column — row presence implies generated. No `status='ready'` filter needed.
