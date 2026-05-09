---
task_number: 7
task_name: "QuizPromptBuilder + Jinja2 templates"
task_goal_hash: b64ab50bd325f456a4a4229f202f3ed7f626d11bb4852849e6fe2abec70874e4
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T00:36:00Z
completed_at: 2026-05-09T00:42:00Z
files_touched:
  - backend/app/services/quiz/prompt_builder.py
  - backend/app/templates/quiz/question.j2
  - backend/app/templates/quiz/grade.j2
  - backend/app/templates/quiz/explain.j2
  - backend/app/templates/quiz/rollup.j2
  - backend/tests/unit/test_quiz_prompt_builder.py
---

## Summary

- New top-level template dir `backend/app/templates/quiz/` (not service-local under `summarizer/prompts/`) with 4 Jinja2 templates: `question.j2`, `grade.j2`, `explain.j2`, `rollup.j2`.
- `QuizPromptBuilder` exposes 4 methods: `build_generation_prompt`, `build_grading_prompt`, `build_explain_prompt`, `build_rollup_prompt`.
- Token-budget enforcement uses **binary search** on `scope_content[:n]` rather than linear truncation — O(log n) renders instead of O(n) for the 100k-token fixture.
- Defensive fatigue-clause appendix in `build_grading_prompt`: even though `grade.j2` emits the literal phrase, the builder also re-checks and appends if absent, so a future template edit can't silently drop the FR-50 invariant.

## Verification

- `uv run python -m pytest tests/unit/test_quiz_prompt_builder.py -v` → 9 passed in 0.15s.
- `uv run ruff check ...` clean; `uv run ruff format --check ...` clean.

## Notes

- Plan template uses literal `mcq: 0.4, open: 0.45, spot_error: 0.15` but I templated those values from `settings.quiz.shape_target_distribution` so spec §13 stays the single source of truth (FR-31). Test asserts `"mcq: 0.4"` is in the prompt — passes because the default settings match the spec.
- DEVIATION: plan tests reference `"{mcq:" in p or "mcq: 0.4" in p`. I assert the stronger `"mcq: 0.4"` substring directly since templated rendering is deterministic.
- `keep_trailing_newline=True` on the env so the schema sentinel ("Return ONE question conforming to the JSON schema.") never abuts user content.

