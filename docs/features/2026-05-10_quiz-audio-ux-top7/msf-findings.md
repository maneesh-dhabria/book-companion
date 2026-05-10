# MSF Findings — Quiz & Audio UX Top-7 Fixes

**Date:** 2026-05-10
**Source doc:** `01_requirements.md` (Tier 3 — Approved post-grill loop 2)
**Mode:** /msf-req (text-only; no PSYCH scoring)
**Scope:** 1 persona × 2 scenarios × 12 journeys (9 documented + 3 implicit from grill-loop-2 FRs)
**Outcome:** 14 actionable findings (4 Must, 6 Should, 4 Nice)

---

## Persona

| ID | Name | Context | Scenarios |
|----|------|---------|-----------|
| P1 | Self-hosted technical reader | Single user; runs `bookcompanion serve` locally; just generated section/book summaries for a non-fiction title | (A) **First-time** — opening Quiz or Audio tab on this book for the first time. (B) **Returning** — coming back after partial use (some MP3s generated, prior quiz session etc.) |

> The doc explicitly scopes to one user. Splitting into A/B scenarios keeps the matrix meaningful since the new grill FRs (engine picker, partial-delta, compare voices) address Scenario B.

---

## Journeys

| ID | Journey | Source | Scenario |
|----|---------|--------|----------|
| J1 | First-time Quiz — All Summaries scope, happy path | Doc §J1 | A |
| J2 | First-time Audio — instant Listen via Web Speech | Doc §J2 | A |
| J3 | First-time Audio — Generate MP3s via dialog | Doc §J3 | A |
| J1.alt | Quiz with Specific Chapters scope (chapter+reading metric) | Doc §J1.alt | A |
| J2.alt | Listen unavailable (Web Speech disabled) | Doc §J2.alt | A |
| J3.alt | Settings → TTS post-action ("Compare voices" panel) | Doc §J3.alt | A or B |
| E1 | Quiz POST fails (Q-3 path) — toast + inline diagnostic + form-restored | Doc §E1 | A |
| E2 | Quiz next-question fetch fails mid-session — inline retry on card | Doc §E2 | A or B |
| E3 | Web Speech `speak()` throws on Listen click | Doc §E3 | A |
| **J4** | Returning user opens populated Audio tab — engine picker | Implicit (FR-ENGINE-PICKER) | B |
| **J5** | Returning user reopens Generate modal in partial state — delta vs total | Implicit (FR-PARTIAL-DELTA) | B |
| **J6** | Settings → TTS "Compare voices" — A/B engine sample | Implicit (FR-COMPARE-VOICES) | A or B |

---

## M/F/S Matrix

### J1 — First-time Quiz (All Summaries, happy path)

**Motivation**
- *Job:* "I read the book; how much stuck?" — self-test against summaries.
- *Importance:* moderate — non-blocking but reinforces trust in Book Companion as a reading tool.
- *Pull:* hero copy ("Test your retention…") promises a 5-question, ~30 sec experience — lightweight commitment.

**Friction**
- The "~5 questions" string is a placeholder until `/spec` confirms the backend's actual N (OQ-4). If backend generates 4 or 7, hero copy lies on first interaction.
- Hero paragraph is permanent (D5 — always-on, not dismissable). On 5th visit it's noise, not orientation. Acceptable for v1 but watch for habituation.
- "Got it / Partial / Missed" terms appear in hero copy without yet being shown contextually — the user reads them abstractly before seeing them attached to a question.

**Satisfaction**
- First question card replaces form within ~2 sec → user sees the experience matches the orientation copy → trust earned.
- Lifetime tally rail shows "0 past sessions" with helper copy — a clear "you're at the start" signal.

---

### J2 — First-time Audio, instant Listen via Web Speech

**Motivation**
- *Job:* "Listen to the summary while doing chores" — opportunistic, low-commitment.
- *Pull:* verb-led headline "Listen to this book" + parallel CTAs make Listen the obvious zero-cost first action.
- *Importance:* moderate — but the empty-state's prior unreachability of the instant path eroded trust; this is the recovery story.

