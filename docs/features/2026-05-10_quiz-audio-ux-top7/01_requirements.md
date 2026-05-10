---
tier: 3
type: feature
feature: quiz-audio-ux-top7
spec_ref: null
date: 2026-05-10
status: Approved
---

# Quiz & Audio UX — Top-7 Fixes — Requirements

**Date:** 2026-05-10
**Last updated:** 2026-05-10
**Status:** Approved (post-MSF loop 3)
**Tier:** 3 — Feature
**Mode:** interactive
**Open Questions:** 4 (3 resolved in grill loop 2; loop 3 added 1 new FR + 6 FR amendments)

## Problem

Two recently-shipped flows on the book-detail page — Quiz (v0.3.0, 2026-05-08) and Audio (v1.6, 2026-05-03) — fail their first-time UX in a way the [/design-crit](../../../docs/2026-05-10_quiz-and-audio-design-crit/design-crit/design-crit.md) of 2026-05-10 captured concretely. Two failures break trust on the very first click; five more force users to decode engineering language to understand what the feature does.

The seven highest-severity findings, in priority order:

1. **Q-3** Start-quiz silently fails. `POST /quiz-sessions` returns 500; UI shows no toast, no inline error, no spinner, no retry — the button just stays "active" and nothing happens.
2. **A-1** The Audio empty state has a single primary CTA labelled "Generate audio" sitting next to the literal copy "Instant on Web Speech (no pre-generation needed)". A first-time user reads the button as "I must generate before I can listen" — wrong for the default engine.
3. **Q-1** Quiz first-visit shows a bare form (Quiz scope + Theme). Nothing tells the user what a quiz is, how many questions, how long generation takes, or what "Got it / Partial / Missed" means.
4. **A-3** The Audio empty state's hierarchy is inverted — "No audio yet for this book." (muted gray) reads as the headline; the actionable "Instant on Web Speech…" line is sub-caption beneath it.
5. **A-5** The Generate-audio dialog estimate "~3.6 min · ~54 MB for 17 sections" is ambiguous: 3.6 min generation time? Playback duration? It's generation; playback would be ~25 min.
6. **Q-7** The Quiz scope picker shows "0 / 60,000 tokens" — raw LLM-context jargon with no decision anchor.
7. **A-7** Settings → Text-to-speech ships with a "Spike findings" heading — engineering artefact left over from the 2026-05-03 audio spec's research phase.

### Finding-ID legend (for top-down readers)

| ID  | One-line headline                                                          | Severity | Surface                          |
| --- | -------------------------------------------------------------------------- | -------- | -------------------------------- |
| Q-3 | Start-quiz silently fails — no toast / spinner / retry on 500              | high     | Quiz tab + global API client     |
| A-1 | Single "Generate audio" CTA contradicts "Instant on Web Speech" copy       | high     | Audio tab empty state            |
| Q-1 | Quiz first-visit is a bare form with no orientation                       | high     | Quiz tab                         |
| A-3 | Audio empty-state hierarchy inverted ("No audio yet" reads as headline)   | high     | Audio tab empty state            |
| A-5 | Generate-audio estimate "~3.6 min · ~54 MB" is ambiguous (gen vs. play)   | high     | Generate-audio modal             |
| Q-7 | Quiz scope picker shows "0 / 60,000 tokens" — engineering jargon          | high     | Quiz tab scope picker            |
| A-7 | Settings → TTS still shows a "Spike findings" engineering heading         | high     | Settings → Text-to-speech panel  |

### Who experiences this?

