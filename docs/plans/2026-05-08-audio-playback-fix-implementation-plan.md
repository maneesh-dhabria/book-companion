# Audio Playback Fix — Implementation Plan

**Date:** 2026-05-08
**Spec:** `docs/specs/2026-05-08-audio-playback-fix-spec.md`
**Requirements:** `docs/requirements/2026-05-08-audio-playback-fix.md`
**Simulation:** `docs/specs/simulate-spec/2026-05-08-audio-playback-fix-trace.md`

---

## Overview

Wire the Pinia TTS store to actually drive the underlying engine, handle the Web Speech `voiceschanged` race with a 1.5 s wait + visible "starting…" indicator, add a 1 s post-Play liveness watchdog, fix the Retry button so it re-issues `engine.load()`, surface generic error copy with a recoverable CTA, and add a component-level regression test that mounts the real Playbar + real store and asserts `engine.play()` is called on click. Frontend-only.

**Done when:** Clicking Play in the Playbar produces audible speech (Web Speech) or audio playback (MP3) in real Chrome on macOS; `npm run lint`, `npm run type-check`, `npm run test:unit -- src/composables/audio src/stores src/components/audio` all pass; `npm run build` succeeds; Playwright walkthrough on `http://localhost:8765/books/1/sections/3?tab=original` confirms audio output, working pause/resume/next/prev, and a forced error path that surfaces "Audio couldn't start. Try again or check your settings." + Retry.

**Execution order:**

```
T1 (interface)
   └─► T2 (WebSpeechEngine) ──┐
   └─► T3 (Mp3Engine) ────────┼─► T4 (useTtsEngine helpers)
                              │      └─► T5 (store) ──┬─► T6 (callsites + test fixups)
                              │                       └─► T7 (Playbar UI)
                              │                              └─► T8 (wiring regression test)
                              │                                     └─► T9 (final verification)
```

T2 and T3 are parallelizable [P]. Everything else is sequential because `useTtsEngine`, store, and Playbar form a dependency chain through the type system.

---

## Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| P1 | TDD red→green for engine + store changes; component test (T7/T8) written test-first too | (a) Implement-then-test, (b) TDD throughout | (b) — the bug existed because nothing tested wiring end-to-end. Writing failing tests first against the new contracts (engine interface, store actions, Playbar wiring) ensures we never silently ship the same defect class. |
| P2 | Make `bookId` REQUIRED in `OpenContentArgs` (not optional) | (a) Optional with default 0, (b) Required and update all callsites | (b) — defaulting hides bugs (a 0 bookId silently routes to the wrong audio); required `bookId` is what makes `store.retry()` correctly re-issue `engine.load()`. Surfaces test-fixup work explicitly in T6 instead of letting it rot. |
| P3 | Watchdog liveness check uses `synth.speaking` for Web Speech and `audio.onplaying` event firing as the cancel signal for MP3 — NOT `currentTime` advancing | spec §FR-11 said "currentTime hasn't advanced"; (a) keep that, (b) use `audio.onplaying` event instead | (b) — `currentTime` is sampled; if the watchdog fires at exactly 1 s and `timeupdate` hasn't run yet, false positive. `audio.onplaying` is a clean discrete signal. The event-based approach matches Web Speech's `utterance.onstart` pattern, keeping both engines symmetric. Clarifies §FR-11 intent. |
| P4 | Voice-wait listener uses `addEventListener('voiceschanged', cb, { once: true })` PLUS an explicit `removeEventListener` on cleanup, rather than the `onvoiceschanged` setter pattern used in `SettingsTtsPanel.vue` | (a) Mirror existing setter pattern, (b) Add+remove with `{ once: true }` redundancy | (b) — `onvoiceschanged` is a single-slot property; assigning to it overwrites whatever the settings panel set. `addEventListener` lets multiple consumers coexist without stomping. The `{ once: true }` option auto-removes after firing; explicit `removeEventListener` covers the timeout-fires-first path. |
| P5 | Engine constructors stay synchronous; voice-wait happens lazily inside `speakAt` only | (a) Wait for voices in constructor, (b) Wait inside speakAt on first call | (b) — Spec D4. Construction would block `engine.load()` resolution. Lazy wait means `load()` always resolves quickly to `'paused'` and the visible "starting…" only appears if the user actually clicks Play before voices arrive. |
| P6 | Existing `useTtsEngine.spec.ts` and `Playbar.spec.ts` get fixed up in T6 alongside the callsite refactor — not a separate task | (a) One big test fixup task, (b) Fix tests inside whichever feature task introduces the breaking change | (a) — required-`bookId` ripples through ~10+ test files. Doing them all together preserves a single coherent "now everything compiles + passes" checkpoint instead of leaving test files broken across multiple commits. |
| P7 | Skip `git blame ttsPlayer.ts` open question — fix is the same regardless of regression history | (a) Investigate first, (b) Skip and ship | (b) — the spec's open question (was this regressed or never wired) doesn't change the implementation. If a future plan needs the answer, it's a one-line `git log -p` away. |
| P8 | `'starting'` status renders the spinner with `aria-disabled="true"` AND `disabled` attribute on the play button | (a) Just `disabled`, (b) Both | (b) — `aria-disabled` is the screen-reader signal; `disabled` blocks the click event. Using both matches existing TtsPlayButton pattern. |

---

## Code Study Notes

