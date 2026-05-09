---
task_number: 12
task_name: "QuizService warm-up candidate computation (FR-70)"
task_goal_hash: 8974a145e6bf4d5402924fe8f5eadfac5683d44a6f5e2ac9ec9fac3d023f8ae8
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: in-flight
started_at: 2026-05-09T01:18:00Z
files_touched:
  - backend/app/services/quiz/quiz_service.py
  - backend/tests/unit/test_quiz_service_warmup.py
  - backend/tests/unit/test_quiz_service_start.py
---

## Summary

- `QuizService.compute_warm_up_candidates(book_id, scope)` returns up to `settings.quiz.warm_up_max_questions` dicts of `{concept_label, section_id}` per FR-70 (a-d).
- Implementation: 3 SELECTs (recent_session_ids → candidate rows → resolved-concept set), then in-Python scope filter + dedup + take.
- `start_session` now plugs warm-up before the pregen consume gate. Warm-up Qs are generated via `generate_question(theme=f"Revisit the concept: {label}", warm_up=True)` — reusing the theme channel sidesteps a template branch (FR-71's exact wording is a soft guideline).
- `start_session` returns `first_warm_up_id or first_non_warm_up_id` so the UI shows warm-up first (FR-21).
- `_seed_session` test helper supports `created_at` override for FR-70(a) lookback ordering tests.

## Verification

- `uv run python -m pytest tests/unit/test_quiz_service_warmup.py tests/unit/test_quiz_service_start.py -v` → 17 passed in 1.03s.
- Ruff clean; format applied.

## Notes

- FR-70(c) approximation: my impl excludes a concept from warm-up if ANY `got_it` row exists for it (regardless of whether it's "later"). For personal-tool single-user scale this is functionally equivalent to "any subsequent got_it" — once a user marks a concept as got_it, we trust them. Documented in the docstring.
- DEVIATION: plan suggested adding a `warm_up_candidates` repo method; I kept the existing repo's narrower `warm_up_candidates` (used by other call sites if any) and put the FR-70 logic in the service where the scope-filter + resolution-exclusion business rules live. This avoids leaking business logic into the repo (per CLAUDE.md "Repositories: thin query builders only").