The single self-hosted user of Book Companion (matches the workstream's User Segments — technical users, power readers of non-fiction). All seven findings hit on the *first* time the user opens Quiz or Audio for any book; they're onboarding-shaped, not power-user-shaped.

### Why now?

- Quiz shipped to v0.3.0 two days ago (2026-05-08) and **regressed trust** on its primary action: a real bug (the 500) is invisible because the API client doesn't front errors. This is the only finding in the bundle that's actively misleading users; the rest are friction.
- Audio shipped two engines (Web Speech instant + Kokoro generated) in v1.6 (2026-05-03) but the empty-state UI was built around Kokoro's Generate flow only. The instant path is unreachable from the surface that introduces it.
- Settings → TTS still carries a "Spike findings" research block left over from the same 2026-05-03 spec's discovery phase; it never had a copy edit before users saw it. (Note: a codebase grill found this block ALSO contains a user-valuable "Listen to comparison" A/B button — see Decisions D6 reversal.)

### Backend Defect (Q-3 root cause)

`POST /api/v1/quiz-sessions` returns 500 on the live build for the only seeded book. The design-crit observed the symptom (button stays active, no toast); the underlying defect was not diagnosed before the requirements doc was approved. Grill loop 2 added this as a hard precondition for `/spec` entry.

**Status:** Repro pending. Captured below before /spec begins.

| Field | Value |
|-------|-------|
| Endpoint | `POST /api/v1/quiz-sessions` |
| Symptom | 500; UI silent (no toast, no spinner clear) |
| Repro environment | Worktree at `feat/quiz-audio-ux-top7`, fresh `bookcompanion serve --port 8765`, single seeded book |
| Live traceback | _TBD — run repro and paste full stack trace + request body + response payload here._ |
| Suspected root cause | _TBD — to be filled by /spec entry repro task._ |
| Scope assessment | _TBD — does fix require schema migration, prompt template change, dependency update, or local code-only patch? Drives whether requirements need further amendment._ |

**Constraint on /spec:** /spec MUST open with a Q-3 repro task that fills the four `_TBD_` fields above. If the scope assessment reveals the fix requires changes outside the top-7 UX scope (e.g., backend schema, LLM prompt rewrite), pause and amend requirements before continuing.

## Goals & Non-Goals

> Goals are observable user outcomes; engineering acceptance criteria belong in `/spec`.

### Goals

- **G1 — Errors are visible.** When `POST /quiz-sessions` (or any quiz API call) fails, the user sees a toast within 1 s of the click, with the failure reason and a Retry button — measured by: zero silent-fail console lines on the Quiz tab.
- **G2 — Two real listening paths.** A new Audio user can either (a) press Play and hear the book within 1 click via Web Speech, or (b) press a separate Generate CTA and produce MP3s — measured by: one click from Audio tab to first audible word on Web Speech, with `speechSynthesis.speaking === true` within ≤ 2 s on the first chapter and ≤ 1 s on subsequent chapters. The ≤ 2 s budget is achievable because AudioTab.vue pre-warms the voice list on mount (see FR-PRE-WARM) — `getVoices()` + `voiceschanged` resolve before the user reaches the Listen button. **Testing note (MSF S6):** the metric `speechSynthesis.speaking === true` precedes user-perceived first-phoneme audio by 200–400 ms on Chrome (less on macOS Safari). The ≤ 2 s budget covers this gap; tests should not tighten the metric to first-phoneme without adding a Web Audio API listener.
- **G3 — Quiz is self-explanatory on first visit.** A user who has never read the changelog can read the Quiz tab and know what a quiz is, how many questions to expect, how long it will take, and what the lifetime tally tracks — measured by: orientation copy present + ≥1 explicit count/duration estimate near the Start button.
- **G4 — Generate-audio dialog discloses three estimates separately.** Generation time, listening duration, and disk size are three distinct labelled fields, not one ambiguous string — measured by: regex test against the dialog finding all three terms.
- **G5 — Token jargon is gone from the quiz scope picker.** A user-facing budget metric replaces "0 / 60,000 tokens" — measured by: no string `tokens` visible to the user on the Quiz tab.
- **G6 — Settings/TTS reads as user copy, not research notes.** The "Spike findings" heading is renamed to user-facing copy (D6 reversal: rename, not remove — block contains a user-valuable "Listen to comparison" A/B button) — measured by: no string `Spike` visible on Settings → TTS AND the `data-testid="listen-comparison"` button still mounted and functional.
- **G7 — Audio empty-state hierarchy leads with a verb.** The first line a new user sees is an action ("Listen to this book"), not a status ("No audio yet") — measured by: empty-state H2/H1 contains an imperative verb.

### Non-Goals (explicit scope cuts)

- **NOT in this iteration: full QnA UX critique** — because the design-crit's deferred QnA cluster (Q-DEFER) couldn't be observed live (the 500 blocked it). After Q-3 lands, a follow-up crit + spec on the QnA flow (N1/N3/J5/S4/N9 heuristics) is its own feature.
- **NOT changing TTS persistence model** — because the 2026-05-03 spec D1/FR-28 already settled this (server-side via `TTSConfig`, single SettingsService entrypoint). G6 only renames a heading.
- **NOT solving the "lavender button contrast borderline" finding (Q-6) here** — because it's medium-severity and intersects the global `.btn-primary` token already shipped via 2026-05-03 D2/FR-08/09. Address as a token-level fix later.
- **NOT solving the medium-severity findings (Q-4, Q-5, Q-8, Q-9, Q-10, A-2, A-4, A-6, A-8, A-10) or the cross-cutting X-* set** — because the orchestrator scoped this run to the top-7 TL;DR. Each is captured in the design-crit and will be picked up in a subsequent feature.
- **NOT changing the backend quiz-session generation model (provider, prompts, scoring schema)** — because the design-crit didn't critique it. The 500 root cause is a separate backend defect to be fixed in `/spec` of this feature.
- **NOT moving the quiz/audio features behind a feature flag** — because both already shipped to the only user.
- **NOT supporting parallel Listen + Generate in one session** — because the two paths share the playbar today and simultaneous use produces an ambiguous UI state. Treat the choice as exclusive per click; revisit if both paths land healthy and the user explicitly asks for it.

## User Experience Analysis

### Motivation

- **Job to be done (Quiz):** "I read this book; I want to find out how much stuck." The quiz is a self-test against the book's summaries.
- **Job to be done (Audio):** "I want to listen to summaries while doing chores / commuting." Two real shapes — instant ad-hoc playback, or an MP3 set I can scrub through and resume.
- **Importance/Urgency:** Quiz is non-blocking but the silent-failure regression breaks trust; audio is opportunistic but the empty-state block prevents discovery of the "instant" path entirely.
- **Alternatives:** for quiz — manual flashcards, Anki, Readwise Skills. For audio — open the EPUB in a TTS-capable reader externally, or use Speechify/NaturalReader on the source PDF. (See Research Sources.)

### Friction Points

| Friction Point                                                                              | Cause                                                                                            | Mitigation                                                                                                  |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| "I clicked Start quiz; nothing happened. Did it work? Should I click again?"                | API client doesn't surface errors; no spinner; no toast.                                          | Global toast on every quiz API error + button spinner during in-flight POST + Retry button in toast.        |
| "I see 'Generate audio' next to 'Instant on Web Speech'. Do I have to generate to listen?"   | Single primary CTA modelled around Kokoro only; Web Speech path implicit.                         | Two CTAs — primary "Listen" (Web Speech), secondary "Generate MP3 files" (Kokoro modal).                    |
| "What is a quiz here? How long does it take? What do Got it / Partial / Missed mean?"        | Bare form; no orientation copy; no count/duration estimate.                                      | Hero paragraph + inline expectation copy near Start button + empty "0 past sessions" rail.                  |
| "3.6 min — is that how long I'll listen, or how long it generates?"                          | One conflated string in the Generate dialog.                                                     | Three labelled fields: generation, listening, disk.                                                          |
| "0 / 60,000 tokens — what's a token? What's the cap for?"                                    | Raw LLM context budget exposed.                                                                  | Replace with chapter count + reading-time estimate; tooltip the underlying budget.                          |
| "What is 'Spike findings'?"                                                                  | Research-phase block was never copy-edited before shipping.                                      | Rename/remove on Settings → TTS.                                                                            |

### Satisfaction Signals

- After clicking Start quiz that errors: the user sees what failed and can act (Retry). After it succeeds: the question card replaces the form (existing behaviour, out of scope).
- After clicking Listen: the first chapter starts speaking within ~1 second; controls are obvious (play/pause).
- After opening Generate audio: the user knows precisely what they're committing — minutes to generate, minutes to listen, MB on disk — before pressing Generate.
- After landing on the Quiz tab fresh: the user's first read produces no questions for the changelog; they know what to expect.

## Solution Direction

The seven findings break into three coherent solution shapes. **Recommended approach below; see Decisions D1–D3 for the alternatives considered.**

### Shape 1 — Global API-error surfacing (Q-3)

The toast container exists (`AppShell.vue:72`, `ToastContainer.vue`, `ui.ts.showToast()`); the API client (`client.ts:30`) just doesn't push to it on failure. Add a thin wrapper at the API client level that pushes every `ApiError` to the toast store, plus a per-call opt-in for an inline retry-bound error region near the failed action. The quiz `startSession` action gets the inline path; everything else gets the global toast for free.

### Shape 2 — Audio empty-state and Generate-dialog rewrite (A-1, A-3, A-5)

Replace the empty-state component contents in `AudioTab.vue:123-150` with:

```
┌──────────────────────────────────────────────┐
│  Listen to this book                          │  ← H2, verb-led headline (G7)
│  Instant playback via your browser, or        │  ← short subtitle
│  generate MP3s for offline listening.         │
│                                               │
│  ▶ Listen                  ⬇ Generate MP3s    │  ← parallel CTAs
│    (uses your browser)       for offline      │
│                              + scrubbing      │
│                                               │
│  No audio files yet — generate to enable seek/scrub.  ← caption (demoted)
└──────────────────────────────────────────────┘
```

The Generate-audio modal (`GenerateAudioModal.vue:46-47`) replaces the single ambiguous estimate line with three labelled values:

```
~Xmin to generate · ~Ymin to listen · ~ZMB on disk
```

Where:

- **X** is wall-clock generation time, computed for **only the sections that will be generated this click** (delta in the partial-generation case).
- **Y** is total speech duration for the whole-book listening, computed as `sum(section.word_count) ÷ wpm`. `wpm` is an env constant (default `200`) exposed in Settings → TTS for user override (see FR-WPM-CONFIG). Y is whole-book regardless of how many sections are generated, since playback covers the full set.
- **Z** is delta disk usage for the sections being generated this click.

In the empty state (no MP3s yet), all three reflect the whole-book numbers; they're the same as delta. In partial state (some sections already generated), X and Z reflect the delta; Y stays whole-book.

### Shape 3 — Quiz first-visit + scope-picker copy (Q-1, Q-7) and Settings/TTS heading (A-7)

Three small, file-localised copy/structure changes:

- `QuizTab.vue` (or `ScopePicker.vue`) — add a hero block: *"Test your retention with AI-generated questions about this book. We'll generate ~5 questions in under a minute, score Got it / Partial / Missed, and track your tally across sessions."* + inline microcopy near the Start button: *"5 questions · ~30 sec to generate"*.
- `ScopePicker.vue` token-progress rendering — replace `"X / 60,000 tokens"` with a chapter count + a reading-time estimate computed at **~250 words per minute against the section's `content_md` word count** (e.g., `"4 of 12 chapters · ~30 min reading"`). Tooltip the underlying token cap for anyone who wants the technical metric.
- `SpikeFindingsBlock.vue:67` — rename the heading to **"Compare voices"** and clean the dev-only fallback paragraph (`"Run bookcompanion spike tts..."`). KEEP the "Listen to comparison" button — codebase grill confirmed it's user-valuable (A/B-plays the same text on Kokoro and Web Speech back-to-back). When no spike has been run, the fallback should read user-facing copy (e.g., *"Generate audio for any section to enable side-by-side voice comparison."*) instead of a CLI command. (D6 reversed — see Decisions table.)

ASCII diagram of the audio empty-state is in Shape 2 above. Wireframes will live at `frontend/DESIGN.md` references after the wireframes phase.

## User Journeys

### Primary Journey 1 — First-time Quiz (J1)

1. User lands on `/books/:id?tab=quiz` with all sections summarized.
2. User reads the orientation hero — knows what a quiz is, how many questions, ~30 sec wait, Got it / Partial / Missed scoring.
3. User leaves "All summaries" radio selected, presses Start quiz.
4. Spinner appears on the Start button (in-flight indicator).
5. **Happy path:** the first question card replaces the form (Q1 of 5).
6. **Error path (Q-3 fix):** a toast slides into the Notifications region — *"Couldn't start quiz: <reason>. Retry?"* — with a Retry button. The spinner clears; the form returns to the editable state. The user can adjust scope and click Start again, or click Retry in the toast.
7. The lifetime tally on the right rail shows "0 past sessions" while no session has been completed.

### Primary Journey 2 — First-time Audio, instant listen (J2)

1. User lands on `/books/:id?tab=audio` with no audio generated.
2. User reads the verb-led headline "Listen to this book" + subtitle.
3. User clicks **Listen** (the new primary CTA).
4. Web Speech starts speaking the first section's summary within 1 s. The playbar appears at the bottom of the page (existing component, no change).
5. User can pause / scrub / change voice via the existing controls.

### Primary Journey 3 — First-time Audio, generate MP3s (J3)

1. Same landing as J2.
2. User clicks **Generate MP3 files** (secondary CTA).
3. The existing Generate-audio modal opens.
4. User reads the new three-part estimate: *"~3.6 min to generate · ~25 min to listen · ~54 MB on disk"*.
5. User confirms; existing Kokoro generation flow proceeds (out of scope).

### Alternate Journeys

- **J1.alt** — User picks "Specific chapters" instead of "All summaries". The scope picker shows a chapter count + reading-time estimate (Q-7 fix) instead of "0 / 60,000 tokens".
- **J2.alt** — Web Speech is unavailable in the user's browser (rare on modern browsers but possible). The Listen CTA shows a disabled state with a hint (covered by existing voice-availability handling; verify in `/spec`).
- **J3.alt** — User opens Settings → TTS afterward. They see a clean "About this engine" (or no spike block at all), not "Spike findings".

### Error Journeys

- **E1 — Quiz POST fails (any 4xx/5xx).** Global toast + form-restored + Retry button. (Same as J1 step 6.)
- **E2 — Quiz POST succeeds but next-question fetch fails.** Global toast + the question card shows an inline retry button so the user doesn't have to restart the session.
- **E3 — Listen click and Web Speech speak() throws.** Toast + the empty-state returns; user can fall back to Generate.

### Empty States & Edge Cases

| Scenario | Condition | Expected Behavior |
|----------|-----------|-------------------|
| No sections summarized yet | Book exists, summaries pending | Quiz tab shows existing "summaries required" empty state (out of scope; not a top-7 finding) |
| No prior quiz session | Lifetime tally count = 0 | Right rail shows "0 past sessions" + helper copy explaining the tally (G3) |
| 0 chapters selected (Specific scope) | Form submission attempted | Existing "Pick at least one chapter" caption + disabled Start button (out of scope; Q-9 was medium) |
| LLM provider missing entirely | `getLLMStatus().preflight.ok === false` | Existing "no LLM provider" banner (out of scope; not a top-7 finding) |
| Web Speech disabled in the browser | `'speechSynthesis' in window === false` | Listen CTA disabled with hint; Generate remains available |

## Design Decisions

| #  | Decision                                                                                                                                                                                              | Options Considered                                                                                                                                                                                         | Rationale                                                                                                                                                                                                                                                                                |
| -- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1 | **Global API-error toast at the client wrapper level**, with an opt-in inline DIAGNOSTIC region for user-initiated actions (Quiz Start). Toast carries the actionable Retry; inline shows the failure reason + Dismiss only — no double-Retry. Toast lifecycle: sticky for actionable (Retry-bearing); 4 s auto-dismiss for confirmations; dedupe by message within a 5 s window; clear on retry success. Tracks the TanStack Query / SWR / Pinia-Axios convention. | (a) Per-component try/catch in every action that calls the API; (b) Global toast only, no inline; (c) Inline only, no global; (d) **Global + inline-diagnostic (chosen).**                                            | (a) repeats the same code in 30+ places and was clearly skipped here; (b) loses a near-action diagnostic anchor; (c) misses background errors. Hybrid with diagnostic-only inline (resolved in grill loop 2) avoids the two-Retry-button confusion that "global + inline-actionable" would create. (See Research Sources tkdodo, SWR, dev.to refs.) |
| D2 | **CTA labels on the Audio empty state are "Listen" + "Generate MP3 files"**, with subtitles ("uses your browser" / "for offline + scrubbing"). Avoid "Listen now" / "Listen later" framing.              | (a) "Listen now" / "Listen later"; (b) "Stream" / "Download"; (c) "Web Speech" / "Kokoro" (engine names); (d) **"Listen" / "Generate MP3 files" (chosen).**                                                | (a) hides the artifact difference; (b) "Stream" is online-vs-offline framing, not artifact; (c) requires the user to learn engine names. Peer apps (ElevenLabs, Speechify, NaturalReader) frame the second CTA by artifact (Download / Generate / Export), which (d) mirrors.            |
| D3 | **Generate-audio estimate splits into three labelled fields** in one line: "~Xmin to generate · ~Ymin to listen · ~ZMB on disk". X and Z are DELTA (only sections being generated this click); Y is TOTAL (whole-book listening duration, computed as `sum(word_count) ÷ wpm` with `wpm = 200` configurable, see FR-WPM-CONFIG). The dialog also keeps the existing per-content-type checkboxes; X/Y/Z update reactively as checkboxes toggle. | (a) One ambiguous line (status quo); (b) Two-line "Time: X · Size: Y"; (c) **Three-field one-line, delta-X/Z + total-Y (chosen);** (d) Three-line vertical list per content type. | Industry research found no peer that splits all three pre-commit — this is a deliberate differentiator since the user has a real disk-space cost to weigh. (b) drops the listening-duration which is the *value* received. (d) inflates the modal vertically without informational gain. Delta-vs-total split (resolved in grill loop 2) prevents the "~3.6 min to generate" string showing on a partial-state book that finishes in 35 s. |
| D4 | **Replace the quiz scope-picker token progress with a derived "X of N chapters · ~Y min reading" line.** Tooltip the underlying LLM token budget for anyone who wants the technical number.              | (a) Hide the budget entirely; (b) Keep "0 / 60,000 tokens"; (c) **Chapter count + reading-time estimate, tooltip for tokens (chosen).**                                                                    | (a) loses the cap-warning when the user selects too many; (b) is the status quo and unintelligible; (c) gives a decision-anchor (chapters they care about) plus an escape hatch for the technical user.                                                                                  |
| D5 | **Quiz orientation copy lives at the top of the Quiz tab panel, not in a dismissable callout.** It's short — one paragraph + the per-button microcopy.                                                  | (a) Dismissable hero callout (with "don't show again"); (b) Tooltip / "?" icon next to the form; (c) **Always-on hero paragraph (chosen);** (d) Modal on first visit only.                                | (a)/(d) require dismissal state; the user is single-tenant and the form takes the whole panel anyway. (b) buries the orientation. Always-on costs ~3 lines of vertical space and is the simplest correct answer.                                                                          |
| D6 | **The Settings → TTS "Spike findings" block is RENAMED to "Compare voices" with the dev-only fallback paragraph cleaned up.** The "Listen to comparison" A/B button is preserved (it plays the same sample text on Kokoro and Web Speech back-to-back — genuinely user-valuable). | (a) **Rename heading to "Compare voices" + clean fallback (chosen, post-grill);** (b) Remove the block entirely (original choice — reversed); (c) Move the content to a dev-only docs page; (d) Move the comparison button into the engine-picker UI added by FR-ENGINE-PICKER. | Original D6 chose (b) under the assumption the body was research-only. Codebase inspection in grill loop 2 found the "Listen to comparison" button — removing it would delete a useful affordance. (d) is appealing but (a) is lower-risk and ships in the same patch as the heading rename. The dev-only fallback ("Run bookcompanion spike tts...") is replaced with user-facing copy. |

## Functional Requirements (added in grill loop 2)

These FRs were surfaced or sharpened during grill loop 2 and need explicit handles for `/spec` to reference.

| ID | Requirement | Surface | Tied to |
|----|-------------|---------|---------|
| FR-PRE-WARM | On `AudioTab.vue` mount, the component MUST call `speechSynthesis.getVoices()` and await one `voiceschanged` event (or a 500 ms timeout, whichever fires first) before enabling the Listen CTA. This warms the voice list so the first speak() call doesn't pay the async-voice-load cost. | `frontend/src/components/audio/AudioTab.vue` | G2 measurability |
| FR-WPM-CONFIG | TWO related env constants exposed in Settings (resolves MSF S1 wpm asymmetry): `Settings.audio.tts.listen_wpm` (default 200, range 100–400, step 25) drives the listen-time formula `sum(word_count) ÷ listen_wpm`; `Settings.reading.reading_wpm` (default 250, range 100–500, step 25) drives the chapter-picker reading-time estimate (Q-7 fix). Both are independently configurable. The Generate-audio modal's Y estimate and any future per-section listening-duration estimate read from `listen_wpm`. The Quiz scope picker's "X of N chapters · ~Y min reading" string reads from `reading_wpm`. | Settings → TTS panel + Settings → Reading panel; `GenerateAudioModal.vue`; `ScopePicker.vue`; backend env / config | D3 (listen-time formula); Q-7 (reading-time); MSF S1 |
| FR-TOAST-LIFECYCLE | The toast store contract: (a) actionable toasts (any toast with a button) are sticky AND **cannot be user-dismissed** — they clear only on retry-success or replacement by a same-key toast (MSF M1: prevents the single-misclick-removes-recovery edge); (b) confirmation/info toasts auto-dismiss at 4 s and are user-dismissable; (c) toasts dedupe on `message` within a 5 s window — a same-message toast within that window REPLACES the existing one, doesn't stack; (d) calling the action's success path (e.g., the Retry handler completing successfully) clears the originating toast. | `frontend/src/stores/ui.ts` (`showToast` extension) + `ToastContainer.vue` | D1; MSF M1 |
| FR-ENGINE-PICKER | The Audio tab's POPULATED state (after MP3s exist for some/all sections) MUST keep both Listen and Generate CTAs visible. An engine picker rendered as a **segmented control adjacent to the playbar's voice selector** (resolves MSF S3 placement) determines whether Listen plays Web Speech or queues the existing MP3s. **Default rule (resolves MSF S3 surprising-default):** if the book has ≥1 MP3 for the selected scope, default to `mp3`; otherwise default to `web-speech`. User toggles persist for the session via Pinia; cross-session persistence via existing `Settings.audio.tts.engine`. Empty-state copy adapts to "X of Y sections have MP3s" once partial. **Engine switch mid-playback:** stops current playback, resumes from the start of the current section in the new engine (no word-position carryover — explicit non-goal; revisit if user requests). | `AudioTab.vue` (populated-state branch) + playbar | D2; G2 (preserved post-generation); MSF S3 |
| FR-PARTIAL-DELTA | The Generate-audio modal's X (gen time) and Z (disk) values are computed for ONLY the sections that will be generated this click (i.e., not already covered by an MP3). Y is computed for the whole book regardless. Modal labels MUST include the count for clarity ("Generating 3 of 17 sections"). **No overwrite mode in v1** (resolves MSF S4): the modal generates only sections that don't yet have an MP3 for the selected content type. Regenerating an existing MP3 (e.g., after a voice change) is an explicit non-goal — defer to a follow-up feature. | `GenerateAudioModal.vue:46-47, 134` | D3; MSF S4 |
| FR-INLINE-DIAGNOSTIC | The inline error region under Quiz Start (D1's diagnostic surface) shows: (a) the failure reason from `ApiError.message` (or the FR-TOAST-LIFECYCLE fallback string when message is empty/HTML), (b) a Dismiss link. It does NOT carry a Retry button — Retry lives only in the toast (which per FR-TOAST-LIFECYCLE is non-user-dismissable for actionable errors, so the user always has access to Retry). The region is hidden when the form is edited (any input change) or when the toast Retry succeeds. **Mid-session error UX is separate** (see FR-MID-SESSION-RETRY) — the inline-diagnostic-only rule applies to the Start path; mid-session next-question failures use a Retry-bearing inline card affordance with no toast (resolves MSF M2 D1↔E2 contradiction). | `QuizTab.vue` / `ScopePicker.vue` form footer | D1; MSF M2 |
| FR-MID-SESSION-RETRY | When a mid-quiz-session API call fails (e.g., `GET` next question, `POST` self-assessment), the QuestionCard component MUST show an inline error region WITH a Retry button bound to the failed action. No toast is fired (one error surface only, distinct from the Start path). Session state (prior answers, question index) MUST persist across the retry — Retry resumes from the failed step, doesn't restart the session. | `QuizTab.vue` (QuestionCard) | E2; MSF M2 |
| FR-LISTEN-UNAVAILABLE | When `'speechSynthesis' in window === false` OR `getVoices().length === 0` after pre-warm timeout, the Audio empty-state MUST: (a) morph the headline from "Listen to this book" to "Generate MP3s to listen to this book"; (b) render Listen CTA disabled with a tooltip: "Web Speech is unavailable in this browser. Generate MP3 files instead."; (c) keep Generate CTA fully functional. (Resolves MSF M3.) | `AudioTab.vue` empty-state branch | J2.alt; MSF M3 |
| FR-COMPARE-VOICES | Settings → TTS "Compare voices" panel (renamed from "Spike findings") MUST: (a) render with heading text containing no `Spike` substring, (b) keep the `data-testid="listen-comparison"` button mounted and functional regardless of whether any audio has been generated (the button uses `/api/v1/audio/sample` which streams Kokoro on-demand — does not require pre-generated MP3s; resolves MSF S5), (c) replace the dev-only `Run bookcompanion spike tts` fallback paragraph with user-facing copy: "Hear the same sample in both engines. Click below to compare Kokoro and your browser's Web Speech voice side by side." (no chicken-and-egg framing), (d) during A/B playback, mount a transient engine label (e.g., a small chip near the button or a 1-line caption) that names the currently-playing engine — sequence: "Playing Kokoro (af_sarah)…" → "Playing Web Speech…" (resolves MSF M4), (e) sample text SHOULD be the first 1–2 sentences of the current book's first section's content_md when accessed from a book context, falling back to the existing pangram only when invoked from a non-book Settings page (MSF N3 — defer if implementation cost is high). | `frontend/src/components/settings/SpikeFindingsBlock.vue` (rename file as part of /spec optional cleanup) | D6 reversal; G6; MSF M4, S5, N3 |
| FR-Q3-REPRO | `/spec` MUST NOT begin until the `## Backend Defect (Q-3 root cause)` subsection has all four `_TBD_` fields filled with a live repro of `POST /api/v1/quiz-sessions` 500. If the scope assessment shows the fix exceeds the top-7 UX scope, `/spec` MUST pause and re-amend requirements before continuing. | Backend defect repro task | Q-3 |

## Success Metrics

| Metric                                                                       | Baseline (2026-05-10)                                | Target                                                       | Measurement                                                                                        |
| ---------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Silent quiz-error rate                                                       | 100% of `/quiz-sessions` failures are silent         | 0%                                                            | E2E test: stub the route to 500, click Start quiz, assert toast within 1 s + Retry button visible. |
| Time-to-first-listen (instant path)                                          | Unreachable from empty state (single Generate CTA)   | ≤ 1 click + ≤ 1 s of user-perceived latency                   | E2E test: navigate to Audio tab, click Listen, assert `speechSynthesis.speaking === true`.         |
| Quiz orientation comprehension                                               | Bare form, no orientation                            | Hero copy present + count/duration disclosed near Start       | DOM assertion: hero paragraph + microcopy strings exist in the rendered Quiz tab.                  |
| Generate-audio estimate disambiguation                                       | One ambiguous "~3.6 min · ~54 MB" string             | Three labelled fields (`generate`, `listen`, `on disk`)       | DOM assertion: regex finds all three terms in the modal estimate row.                              |
| Token jargon in quiz scope picker                                            | "X / 60,000 tokens" string visible                   | String `tokens` not visible to user; chapter+reading shown    | DOM assertion: no `tokens` substring; chapter+reading regex matches.                                |
| Spike findings heading on Settings → TTS                                     | Heading present                                      | Block absent (removed)                                        | DOM assertion: no `Spike` substring on `/settings/tts`.                                            |
| Audio empty-state hierarchy                                                  | "No audio yet" is H2; instant-listen line is caption | Verb-led H2 ("Listen to this book") + Listen CTA primary      | DOM assertion: H2 text begins with imperative verb; "Listen" CTA has primary-button class.          |

## Research Sources

| Source                                                                                                                                                                  | Type                | Key Takeaway                                                                                                              |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `docs/2026-05-10_quiz-and-audio-design-crit/design-crit/design-crit.md`                                                                                                 | Internal artefact   | Source design-crit; 26 findings, top-7 are this feature's scope.                                                          |
| `frontend/src/components/quiz/QuizTab.vue:133-135` + `quiz/ScopePicker.vue:203-211` + `stores/quizSessions.ts:91-102`                                                    | Existing code       | Quiz Start path; `quizSessions.startSession()` calls API but doesn't push to toast on error.                              |
| `backend/app/api/routes/quiz.py:265-302` + `cli/deps.py:170-182`                                                                                                        | Existing code       | Quiz session POST handler; `_require_service` raises 503 if LLM missing — the live 500 is a separate defect to root-cause. |
| `frontend/src/components/audio/AudioTab.vue:123-150`                                                                                                                    | Existing code       | Audio empty-state panel; single Generate CTA next to the "Instant on Web Speech" copy.                                    |
| `frontend/src/components/audio/GenerateAudioModal.vue:46-47, 134`                                                                                                       | Existing code       | Estimate computation: `minutesText + mbText for totalUnits sections`.                                                     |
| `frontend/src/components/settings/SettingsTtsPanel.vue:131-150` + `SpikeFindingsBlock.vue:67`                                                                           | Existing code       | "Spike findings" heading mounted via `<SpikeFindingsBlock />`.                                                             |
| `frontend/src/components/app/AppShell.vue:72` + `common/ToastContainer.vue` + `stores/ui.ts:33-44`                                                                      | Existing code       | Toast region exists, `showToast()` is wired only into `recordSelfAssessment` — not into start-session error path.         |
| `frontend/src/api/client.ts:3-41`                                                                                                                                        | Existing code       | `ApiError` class + `handleResponse()` — no global onError hook.                                                            |
| `docs/specs/2026-05-03-summary-and-audio-ux-fixes-spec.md` D1, D2, FR-08/09, FR-28                                                                                       | Prior pmos artefact | Established TTS-settings persistence + global .btn-primary contract; this feature must not contradict.                    |
| https://elevenreader.io/ + https://speechify.com/blog/how-to-download-audio-or-mp3-files-with-speechify/ + https://blog.naturalreaders.com/...partnership-with-elevenlabs | Industry            | Audiobook/TTS apps frame the deferred CTA by *artifact* (Download/Export/Generate), not by *time*.                        |
| https://github.com/santinic/audiblez                                                                                                                                     | Industry            | EPUB-to-audiobook tooling shows duration + final size; no peer splits all three (gen / listen / disk) pre-commit.         |
| https://quizlet.com/ai-practice-test-generator + https://www.remnote.com/feature/ai-quiz-maker                                                                          | Industry            | AI quiz peers expose count + types as *pre-generation inputs*; latency rarely quoted.                                     |
| https://docs.readwise.io/changelog (Quiz mode in Skills)                                                                                                                | Industry            | Quizzes built on existing user content typically don't onboard from a blank state — they gate on content existing.        |
| https://tkdodo.eu/blog/react-query-error-handling                                                                                                                        | Industry            | Hybrid global-toast + inline-component handler is the canonical SPA pattern for actionable errors.                       |
| https://swr.vercel.app/docs/error-handling                                                                                                                               | Industry            | SWR: `onError` for toasts, `onErrorRetry` for backoff, `mutate()` for inline retry.                                       |
| https://obeydi-abbassi.me/blog/vue3-axios-pinia-rest-client/                                                                                                              | Industry            | Vue 3 + Pinia + Axios: interceptor → toast store; re-reject so component renders inline retry.                            |

## Open Questions

| #     | Question                                                                                                                                                                                                                       |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OQ-1  | What's the canonical Quiz orientation paragraph wording? Draft: *"Test your retention with AI-generated questions about this book. We'll generate ~5 questions in under a minute, score Got it / Partial / Missed, and track your tally across sessions."* — confirm or rewrite. |
| OQ-2  | What's the exact CTA labelling for the audio empty state? Draft above is *"Listen"* (primary) + *"Generate MP3 files"* (secondary). Confirm or alter — peer apps use "Play"/"Listen" interchangeably for primary; "Generate / Download / Export" all viable for secondary. |
| OQ-3  | ✅ RESOLVED (grill loop 2) — Pre-gen formula `sum(word_count) ÷ wpm` with `wpm = 200` (configurable via Settings → TTS, see FR-WPM-CONFIG). Whole-book Y; post-gen MP3 durations not used. |
| OQ-4  | What's the right number of quiz questions for the orientation copy? Currently the backend generates a fixed N (or LLM-decided?) — confirm in `/spec` before finalising the user-facing "~5 questions" string. **MSF S2 hard gate:** /spec MUST inspect `backend/app/services/quiz_session_service.py` (or equivalent) for the actual N before hero copy is committed. If N is dynamic, copy must reflect range ("4–6 questions") or rewrite to remove the count. |
| OQ-5  | ✅ RESOLVED (grill loop 2) — Inline region is DIAGNOSTIC-ONLY (no Retry; that's in the toast). Placement under the Start button. See FR-INLINE-DIAGNOSTIC. |
| OQ-6  | ✅ RESOLVED from code (grill loop 2) — Block contains a user-valuable "Listen to comparison" A/B button. D6 REVERSED to "rename heading to 'Compare voices' + clean dev-only fallback; preserve comparison button." See FR-COMPARE-VOICES. |
| OQ-7  | When `ApiError.message` from the quiz endpoints is empty or contains an HTML body (e.g., uvicorn's default 500 page), what fallback string should the toast show? Draft: *"Couldn't start quiz — the server returned an unexpected error. Retry?"* Confirm or rewrite during `/spec`. Applies to all quiz endpoints, not just `start_session`. |

---

## Review Log

| Loop | Findings | Changes Made                                                                                                                                                                                                                              |
| ---- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | 7 surfaced (4 + 3 across two AskUserQuestion batches). 5 fixed, 2 added as OQs. | STRUCT-1 fixed (added Finding-ID legend table). CRIT-1 → OQ-7 (toast fallback copy deferred to /spec). CRIT-2 fixed (G2 loosened to ≤2 s first / ≤1 s subsequent). CRIT-5 fixed (added "no parallel Listen+Generate" non-goal). CRIT-7 fixed (pinned 250 wpm formula in Solution Direction Shape 3). POLISH-1 skipped (Goals/Friction lenses kept separate by intent). User confirmed gate-4 terminal exit. |
| 2 (grill) | 8 questions asked (standard depth); 0 deferred; 1 resolved from code. | Q1 (Q-3 root cause) → added `## Backend Defect` subsection + FR-Q3-REPRO. Q2 (listen-time formula) → pinned `wpm=200` configurable; added FR-WPM-CONFIG; updated D3 + Solution Shape 2. Q3 (cold-start) → added FR-PRE-WARM; reworded G2. Q4 (toast lifecycle) → added FR-TOAST-LIFECYCLE; sharpened D1. Q5 (populated audio state) → added FR-ENGINE-PICKER (new gap not in OQs). Q6 (partial-state estimate) → added FR-PARTIAL-DELTA; updated D3. Q7 (toast vs inline retry) → added FR-INLINE-DIAGNOSTIC; sharpened D1; resolved OQ-5. Q8 (D6 reversal from code) → flipped D6 to RENAME; added FR-COMPARE-VOICES; updated G6 measurement; resolved OQ-6. Net: 7 doc gaps applied, 3 OQs resolved (3, 5, 6), 4 OQs remain (1, 2, 4, 7). |
| 3 (MSF) | 14 findings (4 Must, 6 Should, 4 Nice) across 12 journeys × 1 persona × 2 scenarios. Must + Should applied as FR amendments / new FRs. Nice deferred to `msf-findings.md` for follow-up. | M1 → FR-TOAST-LIFECYCLE: actionable-error toasts non-user-dismissable. M2 → added FR-MID-SESSION-RETRY; sharpened FR-INLINE-DIAGNOSTIC scope to Start path only. M3 → added FR-LISTEN-UNAVAILABLE. M4 → extended FR-COMPARE-VOICES with engine label during A/B. S1 → split FR-WPM-CONFIG into `listen_wpm` (200) + `reading_wpm` (250). S2 → hard-gate added to OQ-4 (backend N inspection before hero copy). S3 → FR-ENGINE-PICKER segmented-control placement + default rule (mp3 if exists). S4 → FR-PARTIAL-DELTA explicit no-overwrite-mode non-goal. S5 → FR-COMPARE-VOICES fallback copy rewritten (no chicken-and-egg). S6 → G2 testing note added (perceived-latency gap). N1–N4 deferred to msf-findings.md. |

---

**For UX friction analysis, run `/msf-req` after this doc is committed.** ✅ Done — see `msf-findings.md` adjacent. Loop 3 absorbed Must + Should; Nice items remain in findings doc for follow-up.
