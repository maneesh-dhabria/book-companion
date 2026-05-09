---
task_number: 3
task_name: "Alembic migration v1_7a_quiz_tables"
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T00:09:00Z
completed_at: 2026-05-09T00:14:00Z
files_touched:
  - backend/app/migrations/versions/5f91e6f6cdc7_v1_7a_quiz_tables.py
  - backend/tests/integration/test_quiz_migration.py
---

## Outcome

Single migration `5f91e6f6cdc7_v1_7a_quiz_tables.py` creates 3 tables (quiz_dedup_state, quiz_sessions, quiz_questions) + Book.pre_drafted_q1_id column + 6 indexes (incl. partial `ix_books_pre_drafted_q1`). Round-trip test (up → down → up) passes.

## Deviations from autogenerate

Stripped from autogen output (out of T3 scope):
- `op.drop_table('search_fts*')` × 5 — FTS5 shadow tables created at runtime by triggers, NOT in metadata. Dropping breaks search.
- `annotations.content_type` enum widening (VARCHAR(15) → Enum incl. ANNOTATION) — pre-existing intentional drift per migration `a8b9c0d1e2f3` (FR-21: ANNOTATION is runtime-only, not in DB CHECK).
- `processing_jobs.step` enum widening (VARCHAR(13) → Enum incl. QUIZ values) — column has no CHECK constraint in actual DB; SQLite VARCHAR length is advisory; runtime stores new enum values fine.

Added manually: partial index `ix_books_pre_drafted_q1 ... WHERE pre_drafted_q1_id IS NOT NULL` (autogen does not emit partial indexes from `Index(..., sqlite_where=...)` — used `op.execute` instead).

## Bugs caught & fixed

- **Downgrade failure**: `batch_alter_table('books', drop_column('pre_drafted_q1_id'))` reflects existing indexes and tries to recreate the partial index against the dropped column. Fix: `DROP INDEX IF EXISTS ix_books_pre_drafted_q1` BEFORE the batch_alter_table block.

## Verification evidence

- `pytest tests/integration/test_quiz_migration.py -v` → 1 passed (alembic up → down -1 → up + schema sanity assertions for all 3 tables, books column, and 4 key indexes).
