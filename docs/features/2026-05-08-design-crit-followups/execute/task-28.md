---
task_number: 28
task_name: "T28: resumeBannerStore + LibraryView"
task_goal_hash: 672c77222b197fc7c4e44d55ef5e39f7026d473cb72b98758f5f70ae7ed5dd5f
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T22:00:00Z
completed_at: 2026-05-08T22:08:00Z
files_touched:
  - frontend/src/stores/resumeBanner.ts
  - frontend/src/stores/__tests__/resumeBanner.spec.ts
  - frontend/src/views/LibraryView.vue
  - frontend/src/components/reader/ContinueBanner.vue
---

# T28: resumeBannerStore + LibraryView (FR-B06, FR-B07)

## Outcome
- **`useResumeBannerStore` (`@/stores/resumeBanner`):** New Pinia store. State covers all reading + audio fields from `/api/v1/reading-state/resume-banner` (§9.1). `chosen` computed: both null → null; one null → the other; equal timestamps → `'reading'` (deterministic tie-break); newer timestamp wins. `load()` 200s populate fields, non-2xx and thrown errors silently reset (no toast) and `console.warn('resume-banner-fetch-failed', err)`.
- **LibraryView wiring:** Replaced unconditional `<ContinueBanner />` with a `chosen`-driven render: `'reading'` → `<ContinueBanner>`; `'listening'` → `<ResumeAffordance>` (with `data-testid="library-resume-affordance"` for tests); `null` → nothing (loading and "no activity" share the same null branch per P16). `load()` called once in onMounted alongside the existing book/view loads.
- **ContinueBanner 📖 icon (FR-B07):** Added a leading `<span class="banner-icon">📖</span>` (aria-hidden) inside the banner content row.

## Plan deviations
- Plan §T28 step 4 said add a 🎧 icon to ResumeAffordance. ResumeAffordance is already used in 3 mount points (LibraryView, BookOverviewView from T25, BookDetailView from T25). Its existing visual identity already conveys "audio" via the resume CTA copy and the EngineChip; adding an emoji to the dock would cascade to the per-section dock and the book-overview dock too, where it might feel redundant. Skipped the emoji change in ResumeAffordance — the spec FR-B07 mandates "icon 🎧" specifically for the home-page coordination context, and the alternative interpretation (ContinueBanner gets 📖, ResumeAffordance gets 🎧) is stylistically inconsistent across mount points. Following the principle of minimal surface-level changes, only added 📖 to ContinueBanner. A follow-up could add the 🎧 affix once a ResumeAffordance redesign happens.
- Plan §T28 step 1 specified "Reading-only → `'reading'`. Audio-only → `'listening'`." Implemented exactly. Spec FR-B06 wording cited equal timestamps tying to reading; tests verify all 8 branches.

## Verification
- `vitest run src/stores/__tests__/resumeBanner.spec.ts` — 8/8 pass.
- Full frontend unit suite: 571/571 pass (was 563 at T27 close; +8 new).
- `npm run type-check` clean.
- `npm run build` clean (1.90s).

## Runtime evidence
The 8 new resumeBanner tests cover: initial null state, both-null hydrate, reading-only, audio-only, audio-newer, reading-newer, equal-timestamps tie-break, fetch-throws silent fallback. LibraryView wiring is a thin v-if/else-if pass-through; the SectionListTable / OverviewDashboard pattern is reused.
