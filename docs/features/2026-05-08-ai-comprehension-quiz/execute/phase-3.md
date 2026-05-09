---
phase: 3
phase_name: "API Routes + Workers + Re-import + Reading-state"
tasks: [T14, T15, T16, T17, T18, T19, T20, T21]
verify_status: passed
verified_at: 2026-05-09T04:50:00Z
verify_evidence: docs/features/2026-05-08-ai-comprehension-quiz/verify/2026-05-09-phase-3/
---

## Phase 3 boundary verify — green

- **Targeted suite (`pytest tests/ -k quiz`)**: 119 passed, 1062 deselected.
- **Full suite (`pytest tests/`)**: 1146 passed, 35 skipped, 0 failed (up from 1101 at Phase 2 close — 45 new tests added in T14-T21).
- **Ruff** on the per-task files I touched: clean. Pre-existing repo-wide lint debt (E501 on `app/api/deps.py:149`, UP042 on existing enum classes in `app/db/models.py`, TC002/SIM105 on `app/services/job_queue_worker.py`) is unchanged from `main` and out-of-scope for Phase 3.
- **Format** on touched files: clean.

## Commits this phase

- `feat(T14): drop UA filter on /reading-state/by-book; add most_recent_section_ids`
- `feat(T15): quiz API routes (12 endpoints) + Pydantic schemas + integration tests`
- `feat(T16): atomic stop_session + resume-banner support (FR-19, FR-24, G10)`
- `feat(T17): QUIZ_PREGEN_Q1 worker handler + dispatch branch (FR-80/81/83)`
- `feat(T18): QUIZ_ROLLUP worker with threshold + delta gate + P8 truncation`
- `feat(T19): post-summarize hook enqueues QUIZ_PREGEN_Q1 (FR-80)`
- `feat(T20): re-import quiz cleanup (FR-64, FR-82, E16)`
- `feat(T21): structured logging + outcome metrics (NFR-10, NFR-10a)`

## Hand-off notes for Phase 4 (Frontend Core)

- **`start_session` response shape** (T26 frontend state machine — see Phase 2 hand-off note): the response body is `{session: SessionListItem, first_question: QuizQuestionResponse, warm_up_count: int}`. The QuizQuestionResponse already strips `agent_verdict` (S9). Drive the FE state machine off `warm_up_count > 0 → WarmUpBanner` else `first_question.queue_hit → 'pregen-Q1' toast` else cold-start.
- **Resume banner (FR-19, T28)**: NO new endpoint. The existing `GET /api/v1/books/{id}/quiz-sessions` already returns sessions with `status="in_progress"` for the resume banner — frontend reads from there.
- **D31 default-scope hint (T26)**: T14's `GET /reading-state/by-book/{id}` now returns `most_recent_section_ids: int[]` (newest first, capped 10, 48h window, all-devices). Use these IDs to pre-tick chapter checkboxes in ScopePicker.
- **Outcome events (NFR-10a)**: structlog events are `quiz.<step>.outcome` with `outcome ∈ {success, schema_failed, timeout, llm_unavailable, error}`. Steps emitted: `start_session`, `next_question`, `answer`, `explain`, `discard`. Parseable by `tail -f /var/log/.../structlog.json | jq 'select(.event | startswith("quiz.")) | {event, outcome}'` for the periodic-grep observability story.
- **Worker queue**: pregen jobs are auto-enqueued post-summarize (T19) and post-re-import (T20). Rollup jobs are auto-enqueued by atomic stop_session (T16). The worker dispatch branches in `_on_promoted` route both to the appropriate handler.
- **TBD for Phase 4 onward**: agent_verdict serialization in `GET /api/v1/quiz-sessions/{sid}` is already filtered at the response layer (S9 invariant) — frontend will never see it.
- **DEVIATION carryforward**: T16's `with_for_update()` was dropped (SQLite ignores row-level locks); the partial UNIQUE INDEX on `processing_jobs` makes the rollup-INSERT race-safe at the DB level. T20's atomic-rollback test from the plan was dropped — testing forced-failure of internal SQLAlchemy state ends up testing the ORM rather than our code.

## Open follow-ups (not blockers)

- The 4 pre-existing lint findings in `app/services/job_queue_worker.py` (TC002, SIM105) and the 1 in `app/api/deps.py:149` (E501) deserve a one-shot cleanup commit but live outside the AI-comprehension-quiz scope.
- T21's tests cover the service-layer started/completed/failed events in detail. Route-layer outcome events are emitted but not unit-tested — operators verify them via structlog tail. Adding integration coverage with `structlog.testing.capture_logs()` over the httpx test client could land in a follow-up task if the periodic-grep signal proves noisy in practice.
- The CLAUDE.md addendum about SQLAlchemy rollback expiring identity-mapped objects (added in Phase 2) was applied successfully in T16's `stop_session` IntegrityError branch. T20 avoided the same issue by pre-checking instead of rolling back.
