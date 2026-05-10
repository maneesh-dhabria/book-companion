---
task_number: 20
task_name: "FR-14 Modal close-X + dialog semantics + Esc-to-close"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T16:43:00Z
completed_at: 2026-05-10T16:46:00Z
files_touched:
  - frontend/src/components/audio/GenerateAudioModal.vue
  - frontend/src/components/audio/__tests__/GenerateAudioModal.dialog.spec.ts
---

Existing dialog attrs (`role="dialog"`, `aria-modal="true"`, `aria-labelledby="gen-audio-title"`) verified by test 1; were already present from prior wireframes-review hardening so this task only landed the user-visible affordances. Added close-X icon button at top-right with `aria-label="Close generate audio dialog"` and a `keydown.esc` handler on the dialog wrapper (`tabindex="-1"` so the wrapper can receive the keydown). Both fire `emit('close')`. The h2 carries `pr-8` so the heading doesn't crash into the X button.

3 new tests; 12/12 GenerateAudioModal specs green.
