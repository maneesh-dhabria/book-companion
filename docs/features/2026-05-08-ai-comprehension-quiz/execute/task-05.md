---
task_number: 5
task_name: "Quiz repositories (session, question, dedup_state)"
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T00:15:30Z
completed_at: 2026-05-09T00:22:00Z
files_touched:
  - backend/app/db/repositories/quiz_session_repo.py
  - backend/app/db/repositories/quiz_question_repo.py
  - backend/app/db/repositories/quiz_dedup_state_repo.py
  - backend/tests/unit/test_quiz_repos.py
---

## Outcome

Three thin query-builder repos covering the public surfaces required by Phase 2/3 services:

- `QuizSessionRepository`: create, get_by_id (selectinload questions), list_by_book (DESC), get_in_progress_for_book, update_status.
- `QuizQuestionRepository`: create, get_by_id, recent_stems (FR-60), concepts_with_skip_threshold (FR-44), warm_up_candidates (FR-70), mark_stale_for_book (FR-64), increment_skip_for_stem (FR-43, per-stem semantics), discard, discarded_stems_for_session (FR-47).
- `QuizDedupStateRepository`: get, upsert, reset (FR-64).

`recent_stems` filters: `is_stale=False AND discarded=False AND skip_count<3 AND (warm_up=False OR self_assessment IS NOT NULL)` ordered by `created_at DESC, id DESC`.

`warm_up_candidates` returns `(stem, meta)` tuples for partial/missed answers from the last N sessions.

## Verification evidence

- `pytest tests/unit/test_quiz_repos.py -v` → 10 passed (all repo public methods + the per-stem skip increment spec-critical test).