- **Module-scope engine instance.** `useTtsEngine.ts` already owns a single `lastEngine: TtsEngine | null` at module scope, with a `terminate()` helper that clears it. The new `playActive`/`pauseActive`/etc. helpers slot into this same pattern — they just delegate to `lastEngine` when non-null.
- **Engine wiring already exists for callbacks.** `useTtsEngine.load()` already wires `engine.onError`, `engine.onSentenceChange`, `engine.onEnd` to store actions. The new `engine.onWaitingForVoices` callback follows the same pattern.
- **Engine kinds are symmetric on lifecycle but asymmetric on liveness signals.** Both engines implement `play/pause/nextSentence/prevSentence/seek/terminate/onSentenceChange/onEnd/onError`. WebSpeech reports start via `utterance.onstart`; MP3 reports start via the `audio` element's `playing` event. The watchdog needs to subscribe to whichever signal applies.
- **MP3 engine already handles auto-fail.** `audio.addEventListener('error', this.onAudioError)` already calls `errorCb('mp3_fetch_failed')` on fetch failure. We're adding the watchdog to cover non-error silent stalls (autoplay block, output device unplug).
- **Two callers of `store.open`:** `TtsPlayButton.vue:77` (already has `props.bookId`) and `ResumeAffordance.vue:41,49` (does NOT — needs propagation). Plus 8+ test files that mount the store and call `store.open(...)` without bookId.
- **Pinia store can call composables.** `useTtsPlayerStore.retry()` can call `useTtsEngine().load(...)` directly — Pinia setup-style stores have access to composables.
- **Spinner pattern already exists.** `TtsPlayButton.vue:170-186` uses an inline SVG with `animate-spin` Tailwind utility. Reuse it for the Playbar spinner glyph.
- **Existing error template** lives at `Playbar.vue:69-81` (red text + Retry button). Only the copy and the surrounding `title` attribute need to change.
- **Test patterns.** `useTtsEngine.spec.ts` uses `vi.mock('@/api/audio', ...)` + `setActivePinia(createPinia())`. `Playbar.spec.ts` uses `mount(Playbar)` + `useTtsPlayerStore()`. Reuse both.

---

## Prerequisites

- Repo is on `main`, working tree clean (or on a feature branch dedicated to this fix).
- `cd frontend && npm install` has run.
- For T9 e2e: backend is running on port 8765 with at least one book seeded (CLAUDE.md "Interactive verification" recipe).

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `frontend/src/composables/audio/types.ts` | Extend `TtsEngine` interface with `startWatchdog`, `cancelWatchdog`, `onWaitingForVoices`. Add `WaitingForVoicesHandler` type. |
| Modify | `frontend/src/composables/audio/webSpeechEngine.ts` | Add voice-wait + watchdog + idempotent play + late-onstart guard. Implement new interface methods. |
| Modify | `frontend/src/composables/audio/mp3Engine.ts` | Add watchdog (event-based), idempotent play, no-op `onWaitingForVoices`. Implement new interface methods. |
| Modify | `frontend/src/composables/audio/useTtsEngine.ts` | Add `playActive`/`pauseActive`/`nextActive`/`prevActive`/`seekActive`. Wire `onWaitingForVoices` → store. Set `status='paused'` on load success. Wire watchdog `onTimeout` callback. |
| Modify | `frontend/src/stores/ttsPlayer.ts` | Add `'starting'` to `TtsStatus`. Add `bookId` to `OpenContentArgs` (required) + ref. Wire `play/pause/nextSentence/prevSentence` to engine helpers. Add `seek(idx)` action. Make `retry()` re-invoke `engine.load()`. Make `close()` terminate the engine. Implement FR-20 null-engine setError. |
| Modify | `frontend/src/components/audio/TtsPlayButton.vue:77-81` | Pass `bookId` to `store.open()`. |
| Modify | `frontend/src/components/audio/ResumeAffordance.vue:41-54` | Accept `bookId` prop; pass it to `store.open()`. |
| Modify | `frontend/src/components/audio/Playbar.vue:69-99` | Render spinner glyph + `aria-label="Starting"` when `status === 'starting'`. Replace error copy with generic message + `title` attr. |
| Modify | `frontend/src/composables/audio/__tests__/webSpeechEngine.spec.ts` | Add tests for voice-wait, watchdog, idempotency, late-onstart guard. |
| Modify | `frontend/src/composables/audio/__tests__/mp3Engine.spec.ts` | Add tests for watchdog (onplaying cancels), idempotency. |
| Modify | `frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts` | Add tests for new helpers, status='paused' on load, null-engine setError, watchdog onTimeout wiring. Update existing tests for `bookId`-required `store.open`. |
| Modify | `frontend/src/stores/__tests__/ttsPlayer.spec.ts` | Add tests for new wired actions, retry re-loads, close terminates, bookId capture. |
| Modify | `frontend/src/components/audio/__tests__/Playbar.spec.ts` | Add tests for `'starting'` spinner state, generic error copy. Update existing `store.open()` calls. |
| Modify | other audio component tests calling `store.open(...)` | Add `bookId: 1` to existing calls. |
| Create | `frontend/src/components/audio/__tests__/Playbar.wiring.spec.ts` | FR-16 regression test: mount Playbar + real store + mocked `useTtsEngine` returning a stub engine; click play; assert stub `engine.play` called once. |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Required `bookId` breaks tests in unrelated audio specs that mount the store | High (certain) | T6 explicitly fixes every callsite. Run `npm run type-check` after T5 to enumerate all remaining failures. |
| Watchdog false-positives on a slow but ultimately working start | Medium | Dual-condition checks (Web Speech: `!speaking && !pending`; MP3: `audio.paused && !audio.ended`). If false positives surface in real use, raise threshold from 1000 ms to 1500 ms in `useTtsEngine.playActive`. |
| `voiceschanged` listener leaks if cleanup branches don't all fire | Medium | Single `voiceWaitCleanup` reference + idempotent set-to-null. Test: `cancels voice-wait on terminate` (T2 step 6). |
| Pinia store calling `useTtsEngine()` inside `retry()` action triggers a circular import or "no active pinia" issue at test time | Low | Existing tests wire `setActivePinia(createPinia())` in `beforeEach`. Composable pattern is already used by other Pinia stores in this repo. T5 step 8 verifies. |
| Playwright MCP profile has 0 voices (already observed today) so the e2e step "speech is audible" can't run in MCP | High | T9 documents the prerequisite: e2e runs in macOS system Chrome OR a profile with voices. The voice-wait error path is the e2e fallback that DOES run in MCP. |

---

## Tasks

