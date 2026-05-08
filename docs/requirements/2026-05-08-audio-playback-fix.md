# Audio Playback Fix — Requirements

**Date:** 2026-05-08
**Status:** Draft
**Tier:** 2 — Enhancement (bug fix + UX polish)

## Problem

Pressing the **Play** button in the bottom audio Playbar produces no sound. The button toggles its label to "Pause" (so the UI claims audio is playing), but `speechSynthesis.speaking` stays `false`, no utterance is queued, and no `<audio>` element is created. The user is left staring at a "Pause" button in silence with no error, no recovery affordance, and no way to know what went wrong.

Reproduction (verified live on `http://localhost:8000/books/1/sections/3?tab=original`, 2026-05-08):
1. Open any section in Original tab.
2. Click **Listen** → Playbar appears (engine = "Web Speech", "Limited controls" badge, `0:00 / 0:00`, sentence 1 of N).
3. Click **▶ Play** → button changes to "⏸ Pause". No audio plays. No console error. No toast.

### Who & Why Now

Anyone using the audiobook mode on this build. The audiobook feature shipped recently (v1.6) and is a primary listed capability — silent failure on first interaction is a credibility-breaking first impression, especially because the user's only feedback signal is the button label flipping.

A secondary class of users — those whose browser hasn't loaded Web Speech voices yet on first click — fall into the same silent-failure hole even after the wiring bug is fixed, because the engine emits `engine_unavailable` exactly once and never retries when `voiceschanged` fires.

## Goals & Non-Goals

### Goals

- Clicking **Play** in the Playbar produces audible speech (Web Speech) or audio playback (pregenerated MP3) within ~1s on a normal install.
- Clicking **Pause** stops speech immediately; **Play** again resumes from the same sentence.
- **Next sentence / Previous sentence / sentence-row click-to-seek** all work and the engine actually advances/rewinds.
- A first-click race against Web Speech voice loading no longer causes silent failure — either the engine waits for voices, or the user sees a clear, recoverable error.
- When the engine genuinely cannot play (no voices, blocked by browser policy, lookup failed), the Playbar shows the existing error state — not a "Pause" button over silence.

### Non-Goals

- NOT redesigning the Playbar layout or the Listen entry point — because the issue is wiring + error feedback, not UX surface area.
- NOT changing the default TTS engine away from Web Speech — because the user has not opted into Kokoro and we don't want to change install behavior in a bug-fix release.
- NOT adding a new TTS engine, voice, or speed control — because they're orthogonal to "play does nothing".
- NOT pregenerating MP3 for sections that don't have it — because the Web Speech fallback is the intended behavior; we just need it to actually speak.
- NOT touching `useTtsEngine.load()`'s preload flow or the lookup contract — because that part is working; the gap is between store state and the engine instance.

## Solution Direction

Two related fixes, both required:

**1. Wire store actions to the active engine (the actual bug).**
The Playbar's play/pause/next/prev/seek buttons currently mutate Pinia state only. Make those actions drive the live engine instance returned by `useTtsEngine.load()`. The store should expose a single source of truth that both updates UI status AND tells the engine to start, stop, advance, or seek. This applies to both engine kinds (Web Speech and MP3) — they implement the same `TtsEngine` interface.

**2. Handle the Web Speech voice-loading race.**
When `speechSynthesis.getVoices()` returns empty on first synchronous read, the engine should wait for the `voiceschanged` event (with a short timeout) before emitting `engine_unavailable`. If voices never arrive, surface the existing error state cleanly.

A wireframe is not required — no visual changes; only behavioral changes to existing controls and the existing error state.

## User Journeys

### Primary Journey — Web Speech (voices already loaded)

1. User opens a section, clicks **Listen**.
2. Playbar appears with engine chip "Web Speech", "Limited controls" badge, sentence counter.
3. User clicks **▶ Play**.
4. Within ~250 ms, the browser begins speaking sentence 1. Button changes to **⏸ Pause**. The active sentence is highlighted in the reading area (existing behavior).
5. User clicks **⏸ Pause** → speech stops mid-utterance. Button reverts to **▶ Play**. Sentence index unchanged.
6. User clicks **▶ Play** again → speech resumes from the same sentence (or the start of it, per Web Speech limitations).
7. User clicks **⏭ Next sentence** → current utterance is canceled, next sentence begins speaking, sentence counter increments, highlight moves.

### Primary Journey — Pregenerated MP3

Same sequence as above, but the engine chip says the MP3 engine. Pause/Play resume mid-sentence with frame-accurate position because `<audio>` supports it. Seek-by-sentence jumps to the correct timestamp.

### Voice-Loading Race Journey

1. User opens a fresh tab, clicks **Listen** within ~50 ms of page load.
2. Playbar appears.
3. User clicks **▶ Play** before browser has loaded voices.
4. Engine waits up to ~1.5 s for `voiceschanged` to fire.
5. If voices arrive: speech starts. (Happy path resumes.)
6. If voices never arrive: Playbar enters the existing error state — "Audio error: engine_unavailable" + **Retry** button. User clicks **Retry** → engine re-attempts.

### Error Journeys

| Scenario | Trigger | Expected Behavior |
|----------|---------|-------------------|
| Voices unavailable (timeout) | `getVoices()` returns empty after wait window | Playbar shows error state with Retry; play button is replaced by error message (existing behavior — just needs to actually fire) |
| Audio lookup fails | `/api/v1/audio/lookup` 4xx/5xx | Existing `lookup_failed` error state — verify it surfaces (it currently does) |
| User clicks Play before engine has loaded | Engine instance not yet attached | Play call queues until engine is ready, OR is a no-op that flips back to "Play" within 250 ms (no permanent "Pause-without-audio" state) |
| Browser blocks autoplay | Synthesis denied | Surface `engine_unavailable` (or a new error kind if the cause is distinguishable) with Retry |

