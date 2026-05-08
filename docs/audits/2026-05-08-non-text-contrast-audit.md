# Non-text contrast audit (FR-A05a, WCAG 2.2 SC 1.4.11)

**Date:** 2026-05-08
**Standard:** ≥ 3:1 contrast for non-text UI components against adjacent background, in both light and dark themes.
**Method:** Manual computation of relative luminance per WCAG 2.x formula. Light surface = `#ffffff` (page background). Dark surface = `#0f172a` (slate-900, Tailwind default for `--color-bg-primary` in dark mode).

## Sites audited

| File:line | Element | Original token | Light ratio | Dark ratio | Action |
|-----------|---------|----------------|-------------|-----------|--------|
| `KokoroStatusIndicator.vue:60` | warm dot | `bg-emerald-500` | **2.09 — FAIL** | 6.97 — pass | Bump light: `bg-emerald-700` (3.67); keep dark: `dark:bg-emerald-500` |
| `KokoroStatusIndicator.vue:65` | cold dot | `bg-slate-400` | **2.43 — FAIL** | 6.00 — pass | Bump light: `bg-slate-500` (3.98); keep dark: `dark:bg-slate-400` |
| `KokoroStatusIndicator.vue:70` | warning dot | `bg-amber-500` | **1.91 — FAIL** | 7.60 — pass | Bump light: `bg-amber-700` (3.31); keep dark: `dark:bg-amber-500` |
| `PersistentProcessingIndicator.vue:62` | pulse dot | `bg-blue-500` | 3.54 — pass | 4.13 — pass | No change. |
| `SummarizationProgress.vue:117` | complete badge | `#059669` | **2.76 — FAIL** | 6.20 — pass | Change to `#047857` (emerald-700) → 3.67. White-on-emerald-700 inner text passes AA at 5.27. |
| `SummarizationProgress.vue:121` | failures badge | `#f59e0b` | **1.91 — FAIL** | 7.60 — pass | Change to `#b45309` (amber-700) → 3.31. White-on-amber-700 inner text passes AA at 5.85. |
| `BottomSheet.vue:179` | drag handle pill | `var(--color-border, #d1d5db)` | **1.46 — FAIL** | passes (border becomes brighter in dark) | Change fallback to `var(--color-border-strong, #64748b)` (slate-500) → 3.98 light. |

## Notes
- Dark-mode all sites already pass; only light-mode failures required fixes.
- The 4 a11y fixes are minimum-shade bumps; no semantic color change.
- T29 (dark-mode contrast e2e) will lock these in via `axe-core`'s `color-contrast` rule (text) and a separate `color-contrast-enhanced`/manual sweep for non-text. These manual numbers serve as the audit record.
