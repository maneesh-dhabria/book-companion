---
task_number: 21
task_name: "T21: Drop drawer; enrich TOCDropdown"
task_goal_hash: 344cede95c1f49c3bf506985a98a0c3fdcadf13ff8c684e0291794cdbd5ac50a
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T20:10:00Z
completed_at: 2026-05-08T20:21:00Z
files_touched:
  - frontend/src/components/book/SectionListTable.vue
  - frontend/src/components/book/__tests__/SectionListTable.spec.ts
---

# T21: Drop drawer; enrich TOCDropdown (FR-D03, FR-D04)

## Outcome
- **Drawer drop (FR-D03):** No-op against `ReaderHeader.vue` — that file does not (and per the Phase 2 audit, did not for some time) own a `☰` drawer trigger. The `☰` button that exists in `BookDetailView.vue` toggles the `ContextSidebar` (annotations / chat / notes), which is a different feature from the FR-D03 sections-drawer the spec calls out. Plan §T21 step 1 anticipated this with the "if absent, no-op" guard. ContextSidebar toggle is left intact.
- **TOCDropdown chip enrichment (FR-D04):** TOCDropdown delegates to `SectionListTable` in `compact` mode — extending the chip work there (instead of duplicating into TOCDropdown) keeps the structural alignment FR-33 / NFR-07 already require. The compact-mode summary cell is now a chip strip:
  - **Mode chip** (`data-chip="mode"`): `📋` when `has_summary`, otherwise `📖`. `chip chip--neutral`.
  - **Summary chip** (`data-chip="summary"`): keeps the existing `summaryStatus()` label (`✓` / `✕` / `pending` / `failed` / `retrying…`). `chip chip--accent` when done; `chip chip--neutral` otherwise. `data-summary-kind` preserved for downstream styling.
  - **Audio chip** (`data-chip="audio"`): `🎧` only when `audio.map[s.id]?.has_mp3` is true. `chip chip--info`. Hidden when no MP3 — explicitly NOT rendered as `∅` (FR-D04 wording shows `∅` as a written annotation, not a UI element; rendering an empty placeholder would clutter the dense compact rows).
- **Audio map enabled in compact mode:** `useBookAudioMap(bookId)` now runs in both modes. The composable's module-scoped cache (T18a) dedups the fetch when ReaderHeader's TOCDropdown and SectionDetail's other consumers share the same `bookId`, so opening the dropdown does not trigger a second `/api/v1/audio/sections/by-book/{id}` call.
- **Header rename:** Compact `<th>Summary</th>` → `<th>Status</th>` to match the new 3-chip column content.

## Plan deviations
- Plan §T21 step 2 said "render per-row chips" inside `TOCDropdown.vue`. Since TOCDropdown delegates to `SectionListTable` in compact mode, putting chip logic in TOCDropdown would either (a) duplicate the per-row markup or (b) require the dropdown to override compact rendering. Both options regress the structural reuse FR-33 / NFR-07 mandate. Implemented in `SectionListTable.vue` compact mode instead. TOCDropdown.vue itself unchanged.
- Plan named `chip--success` and `chip--sm` modifier classes that don't exist in `main.css`. Used the existing `chip--accent` / `chip--info` / `chip--neutral` tokens (verified ≥ 4.5 : 1 contrast in T7) and skipped the `chip--sm` modifier — chips are already 0.75rem.
- FR-D04 mentions `∅` for the no-audio case. Implemented as conditional render (chip absent), not an empty-symbol chip. Rationale: dense compact rows; the `📖` mode chip already implies no-audio for sections without summaries (which is where most audio gaps land).

## Verification
- `vitest run src/components/book/__tests__/SectionListTable.spec.ts` — 19/19 pass.
- Full frontend unit suite: 540/540 pass (was 538 at T20 close; +2 new chip tests).
- `npm run type-check` clean.
- `npm run build` clean (1.43s).

## Runtime evidence
The 2 new component tests (#18, #19) cover:
1. Per-row chip rendering: chapter with `has_summary` + MP3 hit shows `📋 + ✓ + 🎧`; chapter without summary or MP3 shows `📖 + ✕` and no audio chip.
2. Chip token class compliance: `mode` chip carries the `chip` token class.

The 17 pre-existing SectionListTable tests still pass — the audio composable promotion to all modes (vs. previous `null` in compact) didn't break the SSE-skip rule or the canListen gate; tests assert both behaviors and remain green.
