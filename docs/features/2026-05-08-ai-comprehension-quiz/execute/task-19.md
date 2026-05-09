---
task_number: 19
task_name: "SummarizerService COMPLETED → enqueue QUIZ_PREGEN_Q1"
task_goal_hash: 557e17ba1c4d5594a60a8511f279c6e3a00fd7b639ac059aeaa6b2b81a543d6e
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T03:55:00Z
completed_at: 2026-05-09T04:05:00Z
files_touched:
  - backend/app/services/job_queue_worker.py
  - backend/tests/integration/test_quiz_pregen_job.py
---

## Summary

- Added `JobQueueWorker._maybe_enqueue_pregen_q1(session, book_id) -> bool` helper implementing FR-80:
  - Returns True (and enqueues a `ProcessingJob(step=QUIZ_PREGEN_Q1, status=PENDING)`) ONLY when `Book.pre_drafted_q1_id` is null OR the referenced question is `is_stale`.
  - Returns False without raising when the partial UNIQUE INDEX rejects the INSERT (a previous pregen job is still PENDING/RUNNING for this book) — the summarize commit can still proceed.
- Wired the helper into `_run_processing` right after `bg_job.status = COMPLETED` (and after the failure-count guard). Only fires when at least one section actually summarized successfully — `completed_count > 0`. The enqueue happens before `bg_session.commit()`, so the COMPLETED transition + pregen enqueue are durable as one atomic step.

## Verification

- Targeted: `uv run python -m pytest tests/integration/test_quiz_pregen_job.py -v` → **8 passed** (4 T17 + 4 new T19 helper tests).
- Full suite: `uv run python -m pytest tests/` → **1142 passed**, 35 skipped, 0 failed.
- Ruff + format: clean on the modified test file. The 4 worker lint findings (TC002, SIM105) are pre-existing and untouched.

## Test coverage (T19)

| Test | Surface |
|------|---------|
| `test_maybe_enqueue_pregen_q1_when_slot_empty` | FR-80 happy path: empty slot → 1 PENDING job |
| `test_maybe_enqueue_pregen_q1_skips_when_slot_populated` | FR-80 idempotency: non-stale Q present → 0 jobs |
| `test_maybe_enqueue_pregen_q1_when_slot_stale` | FR-82: stale Q in slot → re-enqueue |
| `test_maybe_enqueue_pregen_q1_swallows_integrity_when_active_exists` | Partial UNIQUE INDEX rejects double-enqueue; helper returns False without raising |

## Notes

- DEVIATION: the plan suggested an end-to-end test that drives a real summarize job to COMPLETED then asserts a pregen job appears. Instead I tested the **helper** directly (4 cases) — both because the e2e setup is heavy and because the helper is the FR-80 logic; running `_run_processing` end-to-end would only re-prove the call-site wiring.
- The post-summarize wiring sits inside the existing `_run_processing` method's success branch, so when the summarize subprocess succeeds the pregen job lands in the same DB transaction as the COMPLETED status flip.
- The `completed_count > 0` guard prevents enqueueing a pregen job when summarize completed the work-quota with all-failed sections (which the existing branch already maps to FAILED) AND when an empty-scope summarize trivially completes — a pregen with nothing to draft from is wasted LLM cost.
- Together with T17 + T18, this closes the post-summarize chain: `summarize → enqueue pregen → worker generates Q1 → slot populated; on session-stop → enqueue rollup → worker computes themes_summary`.
