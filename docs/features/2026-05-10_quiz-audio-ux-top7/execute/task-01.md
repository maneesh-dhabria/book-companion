---
task_number: 1
task_name: "FR-01 start_session 502 handler"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T00:00:00Z
completed_at: 2026-05-10T00:00:00Z
files_touched:
  - backend/app/api/routes/quiz.py
  - backend/tests/unit/test_quiz_route_502.py
---

Added `SubprocessNonZeroExitError` import + 502 handler clause between `SubprocessTimeoutError` and `QuizGenerationError` in `start_session`. Test seeds book + uses `dependency_overrides[get_quiz_service]` with a stub raising `SubprocessNonZeroExitError`. Deviation: no `seeded_book_id` fixture exists; embedded the seed helper from `test_quiz_routes.py` directly into the new test file. RED→GREEN confirmed; ruff clean.
