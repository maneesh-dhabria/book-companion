---
task_number: 15
task_name: "Listen-unavailable morph (FR-09)"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T15:56:00Z
completed_at: 2026-05-10T16:05:00Z
files_touched:
  - frontend/src/components/audio/AudioTab.vue
  - frontend/src/components/audio/__tests__/AudioTab.listenUnavailable.spec.ts
---

`listenAvailable` computed: `false` when (`'speechSynthesis' in window === false`) OR (`voicesReady && availableVoices.length === 0`). Drives `audioEmptyHeading` ("Listen to this book" → "Generate MP3s to listen to this book") and the Listen-CTA `:disabled` binding. The `<span id="listen-tip" class="sr-only">` is rendered ALWAYS (REVIEW-LOG #2) so the `aria-describedby` reference resolves regardless of state. SSR-safe via the `typeof window === 'undefined'` short-circuit. Implementation fused with T16 (single Edit pass on AudioTab) — see task-16.md for the consolidated layout polish. 2 new tests + full audio/quiz/stores regression (247) green.
