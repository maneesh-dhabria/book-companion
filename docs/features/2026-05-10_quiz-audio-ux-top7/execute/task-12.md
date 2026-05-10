---
task_number: 12
task_name: "ScopePicker chapter+reading metric (FR-21)"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T15:31:00Z
completed_at: 2026-05-10T15:42:00Z
files_touched:
  - frontend/src/components/quiz/ScopePicker.vue
  - frontend/src/components/quiz/__tests__/ScopePicker.readingMetric.spec.ts
  - frontend/src/components/quiz/__tests__/ScopePicker.spec.ts
  - frontend/src/api/settings.ts
---

Replaced the "0 / 60,000 tokens" budget label with a chapter+reading metric: `{X} of {N} chapters · ~{Y} min reading`, plural-aware on the denominator (`1 of 1 chapter`, `0 of 12 chapters`). Reading minutes = `Σ word_count(selected) / settings.reading.reading_wpm` (default 250 when settings not loaded). Token cap kept as `<title>` tooltip on the label so the budget stays inspectable. Mode tabstrip now carries `role="tablist"` + `role="tab"` + `aria-selected`. `AppSettings` interface extended with `tts.listen_wpm` and `reading.reading_wpm` (matching the backend T5 fields). Added Pinia setup to existing `ScopePicker.spec.ts` beforeEach (the store is now a real dependency). 5 new tests + full quiz/stores regression (169) green; vue-tsc clean.
