---
task_number: 5
task_name: "Wire ttsPlayer store"
plan_path: "docs/plans/2026-05-08-audio-playback-fix-implementation-plan.md"
branch: "feature/audio-playback-fix"
worktree_path: ".worktrees/audio-playback-fix"
status: done
started_at: 2026-05-08T00:11:00Z
completed_at: 2026-05-08T00:14:00Z
files_touched:
  - frontend/src/stores/ttsPlayer.ts
  - frontend/src/stores/__tests__/ttsPlayer.spec.ts
---

bookId added to OpenContentArgs + store. play/pause/nextSentence/prevSentence/seek delegate to useTtsEngine helpers. retry() re-invokes engine.load(); close() terminates engine. Cast `ct as AudioContentType` in retry() since the persisted content types are a subset of TtsContentType.

12/12 store tests pass. Type-check now reports 19 errors (all bookId-missing callsites) — exactly the surface T6 fixes.
