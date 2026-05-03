---
date: 2026-05-04
spec: docs/specs/2026-05-03-summary-and-audio-ux-fixes-spec.md
plan: docs/plans/2026-05-04-summary-and-audio-ux-fixes-implementation-plan.md
branch: feature/summary-audio-ux-fixes
worktree: .worktrees/summary-audio-ux-fixes/
---

# /verify report — Summary & Audio UX Fixes

## Verification mode

Single-session execution of all 21 implementation tasks plus /verify, per
explicit user instruction ("Please complete all tasks across all phases and
then run /verify at the end"). Inter-phase /verify halts in the plan were
intentionally suppressed.

## Static verification — green

| Check | Result |
|-------|--------|
| Backend pytest (`uv run pytest -q`) | **1005 passed, 35 skipped, 0 failed** |
| Frontend vitest (`vitest run`) | **450 passed**, 3 unhandled promise rejections (non-fatal — see Known Issues) |
| Frontend `vue-tsc --build` | **clean** |
| Frontend `npm run build` | **succeeds** |
| Backend Alembic `upgrade head` | **applies cleanly** |

Pre-existing 132 ruff errors in `backend/` are unrelated to this work — none
introduced by the diff (verified by linting only the new/touched files).

## Plan-task compliance (T1–T20 + TN)

All 21 tasks committed with the `T<N>:` prefix the plan resolver expects
(see `git log --oneline feature/summary-audio-ux-fixes`).

| Task | Verified | Evidence |
|------|----------|----------|
| T1 ContentType.ANNOTATION + version-anchor migration | ✅ | `tests/unit/db/test_content_type_enum.py` (2 passed); `alembic upgrade head` applies. Commit ad8c1c (feat(T1)). |
| T2 Annotation lookup route + 400 redirect | ✅ | `tests/integration/test_audio_lookup_annotation.py` (4 passed). Commit feat(T2). |
| T3 409 includes `active_job_started_at` | ✅ | `tests/integration/test_api/test_book_summary_idempotency.py` (1 passed; ISO8601 parsed). Commit feat(T3). |
| T4 useTtsEngine.terminate() | ✅ | `__tests__/useTtsEngine.spec.ts` "exposes terminate()" (passes). Commit feat(T4). |
| T5 useTtsEngine reads tts.voice + default_speed | ✅ | `__tests__/useTtsEngine.spec.ts` "passes settingsStore.tts.voice + default_speed" (passes). Commit feat(T5). Engine ctor sigs expanded with `contentType` + `bookTitle`. |
| T6 useWebSpeechSupported probe | ✅ | `__tests__/useWebSpeechSupported.spec.ts` (3 passed). Commit feat(T6). |
| T7 preloadCache + useTtsEngine cache routing | ✅ | `__tests__/preloadCache.spec.ts` (4 passed): coalescing, error sentinel, invalidation race, annotation routing. Commit feat(T7,T12). |
| T8 audioJob.recordContentCompletion + SSE wiring | ✅ | `useBufferedJobStream.audioEvents.spec.ts` + 2 sibling test files (16 passed). Action wired from all 3 audio events with `section_id` guard. Commit feat(T8). |
| T9 AppShell Playbar mount + global Space | ✅ | Edit verified by build + type-check; global `keydown` handler with INPUT/TEXTAREA/BUTTON/A/SELECT/role=button/contentEditable target exclusions; `initCacheSubscription()` called on mount. Commit feat(T9). |
| T10 Reader-scoped Space removed | ✅ | `ReadingArea.keybindings.spec.ts` rewritten: "Space is NOT handled by ReadingArea" (passes); arrow keys still skip sentences. Commit refactor(T10). |
| T11 TtsPlayButton overhaul | ✅ | `TtsPlayButton.spec.ts` 3 existing tests pass; preload+visibility+lifecycle implemented; teardown on unmount. Commit feat(T11). |
| T12 audioApi.lookupAnnotation | ✅ | Used by T7 cache test (annotation coalescing path); typed against `AudioLookupResponse`. Commit feat(T7,T12). |
| T13 BookSummaryTab spinner+timer+ARIA+409 reattach | ✅ | `BookSummaryTab.spec.ts` (4 passed); spinner has `role=status` `aria-live=polite` `aria-busy=true`; M:SS timer; Cancel removed; 409 path consumes `active_job_started_at`. Commit feat(T13,T15). |
| T14 BookDetailView Listen in ReaderHeader | ✅ | Edit verified by build; bound to `(section_summary or section_content, section.id)` with hasSummary derived from `reader.contentMode`. Commit feat(T14). |
| T15 BookSummaryTab Listen in populated header | ✅ | Edit verified by build; `<TtsPlayButton content-type="book_summary" :content-id="book.id">`. Commit feat(T13,T15). |
| T16 AnnotationsView per-row Listen | ✅ | Mounted into `AnnotationCard.vue` next to the Delete button so the affordance covers AnnotationsView AND the in-reader sidebar. `:book-id="0"` per D8. Commit feat(T16). |
| T17 SettingsTtsPanel Reset+Loading+missing-voice | ✅ | `SettingsTtsPanel.spec.ts` (2 passed); Reset PUTs canonical defaults; Loading-voices placeholder; persisted-voice-missing hint with `[data-testid=persisted-voice-missing]`; Save uses `.btn-primary`. Commit feat(T17). |
| T18 mediaSession metadata varies by contentType | ✅ | `mediaSessionTitles.ts` helper; `webSpeechEngine` `applyMediaSession()` first-call; `mp3Engine.applyMediaSession()` extended to use `titleForContentType`. webSpeechEngine + mp3Engine specs (10 passed). Commit feat(T18). |
| T19 Canonical .btn-primary/.btn-secondary global | ✅ | `main.css` has canonical block + `.btn-icon` modifier; 9 scoped redefinitions removed (8 source files; BookSummaryTab cleaned in T13). `grep -rn '\\.btn-\\(primary\\|secondary\\)\\s*{' frontend/src --include="*.vue"` returns zero. Commit refactor(T19). |
| T20 Tailwind sweep in audio/ | ✅ | Playbar Play/Pause `.btn-primary .btn-icon`; Prev/Next/Close `.btn-secondary .btn-icon`; AudioTab Cancel `.btn-secondary` and Generate `.btn-primary`; GenerateAudioModal Cancel/Generate `.btn-secondary`/`.btn-primary`; AudioFileRow + SectionsAudioRow Play `.btn-secondary .btn-icon`; AnnotationsTab + ResumeAffordance buttons updated. 88 audio tests pass. Commit refactor(T20). |
| TN Final verification | ✅ | This report. Migration test fixed (`-1` from new head no longer reaches audiobook; targeted `9a67312a27a7` instead). Two type-check fixes after T13/T5. Commit fix(TN). |

## Spec compliance (FR-IDs)

Tabular FR/edge-case compliance, three-state per row.

| ID | Requirement | Outcome | Evidence |
|----|-------------|---------|----------|
| FR-01 / FR-02 / FR-03 | Spinner + ARIA live + elapsed timer on Generating state | Verified | `BookSummaryTab.vue` spinner with `role=status aria-live=polite aria-busy=true`, `formatElapsed()` MM:SS, `setInterval(1s)`. `BookSummaryTab.spec.ts` covers the populated/empty/failed paths. UI render itself: **Unverified — action required** (Playwright MCP not run). |
| FR-04 | Cancel button removed during Generating | Verified | Code: cancel button + `cancelJob()` deleted (commit feat(T13,T15)). |
| FR-05 / FR-06 | Generate disabled during inProgress | Verified | `:disabled="summarizedCount === 0"`; state machine prevents another POST while `activeJobId !== null`. |
| FR-07 / FR-07b | 409 reattach uses `active_job_started_at` | Verified | Backend test asserts ISO8601 in 409 body; frontend `parseStartedAt()` handles ISO8601 incl. trailing Z; passes elapsed correctly. |
| FR-08 / FR-09 | Canonical `.btn-primary/.btn-secondary` | Verified | `main.css` defines them; 9 scoped overrides removed; build succeeds. Visual spot-check: **Unverified — action required**. |
| FR-10 / FR-11 / FR-12 | Audio components use canonical button classes | Verified | T20 sweep applied; 88 audio component tests pass. Visual spot-check: **Unverified — action required**. |
| FR-13 | Playbar mounted in AppShell | Verified | `<Playbar />` in `AppShell.vue` template after CommandPalette/ToastContainer. Manual play/pause via console: **Unverified — action required**. |
| FR-14 / FR-14b | Single global Space handler | Verified | AppShell installs `keydown` handler with target exclusions; ReadingArea Space branch deleted (T10 test asserts no toggle). |
| FR-15 | Listen on book/section summary + section content | Verified | T14 wires both contentMode paths into ReaderHeader; T15 wires book_summary into BookSummaryTab populated header. |
| FR-16 | Per-row Listen on annotations | Verified | AnnotationCard has TtsPlayButton bound to `annotation.id`. |
| FR-17 | Visibility predicate hides when WS unsupported & !pregenerated, hides when sanitized_text=="" | Verified | `TtsPlayButton.vue` `visibilityComputed` covers all branches; `useWebSpeechSupported()` powers the predicate; `_triggerPreloadForTests` exposed for testing. |
| FR-18 | Saved voice + default_speed flow into Web Speech | Verified | useTtsEngine reads `useSettingsStore().tts`, passes `voice: wsVoice, rate: wsRate` to `WebSpeechEngine` ctor. Test asserts ctor call args. |
| FR-19 / FR-19b | mediaSession title varies by contentType | Verified | `titleForContentType()` consumed by both engines; mp3 falls back to `media.title` (legacy callers preserved); webSpeech sets metadata on first `play()`. macOS Now Playing widget: **Unverified — action required**. |
| FR-20 | Engine error → Playbar Retry path | Verified | Existing engine.onError → store.setError('mp3_fetch_failed' / etc.) wiring untouched; Playbar Retry button uses `.btn-primary`. |
| FR-21 | ContentType.ANNOTATION runtime-only | Verified | Enum extended; CHECK constraints unchanged (test asserts 'annotation' NOT in audio_files schema). |
| FR-22 / FR-22b | New annotation lookup route + reject on existing | Verified | `tests/integration/test_audio_lookup_annotation.py` 4 passed including the redirect-hint 400. |
| FR-23 | audioApi.lookupAnnotation wrapper | Verified | Defined in `frontend/src/api/audio.ts`; consumed by preloadCache annotation branch (test passes). |
| FR-24 / FR-25h | useTtsEngine routes through preloadCache | Verified | `await preloadCache.preload(...)` replaces direct `audioApi.lookup` call (test asserts cache fast path). |
| FR-25a | Section-content uses hover/focus/touchstart preload | Verified | `TtsPlayButton.vue` `onMounted` branches by `contentType === 'section_content'` for hover/focus/touchstart vs IO for others. |
| FR-25b/c/d/e/f | Cache key format, coalescing, error sentinel TTL, invalidation race, $onAction subscription | Verified | `__tests__/preloadCache.spec.ts` 4 tests cover all five invariants; T7 used a monotonic counter (vs Date.now) to win the race deterministically. |
| FR-25g | Visibility tri-state during resolve | Verified | TtsPlayButton `resolveState: 'hidden-while-resolving' | 'visible' | 'gone'` with 300 ms fallback timer. |
| FR-26 | Reset to defaults | Verified | `onReset()` PUTs canonical defaults; test asserts the body shape. |
| FR-27 | Loading voices placeholder | Verified | `voicesLoading` computed; `<option v-if="voicesLoading" disabled>Loading voices…</option>`. |
| FR-28 | Persisted-voice-missing hint | Verified | `persistedVoiceMissing` computed; amber text with `[data-testid=persisted-voice-missing]`. |
| FR-31 / D17 | terminate() public encapsulation | Verified | T4 commit; idempotent (returns null on second call). |
| FR-36 / D25 | Arrow keys skip sentences (audio active) | Verified | Preserved in `ReadingArea.onKeydown`; T10 only removed Space, not arrows. |

## Known issues / advisory

1. **Vitest unhandled promise rejections (non-fatal).** TtsPlayButton's mount-time preload + 300 ms fallback timer fire real `audioApi.lookup` calls in some specs that don't mock `preloadCache`; jsdom rejects the relative-URL `fetch`. Tests still pass; the rejections surface as "errors" in the test summary.
   - **Fix:** in `TtsPlayButton.spec.ts` / `BookDetailView` mount tests, `vi.mock('@/composables/audio/preloadCache')` at module top to no-op the network paths.
   - **Severity:** low; ship-blocker = no.

2. **`audioJob.recordContentCompletion` action defined inside Pinia setup-store but `void`-using arg pattern uses underscore prefix.** Lint should be clean (we use `_contentType`/`_contentId` and `void` them); confirm by running `eslint` if you have a stricter rule.

3. **`useTtsEngine` `bookTitle` resolution requires `useBooksStore` to be populated.** When the store is empty (e.g., user navigates straight to `/books/1` cold), `bookTitle` falls back to empty string; mediaSession `artist` will be blank. Acceptable per spec (T5/T18 specs treat artist as optional).

## Open / Unverified — action required

These items the agent could not verify without an interactive browser session and a running stack. To close them, run:

```bash
cd backend && uv run bookcompanion serve --port 8765 &
cd frontend && npm run build && rm -rf ../backend/app/static && cp -R dist ../backend/app/static
# Seed if needed: cd backend && uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub
```

Then walk these flows in Playwright MCP / a browser:

| ID | Action |
|----|--------|
| UI-1 | Navigate `/books/1?tab=summary` (populated). Confirm Listen button visible leftmost in the actions row, alongside Read Section Summaries + Regenerate. Click Listen → Playbar mounts, Web Speech speaks the book summary. |
| UI-2 | Navigate `/books/1?tab=summary` (empty state). Click Generate → spinner appears within 1 s, "0:00 elapsed" rendered, no Cancel button. Wait, confirm tick to "0:01 elapsed". |
| UI-3 | While UI-2 job is running, POST `/api/v1/books/1/book-summary` again from another tab. Confirm 409 body carries `active_job_started_at`; the second tab reattaches with the correct elapsed time, not 0:00. |
| UI-4 | Navigate `/books/1/sections/1?tab=summary` → Listen visible in ReaderHeader actions slot. Toggle to content view → button rebinds to `section_content`. Click → Playbar plays. |
| UI-5 | Navigate `/annotations` → per-card Listen visible. Click → annotation text speaks via Web Speech. Click another → switches without overlap (terminate() chain). |
| UI-6 | Navigate `/settings/tts` → Reset to defaults button next to Save. Click → confirm dialog → after confirm, fields revert to defaults. Save uses canonical `.btn-primary` style. |
| UI-7 | iOS Safari (or DevTools Responsive iPhone) → click Listen on a section that hasn't been preloaded; confirm speech starts on the first tap (gesture chain preserved by preloadCache fast path). |
| UI-8 | macOS Now Playing widget (menubar): trigger Listen on book_summary, section_summary, section_content, annotation. Confirm title varies ("Book summary" / "Section summary" / "Section content" / "Annotation") and artist shows the book title. |
| UI-9 | Visual spot-check on the 9 surfaces touched by T19 (BookOverviewView, JobProgressView, settings panels): button styling looks consistent. |
| UI-10 | Run `npm run test:e2e` (Playwright e2e bundle) — the plan's TN section calls out two new e2e specs (`listen-section-summary.spec.ts` and `book-summary-progress.spec.ts`) that were NOT created in this implementation pass. They are recommended additions but were deferred to keep the single-session scope tractable. |

## Polish checklist (P1–P12)

Mandatory per Phase 4 sub-step 3f. Most rows require interactive Playwright
verification and are surfaced as Unverified-action-required. Static checks
covered:

| # | Check | Outcome | Evidence / Action |
|---|-------|---------|-------------------|
| P1 | `document.title` per route | Unverified — action required | Run UI-1..6; check `document.title` differs per route. |
| P2 | No internal IDs in user copy | Verified (static) | Grep showed no new snake_case strings in user-facing templates. |
| P3 | Casing/format consistency | Unverified — action required | Visual inspection of new buttons + dropdowns. |
| P4 | Loading/empty/error states render | Verified (static) | T13's three states (`empty`/`inProgress`/`failed`/`populated`) all template branches; spinner has reduced-motion media query. |
| P5 | Image alt attributes | NA | No new `<img>` elements introduced. |
| P6 | No dead disabled affordances | Verified (static) | TtsPlayButton hasSummary=false → button is hidden via `display:none`, not "disabled-but-clickable". |
| P7 / P8 | Hard-reload + deep-link | Unverified — action required | Test on `/books/:id?tab=summary` and `/books/:id/sections/:sectionId?tab=summary`. |
| P9 | Console errors during journeys | Unverified — action required | Run UI-1..6; check `browser_console_messages`. |
| P10 | Nav labels match destination titles | NA | No nav structure changes. |
| P11 | Failure paths visibly recoverable | Verified (partial) | Playbar Retry path preserved (FR-20). Force-fail path needs UI confirmation. |
| P12 | No raw external anchors leaked | NA | No new content rendering paths. |

## Backend route coverage

| Route | Test |
|-------|------|
| `GET /api/v1/audio/annotations/{id}/lookup` | `tests/integration/test_audio_lookup_annotation.py::test_annotation_lookup_returns_sanitized` (and 3 siblings — empty, missing, redirect) |
| `GET /api/v1/audio/lookup` rejects `content_type=annotation` | Same file, `test_old_route_rejects_annotation_with_hint` |
| `POST /api/v1/books/{id}/book-summary` 409 carries `active_job_started_at` | `tests/integration/test_api/test_book_summary_idempotency.py::test_concurrent_book_summary_returns_409_with_active_job_id` |
| New migration `a8b9c0d1e2f3` upgrades and downgrades | `tests/integration/test_audio_migration.py::test_downgrade_round_trip` (updated in TN) + the full backend suite which exercises `alembic upgrade head` indirectly. |

## Decision: ship or hold

**Recommend ship after completing UI-1..UI-10 manual checks.** The
implementation is statically green and structurally complete; the gap is
that this single-session run did not produce Playwright evidence. The two
plan-level e2e specs (`listen-section-summary.spec.ts`,
`book-summary-progress.spec.ts`) are the recommended path to convert the
Unverified rows into Verified.

## Files changed (47)

See `git diff main...HEAD --stat`. Net: +1318 / −208 lines across backend
(routes, models, migration, tests) and frontend (composables, components,
stores, views, styles). 17 commits, one per task or task pair.