### Empty States & Edge Cases

| Scenario | Condition | Expected Behavior |
|----------|-----------|-------------------|
| Section has no narratable text | `sanitized_text === ''` | Listen button is hidden (existing behavior — verify) |
| User switches sections while playing | Navigation event | Existing engine terminates, new engine loads but does NOT auto-play — user must click Play (preserves browser gesture rules) |
| User opens audio in second tab | BroadcastChannel "opening" event | First tab pauses (existing behavior — verify still works after wiring fix) |
| User closes Playbar mid-playback | Click ✕ | Engine terminates, `speechSynthesis.cancel()` runs, no orphaned utterances |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Drive engine commands from the Pinia store, not from the Playbar component directly | (a) Watcher in `useTtsEngine` on `store.status`, (b) Direct calls from store actions to a module-scope `lastEngine`, (c) Move engine ref into the store | (b) — keep `lastEngine` in the engine composable but expose a `playActive()`/`pauseActive()` from `useTtsEngine` that the store calls; matches existing pattern (`terminate()` already does this), keeps the engine module the single owner of the engine instance, avoids dual-source-of-truth bugs. |
| D2 | Web Speech voice-load wait window | (a) No wait — fail fast, (b) Wait indefinitely, (c) 1.5 s, silent, (d) 1.5 s with a small "starting…" indicator on the play button | (d) — most browsers populate voices within a few hundred ms; 1.5 s is well below the user's "is this broken?" threshold. Showing a visible "starting…" state (e.g., spinner glyph on the play button) is more transparent than absorbing the wait silently and gives the user a clear "the system is doing something" signal. Times out into the existing error state, recoverable via Retry. |
| D3 | Should Play also auto-start after `engine.load()` (i.e., merge Listen-click and Play-click)? | (a) Listen → load AND play (one tap), (b) Listen → load only; user must click Play (today's flow) | Keep (b) — preserves the user-gesture chain across iOS Safari, gives the user one extra moment to see the engine chip, and matches existing tests. We're fixing the second click, not redesigning the first. |
| D4 | Where to put the `voiceschanged` listener — engine or composable? | (a) Inside `WebSpeechEngine.speakAt`, (b) In `useTtsEngine.load()` before constructing the engine | (a) — the engine already owns the synth interaction; adding a listener at the speakAt boundary keeps the fix local and means the wait only happens on first speak (not every section load). |
| D5 | Add a "playback didn't start" watchdog as a belt-and-suspenders error path | (a) Rely on D1 + D2 only, (b) Add a 1 s post-Play watchdog | (b) — after `store.play()` invokes the engine, start a 1 s timer; if `speechSynthesis.speaking` is still `false` (or for MP3, `audio.currentTime` hasn't advanced), fire `engine_unavailable` so the user sees the existing error+Retry state. Catches unknown-cause silent failures (browser autoplay policy, muted output device, OS-level audio routing) that D1 and D2 don't directly address. |

## Success Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Play-button → first audible speech | ∞ (silent) | < 500 ms (voices loaded) / < 2 s (race) | Manual Playwright check + a unit test on the wired store action |
| "Pause label without audio" occurrences | Always | 0 | Unit test asserts `engine.play()` is invoked when `store.play()` runs |
| Error state visibility when synthesis fails | Hidden (status stuck on 'playing') | Visible 100% of failures | Unit test: simulate `engine_unavailable` → assert Playbar renders Retry |

## Research Sources

| Source | Type | Key Takeaway |
|--------|------|-------------|
| `frontend/src/stores/ttsPlayer.ts:91-97` | Existing code | `play()`/`pause()` are pure state-setters — no engine call. **This is the bug.** |
| `frontend/src/composables/audio/useTtsEngine.ts` | Existing code | Engine instance is held in module-level `lastEngine`; `terminate()` already shows the call pattern. `onError`/`onSentenceChange`/`onEnd` are wired in `load()`, but no inbound `play`/`pause` ever fires. |
| `frontend/src/composables/audio/webSpeechEngine.ts:79-89` | Existing code | Emits `engine_unavailable` immediately when `getVoices()` is empty — no `voiceschanged` retry. |
| `frontend/src/components/audio/Playbar.vue:30-36, 69-81` | Existing code | Error state UI (Retry button) is already implemented; it just isn't being reached because the failure path doesn't fire. |
| `frontend/src/components/settings/SettingsTtsPanel.vue:125` | Existing code | Settings panel already listens to `voiceschanged` — same pattern can be reused in the engine. |
| MDN: `SpeechSynthesis.getVoices()` async population | External | `voiceschanged` is the documented signal that voices are ready; relying on the first synchronous read is a known pitfall in Chromium. |
| `backend/app/config.py:98-100` | Existing code | Default TTS engine is `web-speech`; Kokoro is opt-in. No backend change needed for this fix. |

## Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Are there existing Playwright/Vitest tests that already assert engine invocation, and did they pass for some now-stale reason (e.g., mocked store)? Worth a `git blame` on `ttsPlayer.ts` to check when/if engine wiring regressed. | Eng | During /plan |

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | Q1 (one-tap play): keep two-click. Q2 (voice wait): 1.5 s + small "starting…" indicator. Q4 (watchdog): add. Q3 (regression history): kept as Open Question. | Updated D2 to specify the visible indicator. Added D5 for the 1 s watchdog. Removed Q1, Q2, Q4 from Open Questions; renumbered. |
