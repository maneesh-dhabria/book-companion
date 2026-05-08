---
task_number: 4
task_name: "useTtsEngine helpers + onWaitingForVoices wiring + load->paused"
plan_path: "docs/plans/2026-05-08-audio-playback-fix-implementation-plan.md"
branch: "feature/audio-playback-fix"
worktree_path: ".worktrees/audio-playback-fix"
status: done
started_at: 2026-05-08T00:08:00Z
completed_at: 2026-05-08T00:11:00Z
files_touched:
  - frontend/src/composables/audio/useTtsEngine.ts
  - frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts
  - frontend/src/stores/ttsPlayer.ts
---

Added module-level `playActive/pauseActive/nextActive/prevActive/seekActive` helpers that delegate to `lastEngine`; `playActive` calls `store.setError('engine_unavailable')` when no engine exists. Wired `engine.onWaitingForVoices` -> `store.status='starting'` (with FR-20 error-state guard). `load()` flips `loading` -> `paused` defensively (skips if `error`).

DEVIATION: Plan T4 step 1 RED test asserts `store.status === 'starting'`, which requires `'starting'` to be in the `TtsStatus` union. Plan T5 step 3 lists adding it as part of T5. I moved that one-line type-union change into T4 — without it, T4's wiring code would not type-check (plan T4 step 5 also requires zero type errors). Documented here; no functional impact.

12/12 useTtsEngine tests pass; type-check clean.
