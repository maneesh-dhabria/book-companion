---
task_number: 18
task_name: "setEngine mid-playback restart-section (FR-12)"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T16:15:00Z
completed_at: 2026-05-10T16:22:00Z
files_touched:
  - frontend/src/stores/ttsPlayer.ts
  - frontend/src/stores/__tests__/ttsPlayer.engineToggle.spec.ts
---

`setEngine(kind)` now: same-kind = no-op; otherwise, if status was `playing` or `starting` it calls `useTtsEngine().pauseActive()` (engine-aware: handles both `<audio>.pause()` and `speechSynthesis.cancel()` through the existing routing), resets `sentenceIndex` to 0 (no word-position carryover, FR-12), flips `engine.value`, and re-issues `playActive()` so the new engine starts from the section's first sentence.

DEVIATION from plan code sketch: plan referenced raw `audioEl?.pause()` / `speechSynthesis?.cancel()` calls inside the store. The codebase already abstracts both engines behind `useTtsEngine().pauseActive()` / `playActive()` — going through that layer keeps the engine-routing single-sourced and the test stubs trivial (the existing `vi.mock('@/composables/audio/useTtsEngine')` shim from `ttsPlayer.spec.ts` continues to work). Idle-toggle path verified: only the ref flips, no playback re-issue. 3 new tests + audio/quiz/stores regression (253) green; vue-tsc clean.

**Phase 4 complete.** All audio empty + populated tasks (T14-T18) landed. Halt point per session policy: pausing at Phase 4/5 boundary so user can /compact before resuming with Phase 5 (Generate-audio modal) + Phase 6 (Settings TTS) + TN.