**Friction**
- **FR-PRE-WARM is best-effort.** On Chrome/Safari, `voiceschanged` can fire >500 ms after mount on cold tabs. The 500 ms timeout fallback in FR-PRE-WARM means the first speak() may still hit a partially-loaded voice list — user picks default voice, not the saved Settings voice.
- **G2 metric is `speechSynthesis.speaking === true`** — not "audible word." User-perceived latency includes the delay between speaking=true and the first phoneme rendering through the audio device. On macOS Safari this is reliable; on Chrome it can lag 200–400 ms.
- **No CTA microcopy on the listen-time impact.** User clicks Listen and doesn't know whether they're committing to 30 seconds or 30 minutes — chapter selection / scrubbing affordances aren't introduced from the empty state.

**Satisfaction**
- Within ~1 click + ~2 sec the user hears the first words → the "instant" promise lands → first impression validates the rewrite.
- Existing playbar appears at bottom; pause/scrub/voice change discoverable from there → continuity with audiobook conventions.

---

### J3 — First-time Audio, Generate MP3s via dialog

**Motivation**
- *Job:* "Make a portable MP3 set I can play offline / scrub / resume."
- *Pull:* secondary CTA labeled "Generate MP3 files" — the artifact is named in the button.
- *Importance:* high commitment moment — generation costs minutes of compute + ~50 MB disk; the 3-field estimate is the trust handshake.

**Friction**
- **The 3-field estimate is dense for a first-time reader.** "~3.6 min to generate · ~25 min to listen · ~54 MB on disk" packs three quantities; no leading visual hierarchy distinguishes the *cost* (X, Z) from the *value received* (Y).
- **`wpm = 200` default is hardcoded for a US-English non-fiction reading pace.** If a section is short (a glossary entry, a footnote chapter), Y over-estimates listening time (people listen to short sections faster). Doc doesn't address per-section variability.
- **Per-content-type checkboxes update X/Y/Z reactively** (per FR-PARTIAL-DELTA), but the reactivity isn't shown in the doc's mockup. User may not realise toggling changes the estimate until they try it.

**Satisfaction**
- Three labelled values let the user form a clear mental model before clicking Generate → the "no surprises" satisfaction signal.
- After confirm, existing Kokoro flow proceeds → continuity with the prior shipped feature.

---

### J1.alt — Quiz with Specific Chapters scope

**Motivation**
- *Job:* "Drill the chapters I just read, not the whole book."
- *Pull:* chapter+reading-time metric ("4 of 12 chapters · ~30 min reading") replaces the opaque token bar — the user now has a decision anchor.

**Friction**
- **Reading-time uses 250 wpm pinned in requirements (review loop 1)**, BUT listening-time uses configurable 200 wpm (FR-WPM-CONFIG). **Asymmetry:** if the user adjusts wpm in Settings expecting both to update, only listen-time changes. Reading-time stays at 250.
- **Tooltip on the underlying token cap** (D4) is invisible until hovered — for a technical user this is fine, but it raises the bar for a casual return.
- The metric phrase "X of N chapters" is plural-ambiguous when X = 1 ("1 of 12 chapter" wrong vs "1 of 12 chapters" correct). Doc doesn't pin the i18n string template.

**Satisfaction**
- Decision-anchor lands: user picks chapters they care about, sees "~30 min reading" → confident the quiz matches their slot.

---

### J2.alt — Listen unavailable (Web Speech disabled)

**Motivation**
- *Job:* same as J2 — user came for instant playback.
- *Pull:* abruptly redirected to Generate.

**Friction**
- **Listen CTA disabled with a hint** — but the hint copy isn't specified. "Web Speech unavailable in this browser" is engineering language; the user may not know what to do.
- **Verb-led headline still says "Listen to this book"** — the heading promises something the page now can't deliver. Should the empty-state morph the headline when Listen is disabled?
- **Generate becomes the ONLY listening path** — but Generate has a per-click cost. The user's intent was zero-cost ad-hoc playback; now they must commit to ~3.6 min generation.

**Satisfaction**
- (None directly — this is a fallback journey. The implicit satisfaction is "at least Generate still works.")

---

### J3.alt — Settings → TTS post-action

**Motivation**
- *Job:* "I just used Listen / Generate; let me see what's behind this."
- *Pull:* curiosity, not a primary use case.

