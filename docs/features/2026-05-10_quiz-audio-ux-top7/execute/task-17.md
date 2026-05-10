---
task_number: 17
task_name: "EnginePicker segmented control + populated layout (FR-11)"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T16:06:00Z
completed_at: 2026-05-10T16:14:00Z
files_touched:
  - frontend/src/components/audio/EnginePicker.vue
  - frontend/src/components/audio/AudioTab.vue
  - frontend/src/components/audio/__tests__/EnginePicker.spec.ts
  - frontend/src/stores/ttsPlayer.ts
---

New `EnginePicker.vue`: `role="radiogroup"` two-segment control with v-model on `TtsEngineKind` (`'mp3' | 'web-speech'`). Each segment is `role="radio"` + `aria-checked` + `data-engine`. Click on the same segment is a no-op. Wired into AudioTab populated/full branches inside a `flex flex-wrap items-center gap-3` row (`data-testid="audio-engine-row"`). Default per FR-11/D11: `coverage.generated >= 1 → 'mp3'` else `'web-speech'`, set in `syncDefaultEngine()` after inventory loads. `onEngineChange` mirrors the local ref into `ttsPlayer.setEngine` so T18's restart-section logic sees the same value.

Store: `setEngine(kind)` stub added to `ttsPlayer` (full mid-playback restart-section logic lives in T18). 3 new tests + audio/stores regression (162) green; vue-tsc clean.

REVIEW-LOG #10 regenerate-CTA caption deferred to T19/T21 modal work — that copy lives on the Generate-audio modal, not on the populated AudioTab branch.
