---
task_number: 18
task_name: "QUIZ_ROLLUP worker handler"
task_goal_hash: 2095b0d5bb28cd127c46074b122a5ec681bd9a2fd6334cdf26eb2041d740a5fc
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T03:40:00Z
completed_at: 2026-05-09T03:55:00Z
files_touched:
  - backend/app/services/job_queue_worker.py
  - backend/tests/integration/test_quiz_rollup_job.py
---

## Summary

- Added the `QUIZ_ROLLUP` dispatch branch to `JobQueueWorker._on_promoted`.
- Implemented `_run_quiz_rollup(job_id, book_id)` per FR-61/62/64/S7/G18/P8:
  - **Threshold gate (S7)**: `non_stale_count > settings.quiz.dedup_verbatim_cap` (default 50). Below → COMPLETED noop, `themes_summary` stays NULL.
  - **Delta gate (G18)**: `(non_stale_count - state.last_rollup_question_count) >= settings.quiz.rollup_delta_threshold` (default 10). Below → COMPLETED noop, state untouched.
  - **Truncation (P8)**: cap stems fed into the LLM prompt at 200 (most-recent-first).
  - **FR-83 graceful degrade**: when no LLM provider exists, COMPLETED with no state mutation.
  - **FR-64**: stems counted from `is_stale=False AND discarded=False` only.
  - On success: writes `themes_summary`, `themes_summary_computed_at = now()`, `last_rollup_question_count = non_stale_count`. Lazy-creates the `quiz_dedup_state` row when missing.

## Verification

- Targeted: `uv run python -m pytest tests/integration/test_quiz_rollup_job.py -v` → **6 passed**.
- Full suite: `uv run python -m pytest tests/` → **1138 passed**, 35 skipped, 0 failed.
- Ruff + format: clean on the new test file. The 4 lint findings on `app/services/job_queue_worker.py` (TC002, SIM105) are pre-existing on `main` — verified by stash-and-re-lint — and untouched by this task.

## Test coverage

| Test | Surface |
|------|---------|
| `test_rollup_noops_below_verbatim_cap` | FR-61 threshold gate; no LLM call |
| `test_rollup_runs_above_threshold` | Happy path: writes themes_summary + last_rollup_question_count |
| `test_rollup_delta_gate_skips_re_run` | G18 delta gate; no LLM call when delta < 10 |
| `test_rollup_excludes_stale_stems_from_count` | FR-64: stale rows excluded from count |
| `test_rollup_truncates_to_200_stems_at_oversize` | P8: most-recent 200 stems reach the LLM prompt; older 50 dropped |
| `test_rollup_graceful_degrade_no_llm` | No provider → COMPLETED noop, state untouched |

## Notes

- Single-attempt model (Decision Log P9): no retry-counter column. A failed rollup leaves `themes_summary` at its previous value (null on first encounter; prior rollup on subsequent re-runs) and the next session-end will re-enqueue.
- The handler imports `QuizPromptBuilder` and `ROLLUP_SCHEMA` from `app.services.quiz` — both already exist from T7/T9.
- `_patch_provider` mirrors the T17 fixture pattern; tests use `FakeLLMProvider([])` to assert the "no LLM call" property of the noop branches (any LLM call would raise on exhaustion).
- The truncation test inserts 250 stems with `Stem N` labels; the handler picks the newest 200 (Stems 50..249), so the prompt must contain `Stem 50` and `Stem 249` but not `Stem 49`.
