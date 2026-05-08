---
task_number: 8
task_name: "Wiring regression test (FR-16)"
plan_path: "docs/plans/2026-05-08-audio-playback-fix-implementation-plan.md"
branch: "feature/audio-playback-fix"
worktree_path: ".worktrees/audio-playback-fix"
status: done
started_at: 2026-05-08T00:20:00Z
completed_at: 2026-05-08T00:22:00Z
files_touched:
  - frontend/src/components/audio/__tests__/Playbar.wiring.spec.ts
---

3-test wiring spec landed. Sanity-failure step performed: un-wired `useTtsEngine().playActive()` from `store.play()` and confirmed the spec failed with `expected 1, got 0`, then restored. Test is genuinely behavioral (it would have caught the original bug).
