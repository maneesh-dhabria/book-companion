# Audio Playback Fix — Simulation Trace

**Date:** 2026-05-08
**Spec:** `docs/specs/2026-05-08-audio-playback-fix-spec.md` (Tier 2)

---

## 1. Scope

**In scope (frontend only):**
- Pinia store `useTtsPlayerStore` (state + actions)
- `useTtsEngine` composable (engine instance ownership)
- `WebSpeechEngine` and `Mp3Engine` (the only `TtsEngine` implementers in-tree)
- `Playbar.vue`, `TtsPlayButton.vue`
- `AppShell.vue` global Space-key handler

**Out of scope:**
- Backend audio_files / audio_position / lookup contract — explicitly untouched
- Kokoro TTS engine — opt-in path, default install uses web-speech
- New TTS controls (rate, voice picker, skip-by-time)

**Companion specs:** none.
**Anticipated future consumers:** none.

---

## 2. Scenario Inventory (33 scenarios)

| # | Scenario | Source | Category |
|---|----------|--------|----------|
| S1 | Happy path Web Speech, voices loaded | Spec §5.1 | happy |
| S2 | Happy path MP3 (pregenerated) | Spec §5.1 variant | happy |
| S3 | Voice-load race (voices arrive within 1.5s) | Spec §5.2 | timing |
| S4 | Watchdog trip (autoplay/mute/unknown) | Spec §5.3 | failure |
| S5 | Pause → Resume | Spec §5.4 | happy |
| S6 | Next/Prev sentence | Spec §5.4 | happy |
| S7 | Seek by sentence-row click | Spec §5.4 | happy |
| S8 | Keyboard Space toggle | Spec §5.5 | happy |
| S9 | Empty section text — Listen hidden | Spec E1 | edge |
| S10 | `lastEngine === null` when Play clicked | Spec E2 | edge |
| S11 | Pause during voice-wait | Spec E3 | concurrency |
| S12 | Next during voice-wait | Spec E4 | concurrency |
| S13 | Close Playbar mid-wait | Spec E5 | edge |
| S14 | Section navigation mid-playback | Spec E6 | edge |
| S15 | Cross-tab BroadcastChannel handoff | Spec E7 | concurrency |
| S16 | Watchdog races with normal start at 1000ms | Spec E8 | timing |
| S17 | Voices never arrive (offline) | Spec E9 | failure |
| S18 | MP3 watchdog false-positive scenario | Spec E10 | failure |
| S19 | Cold-load: Listen+Play within 100ms | Variant | timing |
| S20 | Keyboard-only power user | Variant | input |
| S21 | Backend down, preload fails | Adversarial | failure |
| S22 | Rapid double-click Play | Adversarial | concurrency |
| S23 | User clicks Retry repeatedly during voice-wait | Adversarial | retry |
| S24 | Persisted voice name no longer in voices list | Adversarial | input |
| S25 | Very large section (10k sentences) | Adversarial | boundary |
| S26 | Backend slow, preload pending when Listen clicked | Adversarial | timing |
| S27 | `voiceschanged` fires during watchdog window | Adversarial | ordering |
| S28 | Voice setting points to non-existent voice | Adversarial | input |
| M1 | `synth.pause()` semantics — resume after mid-utterance pause | Model-driven | timing |
| M2 | Two tabs Listen within ms → BroadcastChannel race | Model-driven | concurrency |
| M3 | Double `engine.load()` from rapid Listen-Listen clicks | Model-driven | concurrency |
| M4 | `utterance.onstart` fires late on Chrome — watchdog falsely cancelled / late onstart after error | Model-driven | timing |
| M5 | `voiceschanged` listener leak (fires multiple times) | Model-driven | ordering |

---

## 3. Coverage Matrix (selected scenarios — gaps only)

Most scenarios trace cleanly through FR-01–FR-19. Scenarios that exposed gaps:

