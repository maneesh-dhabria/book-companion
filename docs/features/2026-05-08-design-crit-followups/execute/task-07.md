---
task_number: 7
task_name: "T7: Chip token CSS"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T16:10:00Z
completed_at: 2026-05-08T16:14:00Z
files_touched:
  - frontend/src/assets/main.css
---

# T7: Chip token CSS (FR-A01)

## Outcome
Added `.chip` base + 4 tones (`--accent / --info / --warn / --neutral`) plus 4 `.dark .chip--*` overrides to `frontend/src/assets/main.css`, inserted directly after the `.btn-secondary` block. Values copied verbatim from spec §11.1.

## Verification
- `npm run build` succeeds (1.40s, no CSS parse errors).
- Compiled `dist/assets/index-*.css` contains all 5 light selectors (`.chip{`, `.chip--accent{`, `.chip--info{`, `.chip--warn{`, `.chip--neutral{`) and all 4 dark descendant selectors (`.dark .chip--accent`, …).
- No JS/TS code consumes the tokens yet — that's T8/T9. CSS-only addition; vue-tsc not required to re-run.

## Notes
Plan said "5 base classes + 4 dark variants" — that resolves to 1 base `.chip` + 4 tone modifiers + 4 dark overrides = 9 rules total. Matches spec verbatim.
