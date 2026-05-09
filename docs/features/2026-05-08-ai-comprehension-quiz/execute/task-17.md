---
task_number: 17
task_name: "QUIZ_PREGEN_Q1 worker handler"
task_goal_hash: 4a327e5570e802fd6810c30083180e9f4bbeeef9ed162e1585a51839fe12d265
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T03:20:00Z
completed_at: 2026-05-09T03:35:00Z
files_touched:
  - backend/app/services/job_queue_worker.py
  - backend/tests/integration/test_quiz_pregen_job.py
---

## Summary

- Added the `QUIZ_PREGEN_Q1` dispatch branch to `JobQueueWorker._on_promoted`.
- Implemented `_run_quiz_pregen_q1(job_id, book_id)` per FR-80/81/83/S3:
  - **FR-81a noop**: when `Book.pre_drafted_q1_id` already points at a non-stale question, mark the job COMPLETED without invoking the LLM.
  - **FR-83 graceful degrade**: when no LLM provider is detected, mark the job COMPLETED with `error_message` left null (treats no-LLM as a deferred-state, not a failure).
  - **Single-attempt** (Decision Log P9): no retry-counter column in v1; transient generation errors mark FAILED with `error_message` populated. Slot stays empty so the next post-summarize hook (T19) can re-enqueue.
- Calls `QuizService.generate_question(book_id=..., session_id=None, scope={"mode":"all_summaries"}, warm_up=False)` then flips `q.is_pregen = True` and writes back `book.pre_drafted_q1_id` in the same transaction.

## Verification

- Targeted: `uv run python -m pytest tests/integration/test_quiz_pregen_job.py -v` → **4 passed**.
- Full suite: `uv run python -m pytest tests/` → **1132 passed**, 35 skipped, 0 failed.
- Ruff + format: clean on the new test file. The 4 lint findings on `app/services/job_queue_worker.py` (TC002, SIM105) are pre-existing on `main` — verified by stash-and-re-lint — and untouched by this task.

## Test coverage

| Test | Surface |
|------|---------|
| `test_pregen_handler_populates_slot` | Happy path: slot populated, `is_pregen=True`, `session_id IS NULL`, job COMPLETED |
| `test_pregen_handler_noops_when_slot_populated` | FR-81a: no LLM call, slot unchanged, job still COMPLETED |
| `test_pregen_handler_graceful_degrade_no_llm` | FR-83: no LLM provider → job COMPLETED, slot empty, `error_message` null |
| `test_pregen_handler_marks_failed_on_generation_error` | LLM emits invalid JSON twice → job FAILED with error_message; slot stays empty |

## Notes

- DEVIATION: T19 (next task) wires the post-summarize hook that ENQUEUES these jobs. T17 only implements the consumer. The end-to-end `summarize completion → pregen enqueue → pregen run → slot populated` flow lands in T19.
- DEVIATION: the plan suggested skipping the `max_attempts=2` test for v1 (Decision Log P9). This task ships a single-attempt model — failed pregens leave the slot empty and rely on the next summarize-completion to re-enqueue.
- The handler pattern mirrors `_run_audio_job`'s session/provider scaffolding: opens its own `bg_session`, fetches the job row by id, runs the unit of work in a try/except, persists status + error_message, and never raises out of `_on_promoted`.
- The `_patch_provider` helper monkeypatches `app.services.summarizer.detect_llm_provider` and `create_llm_provider` — the handler imports them inside the method body so this patching is reliable per-test.
