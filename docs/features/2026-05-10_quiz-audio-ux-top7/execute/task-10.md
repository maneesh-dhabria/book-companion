---
task_number: 10
task_name: "InlineDiagnostic.vue + QuizTab integration (FR-05)"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T15:11:00Z
completed_at: 2026-05-10T15:18:00Z
files_touched:
  - frontend/src/components/quiz/InlineDiagnostic.vue
  - frontend/src/components/quiz/QuizTab.vue
  - frontend/src/components/quiz/ScopePicker.vue
  - frontend/src/components/quiz/__tests__/InlineDiagnostic.spec.ts
---

New `InlineDiagnostic.vue` renders `{reason}` paragraph + optional `<details>` for `stderrTail` + Dismiss link (no Retry — that lives on the toast). Mounts in QuizTab between ScopePicker and ThemesCoveredPanel; bound to `store.inlineDiagnostic`. ScopePicker now emits `change` whenever scopeMode/selectedSectionIds/theme mutate (deep watcher) — wired to `store.clearInlineDiagnostic` so any input edit dismisses the diagnostic. `onStartFromScope` swallows the rethrown `ApiError` (toast/inline already display the error). 4 new tests + full quiz/stores regression (161) green; vue-tsc clean.
