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
**Status:** Approved (post-Phase-5 review)
**Tier:** 3 — Feature
**Mode:** interactive
**Open Questions:** 7

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
- Settings → TTS still carries a "Spike findings" research block left over from the same 2026-05-03 spec's discovery phase; it never had a copy edit before users saw it.

## Goals & Non-Goals

> Goals are observable user outcomes; engineering acceptance criteria belong in `/spec`.

### Goals

- **G1 — Errors are visible.** When `POST /quiz-sessions` (or any quiz API call) fails, the user sees a toast within 1 s of the click, with the failure reason and a Retry button — measured by: zero silent-fail console lines on the Quiz tab.
- **G2 — Two real listening paths.** A new Audio user can either (a) press Play and hear the book within 1 click via Web Speech, or (b) press a separate Generate CTA and produce MP3s — measured by: one click from Audio tab to first audible word on Web Speech, with `speechSynthesis.speaking === true` within ≤ 2 s on the first chapter and ≤ 1 s on subsequent chapters (loosened from a flat 1 s to absorb the cold-start voice load that Chrome and Safari exhibit).
- **G3 — Quiz is self-explanatory on first visit.** A user who has never read the changelog can read the Quiz tab and know what a quiz is, how many questions to expect, how long it will take, and what the lifetime tally tracks — measured by: orientation copy present + ≥1 explicit count/duration estimate near the Start button.
- **G4 — Generate-audio dialog discloses three estimates separately.** Generation time, listening duration, and disk size are three distinct labelled fields, not one ambiguous string — measured by: regex test against the dialog finding all three terms.
- **G5 — Token jargon is gone from the quiz scope picker.** A user-facing budget metric replaces "0 / 60,000 tokens" — measured by: no string `tokens` visible to the user on the Quiz tab.
- **G6 — Settings/TTS reads as user copy, not research notes.** The "Spike findings" heading is renamed or removed — measured by: no string `Spike` visible on Settings → TTS.
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

Where X is wall-clock generation, Y is total speech duration, Z is total file size.

### Shape 3 — Quiz first-visit + scope-picker copy (Q-1, Q-7) and Settings/TTS heading (A-7)

Three small, file-localised copy/structure changes:

