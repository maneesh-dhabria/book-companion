---
task_number: 9
task_name: "quizSessions store error flow (FR-05/FR-07)"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T15:00:00Z
completed_at: 2026-05-10T15:10:00Z
files_touched:
  - frontend/src/stores/quizSessions.ts
  - frontend/src/stores/__tests__/quizSessions.errorFlow.spec.ts
---

Wrapped `startSession` in try/catch — on `ApiError`, surfaces D15-substituted message via `ui.showToast` (actionable, sticky, `dedupeKey: 'quiz-start'`) and populates a new `inlineDiagnostic` ref. Retry action re-invokes `startSession(bookId, scope, theme)` with original args; on resolve clears toast via `clearByKey` + nulls inline ref. Empty `e.message` and HTML bodies trigger the fallback string from D15. 4 new tests (object-detail / empty / HTML / retry-success) green; full store suite (82 tests) green.
