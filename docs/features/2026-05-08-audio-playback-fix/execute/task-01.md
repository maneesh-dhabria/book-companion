---
task_number: 1
task_name: "Extend TtsEngine interface"
plan_path: "docs/plans/2026-05-08-audio-playback-fix-implementation-plan.md"
branch: "feature/audio-playback-fix"
worktree_path: ".worktrees/audio-playback-fix"
status: done
started_at: 2026-05-08T00:00:00Z
completed_at: 2026-05-08T00:01:00Z
files_touched:
  - frontend/src/composables/audio/types.ts
---

Added `WaitingForVoicesHandler` type and three new methods (`startWatchdog`, `cancelWatchdog`, `onWaitingForVoices`) to the `TtsEngine` interface. Type-check confirmed both engines now fail to implement, exactly as plan step 2 expected. Commit deferred to bundle with T2 + T3 per plan T3 step 7.
