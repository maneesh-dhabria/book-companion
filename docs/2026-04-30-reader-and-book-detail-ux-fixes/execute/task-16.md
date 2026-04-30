# Task 16 — F8: Reader store URL ?tab sync

## Files touched
- frontend/src/stores/reader.ts (loadSection / toggleContent / navigateSection)
- frontend/src/stores/__tests__/reader.tab.spec.ts (new — 5 tests)

## Decisions / deviations
- Plan suggested using `useRoute()` / `useRouter()` inside the store —
  works in setup-style stores when called from a component, but breaks
  in unit tests that don't mount a component. Instead the store reads
  `(await import('@/router')).default.currentRoute.value`, which works
  in both the production app and unit tests.
- Added a `_setRouterForTests` injection seam (matches existing
  patterns in the codebase) so the spec can wire its own memory-history
  router without spinning up a component tree.
- `navigateSection` now also calls `loadSection` after `router.push` so
  the FR-17 rewrite fires even outside the BookDetailView watcher
  (which the spec scenarios assume). In production the watcher is
  idempotent — second-call cost is one cached fetch.

## Runtime evidence
- `npx vitest run reader.tab` — 5 / 5 pass.
- Full suite `npx vitest run` — 273 / 273 pass.
- `npm run type-check` — clean.
