---
date: 2026-05-03
status: Draft (revised post-grill)
tier: 2 — Enhancement (bundle expanded mid-review)
related:
  - docs/plans/2026-05-02-audiobook-mode-plan.md
  - docs/requirements/2026-05-02-audiobook-mode-requirements.md
---

# Summary & Audio UX Fixes — Requirements

## Problem

After shipping audiobook-mode (v1.6), four UX gaps surfaced on the book-detail
(`/books/{id}`) and section-detail (`/books/{id}/sections/{sectionId}`) surfaces.
Each gap silently degrades the perceived reliability of features that already
work on the backend:

1. **No feedback when a book summary is queued.** On the Summary tab, clicking
   **Generate book summary** fires the POST and the backend creates the job, but
   the UI stays on the empty state. The user has no way to know work started
   without checking the server logs.
2. **Audio surface buttons are visually inconsistent.** Buttons across
   `frontend/src/components/audio/` (the Audio tab itself, `GenerateAudioModal`,
   `AudioFileRow`, `AnnotationPlaylistRow`, `SectionsAudioRow`, `Playbar`,
   `StaleSourceBanner`) and `TtsPlayButton` use raw Tailwind utility classes
   (e.g. `bg-indigo-600`, `border-slate-300`) instead of the app-wide
   `btn-primary` / `btn-secondary` semantic classes used everywhere else
   (Summary tab, modals, reader). They look and behave like strangers inside
   the same shell.
3. **Browser-speech (Web Speech) playback is not exposed in the UI.** The
   audiobook-mode plan shipped a `TtsPlayButton` component that wraps the
   `ttsPlayer` store (which routes to either pre-generated Kokoro MP3 or
   Web Speech depending on availability), but it is only referenced from
   its own test file. From the user's perspective, the only way to listen
   to a summary is to first run the (slow, ffmpeg-and-Kokoro-gated) audio
   generation pipeline — defeating the "click and listen" promise of the
   Web Speech fallback path.
