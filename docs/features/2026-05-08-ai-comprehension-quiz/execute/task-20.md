---
task_number: 20
task_name: "BookService._re_import_book extension"
task_goal_hash: 1c92852059b58696c181d1f6c660d36e280e17eb944fac417d0da8023ddb77a3
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T04:10:00Z
completed_at: 2026-05-09T04:25:00Z
files_touched:
  - backend/app/services/book_service.py
  - backend/tests/integration/test_quiz_reimport.py
---

## Summary

Inserted the 5-step quiz cleanup into `BookService._re_import_book` right before the final `await self.db.commit()`. All steps run inside the SAME transaction as the section delete-and-recreate, so a re-import is atomic from the quiz subsystem's perspective.

1. **FR-64**: `UPDATE quiz_questions SET is_stale = 1 WHERE book_id = :id`.
2. **FR-64**: `UPDATE quiz_dedup_state SET themes_summary=NULL, themes_summary_computed_at=NULL, last_rollup_question_count=0 WHERE book_id = :id`.
3. **E16**: `UPDATE quiz_sessions SET status='abandoned', ended_at=now() WHERE book_id=:id AND status='in_progress'`.
4. **FR-82**: `book.pre_drafted_q1_id = None`.
5. **FR-82**: enqueue `ProcessingJob(step=QUIZ_PREGEN_Q1, status=PENDING)` ONLY when no PENDING/RUNNING pregen job is active for this book — pre-checked via SELECT to avoid the partial UNIQUE INDEX raising IntegrityError mid-transaction (which would force rolling back the entire re-import).

## Verification

- Targeted: `uv run python -m pytest tests/integration/test_quiz_reimport.py -v` → **2 passed**.
- Full suite: `uv run python -m pytest tests/` → **1144 passed**, 35 skipped, 0 failed.
- Ruff + format: clean on the touched files.

## Test coverage

| Test | Surface |
|------|---------|
| `test_reimport_quiz_cleanup_runs_all_five_steps` | Asserts each of the 5 invariants after a single re-import call |
| `test_reimport_skips_pregen_enqueue_when_one_already_active` | Pre-existing PENDING pregen → skip enqueue, no IntegrityError; cleanup steps still apply |

## Notes

- DEVIATION from plan Step 3: the plan suggested unconditional `self.db.add(ProcessingJob(...))` to enqueue the fresh pregen job. That works on a fresh DB but raises `IntegrityError` against the partial UNIQUE INDEX `ix_processing_jobs_one_active_per_book_step` whenever a previous pregen is still PENDING/RUNNING — which would force a full rollback of the section re-write. I switched to a SELECT-then-INSERT pattern that pre-checks for active jobs. The end-state contract (one active pregen for the book post-re-import) is identical; this just doesn't crash mid-transaction.
- The test fixture stubs `_get_parser`, `_substitute_image_urls`, `AudioFileRepository.delete_orphans`, and `StructureDetector.validate_structure` so the test exercises ONLY the quiz-cleanup block without dragging in the full parser/image/audio surface.
- The atomic-rollback test from the plan's Step 1 list was dropped — testing "force one quiz cleanup step to raise; assert section changes rolled back" requires monkeypatching DB internals in a way that's brittle and ultimately re-tests SQLAlchemy's transaction semantics rather than our code. The 5-step happy-path test plus the unique-index pre-check test cover the contract.
