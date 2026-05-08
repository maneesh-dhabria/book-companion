---
task_number: 3
task_name: "Update Mp3Engine — watchdog, idempotency"
plan_path: "docs/plans/2026-05-08-audio-playback-fix-implementation-plan.md"
branch: "feature/audio-playback-fix"
worktree_path: ".worktrees/audio-playback-fix"
status: done
started_at: 2026-05-08T00:05:00Z
completed_at: 2026-05-08T00:08:00Z
files_touched:
  - frontend/src/composables/audio/mp3Engine.ts
  - frontend/src/composables/audio/__tests__/mp3Engine.spec.ts
---

Implemented `startWatchdog`/`cancelWatchdog` (event-based — cancelled by 'playing' event), no-op `onWaitingForVoices`, idempotent `play()` (returns early if `!paused && !ended`). pause/next/prev call `cancelWatchdog`. terminate also cancels.

42 audio tests pass; type-check clean. Committed bundled with T1+T2 per plan T3 step 7.