4. **Web Speech has no settings UI.** Existing voice/rate settings in the app
   are Kokoro-specific. There is no way to choose a Web Speech voice, set
   speaking rate, or test a voice before listening. Without this, the Web
   Speech entry points (gap #3) ship with no user control over how content
   sounds.

### Who & Why Now

A single user (the product owner) on the local dev install. Audiobook-mode
just shipped, so the user is exploring the new audio surface for the first
time and hitting these rough edges immediately. Each one undermines confidence
in the new feature.

## Goals & Non-Goals

### Goals

- **G1.** After clicking **Generate book summary**, the Summary tab shows
  visible feedback within ~1 second — an indeterminate spinner with elapsed
  time (`MM:SS elapsed`), driven by the existing job lifecycle so the user
  knows work is in progress. (Per-section progress is *not* possible: the
  backend treats book-summary as a single LLM call.)
- **G2.** Every button on the Audio tab, in the Generate Audio modal, in
  audio-row components, in the Playbar, and in `TtsPlayButton` uses the
  shared `btn-primary` / `btn-secondary` semantic classes — visual parity
  across surfaces. No raw `bg-indigo-*` / `bg-slate-*` / `border-slate-*`
  button utilities remain in the `audio/` folder or in `TtsPlayButton`.
- **G3.** From any summary view (book summary, section summary), the section
  content view, and individual annotation views, the user can press a
  Listen button and hear the content read aloud via the global Playbar.
  Engine routing: pre-generated Kokoro MP3 plays when available; Web Speech
  is the fallback so users without a Kokoro install (no ffmpeg / no
  pre-generation) can still listen with a single click.
- **G4.** A new "Web Speech" subsection appears in `SettingsView` under an
  "Audio / TTS" group, exposing voice picker, rate slider (0.5×–2.0×, 0.1×
  steps), a Test button to preview the selection, and a Reset-to-defaults
  button. Settings persist per-device in `localStorage` under a versioned key
  and are respected whenever Web Speech is the active engine (i.e., when no
  pre-generated MP3 exists for the content; per D8).

### Non-Goals

- **NOT** redesigning the Summary tab layout — only adding the missing
  progress affordance. *Reason:* scope creep; the existing layout is fine.
- **NOT** rebuilding the design-token / theming system. *Reason:* "inherit
  reader preset" turned out to mean "use the same button classes as the rest
  of the app," not typography inheritance.
- **NOT** changing how Kokoro audio generation works on the Audio tab.
  *Reason:* generation pipeline is correct; only trigger styling is wrong.
- **NOT** adding sentence-level highlight to the new Listen entry points.
  *Reason:* highlight is an existing reader-only concern; this fix delivers
  basic playback control via the existing Playbar. Highlight on summary
  views is a follow-up.
- **NOT** persisting Web Speech playback position. *Reason:* Web Speech is
  the "ephemeral, instant" engine by design; persistence is for Kokoro audio.
- **NOT** extending the `bookcompanion listen` CLI to speak summaries.
  *Reason:* this fix targets web-surface UX gaps; CLI parity is separate.
- **NOT** providing a Cancel button on the new in-progress indicator.
  *Reason:* the existing `/processing/{id}/cancel` endpoint marks the job
  FAILED in the DB but cannot terminate the LLM subprocess, so token spend
  continues. Surfacing a button that doesn't actually cancel is misleading;
  real cancellation is a separate scope.
- **NOT** re-attaching the in-progress indicator on page reload (originally
  J6). *Reason:* requires a `GET /books/{id}/active-jobs` endpoint that
  doesn't exist; out of scope for this bundle. The next click of Generate
  will get a 409 with `active_job_id` and reattach (existing behavior).
- **NOT** server-side persistence of Web Speech settings. *Reason:* voice
  availability is per-device; sync would defeat the purpose. localStorage
  only.
- **NOT** per-book Web Speech voice/rate overrides. *Reason:* global
  settings only for v1; per-book is future work.
- **NOT** Listen entry points on book TOC rows or search results.
  *Reason:* surface proliferation; the in-context views already provide it.
- **NOT** deep-link autoplay (`?play=...` URL params). *Reason:* dodges
  browser autoplay-policy edge cases; explicit user click only.
- **NOT** Playbar collapse / minimize affordance. *Reason:* polish for
  later; out of v1 scope.
- **NOT** settings export/import or telemetry. *Reason:* localStorage is
  intentionally per-device; app is local-only with no telemetry pipeline.
- **NOT** a bundle-size budget assertion. *Reason:* personal tool; existing
  audiobook-mode code already pays the cost.
- **NOT** Listen on annotations playlist (the playlist concept is already
  handled elsewhere by the audiobook-mode plan). *Reason:* this fix adds
  Listen on *individual* annotations only; playlist orchestration is
  separate.

## Solution Direction

```
1. Summary tab progress (frontend-only)
   BookSummaryTab.vue
     ├─ on POST 201/202 → set local activeJobId; flip computed state
     │  to 'inProgress' (local override beats book.default_summary).
     ├─ render an indeterminate spinner + "Generating book summary…
     │  M:SS elapsed" (clock starts at POST response).
     ├─ on SSE processing_completed → emit('book-refetch'); clear
     │  activeJobId; state returns to computed-from-book.
     └─ on SSE processing_failed → swap to existing failed state.

2. Button-parity sweep (frontend-only)
   audio/AudioTab.vue, audio/GenerateAudioModal.vue, audio/AudioFileRow.vue,
   audio/AnnotationPlaylistRow.vue, audio/SectionsAudioRow.vue,
   audio/Playbar.vue, audio/StaleSourceBanner.vue, audio/TtsPlayButton.vue
     └─ replace raw Tailwind utility classes with btn-primary / btn-secondary
        (verify dark-mode variants exist on those classes; extend if not).

3. Listen entry points (frontend-only IF Q7 sanitizer fitness passes;
   otherwise scope expands to a backend content-mode sanitizer profile)
   SectionSummary view, BookSummaryTab, SectionContent view, AnnotationView
     ├─ mount existing TtsPlayButton bound to the right
     │  (contentType, contentId).
     └─ ensure global Playbar mounts ONCE in App.vue; consolidate any
        existing per-view mounts. Playbar continues across navigation;
        only explicit Playbar close stops playback.

4. Web Speech settings (new frontend code)
   SettingsView → new "Audio / TTS → Web Speech" subsection
     ├─ voice picker (async-populated from speechSynthesis.getVoices(),
     │  shows loading state until populated; persists by voice name with
     │  fallback to default if name missing on next load).
     ├─ rate slider (0.5–2.0, step 0.1, default 1.0).
     ├─ Test button (speaks a sample sentence with current selection).
     ├─ Reset-to-defaults button (clears the localStorage key).
     └─ persisted in localStorage under `webspeech_settings_v1`.
        On version bump, write v2 key and either migrate or reset.
```

## User Journeys

### J1 — Generate book summary with feedback (fixes #1)

1. User opens `/books/1?tab=summary` for a book where every section is
   summarized but no book summary exists.
2. Empty state shows "N of N sections summarized." + **Generate book summary**.
3. User clicks the button.
4. Within ~1 second, the empty state is replaced with: an indeterminate
   spinner + "Generating book summary… 0:00 elapsed". The clock ticks each
   second (0:01, 0:02, …).
5. There is no Cancel button (see Non-Goal).
6. On `processing_completed`, the view swaps to the populated summary
   (parent emits a refetch).
7. On `processing_failed`, the view swaps to the existing failed state with
   Retry.

### J2 — Audio surface buttons recognizable (fixes #2)

1. User opens `/books/1?tab=audio`.
2. **Generate audio** is styled identically to **Generate book summary** on
   the Summary tab — same height, padding, color, hover, focus ring.
3. The Generate Audio modal's primary/secondary actions match modals
   elsewhere in the app.
4. Per-row buttons in `AudioFileRow`, `AnnotationPlaylistRow`,
   `SectionsAudioRow` match the same shared button language.
5. The Playbar's action buttons match. `TtsPlayButton` (the new Listen
   button) matches.

