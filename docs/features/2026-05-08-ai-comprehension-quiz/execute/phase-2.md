---
phase: 2
phase_name: "Service Core"
tasks: [T6, T7, T8, T9, T10, T11, T12, T13]
verify_status: passed
verified_at: 2026-05-09T01:48:00Z
verify_evidence: docs/features/2026-05-08-ai-comprehension-quiz/verify/2026-05-09-phase-2/
---

## Phase 2 boundary verify — green

- **Targeted suite (`pytest tests/unit/ -k quiz`)**: 77 passed, 649 deselected, 0 failed.
- **Full suite (`pytest tests/`)**: 1101 passed, 35 skipped, 0 failed.
- **Ruff** on all Phase 2 files (`app/services/quiz/`, `app/templates/quiz/`, `app/exceptions.py`, `app/api/deps.py`, all `tests/unit/test_quiz_*.py`, `tests/unit/conftest.py`): clean. The lone E501 finding sits on `app/api/deps.py:149` for the `BackupService` constructor — pre-existing, unrelated to quiz scope, untouched by Phase 2.
- **Format** clean on all Phase 2 files.

## Commits this phase

- `feat(T6): add tiktoken dep + count_tokens helper`
- `feat(T7): QuizPromptBuilder + 4 Jinja2 prompt templates`
- `feat(T8): concept_label normalization pipeline (FR-34)`
- `feat(T9): QuizService skeleton + JSON schemas + DI wiring`
- `feat(T10): generate_question with strict-schema retry + spot-error validator`
- `feat(T11): start_session with pregen-Q1 4-condition consume`
- `feat(T12): warm-up candidate computation (FR-70 all branches)`
- `feat(T13): grade_answer + skip + explain + override + discard + dedup query`

## Hand-off notes for Phase 3

- **QuizService.start_session** returns `{session_id, question_id, queue_hit, warm_up_count}`. T15's `POST /api/v1/books/{book_id}/quiz-sessions` route maps `QuizValidationError → 400`, `QuizBudgetError → 422`, `QuizGenerationError → 502`. Currently the service rolls back on any failure — the route should NOT also rollback.
- **discard_question** delegates next-question generation through `generate_question` with `scope_content` provided by the route. The route MUST fetch scope_content from the session's `scope_mode` + `scope_section_ids`. For `all_summaries`, that's an extra `_fetch_scope_content` call before `discard_question`. Or expose a `discard_question(question_id, scope)` overload that reads from the session row — T15's call.
- **Active-session resume banner (FR-19, T16)**: `session_repo.get_in_progress_for_book(book_id)` is the gate; route returns it via `GET /api/v1/books/{id}/quiz-sessions/active`.
- **Atomic stop_session (T16)**: not implemented yet; T16 wraps `update_status('completed')` + clear-active-banner SSE.
- **Pregen worker (T17)**: enqueue `QUIZ_PREGEN_Q1` after summarize completes. Reuse `generate_question(book_id, session_id=None, scope={"mode": "all_summaries"}, theme=None, warm_up=False)` then write `book.pre_drafted_q1_id = qq.id`.
- **Re-import extension (T20)**: call `question_repo.mark_stale_for_book(book_id)` + `dedup_repo.reset(book_id)` + clear `book.pre_drafted_q1_id`.
- **Frontend state machine (T26)**: the `start_session` response shape (`queue_hit` / `warm_up_count`) drives the initial state — `warm_up_count > 0 ⇒ WarmUpBanner`; else `queue_hit ⇒ pregen-served-Q1` toast; else `cold-start`.
- **`agent_verdict` is backend-only (S9)**. The route MUST strip it from `feedback_json` when serializing the question for the API — `grade_answer` already returns the UI-shape dict with verdict hidden, but `GET /api/v1/quiz-sessions/{sid}` reads from the persisted column and must filter at the response layer.

## Open follow-ups (not blockers)

- T13 deviation: `discard_question`'s discarded-stems signal goes through the `theme` channel (cheap reuse). If FR-47 wording fidelity matters, T15 / Phase 3 can add a dedicated `discarded_stems` template branch.
- The plan also called for `tests/unit/test_quiz_service_dedup.py` covering `recent_stems`; that's already covered by `tests/unit/test_quiz_repos.py::test_question_recent_stems_filters_stale_discarded_skipped` from T5 — duplicate skipped.
- FEEDBACK_SCHEMA was widened from `feedback: string` to `feedback: object{correct,missing,actual}` between T9 and T13. T9's schema test was updated in-place to assert the new shape.