| Scenario | Step | Spec Artifact | Status |
|----------|------|---------------|--------|
| S6: Next/Prev | Update sentenceIndex when engine bounds out | FR-04 says store updates first, engine overwrites | **GAP B-01** |
| S10: null engine on Play | playActive when lastEngine null | FR-01 says no-op; status flips to 'playing' silently | **GAP B-02** |
| S12: Next during voice-wait | Cancel voice-wait listener+timer on next | FR-18 covers pause only | **GAP B-03** |
| S13/S14: Close / nav mid-wait | terminate clears timers | E5/E6 prose, no FR | **GAP B-04** |
| S22: Double-click Play | engine.play idempotency | Not specified | **GAP B-05** |
| S23: Repeated Retry | Retry re-invokes engine.load | store.retry() only resets state | **GAP B-06** |
| derived | bookId for re-load | Not in OpenContentArgs | **GAP B-09** |
| S26: Slow preload | Same null-engine path as S10 | — | covered by B-02 |
| M3: Double load | load() generation-counter against stale resolve | Not specified | **GAP B-07** (out of scope) |
| M4: Late onstart after error | onstart guard against stale errors | Not specified | **GAP B-08** |

All other scenarios (S1–S5, S7–S9, S11, S15–S21, S24–S28, M1–M2, M5) trace cleanly.

---

## 4. Artifact Fitness Findings

### Bucket 1 (Data) — N/A
Out of scope; no DB changes.

### Bucket 2 (Service Interfaces) — N/A
Out of scope; no API changes.

### Bucket 3 (Behavior — state/workflows)
Status state machine in §8.3 covers all 7 states. `'playing' → 'starting'` momentary inconsistency (store sets `'playing'` synchronously, engine then emits `onWaitingForVoices(true)` → `'starting'`) is cosmetic and acceptable. No findings.

### Bucket 4 (UI)
- Listen-button hidden state (S9) — already wired by `visibilityComputed` in `TtsPlayButton.vue`. ✓
- Spinner glyph + `aria-label="Starting"` (FR-13) — accessible. ✓
- Generic error copy (FR-14) — non-translated, fine for personal tool. ✓
- Close button during `'starting'` — covered by `template v-else` branch. ✓

No findings.

### Bucket 5 (Wire-up)
See §5.

### Bucket 6 (Operational)
- NFR target: <500ms play→audio (G1). Numeric and measurable. ✓
- No logging/metrics for new error kinds — acceptable for personal tool.
- Rollout: no flag, no migration. ✓

No findings.

---

## 5. Cross-Reference (UI ↔ Store ↔ Engine)

### Forward table

| # | Interaction | Trigger | Function chain | Req | Res | Error | Notes |
|---|-------------|---------|----------------|-----|-----|-------|-------|
| W1 | Click Play | Playbar.onPlayPause | `store.play` → `playActive` → `engine.play` | ✓ | ✓ status flips | ✓ via `setError` | clean |
| W2 | Click Pause | Playbar.onPlayPause | `store.pause` → `pauseActive` → `engine.pause` | ✓ | ✓ | ✓ | FR-18 covers timer cleanup |
| W3 | Click Next | Playbar.onNext | `store.nextSentence` → `nextActive` → `engine.nextSentence` | partial | ✓ | — | **B-01, B-03** |
| W4 | Click Prev | Playbar.onPrev | `store.prevSentence` → `prevActive` → `engine.prevSentence` | partial | ✓ | — | **B-01, B-03** |
| W5 | Click Close | Playbar.onClose | `store.close` | broken | — | — | **W-01: terminate not called** |
| W6 | Click Retry | Playbar.onRetry | `store.retry` → `open` | broken | broken | — | **B-06, B-09** |
| W7 | Press Space | AppShell.onGlobalKeydown | `store.play / pause` | ✓ | ✓ | ✓ | inherits W1/W2 |
| W8 | Click sentence row | ReadingArea (existing) | `store...` → `seekActive` → `engine.seek` | partial | ✓ | — | needs B-03 cleanup rule |