**Friction**
- **"Compare voices" panel discoverability is poor.** The user came from Audio tab; they navigate to Settings → TTS panel; they see the new heading. But there's no in-line "Compare voices" affordance from AudioTab itself — discovery requires Settings depth navigation.
- **The fallback copy** ("Generate audio for any section to enable side-by-side voice comparison") is a chicken-and-egg trap if user lands here BEFORE generating. They came to compare voices to *decide* whether to generate — and the panel says "generate first."

**Satisfaction**
- After generation, the comparison button works → user A/B-tests Kokoro vs Web Speech → makes informed engine choice → satisfaction signal is "this is the Settings page for this feature, not a research dump."

---

### E1 — Quiz POST fails (Q-3)

**Motivation**
- *Job:* same as J1 — user clicked Start expecting a quiz.
- *Pull eroded* by the failure; restoration depends on the toast + inline diagnostic.

**Friction**
- **Two error surfaces (toast + inline) require the user to mentally connect them.** The inline says the reason; the toast has the Retry. If the toast auto-positions where it occludes the inline (or vice versa), the connection is lost.
- **Toast Retry is the ONLY actionable affordance** (per FR-INLINE-DIAGNOSTIC). If the user dismisses the toast (even accidentally — clicking the X), they lose Retry. Inline diagnostic has only Dismiss. **The user is one misclick away from no-Retry.**
- **No "always show Retry inline as well" override.** If the toast fades from peripheral vision while the user is reading the diagnostic, they have to click Start again from scratch (form-restored).
- **Toast fallback string when ApiError.message is empty/HTML (OQ-7)** — still deferred to /spec. If the live 500 returns uvicorn's HTML 500 page, the user sees a wall of HTML in the toast unless the fallback lands.

**Satisfaction**
- If retry succeeds → toast clears (per FR-TOAST-LIFECYCLE) → user gets "the system noticed and recovered" satisfaction. **This is the trust-restoration moment Q-3 was costing.**

---

### E2 — Quiz next-question fetch fails mid-session

**Motivation**
- *Job:* "Finish this quiz session" — user is mid-flow, has already invested clicks.
- *Pull:* high — abandoning loses progress on the lifetime tally.

**Friction**
- **The doc says "inline retry button so the user doesn't have to restart the session"** — but FR-INLINE-DIAGNOSTIC scopes inline-diagnostic-only to the Start path. Is mid-session inline retry a separate affordance (with Retry) or a different flavor? Inconsistent: D1 says inline-diagnostic-only; E2 says inline-with-retry.
- **No specification of session state preservation** — if next-question fails, does the user's prior answers persist, or does Retry restart from Q1?

**Satisfaction**
- Inline retry on the question card → user keeps progress → mid-session resilience.

---

### E3 — Web Speech speak() throws on Listen click

**Motivation**
- *Job:* same as J2.
- *Pull eroded* abruptly mid-action.

**Friction**
- **Empty-state returns** but the user just initiated playback — the "back to chooser" experience is jarring. No specification of what error message appears (toast? inline? both?).
- **Browser-side speak() failures are usually transient** (OS audio device issue, locale mismatch). User clicks Listen again — does it just work? Or did the error close the voice list pre-warm window? Unclear.

**Satisfaction**
- (None directly; degrades to J2.alt or J3 fallback path.)

---

### J4 — Returning user, populated Audio tab (engine picker)

**Motivation**
- *Job:* "Resume listening on a book I've partially generated."
- *Pull:* engine picker decides whether to use Web Speech (instant, voice quality lower) or queued MP3s (offline, scrubbable).

**Friction**
- **Engine picker placement is unspecified.** Radio? Segmented control? Where on the tab? Doc says "in AudioTab.vue's populated-state branch" but no layout. /spec or wireframes will pick.
- **Default engine on first-populated open** — does the picker default to Web Speech (existing default) or MP3s (the asset the user explicitly generated)? Surprising-default risk.
- **"X of Y sections have MP3s" copy** — what does Listen (Web Speech) do for the missing sections? Does it concatenate the unmissed sections' content_md? Out-of-scope per the empty-state-only spec? Doc doesn't say.
- **No mention of switching engines mid-playback.** If user is mid-MP3 and toggles to Web Speech, does playback restart? Resume from the current section's word count?

