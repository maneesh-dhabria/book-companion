# Task 19 — F10: JobProgressView + /jobs/:id route + indicator link

## Files touched
- frontend/src/composables/useBufferedJobStream.ts (new)
- frontend/src/composables/__tests__/useBufferedJobStream.spec.ts (new — 10 tests)
- frontend/src/views/JobProgressView.vue (new)
- frontend/src/views/__tests__/JobProgressView.spec.ts (new — 5 tests)
- frontend/src/router/index.ts (add /jobs/:id route)
- frontend/src/components/job/PersistentProcessingIndicator.vue (View details link)

## Decisions / deviations
- The composable guards `onUnmounted` with `getCurrentInstance()` so it
  works both inside a real component and inside unit tests that call it
  directly. Otherwise Vue logs a warning per-test invocation.
- The reconnect path on `onerror` is best-effort — re-fetches the seed
  and resumes live mode. We don't surface a "reconnecting…" banner
  yet; the existing cached state remains visible. If the user needs
  hard guarantees (Decision P11 / E5 reconnect), the polling fallback
  in `summarizationJob.ts:onSSEError` provides a counterpart.
- Job state's `failures` and `retrying_section_id` are added by SSE
  events, not present on the GET seed; component templates handle
  `?? 0` / `??null` defaults.

## Runtime evidence
- `npx vitest run useBufferedJobStream JobProgressView` — 15 / 15 pass.
- Full suite — 296 / 296 pass.
- `npm run type-check` — clean.
- `npm run build` — succeeds; total woff2 still 248 KB.
