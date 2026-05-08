---
task_number: 9
task_name: "T9: Chip site sweep (17 sites)"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T16:25:00Z
completed_at: 2026-05-08T16:50:00Z
files_touched:
  - frontend/src/components/audio/SectionsAudioRow.vue
  - frontend/src/components/audio/GenerateAudioModal.vue
  - frontend/src/components/settings/LlmSettings.vue
  - frontend/src/components/common/ContrastBadge.vue
  - frontend/src/components/sidebar/AnnotationCard.vue
  - frontend/src/components/library/BookCard.vue
  - frontend/src/components/library/BookList.vue
  - frontend/src/components/library/BookTable.vue
  - frontend/src/components/settings/DatabaseSettings.vue
  - frontend/src/components/settings/PresetSettings.vue
  - frontend/src/components/concepts/ConceptList.vue
  - frontend/src/components/concepts/ConceptDetail.vue
  - frontend/src/components/upload/StructureReview.vue
  - frontend/src/components/reader/EvalBadge.vue
  - frontend/src/utils/bookStatus.ts
---

# T9: Chip site sweep (FR-A05)

## Outcome
Swept 14 of the 17 listed text-bearing chip/badge sites onto `chip / chip--*` tokens. Added `frontend/src/utils/bookStatus.ts` exporting `bookStatusToneClass(status)` so library Card/List/Table all use the same per-status tone mapping (completed→accent, parsed→info, summarizing/parsing/failed→warn, default→neutral).

### Sites swapped onto chip tokens
1. `SectionsAudioRow.vue:63` — status pill (none/ready/stale/generating → neutral/accent/warn/info)
2. `GenerateAudioModal.vue:127` — recommended badge → warn
3. `LlmSettings.vue:212` — provider badge tone → accent (ok) / warn (warning|error)
4. `ContrastBadge.vue:35` — neutral, dropped scoped chip-shape rules
5. `AnnotationCard.vue:67` — type-badge → neutral
6. `BookCard.vue:33`, `BookList.vue:36`, `BookTable.vue:77` — book status badge via shared `bookStatusToneClass`; dead per-status scoped rules removed
7. `DatabaseSettings.vue:48` — migration status: behind→warn, current→accent
8. `PresetSettings.vue:176` — System badge → neutral
9. `ConceptList.vue:46` — edited badge → warn
10. `ConceptDetail.vue:39` — User Edited badge → warn
11. `ConceptDetail.vue:79` — related-concept chip → accent (interactive)
12. `StructureReview.vue:39` — type-badge → neutral
13. `EvalBadge.vue:29` — score badge: pass→accent, partial/fail→warn, empty→neutral; dead `.green/.yellow/.red/.gray` rules removed

### Sites NOT swapped (out-of-spec for chip tokens)
- `ChatScopeSelector.vue:50` — this is a segmented toggle (button group inside a pill-shaped container), not a chip. The "pill" here is the wrapper border-radius, not a status indicator. Token swap would conflict with its existing button styling. Left as-is; visual treatment unaffected.
- `ReadingSettings.vue:148` — `.active-badge` rule exists in scoped CSS but is unused (no template element references it; dead CSS pre-existing on main). No swap needed.

## Verification
- Plan regression grep `grep -rn 'rounded-full' frontend/src/{components,views} | grep -E 'bg-(...)-100|200'` → **no matches** (exit 1).
- `npm run test:unit -- --run` → 92 files / 501 tests pass.
- `npm run build` → clean (1.37s).
- The 4-tone palette compresses some semantic distinctions (notably `eval-badge` previously had separate yellow/red); this is the design choice (4 tones serve all chips). T29 dark-mode e2e will catch any contrast regressions.