- `QuizTab.vue` (or `ScopePicker.vue`) — add a hero block: *"Test your retention with AI-generated questions about this book. We'll generate ~5 questions in under a minute, score Got it / Partial / Missed, and track your tally across sessions."* + inline microcopy near the Start button: *"5 questions · ~30 sec to generate"*.
- `ScopePicker.vue` token-progress rendering — replace `"X / 60,000 tokens"` with a chapter count + a reading-time estimate computed at **~250 words per minute against the section's `content_md` word count** (e.g., `"4 of 12 chapters · ~30 min reading"`). Tooltip the underlying token cap for anyone who wants the technical metric.
- `SpikeFindingsBlock.vue:67` — rename the heading to "About this engine" or remove the entire block (depending on whether the body content is still useful to ship; see Open Question OQ-6).

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
| D1 | **Global API-error toast at the client wrapper level**, with an opt-in inline error region for user-initiated actions (Quiz Start). Tracks the TanStack Query / SWR / Pinia-Axios convention.            | (a) Per-component try/catch in every action that calls the API; (b) Global toast only, no inline; (c) Inline only, no global; (d) **Global + inline (chosen).**                                            | (a) repeats the same code in 30+ places and was clearly skipped here; (b) loses the actionable Retry next to the failure; (c) misses background errors. Hybrid is the durable convention (see Research Sources tkdodo, SWR, dev.to refs).                                                |
| D2 | **CTA labels on the Audio empty state are "Listen" + "Generate MP3 files"**, with subtitles ("uses your browser" / "for offline + scrubbing"). Avoid "Listen now" / "Listen later" framing.              | (a) "Listen now" / "Listen later"; (b) "Stream" / "Download"; (c) "Web Speech" / "Kokoro" (engine names); (d) **"Listen" / "Generate MP3 files" (chosen).**                                                | (a) hides the artifact difference; (b) "Stream" is online-vs-offline framing, not artifact; (c) requires the user to learn engine names. Peer apps (ElevenLabs, Speechify, NaturalReader) frame the second CTA by artifact (Download / Generate / Export), which (d) mirrors.            |
| D3 | **Generate-audio estimate splits into three labelled fields** in one line: "~Xmin to generate · ~Ymin to listen · ~ZMB on disk". The dialog also keeps the existing per-content-type checkboxes.        | (a) One ambiguous line (status quo); (b) Two-line "Time: X · Size: Y"; (c) **Three-field one-line (chosen);** (d) Three-line vertical list per content type.                                              | Industry research found no peer that splits all three pre-commit — this is a deliberate differentiator since the user has a real disk-space cost to weigh. (b) drops the listening-duration which is the *value* received. (d) inflates the modal vertically without informational gain. |
| D4 | **Replace the quiz scope-picker token progress with a derived "X of N chapters · ~Y min reading" line.** Tooltip the underlying LLM token budget for anyone who wants the technical number.              | (a) Hide the budget entirely; (b) Keep "0 / 60,000 tokens"; (c) **Chapter count + reading-time estimate, tooltip for tokens (chosen).**                                                                    | (a) loses the cap-warning when the user selects too many; (b) is the status quo and unintelligible; (c) gives a decision-anchor (chapters they care about) plus an escape hatch for the technical user.                                                                                  |
| D5 | **Quiz orientation copy lives at the top of the Quiz tab panel, not in a dismissable callout.** It's short — one paragraph + the per-button microcopy.                                                  | (a) Dismissable hero callout (with "don't show again"); (b) Tooltip / "?" icon next to the form; (c) **Always-on hero paragraph (chosen);** (d) Modal on first visit only.                                | (a)/(d) require dismissal state; the user is single-tenant and the form takes the whole panel anyway. (b) buries the orientation. Always-on costs ~3 lines of vertical space and is the simplest correct answer.                                                                          |
| D6 | **The Settings → TTS "Spike findings" block is removed entirely** rather than renamed. The body content was a research dump; nothing in it is required for the user to make TTS settings decisions.    | (a) Rename heading to "About this engine"; (b) **Remove the block (chosen);** (c) Move the content to a dev-only docs page.                                                                                | (a) keeps the same problem (no decision tied to it); (b) is the cleanest. (c) is overengineering for content that no longer serves a purpose. See OQ-6 for confirmation.                                                                                                                  |

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
| OQ-3  | What playback estimate formula should the dialog use for "~Y min to listen"? Per-section average ~150 wpm × token-to-word conversion? Or take the actual generated MP3 durations once available and pre-compute on Section model? Spec phase decides. |
| OQ-4  | What's the right number of quiz questions for the orientation copy? Currently the backend generates a fixed N (or LLM-decided?) — confirm in `/spec` before finalising the user-facing "~5 questions" string.                |
| OQ-5  | Inline retry-bound error region: should it appear *under* the Start button (replacing the form's bottom margin) or *above* (replacing the orientation copy)? Either works; pick during wireframes.                            |
| OQ-6  | "Spike findings" block on Settings → TTS — does the body content carry any user-actionable info, or is it pure research notes? D6 chose remove; if the body has user value (e.g., browser-voice availability table), rename instead. |
| OQ-7  | When `ApiError.message` from the quiz endpoints is empty or contains an HTML body (e.g., uvicorn's default 500 page), what fallback string should the toast show? Draft: *"Couldn't start quiz — the server returned an unexpected error. Retry?"* Confirm or rewrite during `/spec`. Applies to all quiz endpoints, not just `start_session`. |

---

## Review Log

| Loop | Findings | Changes Made                                                                                                                                                                                                                              |
| ---- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | 7 surfaced (4 + 3 across two AskUserQuestion batches). 5 fixed, 2 added as OQs. | STRUCT-1 fixed (added Finding-ID legend table). CRIT-1 → OQ-7 (toast fallback copy deferred to /spec). CRIT-2 fixed (G2 loosened to ≤2 s first / ≤1 s subsequent). CRIT-5 fixed (added "no parallel Listen+Generate" non-goal). CRIT-7 fixed (pinned 250 wpm formula in Solution Direction Shape 3). POLISH-1 skipped (Goals/Friction lenses kept separate by intent). User confirmed gate-4 terminal exit. |

---

**For UX friction analysis, run `/msf-req` after this doc is committed.**
