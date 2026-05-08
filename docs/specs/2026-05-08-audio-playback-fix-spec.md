# Audio Playback Fix — Spec

**Date:** 2026-05-08
**Status:** Draft
**Tier:** 2 — Enhancement (bug fix + UX polish)
**Requirements:** `docs/requirements/2026-05-08-audio-playback-fix.md`

---

## 1. Problem Statement

Pressing Play in the bottom audio Playbar produces no sound on a clean install. The button label flips to "Pause" but `speechSynthesis.speaking` stays `false`, no utterance is queued, and no `<audio>` element is created. The user has no error, no spinner, and no recovery affordance — just a "Pause" button over silence.

**Primary success metric:** clicking Play in the Playbar produces audible output within 500 ms (voices already loaded) or within 2 s (voice-load race) — measured by a Playwright assertion that `speechSynthesis.speaking === true` (Web Speech) or `<audio>.currentTime > 0` (MP3) after the click.

---

## 2. Goals

| #  | Goal | Success Metric |
|----|------|----------------|
| G1 | Play button drives the active engine | Unit test asserts `engine.play()` is called when `store.play()` runs (both Web Speech and MP3 engines) |
| G2 | Pause/Next/Prev/Seek drive the active engine | Unit tests for each control, both engines |
| G3 | First-click voice-load race no longer fails silently | Vitest: with `getVoices()` returning `[]` then firing `voiceschanged` after 200 ms, audio starts; with no `voiceschanged` for ≥1.5 s, error state appears |
| G4 | Visible "starting…" state during the wait | Playwright snapshot shows spinner glyph + `aria-label="Starting"` while waiting for voices |
| G5 | Watchdog catches unknown silent failures | Vitest: when `engine.play()` returns but `speechSynthesis.speaking` stays `false` past 1 s, error state appears |
| G6 | Existing error state surfaces with friendly copy | Playwright shows generic "Audio couldn't start. Try again or check your settings." + Retry button when any of the above fails |

---

## 3. Non-Goals

- **No backend changes.** This is entirely frontend wiring + UX. — because the audio_files / audio_position routes are not implicated.
- **No engine kind switch.** Default stays `web-speech`; Kokoro stays opt-in. — because changing install behavior in a bug-fix release is out of scope.
- **No new TTS controls (rate, voice, skip-by-time).** — the user's complaint is "play does nothing", not "I want more controls".
- **No collapse of Listen + Play into one tap.** — preserves the iOS Safari user-gesture chain across `engine.load()` and `engine.play()`, matches current tests (D3 in requirements).
- **No translation infrastructure for error copy.** — this is a personal tool; English-only is fine.

---

## 4. Decision Log

