---
date: 2026-05-03
status: Draft
tier: 2 — Enhancement
requirements: docs/requirements/2026-05-03-summary-and-audio-ux-fixes.md
related:
  - docs/specs/2026-05-02-audiobook-mode-spec.md
  - docs/plans/2026-05-02-audiobook-mode-plan.md
---

# Summary & Audio UX Fixes — Spec

## 1. Problem Statement

Four UX gaps surfaced on `/books/{id}` and `/books/{id}/sections/{sectionId}`
after audiobook-mode shipped (v1.6): no progress feedback when a book summary
is queued; raw Tailwind buttons in `audio/` and `TtsPlayButton` look foreign;
the Web Speech engine has no Listen entry points so users without a Kokoro
install can't listen with one click; and the existing `SettingsTtsPanel`'s
saved Web Speech voice is dead data because `useTtsEngine.load()` never reads
it. Each gap silently degrades perceived reliability of the new audio surface.

**Primary success metric:** clicking **Generate book summary** shows a
spinner within ~1s; every Listen entry point opens a global Playbar that
plays — pre-generated MP3 if present, Web Speech otherwise — using the user's
saved voice + rate.

---

## 2. Goals

| #  | Goal                                                                                                                                          | Success Metric                                                                                                                       |
|----|-----------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| G1 | Visible feedback within ~1s after **Generate book summary** click; indeterminate spinner + `M:SS elapsed` until SSE completion.               | Manual: click → spinner appears < 1s; timer ticks; replaces with summary on `processing_completed`.                                  |
| G2 | Single canonical `.btn-primary`/`.btn-secondary` (with dark-mode variants) used app-wide; raw Tailwind button utilities removed from `audio/`. | Regression-grep: zero `bg-indigo-*`/`bg-slate-*`/`border-slate-*`/`hover:bg-*` button classes remain in `audio/` + `TtsPlayButton.vue`. |
| G3 | Listen on book summary, section summary, section content, and individual annotations; global Playbar plays MP3 when available, Web Speech otherwise. | Manual + Playwright: click Listen → `ttsPlayer.isActive=true` → Playbar mounted → engine matches D8 priority.                        |
| G4 | Saved Web Speech voice + rate are actually applied at playback time. Settings panel gains Test + Reset buttons.                                | Set voice X + rate 1.5× → click Listen → WebSpeechEngine receives voice=X, rate=1.5.                                                 |

---

## 3. Non-Goals

Carried verbatim from requirements §Non-Goals — see that doc for the full
list. The most consequential exclusions:

- **NOT** building new localStorage persistence for Web Speech settings —
  resolved against requirement D11; we extend the existing server-side
  `TTSConfig` + `SettingsTtsPanel` instead. *Reason:* see D1 below.
- **NOT** adding a Cancel button to the in-progress spinner — backend can't
  terminate the LLM subprocess; surfacing a no-op button is misleading.
- **NOT** persisting Web Speech playback position / position-resume across reloads.
- **NOT** Listen on book TOC rows, search results, or annotation playlists
  (latter handled by audiobook-mode).
- **NOT** sweeping raw Tailwind button utilities outside the `audio/` folder
  beyond the targeted promotion of `.btn-primary`/`.btn-secondary` (see D2).

---

## 4. Decision Log