**Satisfaction**
- Engine choice visible → user feels in control of the dual-engine system → satisfies the "I generated MP3s for a reason" intuition.

---

### J5 — Returning user, partial-state Generate modal

**Motivation**
- *Job:* "Generate the missing sections" or "regenerate a section I'm not happy with."
- *Pull:* delta semantics promise a focused commit.

**Friction**
- **Delta is computed per-checkbox, not per-section.** If user checks "Section summaries" and 14 of 17 sections already have MP3s, X reads "~30 sec to generate" (delta). But what if user wants to regenerate ALL section summaries (overwrite existing)? Doc doesn't address overwrite mode.
- **Y stays whole-book** — but if a user is regenerating only one section (because Kokoro voice changed), Y of "~25 min to listen" feels disconnected from "~30 sec to generate." Delta-X paired with total-Y reads as inconsistent units even if technically correct.
- **Section-level granularity in the modal** — currently the dialog has per-content-type checkboxes (book summary, section summaries, annotations, content). The per-section selection isn't a checkbox — user generates whole types. So "regenerate section 5 only" isn't a supported workflow. Doc doesn't address this gap.

**Satisfaction**
- Delta numbers prevent the "estimate said 3.6 min, actually finished in 35 sec" confusion → user trusts the modal.

---

### J6 — Settings → TTS Compare voices

**Motivation**
- *Job:* "Hear the engine difference before committing to one."
- *Pull:* A/B button is concrete, low-cost.

**Friction**
- **Sample text is hardcoded** — `"The quick brown fox jumps over the lazy dog, and learning never stops."` That's not a non-fiction summary. The comparison doesn't reflect what the user will actually hear.
- **Sequencing of A/B**: button calls Kokoro `/api/v1/audio/sample` (HTTP), waits for blob, plays, then triggers Web Speech `speak()`. If Kokoro is slow / fails, Web Speech still plays — user gets only one engine in the comparison without realising.
- **No engine label during playback** — user hears voice 1, then voice 2, but no caption says "this is Kokoro" / "this is Web Speech." Required to know which is which.

**Satisfaction**
- After A/B → user has a concrete preference signal → can set engine in TTSConfig → satisfies the "I want to choose, not be auto-defaulted" itch.

---

## Recommendations

> **Severity:** Must (gate /spec), Should (track in /spec), Nice (defer to follow-up feature).

### Must

| # | Finding | Source journey | Action | Effort |
|---|---------|---------------|--------|--------|
| M1 | **Toast Retry is the only actionable affordance — single dismissal removes the recovery path.** Add an "always-show Retry inline as well" override OR extend the toast's sticky behavior to disable the dismiss-X for actionable error toasts. | E1 | Update FR-TOAST-LIFECYCLE: actionable-error toasts CANNOT be user-dismissed; they clear only on retry-success or replacement. OR extend FR-INLINE-DIAGNOSTIC: inline region carries Retry as a secondary, deduped action with the toast. | S |
| M2 | **D1 / E2 contradiction on inline retry.** D1 says inline-diagnostic-only; E2 says inline-retry-on-card. /spec must resolve before implementation — pick one rule and apply consistently. | E2 | Resolve in /spec: explicit FR carving E2's mid-session inline retry as a SEPARATE affordance from the Quiz-Start inline-diagnostic. Document the rule: "diagnostic-only when toast is the canonical action; inline-with-retry when no toast (mid-session card UX)." | S |
| M3 | **J2.alt: Listen-disabled state has no specified hint copy or headline morph.** Empty-state headline still says "Listen to this book" when Listen is unavailable — it lies. | J2.alt | Add FR-LISTEN-UNAVAILABLE: when `'speechSynthesis' in window === false`, headline morphs to "Generate MP3s to listen to this book" and the disabled Listen CTA carries a tooltip ("Web Speech is unavailable in this browser. Generate MP3 files instead."). | S |
| M4 | **J6 / FR-COMPARE-VOICES: no engine label during A/B playback.** User hears 2 voices, no caption identifies which is Kokoro vs Web Speech — comparison is unsignposted. | J6 | Extend FR-COMPARE-VOICES: during A/B playback, mount a transient label (toast or inline text) that names the engine currently playing. Sequence: "Playing Kokoro (af_sarah)…" → "Playing Web Speech (default voice)…" | S |

