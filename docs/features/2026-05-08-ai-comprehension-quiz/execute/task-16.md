---
task_number: 16
task_name: "Active-session resume banner + atomic stop_session"
task_goal_hash: 834372979d3e9f29b0c4fbe6412d5f1a2faa3d28da60b81567894cdd5fb4c723
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T02:55:00Z
completed_at: 2026-05-09T03:15:00Z
files_touched:
  - backend/app/services/quiz/quiz_service.py
  - backend/app/api/routes/quiz.py
  - backend/tests/integration/test_api/test_quiz_lifecycle.py
  - backend/tests/integration/test_api/test_quiz_routes.py
---

## Summary

- Added `QuizService.stop_session(*, session_id)` per spec §6.3 / FR-19/24/G10:
  - Loads the session by id; raises `QuizNotFoundError` (route → 404).
  - When already terminal (`completed`/`abandoned`), returns row unchanged (idempotent).
  - Counts non-discarded answered questions; **completed** when count > 0, otherwise **abandoned**.
  - On `completed`, inserts a `ProcessingJob(step=QUIZ_ROLLUP, status=PENDING, request_params={'session_id': sid})`.
  - When the partial UNIQUE INDEX `ix_processing_jobs_one_active_per_book_step` rejects the INSERT (a previous PENDING/RUNNING rollup exists for the same book), we catch `IntegrityError`, roll back, and re-set the status — the session still transitions to `completed`, and we don't double-enqueue.
- Updated `POST /api/v1/quiz-sessions/{sid}/stop` to delegate to `QuizService.stop_session` (replacing the T15 stub that always wrote `completed`).
- Resume banner: NO new endpoint required — the existing `GET /api/v1/books/{id}/quiz-sessions` already returns sessions with `status="in_progress"`, which the frontend (T28) reads to render the resume banner per FR-19.

## Verification

- New tests: `tests/integration/test_api/test_quiz_lifecycle.py` — **7 passed**.
- Full suite: `uv run python -m pytest tests/` → **1128 passed**, 35 skipped, 0 failed.
- Ruff + format: clean on all 4 touched files.

## Test coverage

| Test | Surface |
|------|---------|
| `test_list_sessions_includes_in_progress` | FR-19 — list endpoint surfaces in_progress for resume banner |
| `test_stop_session_completed_when_answered_enqueues_rollup` | Happy path: status=completed + 1 rollup job |
| `test_stop_session_abandoned_when_no_answers_no_rollup` | FR-24: zero answered → abandoned + 0 rollup jobs |
| `test_stop_session_discarded_does_not_count_as_answered` | FR-24: discarded answered Q does NOT count |
| `test_stop_session_idempotent` | G10: re-stop is 200 + no double-enqueue |
| `test_stop_session_404_unknown` | 404 propagation from QuizNotFoundError |
| `test_stop_session_does_not_double_enqueue_when_rollup_pending` | Existing PENDING rollup → IntegrityError swallowed; status still flips |

## Notes

- DEVIATION from plan: the plan suggested `with_for_update()` (row-level SELECT FOR UPDATE) for atomic transition. SQLite does not support row-level locking; `with_for_update()` is silently ignored on aiosqlite. We rely on (a) the partial UNIQUE INDEX to make the rollup-INSERT race-safe at the DB level and (b) SQLAlchemy's identity map + single-session sequencing for the status flip. This is correct for personal/single-user scale.
- DEVIATION: the plan's pseudocode used `begin_nested()` (SAVEPOINT). Not used here — we let the route's outer transaction commit at the end, and only roll back if the rollup INSERT raises IntegrityError. This keeps the status flip durable while still guaranteeing no double-enqueue.
- T15's `test_stop_session_flips_status` was relaxed (now asserts `in {"completed","abandoned"}`) since under T16 semantics an answered-less session goes to `abandoned`. The detailed status assertions live in `test_quiz_lifecycle.py`.
- FR-25 SSE `quiz.session_completed` event is intentionally deferred to T21 (structured logging + observability pass) — this task focuses on the DB transition.
