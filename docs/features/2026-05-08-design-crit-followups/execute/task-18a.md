---
task_number: 18.5
task_name: "T18a: useBookAudioMap composable"
task_goal_hash: 5d95908b478cffb5060b2937ee57fcc1616ec5e5c9484d14b2a36bb4574d191f
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T19:05:00Z
completed_at: 2026-05-08T19:12:00Z
files_touched:
  - frontend/src/api/audio.ts
  - frontend/src/composables/useBookAudioMap.ts
  - frontend/src/composables/__tests__/useBookAudioMap.spec.ts
---

# T18a: useBookAudioMap composable (P14, FR-C20)

## Outcome
- `audioApi.sectionsByBook(bookId)` added to `frontend/src/api/audio.ts`. Calls the existing backend `GET /api/v1/audio/sections/by-book/{bookId}` endpoint (T5). New `AudioByBookEntry` + `AudioByBookResponse` types exported.
- `frontend/src/composables/useBookAudioMap.ts` exports `useBookAudioMap(bookId)` returning `{ map, failed, ready }` refs. Module-scoped `cache` Map (resolved state) + `inflight` Map (in-progress dedupe). On API success: builds `Record<sectionId, {has_mp3, engine}>` and caches. On API error: caches `{ map: {}, failed: true }`. Subsequent calls for the same bookId return cached state immediately.
- Test seam: `_resetBookAudioMapCache()` exported for unit tests to clear the module-scoped maps.

## Plan deviations
- Plan §T18a step 2 prescribed exactly the implementation pattern. I followed it but used `.then()` instead of `.finally()` for the result-propagation step that updates the local refs (the second hook), because `.finally()` doesn't receive the promise's result and we don't need it — we read from the cache by then. Behavior is identical; the change keeps types clean.

## Verification
- `npm run test:unit -- --run src/composables/__tests__/useBookAudioMap.spec.ts` — 4/4 pass.
- Full frontend unit suite: 528/528 pass (was 524 after T18; +4 new).
- `npm run type-check` clean.

## Runtime evidence
The 4 unit tests cover: (1) two calls for the same bookId → spy invoked exactly once, both call sites populate; (2) different bookIds → 2 distinct fetches; (3) API rejection → `failed=true`, empty map, ready=true; (4) cache hit on subsequent call → ready=true synchronously. Each test resets the module-scoped cache via `_resetBookAudioMapCache()` and stubs `audioApi.sectionsByBook` directly.
