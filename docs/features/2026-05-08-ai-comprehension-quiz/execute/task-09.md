---
task_number: 9
task_name: "QuizService skeleton + JSON schemas + DI wiring"
task_goal_hash: ee455a13e0b5a3afce196bf14c1aeede45d315eaf6e475f30db4fae67d964d55
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T00:46:00Z
completed_at: 2026-05-09T00:52:00Z
files_touched:
  - backend/app/services/quiz/schemas.py
  - backend/app/services/quiz/quiz_service.py
  - backend/app/api/deps.py
  - backend/tests/unit/test_quiz_schemas.py
  - backend/tests/unit/test_quiz_deps.py
---

## Summary

- `schemas.py` defines `QUESTION_SCHEMA`, `FEEDBACK_SCHEMA`, `ROLLUP_SCHEMA` as plain dicts (not pydantic) so they can be passed directly to Claude/Codex `--json-schema` / `--output-schema`.
- `QUESTION_SCHEMA` uses `allOf` with `if/then` blocks for shape-conditional required fields (`mcq_options` for `mcq`; `intended_error` + `error_explanation` for `spot_error`). Bloom enum includes `create` (G21).
- Added `mcq_correct_index` (0-3) to the schema — required when shape=mcq. Plan didn't enumerate it but spec FR-30 implies it (otherwise grading is ambiguous).
- `quiz_service.py` is a skeleton: constructor wires repos + builder; all 8 methods raise `NotImplementedError` with a "Filled in by T<N>" hint pointing at the responsible task.
- `get_quiz_service` in `app/api/deps.py` short-circuits to `None` when (a) `settings.quiz.enabled is False` OR (b) `_get_llm_provider` returns None.
- Used `from __future__ import annotations` + `TYPE_CHECKING` import for `Settings`/`AsyncSession`/`LLMProvider` to keep the runtime import graph tight (TC001 ruff rule).

## Verification

- `uv run python -m pytest tests/unit/test_quiz_schemas.py tests/unit/test_quiz_deps.py -v` → 7 passed in 0.17s.
- `uv run ruff check ...` clean on new code (the one E501 surfaced is pre-existing on `app/api/deps.py:149` for the `BackupService` constructor — out of T9 scope).
- `uv run python -c "from app.services.quiz.quiz_service import QuizService; print('import-ok')"` → import-ok.

## Notes

- Plan's `get_quiz_service` test used `__wrapped__` to bypass FastAPI Depends. I called the function directly with kwargs (`db=None`, `settings=Settings()`) since the function is a plain factory — FastAPI auto-resolves `Depends` only when the function is registered on a route.

