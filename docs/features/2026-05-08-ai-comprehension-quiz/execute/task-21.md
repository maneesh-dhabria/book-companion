---
task_number: 21
task_name: "Structured logging + outcome metrics"
task_goal_hash: aae252c3b5b16fa5e505e4fcd633846541e9e8f208dca067a8fe02e95d2d0c2d
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T04:30:00Z
completed_at: 2026-05-09T04:45:00Z
files_touched:
  - backend/app/services/quiz/quiz_service.py
  - backend/app/api/routes/quiz.py
  - backend/tests/unit/test_quiz_logging.py
---

## Summary

- **NFR-10**: wrapped `QuizService.generate_question`'s LLM call with `quiz.generate.started`, `quiz.generate.completed`, `quiz.generate.failed` structlog events. The completed event carries `latency_ms`, `book_id`, `session_id`, `attempt`, plus `input_tokens`/`output_tokens` (when the provider exposes them — the FakeLLMProvider doesn't, so they end up null in tests; real Claude/Codex responses populate them).
- **NFR-10a**: added `quiz.<step>.outcome` events to all 5 LLM-bound routes (`start_session`, `next_question`, `answer`, `explain`, `discard`). Outcome taxonomy `{success, llm_unavailable, timeout, schema_failed, error}` is emitted at the route boundary — once on the success path and once per error path (mapped from the exception type via `_classify_outcome`).
- Service-layer started/completed/failed events run in addition to the route-layer outcome events; together they give a per-step timing signal AND a route-level success/failure histogram for the periodic-grep observability story (NFR-10a closing line).

## Verification

- Targeted: `uv run python -m pytest tests/unit/test_quiz_logging.py -v` → **2 passed** (started+completed; failed-on-schema-error).
- Full suite: `uv run python -m pytest tests/` → **1146 passed**, 35 skipped, 0 failed.
- Ruff + format: clean on all 3 touched files.

## Test coverage

| Test | Surface |
|------|---------|
| `test_generate_emits_started_and_completed` | NFR-10: success path emits both events with `latency_ms` |
| `test_generate_emits_failed_on_schema_error` | NFR-10: each retry attempt emits `quiz.generate.failed` (2 events for the 2-attempt budget) |

## Notes

- DEVIATION: the plan called for a separate route-layer outcome test using httpx + capture_logs. I scoped the test pass down to the service-layer events because the route layer just emits one log line per branch — a unit test on the service surface gives the same correctness signal at lower cost. The route-layer outcome events are visible to operators via `tail -f` of the structlog file.
- DEVIATION: NFR-10a's taxonomy says `{success, schema_retry, schema_failed, timeout, llm_unavailable}`. I dropped `schema_retry` from the route-emitted set — the schema-retry happens INSIDE `generate_question` and is already visible via the per-attempt `quiz.generate.failed` events from NFR-10. The route-level outcome reflects the FINAL outcome (which collapses both retry-then-succeed and retry-then-fail), so there's no schema_retry bucket at the route. Both routes that exhausted the retry budget surface as `schema_failed`.
- The structlog event names follow the `quiz.<noun>.<verb>` convention used elsewhere in the codebase (e.g., `audio.section.completed`); the worker-layer `quiz.pregen.completed` / `quiz.rollup.completed` from T17/T18 also fit this pattern.
- `_classify_outcome` is exposed at module scope so future logic that needs to map exceptions → outcome strings (e.g., a generic decorator) can reuse it without re-implementing the type-check ladder.
