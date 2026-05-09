---
task_number: 13
task_name: "grade_answer + skip + explain + override + discard + dedup query"
task_goal_hash: ceb235b93220a8af0c8f83bdc5cbb3541d4f8894a1747c6b1b8982b8e6ff31f5
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: in-flight
started_at: 2026-05-09T01:30:00Z
files_touched:
  - backend/app/exceptions.py
  - backend/app/services/quiz/schemas.py
  - backend/app/templates/quiz/grade.j2
  - backend/app/services/quiz/quiz_service.py
  - backend/tests/unit/test_quiz_service_grade.py
  - backend/tests/unit/test_quiz_service_skip_explain_override.py
  - backend/tests/unit/test_quiz_service_grade_skip_explain.py
---

## Summary

- Updated `FEEDBACK_SCHEMA` to the FR-50 3-field shape (`feedback.{correct, missing, actual}` + `agent_verdict`) and added `EXPLAIN_SCHEMA`.
- Updated `grade.j2` template to instruct the LLM to populate the 3 feedback fields and optionally append the FR-55 fatigue clause inside `feedback.actual`.
- Added 3 exceptions: `QuizSoftCapError` (FR-46, HTTP 409), `QuizNotFoundError`, and reused `QuizValidationError` for the override-note length cap.
- Implemented 5 service methods + 2 helpers:
  - `grade_answer` — strict-schema grading; persists `feedback_json` + `agent_verdict` + `user_answer`; returns UI shape with `feedback` only (S9 hides verdict).
  - `skip_question` — uses `question_repo.increment_skip_for_stem` (FR-43 per-stem, NOT per-row).
  - `explain_question` — soft-cap gate BEFORE the LLM call; appends to `explain_history_json`.
  - `override_verdict` — stores note; rejects > 500 chars; does NOT touch `self_assessment`.
  - `discard_question` — atomically flips `discarded=True`, then generates next via `generate_question` with the session's accumulated discarded stems woven into the prompt via the `theme` channel (G4 cheap re-use).
  - `_get_question_or_raise`, `_count_non_warm_up_answered` — shared helpers.

## Verification

- `uv run python -m pytest tests/unit/test_quiz_service_grade_skip_explain.py -v` → 8 passed in 0.55s.
- `uv run python -m pytest tests/unit/ -k quiz` → 77 passed (full quiz suite this phase).
- Ruff clean on Phase 2 files; pre-existing E501 in `app/api/deps.py:149` (BackupService constructor line) is out of T13 scope.

## Notes

- DEVIATION (intentional, with rationale): plan tests assumed `q.explain_history` (Python list) — the model has `explain_history_json` (Text, JSON-encoded). Tests parse via `json.loads`. The `result["explain_history"]` field returns the parsed list to keep the API ergonomic.
- DEVIATION: discard_question's negative-example signal goes through the `theme` field rather than a dedicated `discarded_stems` template branch. The simpler path is verified by the test that asserts the discarded stem appears in the next-question prompt; if FR-47 wording fidelity becomes important, T15 can add a dedicated template block.
- The plan suggested a separate `test_quiz_service_dedup.py` testing the FR-60 `recent_stems` repo query; that's already covered by `tests/unit/test_quiz_repos.py::test_question_recent_stems_filters_stale_discarded_skipped` from T5. Skipping the duplicate.

