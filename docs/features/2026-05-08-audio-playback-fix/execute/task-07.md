---
task_number: 7
task_name: "Playbar UI updates — spinner + generic error copy"
plan_path: "docs/plans/2026-05-08-audio-playback-fix-implementation-plan.md"
branch: "feature/audio-playback-fix"
worktree_path: ".worktrees/audio-playback-fix"
status: done
started_at: 2026-05-08T00:18:00Z
completed_at: 2026-05-08T00:20:00Z
files_touched:
  - frontend/src/components/audio/Playbar.vue
  - frontend/src/components/audio/__tests__/Playbar.spec.ts
---

Spinner glyph + aria-label="Starting" + disabled/aria-disabled for `status='starting'`. Generic error copy with errorKind exposed only via title attr.

Added `data-testid="audio-error-message"` so the test can target the title attribute reliably (FR-14 copy + FR-15 retry both covered). 8/8 Playbar tests + 476/476 full unit suite pass.