| #  | Decision | Options Considered | Rationale |
|----|----------|-------------------|-----------|
| D1 | Drive engine commands from `useTtsEngine` helpers; store delegates | (a) Store imports module-scope `lastEngine` directly, (b) Watcher in `useTtsEngine` on `store.status`, (c) Extend `useTtsEngine` with `playActive()`/`pauseActive()`/`nextActive()`/`prevActive()`/`seekActive(idx)` and have store actions call them | (c) — keeps the engine module the single owner of the engine instance (matches existing `terminate()` pattern), avoids reactive timing surprises (status flipping during `load()` would prematurely fire a watcher), avoids store→composable coupling on internal module state. |
| D2 | Web Speech voice-load wait window | (a) No wait — fail fast, (b) Wait indefinitely, (c) 1.5 s with visible "starting…" indicator | (c) — Chromium populates voices in a few hundred ms typically; 1.5 s covers slow first paints without crossing the user's "is this broken?" threshold. Visible indicator > silent absorb because the user already lost trust on the silent-failure incident. |
| D3 | Keep two-click flow (Listen → Play) | (a) Auto-play after Listen, (b) Two clicks | (b) — preserves user-gesture chain across `engine.load()` and `engine.play()`, keeps existing tests valid. Carry-forward from requirements D3. |
| D4 | Voice-wait listener lives inside `WebSpeechEngine.speakAt` | (a) Engine, (b) `useTtsEngine.load()` before constructing engine | (a) — engine already owns synth interaction; localizing the wait to first `speakAt` avoids a wait penalty on every section load. |
| D5 | 1 s post-Play watchdog as a safety net | (a) D1 + D2 only, (b) Engine self-reports liveness via `startWatchdog()` hook | (b) — each engine knows its own liveness signal (`speechSynthesis.speaking` for Web Speech, `audio.currentTime` advancing for MP3). Store-only timer would false-positive on slow starts. Belt-and-suspenders catches autoplay-policy and OS-mute failures that D1/D2 don't address. |
| D6 | "Starting…" indicator UX | (a) Spinner glyph in play button + `aria-label="Starting"`, (b) Separate chip element, (c) Full-Playbar loader | (a) — minimal visual change, accessible, mirrors the spinner pattern already used in `TtsPlayButton.vue` for preload. |
| D7 | Error copy strategy | (a) Per-error-kind copy, (b) One generic message + Retry, kind in tooltip, (c) Keep raw `errorKind` display | (b) — generic "Audio couldn't start. Try again or check your settings." is friendlier; raw `errorKind` carried in `title` attribute for debug. Updates the existing Playbar error template — no new error UI surface. |
| D8 | Keyboard Space handler in `AppShell.vue` follows the same wiring | (a) Leave as-is (state-only), (b) Use the same store actions which now drive the engine | (b) — Space and Playbar buttons share `store.play()`/`store.pause()`. Once those are wired, Space works for free. Captured as FR-08 explicitly. |
| D9 | `engine.load()` success transitions status from `'loading'` to `'paused'` | (a) Leave status at `'loading'` and treat that as playable in the Playbar, (b) Set `status='paused'` at end of `useTtsEngine.load()` success path | (b) — preserves the invariant that `'loading'` means "engine not attached yet" and `'paused'` means "ready to play". Matches the transition diagram in §8.3 and avoids a Playbar special-case for `'loading'`. |
| D10 | Watchdog timing relative to voice-wait | (a) Start watchdog in `playActive()` and have it fire even during voice-wait, (b) Adjust timeout dynamically by the voice-wait remainder, (c) Engine starts the watchdog inside `speakAt` immediately before `synth.speak(utt)` — so each timer measures what it actually measures | (c) — voice-wait and watchdog are conceptually independent: one measures "did voices ever arrive?", the other "did synthesis actually produce sound?". Coupling them via a dynamic timeout (b) adds branching for no benefit; (a) would false-fire during legitimate voice-waits — exactly the path most likely to need watchdog protection later. |
| D11 | Regression test that would have caught the original bug | (a) Rely on unit tests in §11.1 to cover the wiring collectively, (b) Add a dedicated component-level test that mounts the real Playbar + real store + a mock engine and asserts `engine.play()` is called on click | (b) — the bug existed because nothing tested the wiring end-to-end at the component level. A click-through assertion is the cheapest insurance against re-regression. Captured as FR-16. |

---

## 5. User Journeys

### 5.1 Happy Path (Web Speech, voices loaded)

1. User clicks **Listen** on the section header.
2. `TtsPlayButton.onClick` → `store.open()` (status = `loading`) → `engine.load()` constructs a `WebSpeechEngine`, wires callbacks, sets `status='paused'` on success (D9). Engine instance is now the active `lastEngine`.
3. Playbar renders with engine chip "Web Speech", "Limited controls" badge, ▶ Play button (enabled because status is `paused`).
4. User clicks **▶ Play**.
5. `Playbar.onPlayPause` → `store.play()` → calls `useTtsEngine.playActive()` → `engine.play()`.
6. `engine.play()` → `speakAt(0)` → `synth.getVoices()` finds ≥1 voice → engine starts the 1 s watchdog (D10) → calls `synth.speak(utt)`. Browser begins speaking sentence 1.
7. `utterance.onstart` fires → engine cancels the watchdog. Speech continues.
8. Button shows ⏸ Pause. Sentence highlight tracks the active sentence (existing `onSentenceChange` callback).

### 5.2 Voice-Load Race

1–3. Same as 5.1.
4. User clicks **Play** before voices have populated.
5. `store.play()` → `playActive()` → `engine.play()` → `speakAt(0)` → `synth.getVoices()` returns `[]`.
6. Engine attaches a one-shot `voiceschanged` listener and starts a 1.5 s timeout. Calls back to the store via a new callback `onWaitingForVoices()` → store sets `status = 'starting'` (new status).
7. Playbar re-renders the play button as a disabled spinner glyph (⧗) with `aria-label="Starting"`.
8. **Branch A** — voices arrive within 1.5 s: listener fires, engine starts the watchdog (D10) and calls `synth.speak(utt)`, status transitions to `playing`, button reverts to ⏸ Pause. `utterance.onstart` cancels the watchdog.
9. **Branch B** — timeout fires: engine calls `errorCb('engine_unavailable')` → store `setError` → Playbar shows error template "Audio couldn't start. Try again or check your settings." + Retry button.