### T1: Extend `TtsEngine` interface

**Goal:** Add `startWatchdog`, `cancelWatchdog`, `onWaitingForVoices` to the `TtsEngine` contract. This is the foundation for T2/T3.
**Spec refs:** FR-09, FR-19. Spec §8.1 (types.ts).

**Files:**
- Modify: `frontend/src/composables/audio/types.ts`

**Steps:**

- [ ] Step 1: Add `WaitingForVoicesHandler` type and extend the `TtsEngine` interface. Edit `types.ts`:
  ```ts
  export interface WaitingForVoicesHandler {
    (waiting: boolean): void
  }

  export interface TtsEngine {
    // ... existing fields ...
    startWatchdog(timeoutMs: number, onTimeout: () => void): void
    cancelWatchdog(): void
    onWaitingForVoices(cb: WaitingForVoicesHandler): void
  }
  ```

- [ ] Step 2: Run type-check to verify the change compiles AND fails the existing engines (which don't yet implement the new methods).
  Run: `cd frontend && npm run type-check`
  Expected: errors of the form `Class 'WebSpeechEngine' incorrectly implements interface 'TtsEngine'. Property 'startWatchdog' is missing` (and same for `cancelWatchdog`, `onWaitingForVoices`, both engines).

- [ ] Step 3: Commit only when T2 and T3 are also done (this commit is bundled — see T3 step 7).

**Inline verification:**
- `npm run type-check` produces the expected errors and no others (i.e., the type system is now demanding the new methods on every implementer).

---

### T2: Update `WebSpeechEngine` — voice-wait, watchdog, idempotency, late-onstart guard [P]

**Goal:** Implement the new interface methods AND fix the silent-failure paths inside `WebSpeechEngine`.
**Spec refs:** FR-05, FR-06, FR-07, FR-09, FR-10, FR-18, FR-23, FR-25.

**Files:**
- Modify: `frontend/src/composables/audio/webSpeechEngine.ts`
- Modify: `frontend/src/composables/audio/__tests__/webSpeechEngine.spec.ts`

**Steps:**

- [ ] Step 1 (RED): Add failing tests for the new behaviors. Open `webSpeechEngine.spec.ts` and append:
  - **`waits for voiceschanged when getVoices is empty, then speaks once voices arrive`** — mock `synth.getVoices` to return `[]` initially, then `[{ name: 'Samantha' }]` after `synth.dispatchEvent(new Event('voiceschanged'))`. Spy on `synth.speak`. Use `vi.useFakeTimers()`. Assert `synth.speak` is called once after the event fires, NOT before.
  - **`emits engine_unavailable after 1500 ms timeout when voices never arrive`** — `getVoices` always `[]`. Capture the `onError` callback. `await vi.advanceTimersByTimeAsync(1500)`. Assert `onError('engine_unavailable')` called exactly once.
  - **`emits onWaitingForVoices(true) then false`** — record handler invocations. Run race scenario (voices arrive after 200 ms). Assert sequence `[true, false]`.
  - **`pause() cancels voice-wait listener and timer`** — start wait, call `pause()`, advance timer beyond 1500 ms. Assert `onError` NOT called. Assert `removeEventListener('voiceschanged', ...)` was called.
  - **`terminate() cancels voice-wait listener and timer`** — same as above but with `terminate()`.
  - **`startWatchdog fires onTimeout when speaking stays false at 1000 ms`** — mock `synth.speaking = false`. Call `startWatchdog(1000, onTimeout)`. Advance 1000 ms. Assert `onTimeout` called.
  - **`startWatchdog onTimeout NOT called when utterance.onstart fired`** — start watchdog. Trigger `utt.onstart` (capture it from the `synth.speak` call). Advance 1000 ms. Assert `onTimeout` NOT called.
  - **`play() is idempotent — second call mid-utterance is a no-op`** — call `play()`, capture `currentUtterance`. Call `play()` again WITHOUT firing `onend`. Assert `synth.speak` was called only once total.
  - **`utterance.onstart cancels late-arriving utterance if error already emitted`** — start watchdog with low timeout, let it fire `onError('engine_unavailable')`, then trigger `utt.onstart`. Assert `synth.cancel()` was called.

- [ ] Step 2 (verify RED): `cd frontend && npm run test:unit -- src/composables/audio/__tests__/webSpeechEngine.spec.ts -t "waits for voiceschanged"`
  Expected: FAIL — methods/behaviors don't exist yet.

- [ ] Step 3 (GREEN — interface methods + private state). Edit `webSpeechEngine.ts`:
  - Add private fields: `voiceWaitCleanup: (() => void) | null = null`, `watchdogTimer: number | null = null`, `errorEmitted = false`, `waitingCb: WaitingForVoicesHandler | null = null`.
  - Implement `startWatchdog(timeoutMs, onTimeout)`: stores timer ID via `setTimeout(() => { if (!synth.speaking && !synth.pending) onTimeout() }, timeoutMs)`.
  - Implement `cancelWatchdog()`: `if (watchdogTimer !== null) { clearTimeout(watchdogTimer); watchdogTimer = null }`.
  - Implement `onWaitingForVoices(cb)`: `this.waitingCb = cb`.
  - In `emitError`: set `this.errorEmitted = true` before invoking `errorCb`.

- [ ] Step 4 (GREEN — speakAt rewrite). Replace the `if (!voices || voices.length === 0)` branch with the voice-wait flow per pseudocode §6.1 of the simulation trace. Key invariants:
  - Use `synth.addEventListener('voiceschanged', listener, { once: true })`.
  - Set `voiceWaitCleanup` to a closure that calls `removeEventListener` AND `clearTimeout` AND emits `waitingCb?.(false)`.
  - Set `voiceWaitCleanup = null` at the start of cleanup to make it idempotent.
  - In the listener body: clear cleanup, then `speakAt(idx)` recurses (voices are now populated).
  - In the timeout body: clear cleanup, then `emitError('engine_unavailable')`.

- [ ] Step 5 (GREEN — utterance handlers). In the post-voices speech path:
  - `utt.onstart = () => { this.cancelWatchdog(); if (this.errorEmitted) synth.cancel() }` — covers FR-25.
  - Before `synth.speak(utt)`: `this.startWatchdog(1000, () => this.errorCb?.('engine_unavailable'))`.

- [ ] Step 6 (GREEN — idempotent play). Add an explicit `isSpeaking: boolean = false` private field. Set it `true` inside `utt.onstart` (alongside the watchdog cancel and late-error guard), and `false` inside `utt.onend` and `utt.onerror`. At the top of `play()`:
  ```ts
  if (this.isSpeaking) {
    // Already mid-utterance: resume if paused, otherwise no-op.
    if (synth?.paused) synth.resume()
    return
  }
  ```
  (Avoids the fragile "currentUtterance not yet onend'd" comment-as-condition. `isSpeaking` is single-source truth for "engine is currently producing audio.")

- [ ] Step 7 (GREEN — pause/terminate cleanup). Update `pause()`:
  ```ts
  pause(): void {
    this.cancelWatchdog()
    if (this.voiceWaitCleanup) { this.voiceWaitCleanup(); this.voiceWaitCleanup = null }
    this.getSynth()?.pause()
  }
  ```
  And add equivalent cleanup at the top of `nextSentence`, `prevSentence`, `seek`, `terminate` (per FR-18).

- [ ] Step 8 (verify GREEN): `cd frontend && npm run test:unit -- src/composables/audio/__tests__/webSpeechEngine.spec.ts`
  Expected: all new + existing tests pass. **N passed, 0 failed** (where N includes the original ~5 tests plus the ~9 new ones).

**Inline verification:**
- `cd frontend && npm run test:unit -- src/composables/audio/__tests__/webSpeechEngine.spec.ts` — all tests pass.
- `npm run lint -- src/composables/audio/webSpeechEngine.ts` — no errors.

---

### T3: Update `Mp3Engine` — watchdog (event-based), idempotency [P]

**Goal:** Implement the new interface methods on `Mp3Engine`. Watchdog uses `audio.onplaying` as the cancel signal (D10/P3).
**Spec refs:** FR-09, FR-11, FR-18, FR-23.

**Files:**
- Modify: `frontend/src/composables/audio/mp3Engine.ts`
- Modify: `frontend/src/composables/audio/__tests__/mp3Engine.spec.ts`

**Steps:**

- [ ] Step 1 (RED): Add failing tests:
  - **`startWatchdog fires onTimeout when audio.paused stays true at 1000 ms`** — `audio.paused = true`. `startWatchdog(1000, cb)`. Advance 1000 ms. Assert `cb` called.
  - **`watchdog cancelled when audio fires "playing" event`** — `startWatchdog(1000, cb)`. Dispatch `playing` event on the `<audio>`. Advance 1000 ms. Assert `cb` NOT called.
  - **`onWaitingForVoices is a no-op (always emits false or never emits)`** — set handler, never call. Trivial to verify by exposing a flag.
  - **`play() is idempotent — second call while playing is a no-op`** — set `audio.paused = false`. Spy on `audio.play`. Call `engine.play()` twice. Assert `audio.play` called exactly once.

- [ ] Step 2 (verify RED): `npm run test:unit -- src/composables/audio/__tests__/mp3Engine.spec.ts -t "startWatchdog"`
  Expected: FAIL — methods don't exist.

- [ ] Step 3 (GREEN): Implement on `Mp3Engine`:
  - Private `watchdogTimer: number | null = null`, `watchdogPlayingHandler: (() => void) | null = null`.
  - `startWatchdog(timeoutMs, onTimeout)`: sets timer that fires `onTimeout` only if `this.audio.paused && !this.audio.ended` AND error wasn't fired. Also attaches a one-shot `playing` listener that calls `cancelWatchdog()`.
  - `cancelWatchdog()`: clear timer, remove `playing` listener.
  - `onWaitingForVoices(cb)`: store cb but don't call (MP3 never waits on voices). Acceptable to keep cb un-invoked; document.
  - Idempotent `play()`: at top of `play()`, `if (!this.audio.paused && !this.audio.ended) return`. Otherwise existing flow + `this.startWatchdog(1000, () => this.errorCb?.('engine_unavailable'))` before `await this.audio.play()`.
  - Update `pause`/`nextSentence`/`prevSentence`/`seek`/`terminate` to call `this.cancelWatchdog()` first (per FR-18).

- [ ] Step 4 (verify GREEN): `npm run test:unit -- src/composables/audio/__tests__/mp3Engine.spec.ts`
  Expected: all new + existing tests pass.

- [ ] Step 5: type-check should now pass for both engines.
  Run: `cd frontend && npm run type-check`
  Expected: zero errors.

- [ ] Step 6 (lint): `npm run lint -- src/composables/audio/`
  Expected: zero errors.

- [ ] Step 7 (commit T1+T2+T3 together, since they form a coherent type-system change):
  ```bash
  git add frontend/src/composables/audio/types.ts \
          frontend/src/composables/audio/webSpeechEngine.ts \
          frontend/src/composables/audio/mp3Engine.ts \
          frontend/src/composables/audio/__tests__/webSpeechEngine.spec.ts \
          frontend/src/composables/audio/__tests__/mp3Engine.spec.ts
  git commit -m "fix(audio): add voiceschanged race handling, watchdog, idempotent play to TTS engines"
  ```

**Inline verification:**
- `npm run test:unit -- src/composables/audio` — all engine tests pass.
- `npm run type-check` — zero errors.

---

### T4: Extend `useTtsEngine` with action helpers + onWaitingForVoices wiring + load→paused

**Goal:** Add the helpers the store will call; wire engine `onWaitingForVoices` to store status transitions; flip status to `'paused'` on `load()` success; wire watchdog `onTimeout` to `setError`.
**Spec refs:** FR-01, FR-12, FR-17, FR-20.

**Files:**
- Modify: `frontend/src/composables/audio/useTtsEngine.ts`
- Modify: `frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts`

**Steps:**

- [ ] Step 1 (RED): Add tests in `useTtsEngine.spec.ts`:
  - **`load() sets store.status to 'paused' on success`** — mock lookup, call `load()`, assert `store.status === 'paused'`.
  - **`playActive() calls engine.play() when lastEngine is set`** — call `load()` to set lastEngine; spy on it; call `playActive()`; assert `play` called.
  - **`playActive() calls store.setError('engine_unavailable') when lastEngine is null`** — fresh module state; call `playActive()`; assert `store.errorKind === 'engine_unavailable'` and `store.status === 'error'`.
  - **`pauseActive/nextActive/prevActive/seekActive forward to engine`** — one assertion per method.
  - **`onWaitingForVoices(true) sets store.status='starting'; (false) sets store.status='playing' (or paused if engine isn't speaking)`** — wire engine via load(); invoke the handler; assert.
  - **`load() wires watchdog onTimeout to store.setError`** — capture the `startWatchdog` callback the engine will eventually use. Verify wiring (this can be done by spying on the engine's `startWatchdog` method called inside `playActive`'s caller chain, or by asserting that when the engine's onError is invoked the store sets error — already covered by existing wiring).

- [ ] Step 2 (verify RED): `npm run test:unit -- src/composables/audio/__tests__/useTtsEngine.spec.ts`
  Expected: FAIL — helpers don't exist; status not set.

- [ ] Step 3 (GREEN): Edit `useTtsEngine.ts`:
  - Export new helpers from the same module:
    ```ts
    export function playActive(): Promise<void> {
      const store = useTtsPlayerStore()
      if (!lastEngine) { store.setError('engine_unavailable'); return Promise.resolve() }
      return Promise.resolve(lastEngine.play())
    }
    export function pauseActive(): void { lastEngine?.pause() }
    export function nextActive(): void { lastEngine?.nextSentence() }
    export function prevActive(): void { lastEngine?.prevSentence() }
    export function seekActive(idx: number): void { lastEngine?.seek(idx) }
    ```
  - Inside `load()` after `lastEngine = engine`:
    - Wire `engine.onWaitingForVoices((waiting) => { store.status = waiting ? 'starting' : 'playing' })`.
    - Defensive status update: `if (store.status === 'loading') store.status = 'paused'` — this avoids overwriting an `'error'` state that FR-20 may have set if the user clicked Play during the in-flight `load()` (null-engine race).
  - Decide: include the helpers in `UseTtsEngineApi` (return them from `useTtsEngine()`)? Yes — for parity with `terminate`. Update the API:
    ```ts
    export interface UseTtsEngineApi {
      load(args: LoadArgs): Promise<TtsEngine & { lookup: AudioLookupResponse }>
      terminate(): TtsEngine | null
      playActive(): Promise<void>
      pauseActive(): void
      nextActive(): void
      prevActive(): void
      seekActive(idx: number): void
    }
    ```
    And reference the module-level functions from inside `useTtsEngine()`.

- [ ] Step 4 (verify GREEN): `npm run test:unit -- src/composables/audio/__tests__/useTtsEngine.spec.ts`
  Expected: all tests pass.

- [ ] Step 5 (lint + types): `npm run lint -- src/composables/audio/useTtsEngine.ts && npm run type-check`
  Expected: zero errors.

- [ ] Step 6 (commit):
  ```bash
  git add frontend/src/composables/audio/useTtsEngine.ts \
          frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts
  git commit -m "fix(audio): expose play/pause/next/prev/seek helpers from useTtsEngine"
  ```

**Inline verification:**
- `npm run test:unit -- src/composables/audio/__tests__/useTtsEngine.spec.ts` — all pass.

---

### T5: Update `useTtsPlayerStore` — bookId, 'starting' status, wired actions, fixed retry, fixed close

**Goal:** Make the store actually drive the engine. Add `'starting'` status, capture `bookId`, route every action through `useTtsEngine` helpers, fix `retry()` to re-invoke `engine.load()`, fix `close()` to terminate the engine.
**Spec refs:** FR-02, FR-03, FR-04, FR-21, FR-22, FR-24.

**Files:**
- Modify: `frontend/src/stores/ttsPlayer.ts`
- Modify: `frontend/src/stores/__tests__/ttsPlayer.spec.ts`

**Steps:**

- [ ] Step 1 (RED): Add tests in `ttsPlayer.spec.ts` (create file if missing — it exists per code study). Add:
  - **`open() captures bookId in store`** — call `store.open({ bookId: 7, contentType: 'section_summary', contentId: 1 })`. Assert `store.bookId === 7`.
  - **`play() calls useTtsEngine().playActive()`** — `vi.mock` `useTtsEngine` to return a stub with spies. Call `store.play()`. Assert spy invoked.
  - **`pause() calls pauseActive`; `nextSentence calls nextActive`; `prevSentence calls prevActive` (one test each).**
  - **`nextSentence does NOT pre-update sentenceIndex`** — set `store.sentenceIndex = 5`. Call `store.nextSentence()`. Assert `store.sentenceIndex === 5` (engine hasn't fired `onSentenceChange` yet).
  - **`retry() re-invokes useTtsEngine().load() with captured bookId/contentType/contentId`** — open with bookId 7. Set `status='error'`. Call `retry()`. Assert load spy called with `{ bookId: 7, contentType: 'section_summary', contentId: 1 }`.
  - **`close() calls useTtsEngine().terminate()`** — open + close. Assert terminate spy invoked.
  - **`status='starting' has isPlaying === false`** — set `store.status='starting'`. Assert `store.isPlaying === false`.

- [ ] Step 2 (verify RED): `npm run test:unit -- src/stores/__tests__/ttsPlayer.spec.ts`
  Expected: FAIL.

- [ ] Step 3 (GREEN — type changes). Edit `ttsPlayer.ts`:
  - Add `'starting'` to the `TtsStatus` union.
  - Add `bookId: number` to `OpenContentArgs` (required, no default).
  - Add `const bookId = ref<number | null>(null)` to the store state.
  - In `open()`: `bookId.value = args.bookId`.
  - In `close()`: `bookId.value = null` (after terminate).

- [ ] Step 4 (GREEN — wired actions). Replace `play`/`pause`/`nextSentence`/`prevSentence`:
  ```ts
  function play() {
    status.value = 'playing'
    useTtsEngine().playActive().catch(() => {
      // Engine errors flow through the wired onError → setError path.
      // The .catch here is purely to silence unhandled-rejection warnings.
    })
  }
  function pause() {
    status.value = 'paused'
    useTtsEngine().pauseActive()
  }
  function nextSentence() {
    // No pre-update; engine.onSentenceChange will set sentenceIndex
    useTtsEngine().nextActive()
  }
  function prevSentence() {
    useTtsEngine().prevActive()
  }
  function seek(idx: number) {
    useTtsEngine().seekActive(idx)
  }
  ```
  Export `seek` from the store return statement.

- [ ] Step 5 (GREEN — close). Update `close()`:
  ```ts
  function close() {
    useTtsEngine().terminate()
    isActive.value = false
    // ... rest of existing reset logic
    bookId.value = null
  }
  ```

- [ ] Step 6 (GREEN — retry). Update `retry()`:
  ```ts
  async function retry() {
    if (contentType.value === null || contentId.value === null || bookId.value === null) {
      errorKind.value = null
      return
    }
    const at = sentenceIndex.value
    const ct = contentType.value
    const ci = contentId.value
    const bid = bookId.value
    open({ bookId: bid, contentType: ct, contentId: ci, sentenceIndex: at })
    try {
      await useTtsEngine().load({ bookId: bid, contentType: ct, contentId: ci })
    } catch {
      // load() already calls setError on its own catch; nothing to do
    }
  }
  ```

- [ ] Step 7 (verify GREEN): `npm run test:unit -- src/stores/__tests__/ttsPlayer.spec.ts`
  Expected: all pass.

- [ ] Step 8 (sanity — type-check the whole frontend now). `npm run type-check`
  Expected: errors at every callsite of `store.open(...)` that doesn't pass `bookId`. Count them; T6 fixes them.

- [ ] Step 9 (commit):
  ```bash
  git add frontend/src/stores/ttsPlayer.ts frontend/src/stores/__tests__/ttsPlayer.spec.ts
  git commit -m "fix(audio): wire ttsPlayer store actions to engine; add bookId, 'starting' status"
  ```

**Inline verification:**
- `npm run test:unit -- src/stores/__tests__/ttsPlayer.spec.ts` — all pass.
- `npm run type-check` — fails ONLY at `store.open(...)` callsites missing `bookId`. No other errors.

---

### T6: Update `OpenContentArgs` callsites + audio test fixups

**Goal:** Make the codebase compile again. Pass `bookId` everywhere `store.open(...)` is called, including the ~10+ test files exposed by T5 step 8.
**Spec refs:** FR-21 (cascading from T5).

**Files:**
- Modify: `frontend/src/components/audio/TtsPlayButton.vue:77-81`
- Modify: `frontend/src/components/audio/ResumeAffordance.vue:41-54` + props
- Modify: every audio component test file calling `store.open(...)` — list to be enumerated by `npm run type-check` output.

**Steps:**

- [ ] Step 1: Tighten `TtsPlayButton.vue`:
  - Change `defineProps` to make `bookId: number` REQUIRED (drop the `?`).
  - In `onClick`, before any work: `if (!props.bookId) { console.warn('[TtsPlayButton] bookId is required'); return }`.
  - Pass `bookId: props.bookId` (no `?? 0`) to both `store.open` and `engine.load`.
  - Run `grep -rn "<TtsPlayButton" frontend/src --include="*.vue"` to enumerate parents and confirm they all pass `bookId`. Update any that don't.

- [ ] Step 2: Update `ResumeAffordance.vue`:
  - Add `bookId: number` to defineProps (REQUIRED).
  - Pass `bookId: props.bookId` in both `store.open` calls (lines 41, 49).
  - Run `grep -rn "ResumeAffordance" frontend/src --include="*.vue"` to enumerate parents. Update them to pass `bookId`.

- [ ] Step 3: Update every test file flagged by `npm run type-check` output. For each, add `bookId: 1` (or any positive integer) to existing `store.open(...)` calls. Likely files (verify with type-check):
  - `frontend/src/components/audio/__tests__/Playbar.spec.ts`
  - `frontend/src/components/audio/__tests__/Playbar.midListenRegen.spec.ts`
  - `frontend/src/components/audio/__tests__/ResumeAffordance.spec.ts`
  - `frontend/src/components/audio/__tests__/EngineChip.spec.ts`
  - any other `.spec.ts` in the audio test dirs that mounts the store.

- [ ] Step 4 (verify): `cd frontend && npm run type-check`
  Expected: zero errors.

- [ ] Step 5 (verify): `npm run test:unit -- src/components/audio src/stores src/composables/audio`
  Expected: all tests pass. **No regressions in any pre-existing test.**

- [ ] Step 6 (lint): `npm run lint`
  Expected: zero errors.

- [ ] Step 7 (commit):
  ```bash
  git add -A
  git commit -m "fix(audio): pass bookId through OpenContentArgs at all call sites"
  ```

**Inline verification:**
- `npm run type-check` — zero errors.
- `npm run test:unit -- src/components/audio src/stores src/composables/audio` — all pass.

---

### T7: Update Playbar UI — spinner glyph for 'starting', generic error copy

**Goal:** Render the visible "starting…" state (spinner + aria-label) and replace error template copy with the generic message.
**Spec refs:** FR-13, FR-14, FR-15.
**Wireframe refs:** None (no wireframes for this fix; reusing existing Playbar layout).

**Files:**
- Modify: `frontend/src/components/audio/Playbar.vue`
- Modify: `frontend/src/components/audio/__tests__/Playbar.spec.ts`

**Steps:**

- [ ] Step 1 (RED): Add tests in `Playbar.spec.ts`:
  - **`renders spinner glyph and aria-label="Starting" when status === 'starting'`** — set `store.status = 'starting'` after open. Mount. Assert the play-pause button has `aria-label="Starting"` and `disabled` attribute. Assert the spinner SVG (via class `animate-spin`) is rendered.
  - **`error template shows generic copy and Retry button`** — set `status='error'`, `errorKind='engine_unavailable'`. Mount. Assert text contains `"Audio couldn't start. Try again or check your settings."`. Assert `[data-testid="retry"]` exists. Assert the surrounding element's `title` attribute contains `engine_unavailable`.

- [ ] Step 2 (verify RED): `npm run test:unit -- src/components/audio/__tests__/Playbar.spec.ts -t "starting"`
  Expected: FAIL.

- [ ] Step 3 (GREEN). Edit `Playbar.vue`:
  - In the `<template v-else>` block, change the play-pause button to handle three states:
    ```vue
    <button
      type="button"
      data-testid="play-pause"
      class="btn-primary btn-icon"
      :aria-label="store.status === 'starting' ? 'Starting' : (store.status === 'playing' ? 'Pause' : 'Play')"
      :disabled="store.status === 'starting' || undefined"
      :aria-disabled="store.status === 'starting' ? 'true' : undefined"
      @click="onPlayPause"
    >
      <svg v-if="store.status === 'starting'" class="h-4 w-4 animate-spin" viewBox="0 0 20 20" aria-hidden="true">
        <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="40" />
      </svg>
      <template v-else>{{ store.status === 'playing' ? '⏸' : '▶' }}</template>
    </button>
    ```
  - In the `<template v-if="store.status === 'error'">` block, replace the message and add `:title`:
    ```vue
    <span class="text-sm text-red-600 dark:text-red-400" :title="`errorKind: ${store.errorKind ?? 'unknown'}`">
      Audio couldn't start. Try again or check your settings.
    </span>
    <button data-testid="retry" type="button" class="btn-primary" @click="onRetry">Retry</button>
    ```
  - In `onPlayPause`: also handle the `'starting'` case as a no-op (button is disabled, but defensive).

- [ ] Step 4 (verify GREEN): `npm run test:unit -- src/components/audio/__tests__/Playbar.spec.ts`
  Expected: all pass.

- [ ] Step 5 (lint): `npm run lint -- src/components/audio/Playbar.vue`
  Expected: zero errors.

- [ ] Step 6 (commit):
  ```bash
  git add frontend/src/components/audio/Playbar.vue \
          frontend/src/components/audio/__tests__/Playbar.spec.ts
  git commit -m "fix(audio): add 'starting' spinner state and generic error copy to Playbar"
  ```

**Inline verification:**
- `npm run test:unit -- src/components/audio/__tests__/Playbar.spec.ts` — all pass.

---

### T8: Component-level wiring regression test (FR-16)

**Goal:** Add a test that mounts the real Playbar + real store + a mocked `useTtsEngine` returning a stub engine, and asserts `engine.play()` is invoked when the user clicks Play. This is the test that would have caught the original bug.
**Spec refs:** FR-16.

**Files:**
- Create: `frontend/src/components/audio/__tests__/Playbar.wiring.spec.ts`

**Steps:**

- [ ] Step 1 (RED — by writing the test against the current state of T1–T7). Create `Playbar.wiring.spec.ts`:
  ```ts
  import { mount } from '@vue/test-utils'
  import { createPinia, setActivePinia } from 'pinia'
  import { beforeEach, describe, expect, it, vi } from 'vitest'

  const playSpy = vi.fn()
  const pauseSpy = vi.fn()
  const nextSpy = vi.fn()
  const prevSpy = vi.fn()
  const terminateSpy = vi.fn()

  vi.mock('@/composables/audio/useTtsEngine', () => ({
    useTtsEngine: () => ({
      load: vi.fn().mockResolvedValue({ kind: 'web-speech' }),
      terminate: terminateSpy,
      playActive: playSpy,
      pauseActive: pauseSpy,
      nextActive: nextSpy,
      prevActive: prevSpy,
      seekActive: vi.fn(),
    }),
  }))

  import Playbar from '@/components/audio/Playbar.vue'
  import { useTtsPlayerStore } from '@/stores/ttsPlayer'

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Playbar ↔ engine wiring (regression guard)', () => {
    it('clicking Play after engine is attached invokes engine.play exactly once', async () => {
      const store = useTtsPlayerStore()
      store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
      store.status = 'paused'
      const wrap = mount(Playbar)
      await wrap.find('[data-testid="play-pause"]').trigger('click')
      expect(playSpy).toHaveBeenCalledTimes(1)
    })

    it('clicking Pause invokes engine.pause', async () => {
      const store = useTtsPlayerStore()
      store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
      store.status = 'playing'
      const wrap = mount(Playbar)
      await wrap.find('[data-testid="play-pause"]').trigger('click')
      expect(pauseSpy).toHaveBeenCalledTimes(1)
    })

    it('clicking Close terminates the engine', async () => {
      const store = useTtsPlayerStore()
      store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
      const wrap = mount(Playbar)
      await wrap.find('[aria-label="Close player"]').trigger('click')
      expect(terminateSpy).toHaveBeenCalledTimes(1)
    })
  })
  ```

- [ ] Step 2 (verify GREEN — should pass first run because T5 already wired everything):
  Run: `npm run test:unit -- src/components/audio/__tests__/Playbar.wiring.spec.ts`
  Expected: 3 passed, 0 failed.
  
  *Note on the "RED" framing:* T8 is the regression guard, not a feature gate. If it fails on first run, T5/T7 has a wiring bug to fix before continuing.

- [ ] Step 3 (intentional sanity-fail to prove the test catches the original bug). Temporarily comment out the `void useTtsEngine().playActive()` line in `ttsPlayer.ts:play()`. Re-run the spec.
  Expected: the "clicking Play... invokes engine.play" test FAILS with `expected 1, got 0`.
  Restore the line. Re-run; expect PASS.
  This step is mandatory — it validates the test is genuinely behavioral, not structural.

- [ ] Step 4 (lint): `npm run lint -- src/components/audio/__tests__/Playbar.wiring.spec.ts`
  Expected: zero errors.

- [ ] Step 5 (commit):
  ```bash
  git add frontend/src/components/audio/__tests__/Playbar.wiring.spec.ts
  git commit -m "test(audio): add Playbar↔engine wiring regression test (FR-16)"
  ```

**Inline verification:**
- `npm run test:unit -- src/components/audio/__tests__/Playbar.wiring.spec.ts` — 3 passed.
- Step 3 sanity check confirmed the test fails when wiring is removed.

---

### T9: Final Verification

**Goal:** Verify the entire implementation works end-to-end on a live build.

- [ ] **Lint & format:** `cd frontend && npm run lint && npx prettier --check src/composables/audio src/components/audio src/stores`
  Expected: zero errors.

- [ ] **Type check:** `cd frontend && npm run type-check`
  Expected: zero errors.

- [ ] **Frontend unit tests (focused):** `cd frontend && npm run test:unit -- src/composables/audio src/stores src/components/audio`
  Expected: all pass; count includes new tests from T2 (~9), T3 (~4), T4 (~6), T5 (~7), T7 (~2), T8 (3) — roughly 30+ new tests.

- [ ] **Frontend full unit suite (regression):** `cd frontend && npm run test:unit`
  Expected: full suite passes; no regressions outside audio.

- [ ] **Frontend build:** `cd frontend && npm run build`
  Expected: build succeeds; emits `dist/`.

- [ ] **Backend unit tests (no expected impact, sanity):** `cd backend && uv run python -m pytest tests/unit/ -q`
  Expected: pass (no regression — backend untouched).

- [ ] **Deploy frontend into backend static dir** (per CLAUDE.md interactive verification recipe):
  ```bash
  cd frontend && npm run build && rm -rf ../backend/app/static && cp -R dist ../backend/app/static
  ```

- [ ] **Start backend on a free port:**
  ```bash
  cd backend && uv run bookcompanion serve --port 8765 &
  sleep 2 && curl -sf http://localhost:8765/api/v1/health
  ```
  Expected: 200 OK JSON.

- [ ] **Frontend smoke test (Playwright MCP, macOS Chrome with system voices):**
  1. `browser_navigate` → `http://localhost:8765/books/1/sections/3?tab=original`.
  2. Snapshot — confirm Listen button is visible.
  3. Click Listen — Playbar appears with engine="Web Speech", status='paused', play button visible.
  4. Click Play.
  5. Within 2 s, `browser_evaluate` → `() => ({ speaking: speechSynthesis.speaking, voiceCount: speechSynthesis.getVoices().length })`.
     Expected: `speaking === true && voiceCount > 0`.
  6. Click Pause. `browser_evaluate` → `() => speechSynthesis.speaking`. Expected: `false`.
  7. Click Play again. Expected: speech resumes.
  8. Click ⏭. Expected: sentence counter advances; speech restarts at the next sentence.
  9. **Hard-reload the route** (open `http://localhost:8765/books/1/sections/3?tab=original` in a fresh tab, not via in-app nav). Expected: section 3 (Introduction) renders, not section 1.
  10. **Force an error path:** before clicking Play, run `browser_evaluate` → `() => { Object.defineProperty(window, 'speechSynthesis', { value: null }); }` — then click Play. Expected: Playbar shows "Audio couldn't start. Try again or check your settings." with a Retry button. Click Retry — engine.load() is re-invoked (visible in network requests).
  11. `browser_console_messages(level: 'error')` — expected: zero uncaught console errors during the journey.

- [ ] **UX polish checklist:**
  - `document.title` is `"Reader — Book Companion"` on the section page (existing behavior, verify unchanged).
  - No internal IDs leaked in error copy (FR-14 generic copy, verified).
  - Casing/date-format consistency: N/A (no new dates rendered).
  - Image `alt` attributes: N/A (no new images).
  - No dead disabled affordances: spinner state correctly disables play button; close button stays clickable.
  - Zero uncaught console errors during golden path AND error path: verified in step 11 above.
  - Navigation labels match destination titles: N/A (no new nav).

- [ ] **Wireframe diff:** N/A (no wireframes for this fix).

- [ ] **Manual spot check:**
  - Click Listen → Play → Pause → Play. Confirm audio plays, pauses, resumes audibly.
  - Open a second tab on a different section, click Listen there. Confirm the first tab's Playbar's play button reverts to ▶ (BroadcastChannel handoff still works).
  - With the Playbar open, press Space (focused on the page body, not on an input). Confirm play/pause toggles via keyboard.

- [ ] **Cleanup:**
  - Stop the verification backend: `kill $(lsof -ti:8765)`.
  - Do NOT touch the user's port-8000 backend.
  - Confirm no stray temporary files: `git status` shows only the intended changes.

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| _initial_ | — | First draft. |
| 1 | bookId fallback in T6 silently misroutes; play() idempotency uses fragile comment-as-condition; load() success could overwrite error state from FR-20 race; T8 sanity check is one-time (acceptable). | T6 step 1/2 tightened: bookId required in TtsPlayButton + ResumeAffordance, parents updated. T2 step 6 reworked to use explicit `isSpeaking` field. T4 step 3 made defensive: `if (status === 'loading') status = 'paused'`. T8 sanity step kept as-is. |
| 2 | T2 size acceptable (kept monolithic); playActive Promise discard could swallow rejections silently; FR-08 Space-key already covered by T9 manual spot check. | T5 step 4 updated: `useTtsEngine().playActive().catch(() => {})` with comment explaining engine errors still flow through onError. No T2 split. No new FR-08 task (T9 covers). |
