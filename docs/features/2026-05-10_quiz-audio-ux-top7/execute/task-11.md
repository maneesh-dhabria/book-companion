---
task_number: 11
task_name: "Mid-session retry inline (FR-06)"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T15:19:00Z
completed_at: 2026-05-10T15:30:00Z
files_touched:
  - frontend/src/stores/quizSessions.ts
  - frontend/src/stores/__tests__/quizSessions.midSession.spec.ts
  - frontend/src/components/quiz/ActiveSession.vue
  - frontend/src/components/quiz/__tests__/ActiveSession.midSessionRetry.spec.ts
---

DEVIATION from plan: plan T11 says render the inline-error block in `QuizTab.vue` ("the question-card surface lives inline here — code-study confirmed no `QuestionCard.vue`"). Code-study during implementation found the question-card surface actually lives in `ActiveSession.vue` (which `QuizTab` mounts when `mode === 'active'`); `QuizTab.vue` only handles ready/no-llm/resume modes, never renders questions. Rendered the inline-error block in `ActiveSession.vue` next to the question card where users will actually see it.

Store: added `midSessionError` ref `{message, action}` + `retryMidSession()` action that calls the captured action, clears on success. Wrapped `loadNextQuestion` and `submitAnswer` to capture-and-rethrow via `captureMidSessionError`. UI: inline alert block (`role="alert"`, `data-testid="mid-session-error"`, `data-action="retry"`) renders between LoadingSpinner and QuestionTurn. No toast fires. 3 new tests (2 store + 1 mount) green; full quiz/stores regression (164) green.
