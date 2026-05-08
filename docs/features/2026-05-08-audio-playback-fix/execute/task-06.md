---
task_number: 6
task_name: "bookId callsite + test fixups"
plan_path: "docs/plans/2026-05-08-audio-playback-fix-implementation-plan.md"
branch: "feature/audio-playback-fix"
worktree_path: ".worktrees/audio-playback-fix"
status: done
started_at: 2026-05-08T00:14:00Z
completed_at: 2026-05-08T00:18:00Z
files_touched:
  - frontend/src/components/audio/TtsPlayButton.vue
  - frontend/src/components/audio/ResumeAffordance.vue
  - frontend/src/components/audio/AnnotationsTab.vue
  - frontend/src/components/audio/__tests__/Playbar.spec.ts
  - frontend/src/components/audio/__tests__/Playbar.midListenRegen.spec.ts
  - frontend/src/components/audio/__tests__/ResumeAffordance.spec.ts
  - frontend/src/components/audio/__tests__/TtsPlayButton.spec.ts
  - frontend/src/components/audio/__tests__/AnnotationsTab.spec.ts
  - frontend/src/components/reader/__tests__/ReadingArea.keybindings.spec.ts
---

TtsPlayButton: bookId required (was optional with `?? 0` fallback). ResumeAffordance: bookId required. AnnotationsTab: pass `props.bookId`. Test fixups: added `bookId: 1` to existing `store.open(...)` test calls; added `vi.mock('@/composables/audio/useTtsEngine', ...)` to Playbar.spec and ReadingArea.keybindings.spec because the now-engine-routed actions would otherwise hit `setError('engine_unavailable')` on every test interaction.

Also updated ReadingArea.keybindings tests: ArrowLeft/Right no longer mutate store.sentenceIndex (per FR-22 / D5); now assert prev/nextActive spies were called.

474/474 tests pass. Type-check clean.
