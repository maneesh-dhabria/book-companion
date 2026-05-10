---
task_number: 24
task_name: "FR-18 Engine chip transitions during A/B playback"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T17:00:00Z
completed_at: 2026-05-10T17:03:00Z
files_touched:
  - frontend/src/components/settings/SpikeFindingsBlock.vue
  - frontend/src/components/settings/__tests__/SpikeFindingsBlock.engineChip.spec.ts
---

Added a transient `bc-chip bc-chip--engine` chip (testid `engine-chip`, `aria-live="polite"`) next to the Listen-to-comparison button. Click → chip text "Playing Kokoro (af_sarah)…" while Kokoro audio plays. On `<audio>.ended` the chip transitions to "Playing Web Speech…" and Web Speech utterance is queued. On the utterance's `onend`, a 1000ms timer clears the chip.

Restructured the click handler so Web Speech is now triggered FROM Kokoro's `ended` listener (was previously fire-and-forget in parallel). This matches the wireframe sequence — the user hears Kokoro first, then Web Speech, with chip text reflecting which one. If the Kokoro fetch fails, chip flips straight to "Playing Web Speech…" (covered by Flow #3 of the TN smoke later).

1 new test; 6/6 SpikeFindingsBlock specs green; vue-tsc clean.