### Reverse scan
- All `useTtsEngine` helpers have store consumers. ✓
- All `TtsEngine` methods are called by `useTtsEngine` helpers. ✓
- New methods (`startWatchdog`, `cancelWatchdog`, `onWaitingForVoices`) are called by engine internals + `useTtsEngine.load()`. ✓
- Orphan: `store.close()` does not terminate engine. **W-01.**

---

## 6. Pseudocode (3 flows)

### 6.1 `WebSpeechEngine.speakAt(idx)` — voice-wait + watchdog

```
FUNCTION speakAt(idx):
  IF terminated: RETURN
  text = sentences[idx]
  IF text empty: endCb?.(); RETURN

  synth = window.speechSynthesis
  IF synth null: emitError('engine_unavailable'); RETURN

  voices = synth.getVoices()
  IF voices empty:
    waitingCb?.(true)
    listener = () => {
      synth.removeEventListener('voiceschanged', listener)
      clearTimeout(timeoutId)
      voiceWaitCleanup = null
      waitingCb?.(false)
      IF terminated: RETURN
      speakAt(idx)            # re-enter; voices are now loaded
    }
    timeoutId = setTimeout(() => {
      synth.removeEventListener('voiceschanged', listener)
      voiceWaitCleanup = null
      waitingCb?.(false)
      IF terminated: RETURN
      emitError('engine_unavailable')
    }, 1500)
    voiceWaitCleanup = () => {
      synth.removeEventListener('voiceschanged', listener)
      clearTimeout(timeoutId)
      waitingCb?.(false)
    }
    synth.addEventListener('voiceschanged', listener, { once: true })
    RETURN

  utt = new SpeechSynthesisUtterance(text)
  utt.rate = rate
  IF voiceName:
    v = voices.find(name === voiceName)
    IF v: utt.voice = v
  utt.onstart = () => {
    cancelWatchdog()
    IF errorEmitted: synth.cancel()         # FR-25 — silence late onstart after error
  }
  utt.onend = () => {
    cancelWatchdog()
    IF terminated: RETURN
    next = idx + 1
    IF next >= totalSentences: endCb?.(); RETURN
    idx = next
    sentenceCb?.(idx)
    speakAt(idx)
  }
  utt.onerror = () => { cancelWatchdog(); emitError('utterance_failed') }
  currentUtterance = utt
  startWatchdog(1000, () => errorCb?.('engine_unavailable'))
  synth.speak(utt)
```

- **DB calls:** N/A.
- **State transitions:** not-speaking → speaking (synth.speak); speaking → idle (utt.onend); waiting → speaking (listener fires); waiting → error (timeout); any → terminated (terminate).
- **Error branches:** synth absent / voices empty timeout / utt.onerror / watchdog timeout — all flow through `emitError` → store.setError. Late onstart after error → cancel utterance to keep audio matching UI.
- **Concurrency notes:** `voiceWaitCleanup` is single-slot and idempotent; `terminate()`, `pause()`, `next/prev/seek` all call it before delegating (FR-18). `voiceschanged` listener uses `{ once: true }` plus explicit removal for redundancy.

### 6.2 `WebSpeechEngine.pause()` — timer-aware

```
FUNCTION pause():
  cancelWatchdog()
  IF voiceWaitCleanup:
    voiceWaitCleanup()
    voiceWaitCleanup = null
  getSynth()?.pause()
```

- **State transitions:** speaking → paused (synth.pause); waiting → idle (cleanup).
- **Concurrency notes:** Cleanup is idempotent. Does NOT clear `currentUtterance` — resume needs it.

### 6.3 `useTtsPlayerStore.retry()` — reload-aware

```
FUNCTION retry():
  IF contentType null OR contentId null OR bookId null:
    errorKind = null
    RETURN
  at = sentenceIndex
  open({ contentType, contentId, sentenceIndex: at })   # status='loading'
  await useTtsEngine().load({ bookId, contentType, contentId })
  # load() success path sets status='paused' (FR-17)
```