### Should

| # | Finding | Source journey | Action | Effort |
|---|---------|---------------|--------|--------|
| S1 | **wpm asymmetry**: listen-time configurable (FR-WPM-CONFIG, default 200), reading-time pinned at 250. Settings change won't affect the chapter-picker reading metric. | J1.alt | Either (a) extend FR-WPM-CONFIG with a `reading_wpm` companion (default 250) OR (b) pin both to one constant in /spec and document the choice. | S |
| S2 | **Hero copy "~5 questions" is a placeholder pending OQ-4.** If backend N is not 5, copy lies on first interaction. | J1 | /spec MUST resolve OQ-4 before final hero copy is committed. Inspect `backend/app/services/quiz_session_service.py` for the actual N. If N is dynamic, copy must reflect range ("4–6 questions") or rewrite to remove the count. | XS |
| S3 | **Engine picker default + placement unspecified for J4.** Surprising-default risk if user generated MP3s but picker defaults to Web Speech. | J4 | /spec or wireframes pin: (i) default engine = `mp3` IF book has ≥1 MP3 ELSE `web-speech`; (ii) picker as segmented control adjacent to the playbar's voice selector. | M |
| S4 | **J5 partial-state / overwrite mode unspecified.** User can't regenerate existing sections via the modal. | J5 | If overwrite is in scope: add FR-REGENERATE-OVERWRITE (checkbox: "Replace existing MP3s"). If out of scope: explicit non-goal. /spec decides. | M |
| S5 | **J3.alt fallback text creates chicken-and-egg if user visits Compare voices BEFORE generating.** | J3.alt | Tweak FR-COMPARE-VOICES fallback copy to acknowledge the pre-generation case: "Hear the same sample in both engines below" with the comparison button still functional (it doesn't need a generated MP3 — sample uses `/api/v1/audio/sample` which streams Kokoro on demand). | XS |
| S6 | **G2 metric `speechSynthesis.speaking === true` ≠ user-perceived latency.** On Chrome the gap to first-phoneme is 200–400 ms. | J2 | Either (a) accept and document the metric vs perceived gap in spec testing notes, OR (b) add a Web Audio API listener for the first audible buffer to tighten the metric. (a) is recommended unless first-phoneme tightness becomes a complaint. | S |

### Nice

| # | Finding | Source journey | Action | Effort |
|---|---------|---------------|--------|--------|
| N1 | Hero paragraph permanence (D5) becomes noise on the 5th visit. | J1 | If habituation is observed: switch to a dismiss-once pattern. v1 ships always-on; revisit if user feedback signals fatigue. | S |
| N2 | Plural ambiguity: "1 of 12 chapter" vs "1 of 12 chapters". | J1.alt | Use Intl.PluralRules or a simple `n === 1 ? 'chapter' : 'chapters'` ternary. | XS |
| N3 | Compare voices sample text is a pangram, not a non-fiction summary. | J6 | Use the first 1–2 sentences of the book's first section's content_md (or a hardcoded "from your library" sentence) so the comparison reflects actual usage. | S |
| N4 | E3 (speak() throws) — no specified error UX or pre-warm side-effect. | E3 | /spec should specify: speak()-throw triggers toast + retains pre-warmed voice list (no re-mount required for second click). | S |

---

## Process notes

- Single persona, 12 journeys (9 documented + 3 implicit). 14 findings across Must/Should/Nice; no padded items. The grill loop 2 already absorbed the high-leverage UX gaps; this MSF pass finds residual gaps the grill missed (toast-dismiss-removes-Retry edge, inline-vs-card retry contradiction, Listen-disabled headline morph, engine label during A/B).
- Heavy dependency on /spec: 4 of 4 Must items + 4 of 6 Should items resolve as new FRs or FR amendments in /spec. /msf-req does not touch the requirements doc; the user folds these into a manual review-loop-3 edit on `01_requirements.md`, OR /spec absorbs them as "decisions" with traceability back to MSF finding IDs.
- Grill-loop-2 D6 reversal validated by J6 walk: the panel does serve a real user-job (engine A/B before commit). M4 + N3 sharpen its UX further.
