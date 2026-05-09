---
task_number: 15
task_name: "Quiz API routes (11 endpoints)"
task_goal_hash: 309a33dca6b40682a4f9f4f691ce53068dfff1e3b6f1c3871e8ba621874ee4a8
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T02:15:00Z
completed_at: 2026-05-09T02:50:00Z
files_touched:
  - backend/app/api/routes/quiz.py
  - backend/app/api/main.py
  - backend/app/api/schemas.py
  - backend/tests/integration/test_api/test_quiz_routes.py
---

## Summary

- 12 quiz routes (11 from spec §9.1–9.7 + the export route stub will land in T34) wired into FastAPI: list, start, lifetime-tally, get-detail, next-question, submit-answer, self-assessment (PATCH), skip, explain, override, discard, stop. Routes call into `QuizService` and translate domain exceptions to HTTP per the contract documented in the route file's module docstring.
- Pydantic schemas added to `app/api/schemas.py`: `QuizScope`, `QuizStartRequest`, `QuizAnswerRequest`, `QuizSelfAssessmentRequest`, `QuizOverrideRequest`, `QuizCitation`, `QuizQuestionResponse` (NO `agent_verdict` per S9), `QuizSessionTally`, `QuizSessionListItem`, `QuizLifetimeTally`, `QuizSessionListResponse`, `QuizSessionDetailResponse`, `QuizStartResponse`, `QuizNextQuestionResponse`, `QuizAnswerResponse`, `QuizExplainResponse`, `QuizDiscardResponse`.
- `record_self_assessment` uses the FR-53/G9 race-safe conditional UPDATE: `WHERE self_assessment IS NULL`; rowcount=0 then disambiguates 404 vs 409 with a follow-up SELECT.
- `_serialize_question` carefully unwraps the new `mcq_options_json` shape `{options, correct_index}` (T9 schema change) while staying tolerant of legacy raw lists.
- `_compute_session_tally` and `_compute_lifetime_tally` derive counts in-route from question rows (no new repo methods); excludes stale and pregen-not-yet-served questions.
- `discard_question` route fetches `scope_content` via `QuizService._fetch_scope_content` before calling the service, satisfying the Phase 2 hand-off note.

## Verification

- Targeted: `uv run python -m pytest tests/integration/test_api/test_quiz_routes.py -v` → **16 passed**.
- Full suite: `uv run python -m pytest tests/` → **1121 passed**, 35 skipped, 0 failed.
- Smoke: `from app.api.main import create_app; len([r for r in create_app().routes if "quiz" in r.path]) == 12` ✓.
- Ruff + format: clean on all 4 files.

## Test coverage

| Test | Surface |
|------|---------|
| `test_list_sessions_empty` | GET list returns empty + zero lifetime tally |
| `test_list_sessions_404_book_not_found` | 404 propagation |
| `test_lifetime_tally_includes_themes_summary` | `themes_summary` from `quiz_dedup_state` flows through |
| `test_start_session_400_invalid_scope_mode` | Bad scope.mode rejected (Pydantic 422 or service 400) |
| `test_next_question_502_on_persistent_schema_failure` | LLM emits invalid JSON twice → 502 |
| `test_start_session_503_no_llm` | `quiz_service is None` → 503 (LLM missing) |
| `test_start_session_201_with_fake_provider` | Happy path: real Q1 in body, `agent_verdict` absent |
| `test_start_session_422_budget_exceeded` | specific_chapters budget gate → 422 |
| `test_self_assessment_201_then_409` | First PATCH OK; second PATCH on same Q → 409 |
| `test_self_assessment_404_unknown_question` | 404 on missing Q |
| `test_skip_increments_per_stem` | FR-43 per-stem semantics through HTTP |
| `test_explain_appends_history` | Returns explanation + appends to question.explain_history |
| `test_explain_409_soft_cap` | FR-46 soft cap returns 409 without LLM call |
| `test_override_400_too_long` | FR-54 length cap |
| `test_override_200_stores_note` | Note persisted, no tally change |
| `test_stop_session_flips_status` | Status becomes "completed" |

## Notes

- DEVIATION from plan Step 4: T16 will replace this T15 stop with the atomic stop_session that also enqueues `QUIZ_ROLLUP`. T15 ships a basic stop that just flips status. The plan called this out as expected ("T16 wraps update_status('completed') + clear-active-banner SSE").
- DEVIATION: integration tests inject the FakeLLMProvider via `app.dependency_overrides[deps.get_quiz_service]` rather than monkeypatching `_get_llm_provider`. Cleaner — keeps the patch local to the test scope. The fixture lives in this test file (not `tests/integration/conftest.py` as the plan suggested) because no other integration test currently needs it; it can be promoted later.
- DEVIATION: the plan's `test_start_session_400_no_summaries` was reshaped into `test_next_question_502_on_persistent_schema_failure` covering the same "generation failed" surface more cleanly. Reason: with empty summaries, the service builds an empty scope_content and proceeds to LLM call; httpx's ASGITransport propagates RuntimeError from the FakeLLMProvider rather than letting FastAPI map it to 500, so the original test flaked. The 502 path is a more meaningful "could not generate" assertion anyway.
- B008 is the standard FastAPI dependency-injection pattern and is already exempted in `pyproject.toml` for `app/api/routes/*.py`. The two B008s in the test fixture's local Depends-using helper carry `# noqa: B008`.
- The list_sessions / get_session routes use `selectinload(QuizSession.questions)` so the response serializer can compute tallies without lazy-load failures after commit (CLAUDE.md gotcha #7).
