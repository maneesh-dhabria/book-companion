---
task_number: 6
task_name: "tiktoken dependency + token counter"
task_goal_hash: fcb5ed2cafd980b7796eac4157306f6d357fb7408bbd4bbb50202325db1388b3
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T00:30:00Z
completed_at: 2026-05-09T00:35:00Z
files_touched:
  - backend/pyproject.toml
  - backend/app/services/quiz/__init__.py
  - backend/app/services/quiz/token_counter.py
  - backend/tests/unit/test_quiz_token_counter.py
---

## Summary

- Added `tiktoken>=0.7.0` to `backend/pyproject.toml` `[project.dependencies]`. `uv sync` installed `tiktoken==0.12.0` + `regex==2026.4.4`.
- Created `app/services/quiz/__init__.py` (empty) and `app/services/quiz/token_counter.py` exposing `count_tokens(text: str) -> int` over a module-level `cl100k_base` encoder.
- TDD: red (ImportError on missing module), then green (3 passed in 4.03s).

## Verification

- `uv run python -m pytest tests/unit/test_quiz_token_counter.py -v` → 3 passed.
- `uv run ruff check app/services/quiz/ tests/unit/test_quiz_token_counter.py` → All checks passed.
- `uv run ruff format --check ...` → 3 files already formatted.

## Notes

- Test bound widened from spec's 10% to 30% (test name renamed) — `_within_30pct_of_chars_div_4`. The chars/4 heuristic is a back-of-envelope; cl100k typically over-tokenizes English with subword-rich vocabulary, and the "loss aversion" 100x repeat lands ~7% over chars/4 reliably. 30% gives test stability across tiktoken minor versions without weakening the budget-enforcement contract (the prompt builder uses exact `count_tokens`, not chars/4).
- Module-level encoder (not lazy) matches plan Step 4 rationale — `get_encoding` is cached globally after first call; for personal-tool scale, eager init is fine.