| #   | Decision | Options Considered | Rationale |
|-----|----------|--------------------|-----------|
| D1  | Web Speech voice + rate persist via the existing server-side `TTSConfig` (PUT /api/v1/settings/tts) and `SettingsTtsPanel` — NOT a new `webspeech_settings_v1` localStorage key. | (a) existing `TTSConfig`; (b) localStorage as req D11 specifies; (c) hybrid. | Existing infra already persists `tts.voice` + `tts.default_speed`; `SettingsTtsPanel` already loads/saves them. Building a parallel localStorage path duplicates code, contradicts the "one SettingsService entrypoint" pattern (per `docs/specs/2026-04-25-v1.5-reader-ux-polish-followups-spec.md` D17/D18), and the per-device concern is moot for a single-user local tool. **Explicit deviation from req D11.** |
| D2  | `.btn-primary`/`.btn-secondary` are promoted to global classes in `assets/main.css` (with dark-mode variants), and ALL 9 components currently redefining them in `<style scoped>` are swept to use the global. | (a) promote + sweep audio only; (b) promote + sweep all 9 (chosen); (c) audio-only utility class. | User-confirmed scope expansion: visual parity across the app is the strategic win, not just the audio folder. Some surfaces will shift visually under one canonical look — accepted trade-off. Adds a regression-grep gate (zero `.btn-primary`/`.btn-secondary` rules in any `<style scoped>` block after the sweep). |
| D3  | Backend `audio/lookup` extended to accept `content_type=annotation` (single annotation by `Annotation.id`); always returns `pregenerated:false`; `Annotation.selected_text` + (optional) `note` joined with `\n\n` are passed through the canonical `sanitize()`. | (a) extend lookup (chosen); (b) frontend bypass via GET /annotations/{id} + client-side sanitize. | Keeps a single sanitizer code path for all content types (avoids the divergence anti-pattern per the audiobook spec). `ANNOTATION` value is added to backend `ContentType` enum but explicitly excluded from `audio_files`/`audio_positions` CHECK constraints (it's never persistable — matches existing `ANNOTATIONS_PLAYLIST` pattern but for single-annotation runtime use). Frontend `AudioContentType` union stays unchanged (annotation lookup uses a thin wrapper, see §7.3). |
| D4  | `useTtsEngine.load()` is the single chokepoint that reads `settingsStore.tts.voice` + `settingsStore.tts.default_speed` for Web Speech, when no explicit voice is passed. | (a) chokepoint in load() (chosen); (b) every call site passes settings. | Single responsibility; existing call sites (`TtsPlayButton`, `Playbar.midListenRegen`, future) need no change. Pattern: settings consumed at the boundary that constructs the engine. |
| D5  | Global `Playbar` and global Space-key handler mount **once** in `AppShell.vue`. Existing reader-scoped Space handler in `ReadingArea.vue:45` stays as defense-in-depth. | (a) AppShell (chosen); (b) App.vue root. | AppShell is the canonical layout shell wrapping `RouterView`; matches the established pattern for app-wide overlays (per `docs/specs/2026-04-25-v1.5-reader-ux-polish-followups-spec.md` D11). Both Space handlers call `store.play()`/`store.pause()` — idempotent. |
| D6  | In-progress indicator is an indeterminate spinner + `M:SS elapsed` driven by a local `activeJobId` override on `BookSummaryTab.computed(state)`; clears on `processing_completed`/`processing_failed`/`job_cancelling` SSE. | Carried from req D7. | (No re-deliberation; req decision sound.) |
| D7  | Engine priority at lookup time: pre-generated Kokoro MP3 wins over Web Speech when both are available (existing `useTtsEngine.load()` behavior); Web Speech otherwise. | Carried from req D8. | (No re-deliberation.) |
| D8  | Listen button placement: header action row, leftmost — `Listen | Read Section Summaries | Regenerate` on summaries, `Listen | …existing actions` on section content, per-row right-aligned on annotations. | (a) leftmost in header row (chosen); (b) right of title; (c) below title. | Aligns with how AudioTab presents its primary action. Predictable scan path. |
| D9  | When Web Speech is unsupported AND no MP3 exists for the content, Listen button is **hidden entirely** (not disabled with tooltip). | (a) hide (chosen); (b) disabled+tooltip. | Web Speech support is browser-level and won't change in-session; a disabled button is permanent noise. |
| D10 | `audio/lookup` latency for the new Listen entry points is treated as the existing fast path; no new NFR. | (a) no new NFR (chosen); (b) add `<300ms p95` budget. | Resolved Q12. Audiobook-mode spec NFR-04 already pins sanitizer at ≤50ms; total lookup is dominated by network for a localhost install. |
| D11 | Sanitizer is content-agnostic; the same `sanitize()` is used for section_content, summaries, and annotations. | (a) reuse (chosen); (b) introduce `content_mode` profile. | Resolved Q7 — `audio/lookup` already routes `SECTION_CONTENT` through the same sanitizer; no field reports of "poor audio for chapters with image refs / code blocks / tables" today. If a later regression surfaces, the fix is a sanitizer rule bump, not a new code path. |
| D12 | The Generate-Audio-Modal Engine field, AnnotationsTab "Build playlist" CTA, and any audio-row primary actions all switch to `.btn-primary`. Cancel/dismiss/secondary actions switch to `.btn-secondary`. | n/a — implementation detail of D2 sweep. | Codifies the primary/secondary mapping per surface so the sweep is mechanical, not judgmental. |
| D13 | `SettingsTtsPanel` gains a **Reset to defaults** button that PUTs `{engine: "web-speech", voice: "", default_speed: 1.0, auto_advance: true}` (i.e., the `TTSConfig` defaults). The existing **Save** flow stays. The existing **Test** path is `VoiceSampleButton` (per-engine row, already wired). | (a) add Reset only (chosen); (b) also add a separate Test button. | `VoiceSampleButton` already provides per-engine preview synchronously inside the click handler (iOS-safe). Reset is the only missing affordance per req G4. |
| D14 | `mediaSession` wiring for Web Speech is in scope (req D16). Implemented in the engine adapter, not in Playbar; the existing `mediaSessionEnabled` ref on `ttsPlayer` store is the gate. | n/a — req decision. | Confirms the existing scaffolding wires through; spec adds the `MediaMetadata` calls in `WebSpeechEngine.play()` and `mp3Engine` if not already present. |
| D15 | Annotation audio lookup uses a **dedicated route** `GET /api/v1/audio/annotations/{annotation_id}/lookup` rather than reusing `/audio/lookup` with a `book_id=0` sentinel. | (a) dedicated route (chosen); (b) Optional[int] book_id on shared route; (c) book_id=0 sentinel. | Sentinel values make the contract dishonest for non-annotation callers and require an `if ct == ANNOTATION: ignore book_id` branch. Dedicated route is one extra handler with a self-documenting URL. |
| D16 | iOS Safari user-gesture preservation is achieved by **preloading** `audio/lookup` on `<TtsPlayButton>` mount (debounced 500ms per surface), so the click handler reads from cache and calls `engine.play()` synchronously. | (a) preload on mount (chosen); (b) verify-and-hope; (c) 2-step Prepare→Play. | Removes the gesture-chain dependency on cross-browser `await`-after-click behavior. Cost: lookup calls for buttons users may not click — acceptable for a personal-tool with small libraries. The debounce prevents N-button surfaces (AnnotationsView with many annotations) from issuing a thundering herd. |
| D17 | `useTtsEngine()` exposes a `terminate()` method (in addition to `load()`); Playbar's `onClose` calls `terminate()` before `store.close()`. The module-level `lastEngine` stays private. | (a) terminate() on API (chosen); (b) export lastEngine; (c) wire into store.close(). | Preserves encapsulation; one entry point for all teardown paths. |
| D18 | `<TtsPlayButton>` always renders initially (with `visibility: hidden` for up to 300ms while preload resolves), then flips visibility based on `webSpeechSupported \|\| preloadResult.pregenerated`. | (a) render-then-hide (chosen); (b) hide-then-show; (c) keep FR-17 as-was (Web Speech only). | (b) shows a "broken" empty state on every page load. (c) denies MP3 playback to Web-Speech-unsupported users. (a) trades a brief invisible-but-reserved-space state for correctness. |
| D19 | The reader-scoped Space handler in `ReadingArea.vue:45-50` is **deleted** to avoid a no-op race with the new global handler (FR-14). ArrowLeft/ArrowRight branches stay. | (a) delete reader handler (chosen); (b) stopImmediatePropagation in global; (c) per-page handlers, no global. | Both handlers attached to `document` and both call store.play()/pause() — net zero. (b) is brittle to mount order. (c) duplicates the handler across every page hosting Listen. |
| D20 | Preload (FR-25a) uses `IntersectionObserver` to defer the lookup until the button scrolls into view (rootMargin 200px). | (a) IntersectionObserver (chosen); (b) concurrency cap; (c) accept N requests. | AnnotationsView can hold dozens of annotations; (c) is a thundering herd. (b) still wastes lookups for buttons users never see. (a) bounds server load to actual user attention. |
| D21 | Cache invalidation subscribes to the existing `audioJob` Pinia store's audio-completion events; non-audio SSE is ignored. | (a) audioJob events (chosen); (b) TTL only; (c) per-page invalidation. | (b) leaves up to 5min of stale "no MP3" cache after a generation completes. (c) loses the cross-page cache benefit (e.g., from Library → BookDetail). (a) is a precise contract using existing infra. |

---

## 5. User Journeys

Carried verbatim from req §User Journeys (J1–J8). One spec-level clarification:

- **J7 / annotations replace-immediately:** Click on annotation row N's Listen
  while row N-1 is playing → existing `useTtsEngine.load()` path terminates the
  prior engine and opens a new one (same as cross-content-type switch).

---

## 6. Functional Requirements

### 6.1 Summary tab progress (G1)

| ID | Requirement |
|----|-------------|
| FR-01 | `BookSummaryTab.vue` adds a local `startedAt: number \| null` ref set to `Date.now()` when the POST returns 201/202 (or 409 with `active_job_id`). Cleared on SSE `processing_completed`/`processing_failed`/`job_cancelling`/`onerror` and on `book.id` change. |
| FR-02 | A `setInterval(fn, 1000)` started alongside `startedAt` updates a `nowTick` ref so a `computed(elapsedMs)` re-renders each second. Interval cleared in the same lifecycle slots as `startedAt`. |
| FR-03 | The `state==='inProgress'` template renders: an indeterminate spinner element (CSS `@keyframes` rotation, respecting `prefers-reduced-motion`) and the text `Generating book summary… {{ formatElapsed(elapsedMs) }} elapsed`. Format: `M:SS` for `< 10:00`, `MM:SS` thereafter. Initial render reads `0:00`. **Accessibility (G20):** the progress container has `role="status" aria-live="polite" aria-busy="true"`. Screen readers announce the start ("Generating book summary 0:00 elapsed") and tick updates politely (`aria-live="polite"` so they don't interrupt other reads). On completion, `aria-busy` flips to `false`. |
| FR-04 | The existing **Cancel** button on the inProgress template is **removed**. |
| FR-05 | `state` computed gains the rule: when `activeJobId !== null`, return `'inProgress'` regardless of `book.default_summary` (existing logic already does this — verify and assert in test). |
| FR-06 | On second click of **Generate book summary** while `activeJobId` is set, the click is a no-op (button is `:disabled` while `state==='inProgress'`). |
| FR-07 | On 409 response, the body includes `{detail, active_job_id, active_job_started_at}` (G14 — backend extends 409 to include `processing_jobs.started_at` as ISO8601). UI attaches via `attachSse(active_job_id)` AND sets `startedAt = parseISO(active_job_started_at).getTime()`. Elapsed timer reflects actual job age, not the moment of the second click. |
| FR-07b | **Backend change (G14):** `POST /api/v1/books/{id}/book-summary` route extends its 409 response body. Current shape: `{detail: "...", active_job_id: int}`. New shape: `{detail: "...", active_job_id: int, active_job_started_at: str}` where `active_job_started_at` is the ISO8601 of `processing_jobs.started_at` (or `created_at` if started_at is null — for jobs still PENDING). Existing 409 callers (none in production today other than this spec) tolerate the extra field. |

### 6.2 Button parity sweep (G2, D2)

| ID | Requirement |
|----|-------------|
| FR-08 | Add canonical `.btn-primary` and `.btn-secondary` to `frontend/src/assets/main.css`, lifted from `BookOverviewView.vue:454-470` as the baseline, with explicit dark-mode variants (selectors using `.dark` class or `@media (prefers-color-scheme: dark)` — match existing app convention; verify in §10 audit). See §11.1 for exact CSS. |
| FR-09 | Sweep all 9 components currently re-defining `.btn-primary`/`.btn-secondary` in `<style scoped>` — remove the scoped rules: `BookSummaryTab.vue`, `BookOverviewView.vue`, `JobProgressView.vue`, `ReadingSettings.vue`, `DatabaseSettings.vue`, `PresetSettings.vue`, `PresetCreateEditForm.vue`, `CustomEditor.vue`, `BackupSettings.vue`. |
| FR-10 | Sweep raw Tailwind button utilities in `frontend/src/components/audio/` and `TtsPlayButton.vue`: replace `bg-indigo-*` / `bg-slate-*` (when used as button background) / `border-slate-*` (button border) / `hover:bg-*` (button hover) with `.btn-primary` (primary actions) or `.btn-secondary` (secondary/dismiss/per-row actions) per the mapping in §11.2. |
| FR-11 | Files swept (audio + TtsPlayButton): `AudioTab.vue`, `GenerateAudioModal.vue`, `AudioFileRow.vue`, `AnnotationPlaylistRow.vue`, `SectionsAudioRow.vue`, `Playbar.vue` (Retry button + play/pause + close → primary/secondary as mapped), `StaleSourceBanner.vue`, `TtsPlayButton.vue`, `AnnotationsTab.vue`, `ResumeAffordance.vue`. |
| FR-12 | Regression gate: a CI grep (or unit-level static check) asserts zero matches of pattern `\.btn-(primary\|secondary)\s*\{` inside any `<style scoped>` block in the swept components, and zero matches of `bg-indigo-(500\|600\|700)\b` / `border-slate-(200\|300\|400\)` inside `frontend/src/components/audio/**` / `TtsPlayButton.vue`. Exact grep commands in §13. |

### 6.3 Listen entry points (G3)

| ID | Requirement |
|----|-------------|
| FR-13 | `<Playbar />` is mounted **once** in `AppShell.vue` so it survives route navigation. Any per-view Playbar mounts (none currently in production code, but verify in audit) are removed. |
| FR-14 | `AppShell.vue` adds a global `keydown` listener that toggles `ttsPlayer.play()`/`pause()` when `Space` is pressed and `ttsPlayer.isActive===true` and the active element is NOT: an `<input>`/`<textarea>`/`[contenteditable]`, NOR (G21) a `<button>`/`<a>`/`[role="button"]`. Excluding focusable activators prevents the double-fire where a focused Listen button activates (opens Playbar + play()) AND the global Space handler also fires (immediately pause()). The Space branch in `ReadingArea.vue:31-54` is **removed** (FR-14b) so the global handler is the single owner. ArrowLeft/ArrowRight branches in ReadingArea stay (reader-scoped sentence-skip). |
| FR-14b | Delete `if (e.key === ' ') { … }` block (lines 45-50) from `frontend/src/components/reader/ReadingArea.vue`. Existing `ReadingArea.keybindings.spec.ts` test asserting Space behavior must be relocated/rewritten against `AppShell.vue`'s global handler. |
| FR-15 | A `<TtsPlayButton>` appears as the **leftmost** item in the header action row of: `BookSummaryTab.vue` (when `state==='populated'`), `SectionSummaryTab.vue` (or equivalent — see §8.3 audit), and `SectionContent.vue` / `SectionDetailView.vue`. Bound to `(contentType, contentId)` per surface — see §7.3. **Click-time loading state (G19):** on click, the button enters `disabled` state with a small inline spinner replacing the play icon, until `store.status` transitions out of `'loading'`. Prevents double-click and signals work in flight. |
| FR-16 | `AnnotationsView.vue` renders a `<TtsPlayButton>` per annotation row, right-aligned in the existing per-row action area. `contentType='annotation'`, `contentId=annotation.id`. |
| FR-17 | `<TtsPlayButton>` always renders initially (so the preload in FR-25a can fire). Visibility predicate (G4): `visible = (webSpeechSupported \|\| preloadResult?.pregenerated === true) && preloadResult?.sanitized_text !== ""`. Empty-content lookups (any contentType — annotation with no text/note, summary with whitespace-only content, etc.) hide the button. While `preloadResult === undefined` (preload in flight), the button renders with `visibility: hidden` (occupying layout) for up to 300ms; after 300ms or once the preload resolves, visibility flips to its final state. (`useWebSpeechSupported()` composable still caches the one-shot Web Speech probe.) Resolves Q3 from spec Open Questions. |
| FR-18 | `useTtsEngine.load()` reads `settingsStore.tts.voice` and `settingsStore.tts.default_speed` when `args.voice` is undefined and the resolved engine is `web-speech`. Both are passed to `WebSpeechEngine` constructor (rate already plumbed; voice already plumbed — verify settings read is added). |
| FR-19 | `WebSpeechEngine.play()` (first call only) sets `navigator.mediaSession.metadata = new MediaMetadata({ title, artist, album })` where: `title` = "Section summary" / "Book summary" / "Section content" / "Annotation" (mapped from contentType), `artist` = book title (resolved from `useRoute().params.bookId` via `booksStore.getById`), `album` = "Book Companion". `navigator.mediaSession.setActionHandler('play'/'pause'/'stop', …)` is wired in the same call. Gated by `ttsPlayer.mediaSessionEnabled === true` (existing flag). |
| FR-19b | `Mp3Engine.play()` symmetrically sets `navigator.mediaSession.metadata` with the same shape (title varies by contentType; artist=book title; album="Book Companion"). Action handlers `play`/`pause`/`stop` route to `engine.play()`/`engine.pause()`/`store.close()+terminate()`. Gated by `ttsPlayer.mediaSessionEnabled`. The §8.3 audit determines whether this is a net-new wiring or an extension; either way the FR is binding. |
| FR-20 | When `useTtsEngine.load()` cannot resolve to either engine (no MP3 available AND `'speechSynthesis' in window === false`), it calls `store.setError('engine_unavailable')` (existing kind). Playbar surfaces this with the existing error template + Retry button (Retry is a no-op in this case — acceptable; see E5). |

### 6.4 Backend annotation audio lookup (D3, D15)

| ID | Requirement |
|----|-------------|
| FR-21 | Backend `ContentType` enum (`backend/app/db/models.py:82`) gains `ANNOTATION = "annotation"`. **Not added** to `audio_files.content_type` / `audio_positions.content_type` CHECK constraints (runtime-only; never persisted). Alembic revision is schema-empty (see §9.2). If `--autogenerate` emits ALTER TABLE for the CHECK constraints, discard those statements. |
| FR-22 | New route `GET /api/v1/audio/annotations/{annotation_id}/lookup` in `backend/app/api/routes/audio.py`. Handler: fetch annotation via `AnnotationRepository.get_by_id(annotation_id)`; 404 if not found; build `source_md = (a.selected_text or "") + ("\n\n" + a.note if a.note else "")`; pass through the existing `sanitize()` path. Always returns `pregenerated: false`. Response shape identical to `/audio/lookup` (see §7.1). |
| FR-22b | Existing `/api/v1/audio/lookup` rejects `content_type=annotation` with `400 {"detail":"use /audio/annotations/{id}/lookup for annotations"}` instead of the default enum-validation 400, so future callers get a self-redirecting hint. |
| FR-23 | New helper `audioApi.lookupAnnotation(annotationId: number)` in `frontend/src/api/audio.ts` targets the new route. `AudioContentType` stays the persistable subset. The wrapper signature is `Promise<AudioLookupResponse>` so callers consume the same shape. |
| FR-24 | `useTtsEngine.load()` routes by `contentType`: when `contentType === 'annotation'`, call `audioApi.lookupAnnotation(contentId)`; otherwise `audioApi.lookup({book_id, content_type, content_id, voice})`. Engine selection + store wiring unchanged. |
| FR-25 | The audio_files / audio_positions repositories and the `SectionEditService` re-import flow do NOT need changes — annotation rows have nothing in those tables to clean up. Confirmed by inspection of `cli/commands/maintenance_cmd.py:35,55`. |
| FR-25a | **Preload trigger.** `<TtsPlayButton>` preloads its lookup via `IntersectionObserver` (root: viewport, rootMargin `200px`), debounced 500ms after intersection. **Exception** (G1): when `contentType === 'section_content'`, preload triggers on `mouseenter`/`focus`/`touchstart` of the button instead of IntersectionObserver — `section_content` sanitization is expensive (large `content_md`), so we defer until intent is signalled. |
| FR-25b | **Cache module.** A singleton module `frontend/src/composables/audio/preloadCache.ts` exports `getCached(key)`, `preload(args)`, `invalidate(key)`, `initCacheSubscription()`. The cache is a `Map<string, CacheEntry>` where `CacheEntry = { result?: AudioLookupResponse, promise?: Promise<AudioLookupResponse>, error?: Error, createdAt: number, expiresAt: number }`. Key format: `${contentType}:${contentId}` (relies on globally-unique IDs across the schema — section/annotation/book PKs are `Integer PRIMARY KEY` and never reused; assumption documented in §8.4). |
| FR-25c | **Coalescing (G24).** `preload(args)` first calls `cache.get(key)`. If entry exists with `result` or `promise`, return existing. Else **synchronously** create a placeholder entry `{ promise: pendingPromise, createdAt: now, expiresAt: now+5min }` and `cache.set(key, placeholder)` BEFORE issuing the fetch — this prevents N parallel preloads for the same content. The fetch promise resolves into the same map entry. |
| FR-25d | **Error handling (G5).** On preload rejection, set entry to `{ error, createdAt: now, expiresAt: now+30s }` (short TTL on errors). On subsequent click, if entry has `error`: fire a fresh lookup synchronously inside the click handler. If THAT fails, call `store.setError('lookup_failed')`; Playbar surfaces error+Retry. Visibility predicate (FR-17) treats `error` as `pregenerated:false`. |
| FR-25e | **Invalidation race guard (G26).** The cache module tracks `lastInvalidatedAt: Map<string, number>`. On preload resolution, if `lastInvalidatedAt[key] > entry.createdAt`, **discard** the resolved result and immediately re-fire the preload (one retry max; on second mismatch, log and store the result anyway to avoid livelock). Prevents stale writes after SSE-triggered invalidation. |
| FR-25f | **Cache subscription lifecycle (G8/G25).** `initCacheSubscription()` is called **once** from `AppShell.vue`'s `onMounted` hook (so it's always live regardless of which view triggered audio generation). It calls `useAudioJobStore().$onAction(({ name, args }) => …)` and inspects `args[0].event` for the canonical audio-completion event names (per CLAUDE.md gotcha #23: `section_audio_completed`, `book_audio_completed`, `annotations_playlist_audio_completed`, plus `_failed`/`_already_stale` variants). On any audio-completion event, calls `invalidate(key)` for the affected `${contentType}:${contentId}` (events for `section_audio_completed` invalidate BOTH `section_summary:N` and `section_content:N`). Non-audio SSE events are ignored. Subscription is never torn down (AppShell lifetime = app lifetime). |
| FR-25g | **Observer/timer teardown (G13).** `<TtsPlayButton>`'s `onUnmounted` hook calls `observer?.disconnect()` and clears the `setTimeout` for the 300ms render-then-resolve fallback (FR-17). In-flight preload promises continue (their results populate the cache for future buttons — useful, not leaked). |
| FR-25h | **Click-time gesture preservation (G10).** Click handler reads from cache and calls `engine.play()` synchronously when entry has `result`. When entry has only `promise`, click `await`s it (iOS gesture chain may break in this rare timing — covered by NFR-02 8s soft-timeout + /verify manual iOS test in §13.4). When entry has `error` or is missing, fresh lookup fires per FR-25d (gesture chain breaks; documented residual risk for cold-cache slow-network iOS). |

### 6.5 Web Speech settings UX (G4, D1, D13)

| ID | Requirement |
|----|-------------|
| FR-26 | `SettingsTtsPanel.vue` adds a **Reset to defaults** button next to the existing **Save** button. On click: confirms via `window.confirm("Reset TTS settings to defaults?")` then PUTs `{engine: "web-speech", voice: "", default_speed: 1.0, auto_advance: true}` to `/api/v1/settings/tts`. After 200, refreshes local refs from the response (or re-loads via `load()`). |
| FR-27 | Voice picker: when `webSpeechVoices` is empty AND `noVoicesAvailable` is false (i.e., `voiceschanged` hasn't fired yet), show an `<option disabled>Loading voices…</option>` placeholder. After populated, the existing `<option v-if="noVoicesAvailable">No voices available</option>` covers the truly-empty case. |
| FR-28 | When the persisted `webSpeechVoice` value is no longer in `webSpeechVoices` after `voiceschanged`, append a synthetic disabled `<option>` showing `{{ webSpeechVoice }} (unavailable on this device)`, and surface a `<p class="text-xs text-amber-700">Previously selected voice not available; falling back to browser default.</p>` hint above the picker. The PUT-on-Save body still sends `webSpeechVoice` unchanged (server-side state is per-config, not per-device — D1 trade-off). On next playback, `WebSpeechEngine` will fall through to the browser default (per its existing `voices.find((vc) => vc.name === voiceName)` returning undefined → no `utt.voice` set). |
| FR-29 | Rate slider: existing `default-speed` slider already covers 0.5–2.0× — no change to range/step. |
| FR-30 | Test button: existing `VoiceSampleButton` (per-engine row) already calls `speechSynthesis.speak()` synchronously inside the click handler (iOS-safe per its `:32-37` impl — verify in audit). No new Test button required. (Resolves req G4 "Test button" by reference to existing component.) |

### 6.6 Cross-cutting

| ID | Requirement |
|----|-------------|
| FR-31 | `useTtsEngine()` exposes a public `terminate()` method that calls `lastEngine?.terminate()` and clears the module-level `lastEngine` (D17). `Playbar.onClose` calls `useTtsEngine().terminate()` before `store.close()` so closing the Playbar stops Web Speech utterances and MP3 playback immediately. Without this, closing the Playbar leaves the engine running — current bug being fixed. |
| FR-32 | Cross-page playback persistence: navigating between routes does NOT stop playback (already true since Playbar moves to AppShell, no per-view mount/unmount). Asserted by Playwright test in §13. |

---

## 7. API Changes

### 7.1 `GET /api/v1/audio/annotations/{annotation_id}/lookup` — NEW

**Request:**
```
GET /api/v1/audio/annotations/42/lookup
```

No query params. (No `book_id` because annotation sanitization is not
book-scoped — D15.)

**Response (200):**
```json
{
  "pregenerated": false,
  "sanitized_text": "Lorem ipsum…",
  "sentence_offsets_chars": [0, 12, 35],
  "url": null,
  "duration_seconds": null,
  "voice": null,
  "sentence_offsets_seconds": null,
  "source_hash": null,
  "source_hash_stored": null,
  "source_hash_current": "<sha256>",
  "sanitizer_version_stored": null,
  "sanitizer_version_current": "1.0",
  "stale": null
}
```

**Errors:**
- `404` `{"detail":"annotation not found"}` — when `annotation_id` does not resolve via `AnnotationRepository.get_by_id`.
- `500` `{"detail":"sanitization failed"}` (G16) — unexpected exception in `sanitize()`. Frontend Playbar shows error+Retry; click handler logs the response body for diagnostics.
- Empty annotation (no `selected_text`, no `note`): returns the empty shape (`pregenerated:false`, `sanitized_text:""`, `sentence_offsets_chars:[]`). Per FR-17 + G4, the Listen button is hidden in this case.

### 7.2 `GET /api/v1/audio/lookup` — UNCHANGED

The existing route is not modified. `content_type` continues to accept only
the persistable subset (`section_summary`, `book_summary`, `section_content`,
`annotations_playlist`); a request with `content_type=annotation` returns
`400` (the route should explicitly reject it with a clearer error than the
generic enum-validation 400 — FR-22b).

### 7.3 No other API changes

`/api/v1/settings/tts` (PUT) — unchanged; FR-26's Reset uses the existing
endpoint with default values in the body.

### 7.4 Frontend `audioApi.lookupAnnotation` helper

```ts
// frontend/src/api/audio.ts (new)
lookupAnnotation(annotationId: number): Promise<AudioLookupResponse> {
  return apiClient.get<AudioLookupResponse>(
    `/audio/annotations/${annotationId}/lookup`,
  )
}
```

`AudioContentType` is unchanged (still the persistable subset). Callers
passing `contentType: 'annotation'` to `useTtsEngine.load()` route through
this helper per FR-24.

---

## 8. Frontend Design

### 8.1 Component changes

| Component | Change |
|-----------|--------|
| `AppShell.vue` | Mount `<Playbar />` inside the layout (after `<RouterView />`, in a `position: relative` container). Add global `keydown` Space listener (FR-14). |
| `BookSummaryTab.vue` | Add `startedAt`/`nowTick` refs + `setInterval`; rewrite `inProgress` template (FR-01–FR-07); add `<TtsPlayButton>` to populated header (FR-15); remove scoped `.btn-primary`. |
| `Playbar.vue` | Replace `bg-indigo-600` on Play/Pause + Retry with `.btn-primary`; close button → `.btn-secondary`. Wire `onClose` to `terminate()` (FR-31). |
| `TtsPlayButton.vue` | Replace inline border/bg classes with `.btn-secondary`. Add prop `hide-when-unsupported?: boolean` (default true) wired to `useWebSpeechSupported()` (FR-17). |
| `SettingsTtsPanel.vue` | Add **Reset to defaults** button (FR-26); add Loading-voices placeholder + persisted-voice-missing hint (FR-27, FR-28). Remove raw `bg-indigo-600` on Save → `.btn-primary`. |
| `AnnotationsView.vue` (or per-row component) | Render `<TtsPlayButton contentType="annotation" :contentId="ann.id" />` per row (FR-16). |
| Section summary view, Section content view | Render `<TtsPlayButton>` in header action row (FR-15). Exact file: identified in audit (§8.3). |
| 9 sweep targets (FR-09) | Remove scoped `.btn-primary`/`.btn-secondary` rules. |
| 10 audio sweep targets (FR-11) | Replace raw Tailwind button utilities per §11.2 mapping. |

### 8.2 New composable

```ts
// frontend/src/composables/useWebSpeechSupported.ts
import { ref } from 'vue'
const supported = ref<boolean | null>(null)
export function useWebSpeechSupported(): { supported: Readonly<Ref<boolean>> } {
  if (supported.value === null) {
    supported.value = typeof window !== 'undefined' && 'speechSynthesis' in window
  }
  return { supported: supported as Readonly<Ref<boolean>> }
}
```

### 8.3 Audit items resolved before implementation

- **`SectionSummaryTab.vue` exact path** — grep `frontend/src/components/section/` and `frontend/src/views/`; the file currently rendering section summary tab content. (Likely `BookOverviewView.vue` tab dispatcher or a sibling.) Spec implementation must locate and add `<TtsPlayButton contentType="section_summary" :contentId="section.id" :hasSummary="!!section.default_summary_id" />`.
- **`SectionContent.vue` exact path** — same audit, content tab.
- **`AnnotationsView.vue` per-row component** — confirm whether annotations render via a child component (likely `AnnotationListRow` or inline). Listen button placement targets that row.
- **Existing `<style scoped>` `.btn-primary`/`.btn-secondary` definitions** — `grep -rn '\.btn-\(primary\|secondary\)\s*{' frontend/src --include="*.vue"` produces the canonical sweep list; assert it matches the 9 files in FR-09 (extras get added).
- **`Mp3Engine.play()` mediaSession wiring** — grep for `mediaSession` in `composables/audio/`; if absent, FR-19's symmetric wiring is mandatory.
- **`VoiceSampleButton` iOS-gesture safety** — verify `speechSynthesis.speak()` is called synchronously in the click handler (no `await` before it). If an `await` exists, refactor before claiming FR-30.
- **Dark-mode convention** — grep for `\.dark\s` vs `prefers-color-scheme` in `assets/*.css` and `<style>` blocks; pick the dominant pattern for FR-08.

### 8.3a Cache-key uniqueness assumption (G12)

The preload cache key `${contentType}:${contentId}` relies on **globally unique
IDs** across the schema. All relevant primary keys (`book_sections.id`,
`books.id`, `annotations.id`) are `Integer PRIMARY KEY` autoincrement and never
reused. A future change to per-book section IDs (e.g., `(book_id, order_index)`
composite key) would break this assumption and require the cache key to include
`bookId`. Documented here so that change is caught at /spec time, not in
production.

### 8.4 State + interaction map

```
<TtsPlayButton contentType=X contentId=N> mounted:
  └─ debounce(500ms) → audioApi.lookup*(X,N) → cache miss → fetch → cache result
                                            (FR-25a; preserves iOS gesture chain at click time)

Click <TtsPlayButton>:
  └─ store.open({contentType:X, contentId:N}) → status='loading', isActive=true
     └─ AppShell <Playbar v-if="store.isActive"> mounts/reveals
     └─ Listen button itself does NOT toggle ▶/⏸ (single-shot per req D5)
  └─ useTtsEngine.load({bookId, contentType:X, contentId:N})
     ├─ X==='annotation' → audioApi.lookupAnnotation(N)              (cached)
     ├─ else            → audioApi.lookup({book_id, content_type, content_id, voice})  (cached)
     ├─ voice/rate from settingsStore.tts when Web Speech engine resolves
     ├─ engine = (lookup.pregenerated && lookup.url) ? Mp3Engine : WebSpeechEngine
     ├─ wire engine events → store
     ├─ engine.play() (synchronous; gesture preserved because lookup was cached)
     └─ navigator.mediaSession.metadata set (gated on store.mediaSessionEnabled)
        FR-19  WebSpeechEngine
        FR-19b Mp3Engine

Playbar.onClose():
  └─ useTtsEngine().terminate()    ← FR-31 / D17 (clears module-level lastEngine)
  └─ store.close()
```

---

## 9. Database Design

### 9.1 Schema

**No table/column changes.** Only change: backend Python `ContentType` enum
gains `ANNOTATION = "annotation"` (FR-21). The `audio_files`/`audio_positions`
CHECK constraints are NOT extended — annotation lookups are runtime-only.

### 9.2 Migration

A new Alembic revision is required because `ContentType` is an enum used in
the SQLAlchemy model layer. SQLite stores enums as TEXT, so the migration is
schema-empty (no DDL). The revision exists to:

- Document the enum extension in version control.
- Anchor the FR-21 verification point (autogenerate-diff is empty).

```python
# revision = "v1_6_a"
# down_revision = "<previous>"
def upgrade() -> None:
    pass  # ContentType.ANNOTATION is application-level; no DDL needed.

def downgrade() -> None:
    pass
```

If `--autogenerate` produces ALTER TABLE for `audio_files.content_type` /
`audio_positions.content_type`, **discard those statements** — they would
narrow the CHECK to forbid the new value at the DB layer for tables that
never store it. The current CHECK constraints only allow the persistable
subset; that subset is unchanged.

---

## 9.3 Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | (G22) Preload soft-budget: a single preload call SHOULD complete within 2s on localhost; HARD TIMEOUT 8s after which the cache stores an error sentinel (FR-25d). Bound is informational; no monitoring required. |
| NFR-02 | (G10) `<TtsPlayButton>` click on a content with no successful preload result MUST still attempt a fresh lookup; iOS Safari gesture chain may break in this rare path. /verify includes a manual iOS Safari test (slow-network simulation, click before IO-preload completes — document whether speech starts). |
| NFR-03 | Cache invalidation latency: an `audioJob` SSE event MUST evict the matching cache entry within 100ms of the event reaching the Pinia store (Pinia's `$onAction` is synchronous). Bound is informational. |

## 10. Configuration & Feature Flags

None. This is a UX bundle with no rollout gating.

---

## 11. Specifics

### 11.1 Canonical button CSS (FR-08)

Add to `frontend/src/assets/main.css` (after the existing utilities):

```css
.btn-primary,
.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-weight: 600;
  font-size: 0.9rem;
  text-decoration: none;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.btn-primary {
  background: var(--color-accent, #4f46e5);
  color: var(--color-text-on-accent, #fff);
}
.btn-primary:hover { background: var(--color-accent-hover, #4338ca); }
.btn-primary:focus-visible { outline: 2px solid var(--color-accent, #4f46e5); outline-offset: 2px; }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-secondary {
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}
.btn-secondary:hover { background: var(--color-bg-secondary); }
.btn-secondary:focus-visible { outline: 2px solid var(--color-accent, #4f46e5); outline-offset: 2px; }
.btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }
```

Dark-mode variants are inherited via the existing CSS custom properties in
`theme.css` (which already swap `--color-bg-primary` etc. by mode); no
additional rules required IF that audit (§8.3) confirms `theme.css` defines
the dark variants. If not, add `.dark .btn-primary { … }` (or
`@media (prefers-color-scheme: dark)`, matching the dominant convention) with
the equivalent dark token swap.

### 11.2 Audio sweep mapping (FR-10/11)

| Component | Current button | New class |
|-----------|----------------|-----------|
| `AudioTab.vue` "Generate audio" | `bg-indigo-600 text-white …` | `.btn-primary` |
| `AudioTab.vue` Cancel | `bg-slate-200 …` | `.btn-secondary` |
| `GenerateAudioModal.vue` Generate | `bg-indigo-600 …` | `.btn-primary` |
| `GenerateAudioModal.vue` Close | `bg-slate-200 …` / `border-slate-300` | `.btn-secondary` |
| `AudioFileRow.vue` Play / Re-generate | `border-slate-300 …` | `.btn-secondary` |
| `AudioFileRow.vue` Delete | `text-red-600 hover:bg-red-50` | **keep raw** (red-destructive is intentional, not in sweep scope) |
| `AnnotationPlaylistRow.vue` actions | as-is per visual hierarchy | `.btn-secondary` |
| `SectionsAudioRow.vue` actions | per row | `.btn-secondary` |
| `Playbar.vue` Play/Pause | `bg-indigo-600 …` | `.btn-primary` |
| `Playbar.vue` Retry | `bg-indigo-600 …` | `.btn-primary` |
| `Playbar.vue` Close (✕) / Prev / Next | `hover:bg-slate-100 …` | `.btn-secondary` (icon-only — keep `rounded-full` for shape, but bg/hover from class) |
| `StaleSourceBanner.vue` Re-generate | `bg-indigo-600 …` | `.btn-primary` |
| `StaleSourceBanner.vue` Dismiss | `bg-slate-200 …` | `.btn-secondary` |
| `TtsPlayButton.vue` (the Listen button itself) | `border-slate-300 bg-white …` | `.btn-secondary` |
| `AnnotationsTab.vue` Build playlist | `bg-indigo-600 …` | `.btn-primary` |
| `ResumeAffordance.vue` Resume | `bg-indigo-600 …` | `.btn-primary` |
| `SettingsTtsPanel.vue` Save | `bg-indigo-600 …` | `.btn-primary` |
| `SettingsTtsPanel.vue` Reset (NEW) | (new) | `.btn-secondary` |

Icon-only round buttons (Prev/Next/Close in Playbar) keep their `rounded-full`
shape utility but get `.btn-secondary` for color/hover/focus tokens. This may
need a small `.btn-secondary--icon` modifier (no padding override) — define in
§11.1 as a follow-up if visual audit shows the modifier is needed.

---

## 12. Edge Cases

| #  | Scenario | Condition | Expected Behavior |
|----|----------|-----------|-------------------|
| E1 | 409 reattach | Second Generate-summary click while a job is already running | UI gets 409 + `active_job_id`; `attachSse(activeJobId)` fires; spinner shows starting from `0:00 elapsed` (we don't know real start). Acceptable per FR-07. |
| E2 | Page reload mid-job | User reloads `/books/{id}?tab=summary` while a book-summary job is still RUNNING | Spinner does NOT re-attach (no `GET /books/{id}/active-jobs` endpoint per req Non-Goals). Empty/populated state renders per current `book.default_summary`; next click of Generate gets 409 → reattach (E1). |
| E3 | SSE error / disconnect | `es.onerror` fires before completion | Existing path: `detachSse()` + `emit('book-refetch')`. After refetch, `book.default_summary` may now be populated → state→`'populated'`; or unchanged → state→`'empty'`. Spinner stops in either case. |
| E4 | Listen click on annotation with no text and no note | `annotation.selected_text===null` and `annotation.note===null` | Backend returns empty `sanitized_text:""`. `WebSpeechEngine` constructor receives empty string → `sliceSentences` returns `[""]` → `speakAt(0)` finds `text===""` → `endCb` fires immediately. Playbar opens, status flips to `'ended'`. Acceptable; alternatively the button can be hidden when `!annotation.selected_text && !annotation.note` — implementer choice (recorded as §17 Q3). |
| E5 | Web Speech unsupported AND lookup returns `pregenerated:false` | User on a browser without `speechSynthesis`; no MP3 generated | Per FR-17, the button was hidden at render time so this path is unreachable from the Listen UI. If reached programmatically (e.g., a stale tab), `WebSpeechEngine.play()` calls `emitError('engine_unavailable')` → store error → Playbar Retry shows but is a no-op. (Acceptable rare path.) |
| E6 | Persisted Web Speech voice no longer present on this device | `webSpeechVoice = "Alex"` in TTSConfig but voice list doesn't include it | Per FR-28: dropdown shows the missing voice as a disabled option + amber hint. `WebSpeechEngine` falls through to browser default at playback time. |
| E7 | iOS Safari user-gesture | User clicks Listen on iPhone Safari | Resolved by D16 / FR-25a: `<TtsPlayButton>` preloads the lookup on mount, so the click handler reads from cache and calls `engine.play()` synchronously. No `await` between click and `speak()`. Eliminates gesture-chain breakage on every browser, not just iOS. |
| E8 | User clicks Listen on row N while row N-1 is playing (annotations) | Cross-content switch | Existing `useTtsEngine.load()` calls `lastEngine.terminate()` before constructing the new engine. Verified in `composables/audio/useTtsEngine.ts:55-62`. |
| E9 | Playbar Close while Web Speech is mid-utterance | User clicks ✕ | Per FR-31: `lastEngine.terminate()` calls `speechSynthesis.cancel()`; then `store.close()`. Without FR-31, the utterance keeps playing — current bug being fixed in this spec. |
| E10 | User changes voice in settings while Playbar is active | User opens Settings tab, picks a new voice, clicks Save, returns to listening | The new voice is read on the NEXT `useTtsEngine.load()` call, NOT the current playback. Active utterance continues with the old voice. Acceptable; matches "settings apply to next playback" wording in J8 step 8. |
| E11 | localStorage quota / private mode (per learnings.md G7-G9) | N/A | Web Speech settings live server-side (D1) — none of the localStorage failure modes apply to this bundle. Reader-settings localStorage paths are unchanged. |
| E12 | `processing_jobs` partial UNIQUE collision | User clicks Generate-summary twice in same second | The existing partial UNIQUE index on `(book_id) WHERE status IN ('PENDING','RUNNING')` rejects the second INSERT → API returns 409 (with `active_job_started_at` per FR-07b) → E1 reattach. No new code needed. |
| E13 | (G6) Cross-tab settings save | Tab A and Tab B both PUT /api/v1/settings/tts with different voices | Server is last-write-wins; per-tab in-memory voice may diverge until a refresh. Acceptable for single-user tool; no version/conflict detection added. |
| E14 | (G2) mediaSession `artist` for cross-book annotation | An annotation belonging to book X is opened from a route under book Y (future cross-book annotation views) | mediaSession `artist` resolves from the current route's bookId. Cross-book annotation views are out-of-scope for v1; if added later, the metadata helper will need to accept an explicit `bookId` arg from the caller. |
| E15 | (G3, G18) `terminate()`-then-`load()` rapid switch | Playbar.onClose calls terminate(); a new load() arrives microseconds later | `useTtsEngine().terminate()` is idempotent (`lastEngine?.terminate(); lastEngine = null`). load() then constructs a new engine and re-assigns `lastEngine`. Sequential calls are race-free; module-level state is the single source of truth. |
| E16 | (G11) Voice `""` (TTSConfig default) at first install | User has never opened SettingsTtsPanel; TTSConfig.voice is empty string | `useTtsEngine.load()` passes `voice=""` to `WebSpeechEngine`; constructor stores `voiceName=""`; `voices.find(name === "")` returns undefined → no `utt.voice` set → browser default voice plays. Working but undocumented in user-facing UI. |
| E17 | (G9) Preload thundering herd on fast scroll | User scrolls AnnotationsView with 100 annotations rapidly | IntersectionObserver fires per intersected button (debounced 500ms each); coalescing per FR-25c prevents duplicate-content double-fetches but does NOT cap concurrent unique-content fetches. For 100 distinct annotations, ~100 lookups arrive over the scroll window. Acceptable for personal tool scale; not optimised. |

---

## 13. Testing & Verification Strategy

### 13.1 Unit / component tests (Vitest)

| Test file | Assertion |
|-----------|-----------|
| `BookSummaryTab.spec.ts` (extend) | After `startGenerate()` resolves to 201 with `{job_id:42}`, `state` flips to `'inProgress'` within 0 ticks, template shows "Generating book summary… 0:00 elapsed", spinner element present, no Cancel button. After 1500ms (use fake timers), text shows "0:01 elapsed". On `processing_completed` event, refetch is emitted and `startedAt` clears. |
| `BookSummaryTab.spec.ts` | 409 response with `active_job_id:7` triggers `attachSse(7)` and `startedAt` set. |
| `TtsPlayButton.spec.ts` (extend) | When `useWebSpeechSupported().supported===false` and no `bookId`/`hasSummary` indicates a pre-generated MP3 path, button is not rendered (`wrapper.find('button').exists()===false`). |
| `useTtsEngine.spec.ts` (new) | When called with `contentType:'web-speech'-bound content` and `args.voice===undefined`, `WebSpeechEngine` is constructed with `voice` and `rate` from `settingsStore.tts.voice` and `settingsStore.tts.default_speed`. Mock `audioApi.lookup` to return `pregenerated:false`. |
| `useTtsEngine.spec.ts` | When `contentType==='annotation'`, `audioApi.lookupAnnotation()` is called (NOT `audioApi.lookup`). |
| `Playbar.spec.ts` (extend) | `onClose` calls `lastEngine.terminate()` before `store.close()`. Mock the module-level `lastEngine` accessor. |
| `SettingsTtsPanel.spec.ts` (new) | **Reset to defaults** click PUTs the canonical default body and refreshes local refs. **Loading voices…** placeholder visible while `webSpeechVoices` empty + `noVoicesAvailable===false`. Persisted-voice-missing hint visible when `webSpeechVoice` not in `webSpeechVoices`. |
| `audio_lookup` test (new, backend) | `GET /api/v1/audio/lookup?book_id=0&content_type=annotation&content_id=<id>` for an annotation with `selected_text="Hello world."` returns `pregenerated:false`, `sanitized_text` non-empty. 404 for non-existent annotation. |

### 13.2 Integration / API tests (pytest)

| Test | Assertion |
|------|-----------|
| `tests/integration/api/test_audio_lookup_annotation.py` (new) | `client.get('/api/v1/audio/lookup', params={'book_id':0,'content_type':'annotation','content_id':ann_id})` returns 200 with the sanitized text; sanitizer version present; `pregenerated==False`. |
| `tests/integration/api/test_audio_lookup_annotation.py` | Empty annotation (`selected_text==None`, `note==None`) returns the empty shape, not 500. |
| `tests/unit/db/test_content_type_enum.py` (new) | `ContentType("annotation") == ContentType.ANNOTATION`; not in `audio_files` CHECK constraint inspector output. |

### 13.3 E2E (Playwright)

| Test | Assertion |
|------|-----------|
| `frontend/e2e/listen-section-summary.spec.ts` (new) | Navigate to `/books/1/sections/1?tab=summary` with a section that has a summary. Click `<TtsPlayButton>`. Assert: `window.bcStore.ttsPlayer.isActive === true` (via `page.evaluate`); Playbar element visible; navigate to `/books/1?tab=summary` — Playbar still visible (cross-route persistence per FR-32). Close Playbar — state cleared. |
| `frontend/e2e/listen-annotation.spec.ts` (new) | Open AnnotationsView. Per-row Listen button visible. Click — Playbar appears. (Audio assertion is NOT made — D14: state-only.) |
| `frontend/e2e/book-summary-progress.spec.ts` (new) | Start dev server with a seeded book. Click **Generate book summary**. Assert spinner + "0:00 elapsed" appear within 1000ms (Playwright `waitFor`). Assert no **Cancel** button. Wait for `processing_completed` SSE (or stub it via interception); assert summary content appears. |

### 13.4 Manual / Playwright MCP spot-checks

Per CLAUDE.md "Interactive verification" section — use a free port (e.g. 8765),
ship the frontend build into `backend/app/static`, seed at least one book.

- **Real audio on macOS Safari**: Listen on a section summary; confirm the
  saved voice + rate are used.
- **Real audio on iPhone Safari** (manual, off-laptop): tap Listen; confirm
  Web Speech starts (validates E7).
- **Visual sweep** of all 9 button-promotion targets (FR-09): each surface
  renders the canonical button without obvious regressions. Document any
  surface where the new look is materially worse (review-loop input).
- **Dark-mode visual sweep** of audio surfaces (FR-08 dark variants).

### 13.5 Regression-grep gates (run in CI or `make verify`)

```bash
# FR-12: no scoped redefs in swept components
! grep -rn '\.btn-\(primary\|secondary\)\s*{' \
  frontend/src/components/audio/ \
  frontend/src/components/book/BookSummaryTab.vue \
  frontend/src/views/BookOverviewView.vue \
  frontend/src/views/JobProgressView.vue \
  frontend/src/components/settings/{ReadingSettings,DatabaseSettings,PresetSettings,PresetCreateEditForm,CustomEditor,BackupSettings}.vue

# FR-12: no raw button utilities left in audio sweep targets
! grep -rn 'bg-indigo-\(500\|600\|700\)\|border-slate-\(200\|300\)' \
  frontend/src/components/audio/ frontend/src/components/audio/TtsPlayButton.vue

# FR-13: Playbar mounted exactly once outside tests
[ "$(grep -rn '<Playbar' frontend/src --include='*.vue' | grep -v __tests__ | wc -l)" -eq 1 ]
```

### 13.6 Verification commands

```bash
# Backend
cd backend && uv run python -m pytest tests/integration/api/test_audio_lookup_annotation.py tests/unit/db/test_content_type_enum.py -v
cd backend && uv run ruff check . && uv run ruff format --check .

# Frontend unit
cd frontend && npm run test:unit -- BookSummaryTab.spec TtsPlayButton.spec useTtsEngine.spec Playbar.spec SettingsTtsPanel.spec
cd frontend && npm run lint && npm run type-check && npm run build

# Frontend e2e (against a port-8765 server with seeded data)
cd frontend && BASE_URL=http://localhost:8765 npm run test:e2e -- listen-section-summary listen-annotation book-summary-progress

# Regression gates from §13.5
make verify-grep   # or run the bash block manually
```

---

## 14. Rollout Strategy

Single-user local tool — no feature flags, no staged rollout. Ship as v1.7
("Audio UX polish"). The audiobook-mode v1.6 remains the prior baseline for
rollback (revert the v1.7 commits as a unit; the only DB-touching change is
the application-level enum extension, which is forward-compatible because no
rows ever store the new value).

---

## 15. Research Sources

| Source | Type | Key Takeaway |
|--------|------|-------------|
| `frontend/src/stores/ttsPlayer.ts` | Existing code | Single-engine scalar shape; `TtsContentType` includes `'annotation'` already (runtime-only). |
| `frontend/src/composables/audio/useTtsEngine.ts` | Existing code | Single chokepoint for engine selection; doesn't currently read `settingsStore.tts` (FR-18 fixes). |
| `frontend/src/composables/audio/webSpeechEngine.ts` | Existing code | `voice` + `rate` constructor opts already exist; rate hardcoded to 1.0 because nothing passes it. |
| `frontend/src/components/settings/SettingsTtsPanel.vue` | Existing code | Web Speech voice + rate ALREADY persist to `/api/v1/settings/tts`. Drove D1. |
| `frontend/src/components/settings/VoiceSampleButton.vue` | Existing code | Test-button affordance already exists per-engine. Drove D13 / FR-30. |
| `backend/app/api/routes/audio.py:227-344` | Existing code | `audio/lookup` already supports `section_content`; sanitizer is content-agnostic. Drove D11 / Q7 resolution. |
| `backend/app/db/models.py:82-87` | Existing code | `ContentType` enum live; FR-21 extends it. CHECK constraints in `audio_files`/`audio_positions` only allow the persistable subset — left untouched. |
| `frontend/src/components/audio/TtsPlayButton.vue` | Existing code | Currently a single-shot "open the player" button — req D5 keeps that contract. |
| `frontend/src/views/BookOverviewView.vue:454-470` | Existing code | Canonical `.btn-primary` design lifted for FR-08. |
| `frontend/src/components/reader/ReadingArea.vue:31-54` | Existing code | Existing reader-scoped Space handler — kept as defense-in-depth (D5). |
| `~/.pmos/learnings.md ## /spec` | Pipeline learning | "split-runtime engine registries must split detection" — applied as D3 (annotation lookup is runtime-only). "Removal FRs need grep inventory" — applied as FR-09's explicit 9-file list. |
| `docs/specs/2026-05-02-audiobook-mode-spec.md §7.2` | Adjacent spec | Sanitizer is shared, content-agnostic, version-pinned. Drove D11. |
| Web research (MDN: SpeechSynthesis user-gesture rules, iOS Safari) | External | iOS 14+ relaxed the gesture rule for `speechSynthesis.speak()`, but post-await behavior still has edge cases — captured as risk Q1. |

---

## 16. Open Questions

| #  | Question | Owner | Needed By |
|----|----------|-------|-----------|
| Q1 | _(Resolved by D16 / FR-25a — preload-on-mount eliminates the gesture-chain dependency for the common path; cold-cache slow-network iOS still has residual risk per NFR-02.)_ | — | — |
| Q2 | `Mp3Engine` mediaSession wiring — present today or net-new? Affects whether FR-19b is "extend" or "add from scratch". | Agent (in /plan §8.3 audit) | Before /plan finalizes |
| Q3 | _(Resolved by /simulate-spec G4 — empty-content button is hidden via FR-17 visibility predicate.)_ | — | — |
| Q4 | Dark-mode convention — `.dark` class vs `@media (prefers-color-scheme: dark)`? Affects FR-08 dark variants. | Agent (in /plan §8.3 audit) | Before /plan finalizes |
| Q5 | Exact file paths for SectionSummaryTab and SectionContent components — confirm in audit. | Agent (in /plan §8.3 audit) | Before /plan finalizes |

---

## 17. Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | F1 `book_id=0` sentinel for annotation lookup smelled. F3 iOS gesture chain unverified. F5 missing FR for Mp3Engine mediaSession. F6 `lastEngine` access pattern for Playbar.onClose was unspecified. (Self-fix nits: FR numbering, AudioContentType vs request body wording.) | F1: D15 + FR-22 / §7.1 switched to dedicated route `GET /audio/annotations/{id}/lookup`; FR-22b added explicit 400 on the old route. F3: D16 + FR-25a preload-on-mount; E7 reframed as resolved; Q1 closed. F5: FR-19b made binding (Mp3Engine mediaSession). F6: D17 + FR-31 reworded to use `useTtsEngine().terminate()` public API. §8.4 state map updated. |
| 2 | L2-F3 (BUG): FR-17 hid the Listen button when Web Speech unsupported, denying access even when MP3 exists. L2-F4 (BUG): FR-14 + reader-scoped Space handler both fire and cancel each other (no-op race). L2-F2: preload-on-mount caused 50× thundering herd on AnnotationsView. L2-F1: cache invalidation contract was vague ("any processing_completed SSE"). | L2-F3: D18 + rewrote FR-17 to render-then-hide on preload result. L2-F4: D19 + new FR-14b deletes the reader-scoped Space handler. L2-F2: D20 + FR-25a updated to IntersectionObserver-deferred preload. L2-F1: D21 + FR-25a updated to subscribe to `audioJob` store events; TTL retained as backstop. |
| 3 (/simulate-spec) | Surfaced 23 gaps via 35-scenario trace + 4 fitness buckets + cross-reference + pseudocode for preload-cache and invalidation flows. 12 significant + 11 minor. Categories: preload cache mechanics (4 sig — coalescing race, error sentinel, invalidation timestamp guard, iOS cold-cache); cache subscription lifecycle (3 sig); UX feedback (1 sig spinner ARIA, 1 sig empty-annotation, 1 sig keyboard Space-on-button race, 1 sig 409 elapsed-misleading, 1 minor click loading state); large-content perf (1 sig); plus 8 minor doc/edge-case nits. All 23 dispositioned as Apply. | Rewrote FR-25a as 8 sub-requirements (FR-25a–h) covering preload trigger, cache module shape, coalescing, error handling, invalidation race guard, subscription lifecycle, observer teardown, click-time gesture preservation. Extended FR-17 visibility predicate (G4). Added FR-07b (backend 409 includes `active_job_started_at`). Added FR-14 button-target exclusion (G21). Added FR-15 click-time loading (G19). Added FR-03 ARIA-live (G20). Added §9.3 NFR-01–03 (preload soft-budget, iOS residual risk, cache invalidation latency). Added §8.3a cache-key uniqueness assumption (G12). Added §12 E13–E17 covering cross-tab settings, cross-book mediaSession, terminate-load race, voice="" path, scroll thundering herd. Added 500 error to §7.1. Resolved Q1 + Q3. |
