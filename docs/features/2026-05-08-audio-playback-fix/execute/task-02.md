---
task_number: 2
task_name: "Update WebSpeechEngine — voice-wait, watchdog, idempotency"
plan_path: "docs/plans/2026-05-08-audio-playback-fix-implementation-plan.md"
branch: "feature/audio-playback-fix"
worktree_path: ".worktrees/audio-playback-fix"
status: done
started_at: 2026-05-08T00:01:00Z
completed_at: 2026-05-08T00:05:00Z
files_touched:
  - frontend/src/composables/audio/webSpeechEngine.ts
  - frontend/src/composables/audio/__tests__/webSpeechEngine.spec.ts
---

Implemented voice-wait (1.5s addEventListener+timeout), watchdog (1s), idempotent play (isSpeaking flag), late-onstart guard (cancels stale audio if errorEmitted). pause/next/prev/seek/terminate now all cancel both watchdog and voice-wait.

DEVIATION (test only): the existing test "emits engine_unavailable when getVoices returns empty" tested the OLD synchronous-fail behavior. It was removed and replaced by "waits for voiceschanged when getVoices is empty, then speaks once voices arrive" + "emits engine_unavailable after 1500ms timeout" per plan FR-05/FR-06.

13 tests pass.
