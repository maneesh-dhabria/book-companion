---
task_number: 6
task_name: "T6: /audio/positions/by-book"
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

# T6: GET /api/v1/audio/positions/by-book/{book_id} (FR-E07a)

## Outcome
Added route + Pydantic `AudioPositionByBookResponse`. Returns the most-recent `audio_positions` row across `section_summary`, `section_content`, and `book_summary` content_types — the section types are joined through `book_sections.book_id`; `book_summary` matches `content_id == book_id` directly. `annotations_playlist` rows are excluded by SELECT scope. 404 when no audio position exists for the book; 200 with `{content_type, content_id, sentence_index, updated_at}` otherwise.

## Verification
- `pytest tests/integration/test_api/test_audio_by_book.py::test_positions_by_book_*` → 3/3 pass.
- Cross-book isolation tested: book B's audio_position never surfaces on book A's endpoint.
