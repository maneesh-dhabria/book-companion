---
task_number: 4
task_name: "FR-02 claude_cli stderr capture characterisation"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T00:11:00Z
completed_at: 2026-05-10T00:14:00Z
files_touched:
  - backend/tests/unit/services/__init__.py
  - backend/tests/unit/services/test_claude_cli_stderr_capture.py
---

DEVIATION (logged): plan/spec assert `STDERR_TRUNCATE = 2048`, but live code constant is 500 (`claude_cli.py:23`). Honoring the "verify, not modify" mandate of FR-02, the test asserts against the module's actual `STDERR_TRUNCATE` rather than the spec literal — both edge-case (`len == STDERR_TRUNCATE`) and full-capture invariants are enforced. 3 tests pass on existing code; no source changes. The spec section §16 / FR-02 should be amended to reflect 500, OR claude_cli.py raised to 2048 in a follow-up — flagging to parent for resolution.