### 5.3 Watchdog Trip (autoplay/mute/unknown)

1–7. Same as 5.1.
8. At 1 s, watchdog observes `speechSynthesis.speaking === false` AND no sentence-change fired AND no error fired. Engine calls `errorCb('engine_unavailable')`.
9. Playbar shows generic error + Retry. `title` attribute carries the raw kind for debug.

### 5.4 Pause / Resume / Seek

- **Pause:** `store.pause()` → `pauseActive()` → `engine.pause()`. Button reverts to ▶ Play. Sentence index unchanged.
- **Resume:** `store.play()` → `playActive()` → `engine.play()`. Web Speech: `synth.paused` → `synth.resume()` (or restarts the current sentence on browsers that don't preserve mid-utterance state). MP3: `audio.play()` resumes from `audio.currentTime`.
- **Next/Prev:** `store.nextSentence()` / `store.prevSentence()` → `nextActive()` / `prevActive()` → `engine.nextSentence()` / `engine.prevSentence()`. Engine cancels current utterance, advances index, fires `onSentenceChange`, calls `speakAt(newIdx)`.
- **Seek (sentence-row click in reading area):** existing flow → `store.sentenceIndex = idx` then `seekActive(idx)` → `engine.seek(idx)`.

### 5.5 Keyboard Space

1. User has Playbar open and is focused on the reading area body (not an input).
2. Presses Space → `AppShell.onGlobalKeydown` → `store.play()` or `store.pause()`.
3. Same flow as Playbar buttons; engine receives the command via D8.

---

## 6. Functional Requirements

### 6.1 Engine wiring (the bug fix)

| ID    | Requirement |
|-------|-------------|
| FR-01 | `useTtsEngine` exposes `playActive(): Promise<void>`, `pauseActive(): void`, `nextActive(): void`, `prevActive(): void`, `seekActive(idx: number): void`. Each delegates to the module-scope `lastEngine` (no-op if `null`). |
| FR-02 | `useTtsPlayerStore.play()` calls `useTtsEngine().playActive()` after setting `status='playing'` (or `'starting'` per FR-05). |
| FR-03 | `useTtsPlayerStore.pause()` calls `useTtsEngine().pauseActive()` after setting `status='paused'`. |
| FR-04 | `useTtsPlayerStore.nextSentence()` / `prevSentence()` call `nextActive()` / `prevActive()` AFTER updating `sentenceIndex`. (Engine's `onSentenceChange` callback will overwrite the index when the engine actually advances; intermediate UI flicker is acceptable.) |
| FR-08 | The keyboard Space handler in `AppShell.onGlobalKeydown` continues to call `store.play()` / `store.pause()` and inherits the engine wiring via FR-02/FR-03. No direct engine call from `AppShell`. |

### 6.2 Voice-load race

| ID    | Requirement |
|-------|-------------|
| FR-05 | When `WebSpeechEngine.speakAt(idx)` finds `getVoices()` returns `[]`, it MUST attach a one-shot `voiceschanged` listener AND start a 1500 ms timeout instead of immediately emitting `engine_unavailable`. |
| FR-06 | While waiting for voices, the engine MUST emit a new lifecycle event `onWaitingForVoices(true)`. When voices arrive (or timeout fires), it MUST emit `onWaitingForVoices(false)`. The store maps `true` → `status='starting'`. |
| FR-07 | If `voiceschanged` fires within 1500 ms, the engine MUST call `synth.speak(utt)` immediately. If the timeout fires first, the engine MUST emit `errorCb('engine_unavailable')`. The listener and the timer MUST be cleared after either path resolves to avoid leaks. |

### 6.3 Watchdog

| ID    | Requirement |
|-------|-------------|
| FR-09 | `TtsEngine` interface gains `startWatchdog(timeoutMs: number, onTimeout: () => void): void` and `cancelWatchdog(): void`. Existing test-only `_fakeError` is preserved. |
| FR-10 | `WebSpeechEngine.startWatchdog(1000, ...)` schedules a check at 1000 ms: if `synth.speaking === false` AND `synth.pending === false` AND no sentence has fired AND no error has fired, it calls `onTimeout`. |
| FR-11 | `Mp3Engine.startWatchdog(1000, ...)` schedules a check at 1000 ms: if `audio.currentTime` has not advanced from its value at watchdog start AND `audio.paused === true` AND no error has fired, it calls `onTimeout`. |
| FR-12 | The engine MUST start the watchdog inside `speakAt`, immediately before calling `synth.speak(utt)` (Web Speech) or `audio.play()` (MP3) — NOT inside `useTtsEngine.playActive()`. This ensures the watchdog measures actual synthesis liveness, not voice-wait or other pre-play delays (D10). The engine MUST cancel the watchdog on `utterance.onstart` / `audio.onplaying`, on next sentence change, on terminate, and on any error emit. `useTtsEngine.playActive()` provides the `onTimeout` callback that calls `store.setError('engine_unavailable')`. |

### 6.4 UX

| ID    | Requirement |
|-------|-------------|
| FR-13 | Playbar play button MUST render the spinner glyph `⧗` (or equivalent CSS spinner using existing `animate-spin` utility) when `store.status === 'starting'`, with `aria-label="Starting"` and `disabled=true`. |
| FR-14 | When `store.status === 'error'`, Playbar MUST display: text "Audio couldn't start. Try again or check your settings." (replacing the current `Audio error: {{ store.errorKind }}` template), a Retry button (existing behavior), and `title="errorKind: <kind>"` on the surrounding element for debug. |
| FR-15 | The new `'starting'` status MUST NOT count as `isPlaying` (computed). The play-button `aria-label` mapping is: `'starting'` → `'Starting'`, `'playing'` → `'Pause'`, otherwise → `'Play'`. |
| FR-16 | A regression test MUST exist that mounts the real `Playbar.vue` component with the real `useTtsPlayerStore` and a mocked `useTtsEngine` (returning a stub engine), simulates a click on the play-pause button after `engine.load()` resolves, and asserts the stub engine's `play()` was called exactly once. This guards against the original-bug class (UI state changes without engine invocation) at the component level. Lives at `frontend/src/components/audio/__tests__/Playbar.wiring.spec.ts`. |
| FR-17 | `useTtsEngine.load()` MUST set `store.status = 'paused'` on its success path (after wiring callbacks and assigning `lastEngine`), so the play button is enabled when the user sees the Playbar (D9). On `lookup_failed` it MUST leave the existing `setError` path. |
| FR-18 | `engine.pause()` MUST cancel any pending voice-wait listener + timeout AND any active watchdog before delegating to `synth.pause()` / `audio.pause()`. This guarantees that pressing Pause while in `'starting'` cleanly returns to `'paused'` without a stale timer firing later (covers E3). |
| FR-19 | The new methods on `TtsEngine` interface (`startWatchdog`, `cancelWatchdog`, `onWaitingForVoices`) are REQUIRED — both `WebSpeechEngine` and `Mp3Engine` MUST implement them. No optional/default fallback. Test mocks of `TtsEngine` MUST be updated to include stubs (one-line `vi.fn()` each). |

---

## 7. API Changes

None. This is entirely a frontend-internal change. Backend `/api/v1/audio/lookup`, `/audio_position`, and SSE event names are untouched.

---

## 8. Frontend Design

### 8.1 File-by-file changes

| File | Change |
|------|--------|
| `frontend/src/stores/ttsPlayer.ts` | Add `'starting'` to `TtsStatus` union. Modify `play()`, `pause()`, `nextSentence()`, `prevSentence()` to call new `useTtsEngine` helpers. Add `seek(idx)` action. Update `isPlaying` (still `status === 'playing'`). |
| `frontend/src/composables/audio/useTtsEngine.ts` | Add `playActive`/`pauseActive`/`nextActive`/`prevActive`/`seekActive` exports. Wire `engine.onWaitingForVoices` to `store.status` transitions in `load()`. Set `store.status='paused'` on `load()` success (FR-17). Pass watchdog `onTimeout` callback to engine via `engine.startWatchdog(1000, ...)` triggered from inside the engine itself (FR-12); `playActive()` does NOT start the watchdog directly. |
| `frontend/src/composables/audio/types.ts` | Add `WaitingForVoicesHandler` type and `onWaitingForVoices(cb)` + `startWatchdog`/`cancelWatchdog` methods to `TtsEngine` interface. |
| `frontend/src/composables/audio/webSpeechEngine.ts` | Replace immediate `emitError('engine_unavailable')` on empty voices with `voiceschanged` + 1500 ms timeout. Implement `onWaitingForVoices`, `startWatchdog`, `cancelWatchdog`. Cancel watchdog on first `onstart` callback (utterance.onstart). |
| `frontend/src/composables/audio/mp3Engine.ts` | Implement `startWatchdog`, `cancelWatchdog`. No-op `onWaitingForVoices` (always `false`). Cancel watchdog on `audio.onplaying`. |
| `frontend/src/components/audio/Playbar.vue` | Add spinner glyph branch for `status === 'starting'`. Update error template per FR-14. |
| `frontend/src/components/app/AppShell.vue` | No code change (Space already routes through store actions). Verified by FR-08. |

### 8.2 State map

| State | Owner | Notes |
|-------|-------|-------|
| `status` | Pinia store | Adds `'starting'`. Transitions: `loading` → `playing` (sync, voices ready) OR `loading` → `starting` → `playing` (race) OR `loading` → `starting` → `error` (timeout). |
| `lastEngine` | `useTtsEngine` module-scope | Already exists. Single owner of the active `TtsEngine` instance. |
| Watchdog timer | `WebSpeechEngine` / `Mp3Engine` private field | Cleared on `pause`, `terminate`, sentence change, error. |
| Voice-wait timer | `WebSpeechEngine` private field | Cleared on `voiceschanged` fire OR timeout fire OR `terminate`. |

### 8.3 Status transition diagram

```
                 user clicks Listen
        idle ─────────────────────► loading
                                       │
                                       │ engine.load() resolves
                                       ▼
                                    paused (resting state)
                                       │
                                       │ user clicks Play
                                       ▼
                  ┌──────── playing ◄────── starting (waiting on voices, 1.5s max)
                  │            │                │
       Pause/end  │            │ watchdog       │ timeout
                  ▼            ▼ trips          ▼
                paused       error ◄────────── error
                                  ▲
                                  │ utterance_failed / lookup_failed
                                  │ (any other engine error)
```

---

## 9. Edge Cases

| #  | Scenario | Condition | Expected Behavior |
|----|----------|-----------|-------------------|
| E1 | Empty section text | `lookup.sanitized_text === ''` | Listen button is hidden (existing behavior, regression-tested). |
| E2 | Engine never created (preload failed) | `lastEngine === null` when user clicks Play | `playActive()` is a no-op. Store stays at `paused`. User clicks Retry → goes through `open()` → `engine.load()` again. |
| E3 | User clicks Pause while waiting on voices | `status === 'starting'` and Pause is pressed | Cancel voice-wait timer + `voiceschanged` listener. Status → `paused`. Next Play retries the wait. |
| E4 | User clicks Next while waiting on voices | Same | Cancel voice-wait, advance `idx`, attempt `speakAt(newIdx)` — which itself may re-enter the voice-wait flow. |
| E5 | User closes Playbar mid-wait | `close()` called during `starting` | `terminate()` runs, clearing voice-wait + watchdog timers. No orphaned timers. |
| E6 | Section navigation mid-playback | Existing engine `terminate()` runs | Watchdog and voice-wait timers MUST be cleared in `terminate()`. New section's engine starts fresh. |
| E7 | Cross-tab handoff (BroadcastChannel "opening") | Other tab opens TTS | `lastEngine.pause()` runs (existing). After D1, this still hits the engine directly via the same path; no change needed. |
| E8 | Watchdog races with normal start | Engine starts speaking exactly at 1000 ms | The first `utterance.onstart` callback (Web Speech) or `audio.onplaying` event (MP3) cancels the watchdog. So the watchdog only fires if start was actually never observed. |
| E9 | Voices never arrive (offline / browser without TTS) | 1500 ms timeout | Standard error state with Retry. Retry will repeat the wait (acceptable — user is informed they can retry). |
| E10 | MP3 engine watchdog false positive | Slow CDN, audio.canplaythrough delayed | Watchdog requires `audio.paused === true` AND `currentTime` unchanged AND no error. If `canplay` has fired but playback hasn't started, this is genuinely a failure case (autoplay block) — surfacing the error is correct. |

---

## 10. Configuration & Feature Flags

None. The fix is unconditional — there is no scenario in which the user would prefer the silent-failure behavior.

---

## 11. Testing & Verification Strategy

### 11.1 Unit tests (Vitest)

Add to `frontend/src/composables/audio/__tests__/`:

| Test file | New test | Assertion |
|-----------|----------|-----------|
| `useTtsEngine.spec.ts` | `playActive() calls engine.play() on the active engine` | Mock engine, call `playActive()`, assert `engine.play.mock.calls.length === 1`. |
| `useTtsEngine.spec.ts` | `pauseActive/nextActive/prevActive/seekActive forward to engine` | One assertion per method. |
| `useTtsEngine.spec.ts` | `playActive provides watchdog onTimeout that calls store.setError` | Mock engine. Call `playActive()`. Capture the `onTimeout` callback handed to engine (engine starts the watchdog itself per FR-12). Invoke it. Assert `store.setError('engine_unavailable')` ran. |
| `useTtsEngine.spec.ts` | `load() sets status to 'paused' on success` | Mock preloadCache + engine constructors. Call `load()`. Assert `store.status === 'paused'` after resolve. |
| `webSpeechEngine.spec.ts` | `waits for voiceschanged when getVoices is empty` | `getVoices` returns `[]` initially, `[Samantha]` after `voiceschanged`. Fake timer + manually dispatch `voiceschanged`. Assert `synth.speak` is called only after the event. |
| `webSpeechEngine.spec.ts` | `emits engine_unavailable after 1500 ms timeout` | `getVoices` always returns `[]`. Advance fake timer 1500 ms. Assert `onError('engine_unavailable')` called once. |
| `webSpeechEngine.spec.ts` | `emits onWaitingForVoices(true) then (false)` | Subscribe to handler. Run race scenario. Assert sequence. |
| `webSpeechEngine.spec.ts` | `cancels voice-wait on terminate` | Start wait, call `terminate()`, advance timer. Assert no error fired. |
| `webSpeechEngine.spec.ts` | `startWatchdog fires when speaking stays false` | Mock `synth.speaking === false`. Advance 1000 ms. Assert callback fired. |
| `webSpeechEngine.spec.ts` | `watchdog cleared on utterance.onstart` | Trigger `onstart`. Advance 1000 ms. Assert callback NOT fired. |
| `mp3Engine.spec.ts` | `startWatchdog fires when currentTime never advances` | Mock `audio.currentTime` stuck at 0. Advance 1000 ms. Assert callback. |
| `mp3Engine.spec.ts` | `watchdog cleared on audio.onplaying` | Fire `playing` event. Advance. Assert NOT fired. |
| `ttsPlayer.spec.ts` (store test, may need to be created) | `play() calls playActive` | Spy on `useTtsEngine().playActive`. Call `store.play()`. Assert spy called. |
| `Playbar.spec.ts` | `renders spinner when status is 'starting'` | Mount with status='starting', assert button has `aria-label="Starting"` and `disabled`. |
| `Playbar.spec.ts` | `error template shows generic copy` | Mount with status='error', errorKind='engine_unavailable', assert text contains "Audio couldn't start". Assert `title` contains `errorKind`. |
| `Playbar.wiring.spec.ts` (NEW, FR-16) | `clicking play after engine.load() invokes engine.play()` | Real Playbar + real store + `useTtsEngine` mocked to return a stub engine. Trigger TtsPlayButton click programmatically (or set up Playbar in `paused` state with engine attached). Click play-pause. Assert stub `engine.play.mock.calls.length === 1`. |

### 11.2 Integration test — already covered by unit tests

The store↔engine wiring is exercised by `useTtsEngine.spec.ts`. No new integration test needed.

### 11.3 End-to-end (Playwright MCP, manual via `/verify`)

Per CLAUDE.md "Interactive verification" workflow, run on a backend started on port 8765 with the built frontend:

1. `cd backend && uv run bookcompanion serve --port 8765 &`
2. `cd frontend && npm run build && rm -rf ../backend/app/static && cp -R dist ../backend/app/static`
**Prerequisite:** run on macOS system Chrome (or any browser with at least one Web Speech voice installed). MCP Playwright Chrome may have `voiceCount=0` and exercise the voice-wait path instead — that scenario is covered by the unit tests in §11.1 and the dedicated step 10 below.

3. Navigate to `http://localhost:8765/books/1/sections/3?tab=original`
4. Click **Listen** → Playbar appears.
5. Click **▶ Play**.
6. Within 2 s, evaluate `() => ({ speaking: speechSynthesis.speaking, voiceCount: speechSynthesis.getVoices().length })` and assert `speaking === true` AND `voiceCount > 0`.
7. Click **⏸ Pause** → assert `speechSynthesis.speaking === false`.
8. Click **▶ Play** again → assert resumes.
9. Click **⏭** → assert sentence index advances and speech restarts.
10. Reload page; immediately click Listen + Play (race scenario) — assert spinner glyph is visible during the wait, then transitions to playing.

### 11.4 Verification commands

```bash
cd frontend
npm run lint
npm run type-check
npm run test:unit -- src/composables/audio src/stores src/components/audio
npm run build

# Backend stays untouched, but run the suite to catch any incidental breaks:
cd ../backend
uv run python -m pytest tests/unit/ -q
```

Expected: lint clean, types clean, all new + existing tests pass, build succeeds.

---

## 12. Rollout & Risk

- **Rollout:** ship as part of normal release. No flag, no migration.
- **Rollback:** `git revert` of the implementation commit restores the (broken) prior behavior.
- **Risk — voice-wait timeout too short:** if 1500 ms is too tight for some browsers, increase to 3000 ms. Constant lives in `webSpeechEngine.ts`; no API change.
- **Risk — watchdog false positives on slow MP3 starts:** monitored via the dual condition (`paused && !currentTime advanced && no error`). If false positives surface, raise threshold to 1500 ms or remove MP3-side watchdog (Web Speech is the silent-failure surface in practice).
- **Risk — store action wiring breaks an existing test that mocks `useTtsEngine`:** the new helpers are additive; existing mocks that don't include them will need to gain stubs. Tests-as-changesets: any test mounting Playbar that previously asserted "no engine call" will need updating — but those tests would be asserting the bug.

---

## 13. Research Sources

| Source | Type | Key Takeaway |
|--------|------|-------------|
| `frontend/src/stores/ttsPlayer.ts:91-97` | Existing code | Bug surface: `play()`/`pause()` are pure state-setters. |
| `frontend/src/composables/audio/useTtsEngine.ts:51-61, 155` | Existing code | `lastEngine` module-scope ownership pattern; `terminate()` is the template for the new `playActive`/`pauseActive` helpers. |
| `frontend/src/composables/audio/webSpeechEngine.ts:79-115` | Existing code | `speakAt` synchronously emits error on empty voices; needs the wait-and-listen rewrite. |
| `frontend/src/composables/audio/mp3Engine.ts:1-50` | Existing code | MP3 engine uses `<audio>`; `audio.onplaying`/`audio.currentTime` are the natural watchdog signals. |
| `frontend/src/components/audio/Playbar.vue:55-141` | Existing code | Error template + Retry already wired; only the `template v-if` branch and copy strings change. |
| `frontend/src/components/audio/TtsPlayButton.vue:170-186` | Existing code | Spinner SVG + `animate-spin` utility already exists; reuse for the "starting" state. |
| `frontend/src/components/settings/SettingsTtsPanel.vue:125` | Existing code | `voiceschanged` listener pattern already used; mirror it inside the engine. |
| `frontend/src/components/app/AppShell.vue:21-42` | Existing code | Space-key handler routes through store actions; D8 + FR-08 ensure it inherits the fix. |
| MDN: `SpeechSynthesis.getVoices()` async population | External | `voiceschanged` is the documented signal that voices are ready. |

---

## 14. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Was the engine wiring ever there? `git blame frontend/src/stores/ttsPlayer.ts` to determine whether this regressed in a recent refactor or never landed. | Eng | During /plan — informs whether a missing test should be the first task. |

---

## 15. Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| _initial_ | — | First draft. |
| 1 | Status transition gap (load→paused), watchdog vs voice-wait timing, MP3 watchdog redundancy check, missing component-level wiring test. All four addressed. | Added D9, D10, D11. Added FR-16 (component wiring test) and FR-17 (load→paused). Updated journeys 5.1/5.2 to reflect watchdog inside speakAt. Updated FR-12 to move watchdog start out of playActive into the engine. Updated §8.1 file change row for useTtsEngine.ts. Added two unit tests in §11.1 (status='paused' after load, playActive onTimeout wiring). |
| 2 | Pause-during-starting timer leak risk, engine ABI back-compat ambiguity, e2e env prerequisite for Web Speech voices. All three addressed. | Added FR-18 (pause clears voice-wait + watchdog timers), FR-19 (engine ABI methods are required). Added prerequisite note to §11.3 about macOS Chrome vs MCP profile. |
