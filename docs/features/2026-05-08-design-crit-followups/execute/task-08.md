---
task_number: 8
task_name: "T8: First-class chip rewrites"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T16:15:00Z
completed_at: 2026-05-08T16:22:00Z
files_touched:
  - frontend/src/components/common/TagChip.vue
  - frontend/src/components/audio/EngineChip.vue
  - frontend/src/components/audio/Playbar.vue
---

# T8: First-class chip rewrites (FR-A02, FR-A03, FR-A04)

## Outcome
Three first-class chip components ported onto `.chip / .chip--*` tokens.

- **TagChip.vue** — replaced its scoped `.tag-chip` background/border/font rules with the global `.chip` class. Tone resolves to `.chip--warn` when `suggested`, `.chip--neutral` otherwise. When the `color` prop is set (user-defined hex tag colors), the inline `style.background` overrides the token — preserves library-tag colorings without losing dark-mode legibility on default chips. Kept `.remove` and `.clickable` scoped rules.
- **EngineChip.vue** — swapped Tailwind utilities (`bg-indigo-100 text-indigo-800` / `bg-slate-100 text-slate-700` etc.) for `chip` + `chip--info` (Kokoro) / `chip--neutral` (Web Speech).
- **Playbar.vue** — Limited-controls span now `class="chip chip--warn"`. `data-testid="limited-controls"` preserved.

## Verification
- `npm run test:unit -- --run` — 92 files / 501 tests passed.
- `npm run build` — clean (1.38s).
- No test asserted on the old utility class strings; no test churn needed.
