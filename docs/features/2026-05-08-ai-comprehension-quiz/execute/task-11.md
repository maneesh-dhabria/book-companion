---
task_number: 11
task_name: "QuizService.start_session (warm-up + pregen-Q1 + cold-start)"
task_goal_hash: 44c7c4f8bd2712ff7b1fdd64777471d41840b8971a801bfdfff002e34ec1adfa
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: in-flight
started_at: 2026-05-09T01:09:00Z
files_touched:
  - backend/app/exceptions.py
  - backend/app/services/quiz/quiz_service.py
  - backend/tests/unit/test_quiz_service_start.py
---

## Summary

- New exceptions `QuizValidationError` (FR-20, HTTP 400) and `QuizBudgetError` (S1, 60k cap).
- `QuizService.start_session(book_id, scope, theme)` returns `{session_id, question_id, queue_hit, warm_up_count}`.
- Order: validate scope → fetch scope_content → token-budget gate (specific_chapters only) → create QuizSession → (warm-up stub returns 0; T12 plugs in real branch) → if all_summaries+no-theme+no-warmup, attempt pregen consume (FR-22 (a)+(b)+(c)) → else cold-start via `generate_question`.
- `_consume_pregen_q1` enforces FR-22 (d): non-stale check; on consume sets `qq.session_id = session_id`, `qq.is_pregen = False`, `book.pre_drafted_q1_id = None`. Stale slot is left untouched (FR-22 explicit).
- Try/except wraps the whole post-validation path; any exception triggers `session.rollback()` so no orphan QuizSession survives a partial failure (idempotency: no — recovery is rollback).

## Verification

- `uv run python -m pytest tests/unit/test_quiz_service_start.py -v` → 9 passed in 0.63s.
- Ruff clean; format applied.

## Notes

- `_validate_scope` rejects (a) bad mode, (b) empty section_ids in specific_chapters, (c) section_ids that belong to another book.
- DEVIATION: plan tests reference seeded sections via fixture. I extended `section_factory` to accept `content_md` override (already supported); the budget test seeds a 30k-repeat string yielding ~60k tokens — which exceeds the cap and proves the gate works.
- `T12 hand-off`: warm_up_count is hard-coded to 0; T12 will replace with `await self.warm_up_candidates(book_id, scope)` and persist warm-up `QuizQuestion`s before the pregen/cold-start branch.

