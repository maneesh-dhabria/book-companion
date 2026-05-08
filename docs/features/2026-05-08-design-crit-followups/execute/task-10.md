---
task_number: 10
task_name: "T10: Decorative non-text audit"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T16:52:00Z
completed_at: 2026-05-08T16:58:00Z
files_touched:
  - frontend/src/components/settings/KokoroStatusIndicator.vue
  - frontend/src/components/book/SummarizationProgress.vue
  - frontend/src/components/common/BottomSheet.vue
  - docs/audits/2026-05-08-non-text-contrast-audit.md
---

# T10: Non-text contrast audit (FR-A05a)

## Outcome
Audited all 7 decorative dot/pill sites listed in FR-A05a for WCAG 2.2 SC 1.4.11 (≥ 3:1) compliance in both themes. **6 of 7 sites failed in light mode**; all 7 passed in dark mode (the dot tones were chosen for dark backgrounds and don't have enough lightness contrast against white).

Applied minimum-shade bumps for light mode while preserving the original tone for dark mode via Tailwind's `dark:` variant. SummarizationProgress badge backgrounds (raw hex) were updated directly to emerald-700 / amber-700 — those badges have white text inside, which still passes AA on the deeper shade (≥ 5:1).

See `docs/audits/2026-05-08-non-text-contrast-audit.md` for the full ratio table.

## Verification
- `npm run build` clean (1.37s).
- `npm run test:unit -- --run` 92/92 passing.
- All 7 sites now ≥ 3:1 in both themes per audit table.

## Plan deviation
Plan suggested either no-op + audit doc OR fix + commit. Audit found real failures, so this commit BOTH fixes the failures AND records the audit doc.
