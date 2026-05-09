---
task_number: 2
task_name: "Add Quiz ORM models + Book.pre_drafted_q1_id column"
task_goal_hash: 67ccdbce9d6e591f064ca7708a2f78afd60213dd44232ec62f5f64720f6d0bd7
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T00:01:30Z
completed_at: 2026-05-09T00:08:00Z
files_touched:
  - backend/app/db/models.py
  - backend/tests/unit/test_quiz_models.py
---

## Outcome

Added 3 ORM models (`QuizSession`, `QuizQuestion`, `QuizDedupState`) at end of `backend/app/db/models.py` mirroring spec §10.1 DDL. Added `Book.pre_drafted_q1_id` FK column with `use_alter=True` (resolves circular FK with `quiz_questions.id`). Imported `CheckConstraint` and added 5 named CHECK constraints on `QuizQuestion` (shape/bloom/agent_verdict/self_assessment + shape-conditional payload), 2 on `QuizSession` (scope_mode + status). Added 3 indexes on `QuizQuestion`, 2 on `QuizSession`.

## Deviations from plan

- Added book_factory fixture inline in `test_quiz_models.py` (plan §T2.Step1 said "add to conftest if missing"); kept local for now to scope blast-radius. T5 will need it again — will promote to conftest then.
- Plan example uses `JSON` type for `scope_section_ids` and `Text` for `mcq_options_json` etc.; spec DDL uses TEXT for both. Followed spec: `JSON` for `scope_section_ids` (SQLAlchemy serializes to TEXT in SQLite), `Text` for `mcq_options_json` / `citation_json` / etc. (raw JSON strings, no implicit deserialization — service code will `json.loads()` explicitly).

## Verification evidence

- `pytest tests/unit/test_quiz_models.py -v` → 8 passed (round-trip, scope_mode CHECK, mcq missing options CHECK, open with bloom=create, spot_error CHECK, dedup_state round-trip, pre_drafted_q1_id nullable, ProcessingStep enum).
- `pytest tests/unit/ -q` → 652 passed, 5 skipped (was 644 + 8 new = 652; zero regressions).
