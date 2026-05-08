---
task_number: 26
task_name: "T26: KeyboardShortcutsOverlay"
task_goal_hash: b3707dfafe2e8dd770ac1ba0c796bbcd583b01e9df31785c95eefb4b4bf8c827
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T21:25:00Z
completed_at: 2026-05-08T21:33:00Z
files_touched:
  - frontend/src/components/app/KeyboardShortcutsOverlay.vue
  - frontend/src/components/app/AppShell.vue
  - frontend/src/components/audio/Playbar.vue
  - frontend/src/components/app/__tests__/KeyboardShortcutsOverlay.spec.ts
---

# T26: KeyboardShortcutsOverlay + Playbar tooltips (FR-E09)

## Outcome
- **`KeyboardShortcutsOverlay.vue`:** New component. Document-level `keydown` listener; `?` toggles visibility (suppressed when an input/textarea/select/contenteditable is focused, or when modifier keys are held). Esc closes. Backdrop click closes. Modal-style overlay listing 5 shortcuts: Space (Play / pause), → (Next sentence), ← (Previous sentence), ? (Toggle this overlay), Esc (Close).
- **AppShell mount:** Added `<KeyboardShortcutsOverlay />` next to `<Playbar />` so it's globally available across all routes.
- **Playbar tooltips:** Added `title` attrs:
  - Prev: `Previous sentence (←)`
  - Play/Pause: `Play (Space)` / `Pause (Space)` (toggles with status)
  - Next: `Next sentence (→)`

## Plan deviations
- None of substance. Plan §T26 step 1 said "modal-style overlay listing: Space (play/pause), → (next sentence), ← (prev sentence), Esc (close)." Added the `?` toggle row too — users discover the overlay by trying `?`, and showing the binding makes the affordance self-documenting.

## Verification
- `vitest run src/components/app/__tests__/KeyboardShortcutsOverlay.spec.ts` — 5/5 pass.
- Full frontend unit suite: 557/557 pass (was 552 at T25 close; +5 new).
- `npm run type-check` clean.
- `npm run build` clean (1.44s).

## Runtime evidence
The 5 new tests cover: hidden-by-default, `?` toggle (open then close), input-focus suppression, Escape-to-close, and shortcut copy contains Space/→/←/Esc.