- **DB calls:** N/A (load handles preload via its own cache).
- **State transitions:** error → loading → paused.
- **Error branches:** load() throws → setError('lookup_failed'); engine wiring picks up subsequent errors.
- **Concurrency notes:** `bookId` must be persisted in store (FR-21). The pre-existing load() race (B-07) is accepted as out-of-scope risk.

---

## 7. Gap Register

| #     | Gap | Exposed By | Severity | Disposition |
|-------|-----|------------|----------|-------------|
| B-01  | next/prev pre-increments index, drifts when engine bounds out | S6 | significant | **Apply patch** → FR-04 rewritten; engine is sole index source |
| B-02  | playActive with `lastEngine === null` silently flips to 'playing' | S10, S26 | blocker | **Apply patch** → FR-20 added (setError instead of no-op) |
| B-03  | next/prev/seek must clear voice-wait + watchdog | S12 | significant | **Apply patch** → FR-18 extended to cover all state-changing methods |
| B-04  | terminate() must clear voice-wait + watchdog | S13, S14 | significant | **Apply patch** → folded into FR-18 |
| B-05  | rapid double-click Play queues second utterance | S22 | significant | **Apply patch** → FR-23 added (engine.play idempotent) |
| B-06  | Retry doesn't re-invoke engine.load | S23 | blocker | **Apply patch** → FR-22 added |
| B-07  | load() race overwrites lastEngine | M3 | minor | **Accept as risk** — pre-existing, low frequency, out of scope |
| B-08  | late onstart after watchdog error | M4 | minor | **Apply patch** → FR-25 added (cancel late utterance) |
| B-09  | bookId not in store, blocks retry re-load | derived | blocker | **Apply patch** → FR-21 added (bookId in OpenContentArgs) |
| W-01  | store.close() doesn't terminate engine | Phase 5 reverse | significant | **Apply patch** → FR-24 added |

---

## 8. Accepted Risks

| # | Risk | Rationale |
|---|------|-----------|
| B-07 | `useTtsEngine.load()` race condition: a slower-resolving first load can overwrite a second load's engine assignment | Pre-existing bug not introduced by this fix. Low frequency in practice (rapid Listen-Listen-Listen by the same user is unusual). Fixing requires a load-generation counter that expands scope. The /plan author may opt to add a separate task; not blocking for this spec's goals. |

---

## 9. Open Questions

None. All gaps either patched or accepted.

(Pre-existing OQ from spec — `git blame ttsPlayer.ts` to determine if wiring regressed — carries forward to /plan unchanged.)

---

## 10. Spec Patches Applied

| Patch | Spec change |
|-------|-------------|
| B-01 | `FR-04` rewritten: store.nextSentence/prevSentence delegate without pre-updating sentenceIndex; engine.onSentenceChange is sole source of truth. Same rule for seekActive. |
| B-03 + B-04 | `FR-18` extended: `pause`, `nextSentence`, `prevSentence`, `seek`, `terminate` all clear voice-wait + watchdog. Engine SHOULD hold a single `voiceWaitCleanup` reference for idempotency. |
| B-02 | `FR-20` added: `playActive` with null engine MUST `store.setError('engine_unavailable')`. |
| B-09 | `FR-21` added: `OpenContentArgs` gains `bookId: number`; store captures it. |
| B-06 | `FR-22` added: `store.retry()` re-invokes `useTtsEngine().load(...)` after `open(...)`. |
| B-05 | `FR-23` added: `WebSpeechEngine.play()` and `Mp3Engine.play()` are idempotent against repeated invocations. |
| W-01 | `FR-24` added: `store.close()` MUST call `useTtsEngine().terminate()`. |
| B-08 | `FR-25` added: `utterance.onstart` checks for prior error and cancels late-arriving utterance. |

The spec now has **25 FRs** (was 19) and 11 decisions.

---

## 11. Review Log

| Loop | Findings | Disposition |
|------|----------|-------------|
| 1 | Re-read spec post-patch. All 5 review checks pass: scenario list complete, all in-scope buckets covered, cross-reference complete forward + reverse, every gap has a disposition, both blockers patched (no deferred blockers). | Exit. |
