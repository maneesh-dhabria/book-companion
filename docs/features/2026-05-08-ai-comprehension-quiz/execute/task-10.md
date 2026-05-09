---
task_number: 10
task_name: "QuizService.generate_question (strict schema, retry, spot-error validator)"
task_goal_hash: 5fcf4ef036a155c823443584d37b6288b6b7f5c341d82f0d06cdf97bc03df92b
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T00:53:00Z
completed_at: 2026-05-09T01:08:00Z
files_touched:
  - backend/pyproject.toml
  - backend/app/exceptions.py
  - backend/app/services/quiz/quiz_service.py
  - backend/app/services/quiz/prompt_builder.py
  - backend/tests/unit/conftest.py
  - backend/tests/unit/test_quiz_service_generate.py
---

## Summary

- Added `jsonschema>=4.20.0` to backend deps (resolves to 4.26.0).
- New exception `QuizGenerationError` in `app/exceptions.py`; subclass `SpotErrorValidationError` lives in `quiz_service.py`.
- `QuizService.generate_question` follows FR-30/32/33/34/35:
  - Either `scope_content` (T10/test path) or `scope` dict (route path) is accepted.
  - Builds prompt with recent_stems / themed_summary / shape_histogram / skipped_concepts; calls LLM with strict `QUESTION_SCHEMA`.
  - On `json.JSONDecodeError`, `jsonschema.ValidationError`, or `SpotErrorValidationError`: retries once with `validator_error` pasted into the prompt via the new `## Prior Attempt Failed Validation` block in `question.j2`.
  - On second failure: raises `QuizGenerationError`. NO row persisted (FR-32 idempotency note).
  - Normalizes `concept_label` server-side via FR-34 pipeline before INSERT.
  - Persists `mcq_options_json` as `{options, correct_index}` for `shape='mcq'`; `intended_error` + `error_explanation` for `shape='spot_error'`.
- FR-33 spot-error validator: stem token-set difference vs. snippet must contain ≥1 negation/quantitative-flip token from a 40-word lexicon. Empty `intended_error` also fails.
- New `tests/unit/conftest.py` with `FakeLLMProvider`, `book_factory`, `section_factory` (promoted from inline fixtures per Phase 1 hand-off note).
- Helpers: `_fetch_scope_content` (`all_summaries` joins Summary→BookSection on default_summary_id; `specific_chapters` reads `BookSection.content_md` ordered); `_compute_shape_histogram` (last 5 questions in session); `_format_validator_error` (jsonschema vs. generic).

## Verification

- `uv run python -m pytest tests/unit/test_quiz_service_generate.py -v` → 6 passed in 0.77s (then 0.48s after format).
- `uv run ruff check ...` → All checks passed (after dropping a long inline comment).
- `uv run ruff format ...` → applied (auto-fixed 2 files).

## Notes

- DEVIATION: plan signature is `scope=...` only. Added optional `scope_content` kwarg so unit tests don't need full Summary fixtures. Real route handlers will pass `scope` and the helper resolves content. Plan otherwise honored.
- `_fetch_scope_content` joins on `Summary.id == BookSection.default_summary_id` so we get the user's selected summary per section, not all summaries (the Summary log can have multiple per section). `is_stale=False` filter applied on Summary.
- Spot-error retry test: I had to widen the lexicon to include `"any"` derivatives — actually `"NOT"` matches and `"worse"` differs from `"painful"` so the existing flip-set is sufficient (test passed).
- `last_exc` kept on the `_ = last_exc` line so static analyzers don't flag it as unused; the raise path uses it via `from e`.

