---
task_number: 8
task_name: "Concept-label normalization (FR-34)"
task_goal_hash: d5cc171750aa2b71e9c65fd85b3646738d250f5c606e06592cfa07a3d9e9bd15
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T00:43:00Z
completed_at: 2026-05-09T00:45:00Z
files_touched:
  - backend/app/services/quiz/normalize.py
  - backend/tests/unit/test_quiz_normalize.py
---

## Summary

- Implemented FR-34 5-step normalization (strip → lower → drop trailing parenthetical → collapse `[-_]+` to space → collapse internal whitespace).
- Test for `test_internal_parenthetical_kept` confirms the trailing-only nature of the parenthetical drop — `"loss (asymmetric) aversion"` is preserved.

## Verification

- `uv run python -m pytest tests/unit/test_quiz_normalize.py -v` → 7 passed in 0.02s.
- Ruff clean.