### J3 — Listen to a section summary instantly (fixes #3)

1. User opens `/books/1/sections/6?tab=summary`.
2. In the header action row of the summary view, a **Listen** button is
   visible (exact placement deferred to /spec — see Q1).
3. User clicks Listen. The global Playbar appears at the bottom of the
   viewport.
4. **Engine selection:** if pre-generated Kokoro MP3 exists for this
   section_summary, the Playbar plays it. Otherwise, Web Speech speaks
   the sanitized summary text using the user's configured voice + rate.
5. Playback control lives in the Playbar (play / pause / close; scrub
   only when the active engine is MP3 — Web Speech utterances are not
   seekable). The Listen button itself does not toggle ▶/⏸ — it is a
   single-shot "open the player" affordance, matching the component's
   existing contract.
6. Pressing **Space** with no input focused toggles play/pause via the
   Playbar.
7. Closing the Playbar (its X button) stops playback. Navigating to
   another route does NOT stop playback — audio continues across
   navigation until explicit close.
8. If the browser has no Web Speech support and no MP3 exists, the
   Listen button is hidden or disabled with a tooltip (see Q2).

### J4 — Listen to a book summary instantly

1. Same as J3 but on `/books/1?tab=summary` once a book summary exists.
2. **Listen** appears in the header action row beside **Read Section
   Summaries** / **Regenerate**.

### J5 — Listen to section content instantly

1. User opens `/books/1/sections/6?tab=content`.
2. **Listen** appears in the same position as on the summary tab.
3. Behavior identical to J3. Note: chapter content can be tens of
   thousands of characters; Web Speech will read it as a single long
   utterance with no resume across reloads. This is an accepted
   limitation for v1 (see Q7 for sanitizer fitness check).

### J6 — Listen to an individual annotation

1. User opens an annotation view (`AnnotationsView` or per-annotation
   surface).
2. A **Listen** button appears beside the annotation body.
3. Clicking it plays the annotation text via the Playbar (engine
   selection per J3).
4. Playlist-level annotation playback is unchanged (handled by
   existing audiobook-mode UI).

### J7 — Switch playback content mid-stream

1. User clicks Listen on section 6 summary. Audio starts.
2. User navigates to section 7, clicks Listen there.
3. New playback replaces the current immediately (matches existing
   `ttsPlayer.open()` overwrite semantics). No queueing, no
   confirmation dialog.

### J8 — Configure Web Speech voice + rate (fixes #4)

1. User opens `SettingsView` and scrolls to "Audio / TTS → Web Speech".
2. Voice picker shows "Loading voices…" briefly, then populates with
   the browser's available voices.
3. User selects a voice; rate slider defaults to 1.0×.
4. User clicks **Test**. The browser speaks a sample sentence
   ("The quick brown fox jumps over the lazy dog.") using the current
   selection — synchronously inside the click handler so iOS Safari's
   user-gesture requirement is satisfied.
5. User adjusts rate; tests again.
6. User clicks **Save** (or settings auto-save — design choice for
   /spec). Settings are written to `localStorage["webspeech_settings_v1"]`.
