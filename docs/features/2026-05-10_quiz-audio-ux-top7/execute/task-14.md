---
task_number: 14
task_name: "AudioTab voice-list pre-warm (FR-08)"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T15:51:00Z
completed_at: 2026-05-10T15:55:00Z
files_touched:
  - frontend/src/components/audio/AudioTab.vue
  - frontend/src/components/audio/__tests__/AudioTab.prewarm.spec.ts
---

`onMounted` now races `voiceschanged` against a 500ms `setTimeout` (mutex via `resolved` flag). `voicesReady` flips once either path fires; `availableVoices` is refreshed at the same moment. When `window.speechSynthesis` is absent entirely (private mode, hardened browsers), `voicesReady` flips immediately so downstream FR-09 morph can render. `defineExpose` opens `voicesReady` + `availableVoices` to the mount-based pre-warm test (the natural test seam — no public API change otherwise). 3 new tests + full audio regression (72) green.