7. User clicks **Reset to defaults** to clear the saved settings.
8. On next Listen click anywhere in the app, the saved voice + rate
   are used.

### Error / Edge Cases

- Web Speech unavailable in browser AND no MP3 exists → Listen entry
  point hidden or disabled with tooltip (see Q2).
- Voice list empty on first call to `getVoices()` → picker shows
  "Loading voices…" until `voiceschanged` fires; never shows an empty
  dropdown.
- Persisted voice name no longer present on next load → fall back to
  browser default voice; surface a small "Previously selected voice
  not available" hint in settings.
- iOS Safari user-gesture requirement → the Listen click handler must
  start `speechSynthesis.speak()` synchronously (no awaited fetches
  before speak); /spec must verify and address.
- User clicks **Generate book summary** twice rapidly → first click
  flips to inProgress; second click is a no-op while activeJobId is
  set, OR the backend returns 409 with `active_job_id` and the UI
  attaches to that job.
- Web Speech utterance error / voice fails / interruption → Playbar
  surfaces the error inline with a Retry button (using existing
  `ttsPlayer.setError()` + `TtsErrorKind`).
- User starts Web Speech while Kokoro Playbar is active (or vice
  versa) → `ttsPlayer.open()` overwrites state; only one engine ever
  plays. (Structurally enforced by the store's scalar shape.)
- User navigates between books while playback is active → playback
  continues with the previous content; the new book page just
  renders alongside.

## Design Decisions

| #  | Decision | Options Considered | Rationale |
|----|----------|--------------------|-----------|
| D1 | In-progress indicator is an indeterminate spinner + `MM:SS elapsed`, NOT an X-of-Y progress bar. | (a) X-of-Y %; (b) indeterminate spinner; (c) toast only. | The backend `book_summary.py` only emits `processing_completed` / `processing_failed` — book-summary is a single LLM call with no per-section events. (a) is impossible without backend instrumentation. (b) is the honest UX. |
| D2 | "Inherit reader preset" = use `btn-primary` / `btn-secondary` classes; sweep covers ALL buttons in `audio/` + `TtsPlayButton`. | (a) reader font/theme tokens; (b) semantic btn classes; (c) both; (d) only the one button user mentioned. | User clarified intent is visual parity, not typography. Sweeping the whole audio folder + TtsPlayButton applies the rule consistently. |
| D3 | Listen on section summary, book summary, section content, AND individual annotations. | (a) section summary only; (b) section + book summary; (c) all three views; (d) all four (with annotations). | Web Speech is already implemented; gating it behind pre-generation defeats its purpose. Annotations added per user direction. |
| D4 | Single bundled requirements doc (now expanded to 4 workstreams). | (a) one bundle; (b) split into 2 (UX vs. settings); (c) 4 separate docs. | All four touch the same surfaces and ship together; one /spec/plan/verify cycle is simpler. |
| D5 | Reuse existing `TtsPlayButton` as a single-shot "open the player" affordance; do NOT extend it to a play/pause toggle. | (a) wire as-is + Playbar drives playback control; (b) extend the button to be self-contained play/pause; (c) both. | Keeps button responsibility narrow. Playback control already lives in Playbar; duplicating it on every Listen button creates conflicting state. |
| D6 | Single-active-engine is structurally enforced by `ttsPlayer` store (scalar `isActive` / `engine` / `status`). No new code required. | n/a — code-derived. | Confirmed by reading `frontend/src/stores/ttsPlayer.ts`. Removing as a "decision" — it's just a fact. |
| D7 | `BookSummaryTab` gains a local `inProgress` state override: when local `activeJobId` is set, the computed `state` returns `inProgress` regardless of `book.default_summary`. On SSE completion, clear `activeJobId` and let the computed state revert. | (a) keep `state` purely computed from `book`; (b) add local override. | Without (b), the UI cannot reflect that work has started until the parent refetches. (b) is the minimum state-machine change; reversion on completion event keeps the source of truth in the book prop. |
| D8 | Engine priority: pre-generated Kokoro MP3 wins over Web Speech when both are available. | (a) MP3 wins; (b) Web Speech wins on the new entry points; (c) ask each time. | MP3 was deliberately generated and is higher quality. Web Speech is the no-pre-gen fallback. Future setting "Always use Web Speech" can override. |
| D9 | Cross-page playback persistence: navigation does NOT stop playback; only closing the Playbar (X) does. | (a) navigation stops; (b) navigation continues; (c) continue within book, stop on book change. | Audiobook UX expectation. Vue Router doesn't unmount the global app shell, so this is the natural behavior. Replaces the earlier "navigating away stops" AC. |
| D10 | Switching content while playing replaces immediately — no queue, no confirmation. | (a) replace; (b) queue; (c) confirm. | Matches existing `ttsPlayer.open()` overwrite semantics; user intent is obvious. |
| D11 | Web Speech settings persistence: `localStorage["webspeech_settings_v1"]`. Versioned key; on schema change, write a new version and reset or migrate. | (a) localStorage; (b) server-side; (c) both. | Voice availability is per-device; server sync would be wrong. Versioning future-proofs schema changes. |
| D12 | Web Speech rate range: 0.5×–2.0×, step 0.1×, default 1.0×. | (a) 0.5–2.0; (b) 0.25–4.0; (c) preset buttons Slow/Normal/Fast. | Practical browser support; matches podcast-app norms. |
| D13 | Voice picker persists by voice **name** (string), with fallback to default voice if the name is no longer present after `voiceschanged`. | (a) by name; (b) by URI; (c) by language only. | Names are the most stable identifier across browsers; URIs vary. Name-with-fallback handles voice list churn. |
| D14 | Test strategy: mock `window.speechSynthesis` in Vitest; Playwright e2e asserts state transitions only (no real audio assertion). Manual verification for actual audio quality. | (a) mocked unit + state-only e2e; (b) heavy e2e with real audio; (c) defer entirely. | jsdom has no SpeechSynthesis; headless Chromium audio assertions are flaky. (a) is the pragmatic minimum that catches regressions. |
| D15 | Global Playbar mounts ONCE in `App.vue`. Existing per-view Playbar mounts (if any) are consolidated. | (a) global; (b) per-view; (c) defer. | Single source of truth; eliminates double-render risk. /spec must audit existing mounts. |
| D16 | mediaSession is in scope for Web Speech: lockscreen "now playing" + hardware play/pause keys. | (a) explicit requirement; (b) verify-and-extend; (c) out of scope. | User asked for explicit requirement. The store already has a `mediaSessionEnabled` flag — wire it through. |
| D17 | Keyboard shortcut: `Space` toggles Playbar play/pause when no input/textarea/contenteditable element is focused. | (a) Space only; (b) full keyboard map (arrows, Esc); (c) no shortcuts. | Standard audiobook UX; small scope; high value. |
| D18 | Settings UI lives in `SettingsView` under a new "Audio / TTS → Web Speech" subsection. | (a) SettingsView; (b) Playbar gear popover; (c) both. | Canonical place; discoverable via main nav; matches existing settings patterns. |
| D19 | Voice preview "Test" button uses a fixed sample sentence ("The quick brown fox jumps over the lazy dog."). | (a) Test button with fixed sample; (b) no preview; (c) user-typed sample. | Critical UX — voice names are not self-describing. Fixed sample is simpler than user input. Speak() must fire synchronously inside the click handler for iOS. |
| D20 | Settings panel includes a **Reset to defaults** button. | (a) yes; (b) no. | Standard settings affordance; clears localStorage key. |
| D21 | Web Speech error display lives in the Playbar (replaces "now playing" with error + Retry). | (a) Playbar inline; (b) toast; (c) inline below Listen button. | Centralized; consistent with how Kokoro errors surface. |
| D22 | Elapsed-time format for the in-progress spinner: `M:SS elapsed` (or `MM:SS` past 9:59). | (a) MM:SS; (b) seconds only; (c) "over N minutes". | Compact, readable, standard. |
| D23 | `btn-primary` / `btn-secondary` dark-mode variants must exist; if missing, /spec extends them as part of this fix. | (a) verify and extend if missing; (b) light-mode only; (c) defer. | App appears to support dark mode (TtsPlayButton has dark: utilities); the sweep must not regress dark-mode usability. |

## Open Questions (carry into /spec)

| #  | Question | Owner | Needed By |
|----|----------|-------|-----------|
| Q1 | Exact placement of **Listen** on each surface — header action row vs. floating-above-content vs. below-title? Should it sit beside Regenerate / Read buttons? | Maneesh | Before /spec |
| Q2 | When Web Speech is unsupported AND no MP3 exists, hide the Listen button or show disabled with "Browser doesn't support speech" tooltip? | Maneesh | Before /spec |
| Q3 | _(Dropped during grill — was about coverage-bar styling alignment, moot once D1 downgraded to indeterminate spinner.)_ | — | — |
| Q4 | Are there other places in the app still using raw Tailwind button utilities that should be normalized in the same pass (consistency sweep beyond `audio/`)? | Maneesh | Before /spec |
| Q5 | _(Resolved by code during grill — `book_summary.py` emits only `processing_completed` / `processing_failed`; no per-section events. Drove D1.)_ | — | — |
| Q6 | _(Resolved by code during grill — `ttsPlayer` store is structurally single-engine. Drove D6.)_ | — | — |
| Q7 | Sanitizer fitness for raw section content (vs. summaries it was tuned for). The audiobook-mode `markdown_to_speech` may produce poor audio for chapters with image refs, code blocks, tables, math. /spec must verify or define a content-mode sanitizer profile. | Agent (in /spec) | Before /spec finalizes |
| Q8 | Does the existing Playbar already wire `navigator.mediaSession` for Kokoro? If yes, extend it for Web Speech; if no, implement from scratch. | Agent (in /spec) | Before /spec finalizes |
| Q9 | Do `btn-primary` / `btn-secondary` shared classes have dark-mode variants? If not, /spec must add them as part of this fix. | Agent (in /spec) | Before /spec finalizes |
| Q10 | Confirm that all existing voice/rate settings in the app are Kokoro-only (i.e., no Web Speech settings infrastructure to reuse). User believes so but isn't certain. | Agent (in /spec) | Before /spec finalizes |
| Q11 | Audit current Playbar mount sites. If Playbar is already mounted at `App.vue`, this fix is trivial; if it lives in `BookOverviewView` or similar, consolidate to global. | Agent (in /spec) | Before /spec finalizes |
| Q12 | Does the Web Speech playback path require a `/audio/lookup` round-trip for sanitized text + sentence offsets, or can sanitization happen client-side? Determines whether AC "starts within ~1 second" is comfortable or tight. | Agent (in /spec) | Before /spec finalizes |

## Acceptance Criteria

### Summary tab progress (G1)

- [ ] Clicking **Generate book summary** swaps the Summary tab to an
  in-progress view within 1 second of the POST returning 201/202.
- [ ] The in-progress view shows an indeterminate spinner and an elapsed
  timer in `M:SS` format, ticking each second from 0:00.
- [ ] No Cancel button is shown on the in-progress view.
- [ ] On `processing_completed`, the Summary tab shows the populated summary
  without a manual page refresh.
- [ ] On `processing_failed`, the Summary tab shows the existing failed
  state with Retry.
- [ ] Local `activeJobId` is cleared on completion or failure so the
  computed state correctly reverts.

### Button parity sweep (G2)

- [ ] No `bg-indigo-*`, `bg-slate-*`, `border-slate-*`, or `hover:bg-*`
  raw Tailwind button utilities remain in `frontend/src/components/audio/`
  or in `frontend/src/components/audio/TtsPlayButton.vue`.
- [ ] Every primary action in those components uses `btn-primary`; every
  secondary / row-level / dismiss action uses `btn-secondary`.
- [ ] The shared classes render correctly in both light and dark mode
  (Q9 may require extending the classes themselves).

### Listen entry points (G3)

- [ ] A **Listen** button is visible and functional on: section-summary
  view, book-summary view (when populated), section-content view, and
  individual annotation view.
- [ ] Clicking Listen mounts (or reveals) the global Playbar with the
  selected content loaded.
- [ ] When pre-generated Kokoro MP3 exists for the content, the Playbar
  plays it; otherwise it plays via Web Speech.
- [ ] Playback continues across in-app navigation; only closing the
  Playbar (X) stops it.
- [ ] Clicking Listen on a different content target while playback is
  active replaces the current playback immediately (no queue, no
  confirmation).
- [ ] Pressing **Space** with no input/textarea/contenteditable focused
  toggles Playbar play/pause.
- [ ] When Web Speech is the active engine (no MP3 available), playback
  respects the user's saved voice and rate from `webspeech_settings_v1`.
- [ ] On Web Speech error (voice unavailable, utterance error,
  interruption), the Playbar shows an error message with a Retry button.
- [ ] When neither Web Speech nor a pre-generated MP3 is available,
  the Listen button is hidden or disabled (per Q2 resolution).
- [ ] On iOS Safari, Listen click successfully starts Web Speech
  playback (the call chain preserves the user-gesture context).
- [ ] `navigator.mediaSession` metadata is set when Web Speech playback
  starts so OS lockscreen / hardware keys reflect "now playing".

### Web Speech settings (G4)

- [ ] `SettingsView` shows a new "Audio / TTS → Web Speech" subsection.
- [ ] The voice picker shows "Loading voices…" until
  `speechSynthesis.getVoices()` populates (via `voiceschanged`), then
  lists available voices.
- [ ] The rate slider ranges 0.5×–2.0× with 0.1× steps, default 1.0×.
- [ ] A **Test** button speaks a fixed sample sentence using the
  currently-selected voice + rate; speak() fires synchronously inside
  the click handler (iOS-safe).
- [ ] A **Reset to defaults** button clears
  `localStorage["webspeech_settings_v1"]` and reverts the picker / slider
  to defaults.
- [ ] Settings persist to `localStorage["webspeech_settings_v1"]` and
  survive page reload.
- [ ] On schema change, the version suffix bumps; old keys are either
  migrated or treated as reset.
- [ ] If the persisted voice name is no longer in the voice list on
  next load, the picker falls back to the browser default and surfaces
  a hint.

### Test strategy (D14)

- [ ] Unit tests mock `window.speechSynthesis`; no real audio is
  invoked in jsdom.
- [ ] Playwright e2e asserts that clicking Listen sets
  `ttsPlayer.isActive = true` and the Playbar appears; does not assert
  audio actually plays.
- [ ] Manual verification covers real audio playback on at least one
  desktop browser and one iOS Safari instance.

## Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | F1 missing reattach journey; F2 unverified SSE granularity; F3 unverified single-engine enforcement; F4 CLI scope unstated. | Added J6 (reattach) + AC; added non-goal for CLI; added Q5 / Q6 as research tasks. |
| 2 | F5 arbitrary 200 ms latency AC; F6 button-state-during-playback contract missing; F7 a11y; F8 cosmetic icon. | F5 rephrased AC; F6 added playback-state language; F7 skipped; F8 noted. |
| 3 (grill — deep, 42 questions) | Code-derived: book-summary backend has no per-section events; ttsPlayer is structurally single-engine; TtsPlayButton is a thin "open the player" shell with no toggle behavior; Web Speech actually playing requires Playbar mounted. User-derived: 35 dispositions covering progress-bar downgrade, button sweep scope, Listen wiring model, Playbar non-goal removal, new Web Speech settings workstream, iOS gesture preservation, mediaSession in scope, cross-page playback policy, engine selection priority, annotations added, J6 dropped, Cancel dropped, keyboard Space, voice preview, rate range, voice persistence by name, dark mode, error display location, etc. | Full rewrite: G1 downgraded to indeterminate spinner; G2 expanded to whole audio/ folder + TtsPlayButton; G3 added MP3-priority + annotations; G4 added entire Web Speech settings workstream. Added D7–D23. Reframed D6 as code-derived fact. Dropped J6 / Cancel / "navigating away stops" / Q3 / D6's status as a decision. Added J7 (switch content), J8 (settings), J6 (annotation Listen). Added Q7–Q12. Acceptance Criteria reorganized by goal. Non-Goals expanded to ~14 items. |
| 4 (post-rewrite consistency review) | Problem #3 and G3 framed Web Speech as the only engine ("no Kokoro install required") which contradicted D8's MP3-priority. G4 overstated that settings apply to "every Web Speech playback" — only true when Web Speech is the active engine. J3 listed "scrub" as a Playbar control, but Web Speech utterances are not seekable. Solution Direction §3 claimed "frontend-only" without acknowledging Q7's potential backend expansion. Open Questions table jumped Q2→Q4 (Q3/Q5/Q6 were dropped or code-resolved but not visibly accounted for). | Reworded Problem #3 + G3 to frame Web Speech as the fallback engine, not the only one. Tightened G4 + the corresponding AC to "when Web Speech is the active engine." Annotated Solution Direction §3 as conditionally frontend-only pending Q7. Re-listed Q3/Q5/Q6 in the Open Questions table with "(Resolved/Dropped during grill — drove Dx)" notes so the trail is visible. Clarified J3 step 5 that scrub applies only when MP3 is the active engine. |
