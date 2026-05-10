# Design Crit — Quiz & Audio (book detail tabs)

Generated: 2026-05-10
Source: `http://localhost:8000/books/1` (live app, signed-in single user, book *Understanding Michael Porter* with all 12 sections summarized)
Journeys reviewed: 2 (Quiz first-time → start → generation; Audio first-time → engine choice → generate dialog)
Screens captured: 9

> **Coverage gap:** the QnA experience (question card, answer textarea, scoring) could not be observed live — `POST /api/v1/books/1/quiz-sessions` returns **500 Internal Server Error** during capture (see Q-3). All Quiz findings beyond the start screen are inferences from the form / scope picker / silent-failure state, not the live question UI.

---

## TL;DR — top 7 recommendations

1. **[high · Q-3] Start-quiz silently fails — no toast, no inline error, no retry.** The button click POSTs `/quiz-sessions`, the server returns 500, and the UI does nothing visible. The user is left wondering whether they clicked. *Fix:* catch `ApiError`, show a notification toast with the error message + Retry button, and add a spinner on the button while the request is in flight.
2. **[high · A-1] On the Audio empty state, a single primary CTA labelled "Generate audio" sits next to copy that says "Instant on Web Speech (no pre-generation needed)" — the affordances contradict each other.** *Fix:* split into two CTAs — **▶ Listen now** (primary, starts Web Speech immediately) and **⬇ Generate MP3 files** (secondary, opens existing dialog). Subtitle the secondary as "for offline + scrubbing".
3. **[high · Q-1] Quiz first-visit is an unexplained bare form.** No copy tells the user what a quiz is, how many questions, how long generation takes, or what the lifetime tally tracks. *Fix:* one-paragraph orientation hero + "We'll generate 5 questions (~30 sec)" inline near the Start button + an empty "0 past sessions" rail.
4. **[high · A-3] Audio empty-state hierarchy is inverted.** "No audio yet for this book." (muted gray) is the headline; the actionable line "Instant on Web Speech…" is smaller below it. *Fix:* lead with the action ("**Listen to this book — instant playback via your browser**"), demote the no-audio-yet line to a sub-caption.
5. **[high · A-5] Generate-audio dialog estimate "~3.6 min · ~54 MB for 17 sections" is ambiguous.** Is 3.6 min generation wall-clock or playback duration? (It's generation; playback for 17 chapter summaries would be ~25 min.) *Fix:* split the labels — "~3.6 min generation · ~25 min listening · ~54 MB on disk".
6. **[high · Q-7] "0 / 60,000 tokens" progress bar in the chapter scope picker exposes implementation detail with no decision-anchor.** Most readers don't know what 60K is. *Fix:* replace with a human metric ("~30 min reading · 4 of 12 chapters selected") and tooltip the cap.
7. **[high · A-7] Settings → Text-to-speech still shows a "Spike findings" heading** — engineering jargon on a user-settings panel. *Fix:* rename to "About this engine" or remove.

---

## Recommendations by journey

### J1 — Quiz feature

Friction stats: clicks=1 to fail (silent 500), 0 keystrokes to start, 1 decision (scope), 0 modal interrupts. **Threshold breach: yes — Cliff at step 2 (silent error, S2/N9).**

- **[high · Q-1] N1/V1 — No first-time orientation.** First visit shows only "Quiz scope" radio + "Theme (optional)". No copy explains what a quiz is, the number of questions, expected duration, what the lifetime tally means. Practitioners who skipped the changelog have zero context. *Fix:* add a one-paragraph hero + inline "We'll generate 5 questions in ~30 sec" near *Start quiz*. Show "0 past sessions" empty rail until a session exists.
- **[high · Q-2] J5/N5 — No question count or time estimate before commit.** *Fix:* add "5 questions · ~30 sec generation" microcopy under the Start button, or expose a "Number of questions" stepper. Set expectation of latency before the click.
- **[high · Q-3] S2/N9 — Start quiz fails silently.** Console: `POST /quiz-sessions → 500`. UI shows no toast/inline error/spinner/timeout. Button stays in `[active]` state and nothing happens. *Fix:* (a) backend: fix the 500 (out of scope for this crit); (b) frontend: surface every quiz-session API error via the existing `<NotificationToast>` slot, with a Retry button and a "View details" expander showing the response body. Add a spinner to the button while POST is in-flight.
- **[medium · Q-4] N1 — No loading state during question generation.** Even if the POST succeeded, there's no skeleton or "Asking the model — usually 10–20 sec…" copy bridging click→first-question. *Fix:* skeleton card + progress copy on click.
- **[medium · Q-5] V1 — Theme textarea visually outweighs the primary CTA.** Theme is a multi-row textbox; *Start quiz* sits in the bottom-right corner in lavender that almost reads as disabled. F-pattern eye-track hits Theme first (an optional field). *Fix:* compress Theme to a single-line input with a "Show advanced" disclosure, OR boost Start-quiz contrast and move it directly under the radios.
- **[medium · Q-6] A1 — Start-quiz button contrast borderline.** Lavender (~#7e7afc) on near-black panel reads under the 4.5:1 threshold by visual sample. Same risk on the Read button and the Web Speech chip. *Fix:* verify with Stark/axe; saturate or darken the surrounding surface to recover.
- **[high · Q-7] N6/F1 — "0 / 60,000 tokens" progress bar.** Raw token count exposed without explanation; most users don't know what the cap is or means. *Fix:* "Selected: 4 of 12 chapters · ~30 min reading" + tooltip explaining the LLM context budget.
- **[medium · Q-8] V1/V6 — Section list lacks Select all / search / filter.** With long books (30+ sections) the user clicks each. Part headings ("Part One", "Part Two") sit at the same depth as numbered chapters in the list — visual hierarchy is flat. *Fix:* "Select all / Select none" links above the list; render Part headings as group separators.
- **[medium · Q-9] N9 — "Pick at least one chapter." floats as a passive caption.** Sits between progress bar and Theme; the cause-effect link to the disabled Start button is implicit. *Fix:* attach the message via `aria-describedby` to the button and place it under the button.
- **[low · Q-10] F3 — Per-section token counts are schema-driven decoration.** Right-aligned "583 tokens", "11,521 tokens" don't drive any decision a non-developer makes. *Fix:* hide behind a "Show technical details" toggle, or remove.
- **DEFERRED — QnA experience (question card / answer textarea / scoring / completion).** Couldn't observe live. Re-run this crit after the 500 is fixed; focus heuristics: N1 (progress "Q3 of 5"), N3 (skip / quit), J5 (step indicator), S4 (success / completion celebration), N9 (low-score recovery framing).

### J2 — Audio feature

Friction stats: clicks=2 (Generate audio → Generate in modal) before any sound is heard via the recommended path; 0 to reach Web Speech (but no obvious entry into Web Speech from this surface). 3 cognitive decisions (engine concept, content selection, time/MB ambiguity). 1 modal interrupt. **Threshold breach: medium (daily-flow interrupt + ambiguous estimate).**

- **[high · A-1] N4/V1 — "Generate audio" is a single primary CTA but Web Speech is instant.** The page literally says "Instant on Web Speech (no pre-generation needed)" right above a button labelled *Generate audio*. New users read "I have to generate before I can listen" — wrong for the default engine. (This was the friction the user named.) *Fix:* two CTAs — **▶ Listen now** (primary, starts Web Speech immediately on the first chapter / book summary) and **⬇ Generate MP3 files** (secondary, opens existing dialog with subtitle "for offline + scrubbing"). The "What's the difference?" link can collapse into a "?" tooltip on the secondary CTA.
- **[high · A-2] N1/F1 — "Web Speech" chip is unexplained.** A bare pill labelled "Web Speech" sits where a panel header should be. No first-time user knows whether it's an engine, a brand, or a status. *Fix:* on first-visit, drop the chip entirely (it conveys no decision yet); on a generated book, expand it to "Engine: Kokoro · voice: af_heart · ⚙" with a settings cog inline.
- **[high · A-3] N1/S1 — Empty-state hierarchy inverted.** "No audio yet for this book." in muted gray reads as the headline; the actionable line "Instant on Web Speech…" is smaller below. *Fix:* lead with the verb — "**Listen to this book — instant playback via your browser**" — and demote the no-audio line to a status sub-caption beneath the buttons.
- **[medium · A-4] N2/N10 — Modal copy is engine-named, not outcome-named.** "Kokoro vs. Web Speech" assumes the user cares about engine names. Most users care about "right now in browser" vs. "download for offline + scrubbing". *Fix:* reframe the modal heading as "Listen now (browser) vs. Download for offline" and let engine names be parenthetical.
- **[high · A-5] N5 — Generate-audio dialog "~3.6 min · ~54 MB for 17 sections" is ambiguous.** Is 3.6 min generation or playback? *Fix:* "~3.6 min to generate · ~25 min to listen · ~54 MB on disk".
- **[medium · A-6] N8/N5 — All three content checkboxes default to checked.** Section summaries + Book summary + Annotations on by default → first-click commits ~54 MB without the user having heard a single sample. *Fix:* default to *Section summaries* only on first run; surface a "Quick-test (1 section)" link so the user can validate voice quality before committing a full book.
- **[medium · A-7] N3 — No way to preview the voice before generating.** *Fix:* "Preview voice (10 sec)" button next to the engine chip plays a sample using the current Kokoro voice config.
- **[low · A-8] V1 — "recommended" pill on Annotations is the only colour accent in the modal.** Drives the eye to a non-primary checkbox. *Fix:* drop the pill, or apply it to all three (with a single "Recommended for full audiobook" footer).
- **[high · A-9] N2/N8 — "Spike findings" heading on Settings → Text-to-speech.** Engineering artefact on a user-facing panel. *Fix:* rename to "About this engine" or remove the section.
- **[medium · A-10] N3/N6 — Save / Reset to defaults pair lacks dirty-state.** Users can press Save without changing anything; Reset is destructive but unconfirmed. *Fix:* disable Save until form is dirty; inline-confirm on Reset.

### Cross-cutting findings (apply to both flows + book detail shell)

- **[high · X-1] N4 — Tab labels are noun-only and have weak scent.** "Audio", "Quiz", "Annotations" don't tell a first-time user what each tab will do. *Fix:* either rename to verb-led labels ("Listen", "Test yourself", "My notes") or add hover/focus tooltip descriptions.
- **[medium · X-2] N7 — No keyboard shortcuts on Quiz / Audio actions.** Header advertises ⌘K for search; nothing else has discoverable shortcuts. *Fix:* ⌘⏎ to start quiz / generate, Space to play-pause audio.
- **[medium · X-3] J6 — Tab change loses transient form state.** Type a Theme in Quiz, click Audio, click Quiz — Theme is gone (component remount). *Fix:* persist transient form state per book at the route or `localStorage` level.
- **[medium · X-4] V1/G4 — Page wastes ~25% left whitespace.** With a thin sidebar, the main panel still has a wide left gutter; no contextual right rail. *Fix:* either widen the content max-width or add a contextual right rail (recent quiz sessions, lifetime tally; audio playback strip / generation queue).
- **[low · X-5] V3 — Tab bar bottom rule sits ~12px from first content row.** *Fix:* +12-16px breathing room below the underline.

---

## Recommendations by component

- **Primary button (lavender on dark)** — contrast borderline (A1); visual weight insufficient against multi-row textareas (V1). *Fix:* one canonical primary token with verified ≥4.5:1 contrast; reserve for the single primary action per screen.
- **Empty-state panel** — currently leads with "No <thing> yet for this <X>." pattern in muted gray. Inverts hierarchy on Audio (A-3); likely repeats elsewhere. *Fix:* an `<EmptyState>` component that takes a verb-led headline as its required prop, with the "no <thing> yet" string demoted to status caption.
- **Engine / status chip** — same component used for "Web Speech" on Audio and "✓ All 12 sections summarized" on the book hero. The two convey different semantics (status vs. user-configurable choice) but look identical. *Fix:* split into `StatusBadge` (read-only, ✓-prefixed) and `EngineChip` (clickable, gear-suffixed).
- **Notification surface** — `region "Notifications"` exists in the snapshot but isn't being used by the quiz-session error path. *Fix:* fronting `ApiError` errors through this region should be the default catch in the API client, not a per-component decision.

---

## Cross-cutting patterns (highest-leverage)

1. **Silent failure (Q-3 + likely siblings).** Pattern: API errors not surfaced to the user. Severity is high because it breaks trust on the second click. The "Notifications" region is already there — wire it to the API client error path globally.
2. **Implementation language leaking into UX (Q-7, A-2, A-4, A-9).** Token counts, "Spike findings", "Kokoro / Web Speech", `audio/positions/by-book` 404 — all reflect engineering language reaching the user surface. Pattern fix: a copy review pass owned by one person before each release; everything user-facing reframed in user vocabulary (N2).
3. **Inverted hierarchy on empty / first-time states (A-3, Q-1).** The status-line ("no audio yet"; "no quiz yet" implicit) is louder than the action that resolves it. Pattern fix: empty-state component contract — verb-led headline mandatory, status string optional and demoted.
4. **Single CTA hides parallel paths (A-1).** When two real options exist (instant vs. generated), one shouldn't be implicit. This pattern — "the second option is hidden behind a sub-link or tooltip" — is worth grepping for elsewhere.

---

## Deferred

- **QnA experience (Q-DEFER).** Couldn't observe live; backend POST returns 500. Re-run this crit after the bug is fixed; pre-flag heuristics N1 / N3 / J5 / S4 / N9.
- **Dispositioning (Phase 4a).** Skipped per-finding `AskUserQuestion` triage — 26 findings × 4-per-call would be 7 prompt rounds for a doc you'd rather read once. Disposition by reading; flag any "won't fix" / "deferred" inline if you want to spec from this.

---

## Appendix A — PSYCH walkthrough

**Quiz** (start: 40, Medium-intent)

| Step | Screen                       | Prev | Δ    | Cum | Severity   | Top drivers                                                                |
| ---- | ---------------------------- | ---- | ---- | --- | ---------- | -------------------------------------------------------------------------- |
| 1    | 01-quiz-firstvisit           | 40   | -5   | 35  | OK         | -3 no orientation copy · -2 borderline-contrast CTA                        |
| 2    | Click Start (silent 500)     | 35   | -25  | 10  | **Cliff**  | -25 silent error, no toast / spinner / retry                                |
| 3    | (would-be) question card     | —    | —    | —   | DEFERRED   | not observable in this session                                              |
| 4    | 04-quiz-scopepicker          | 35   | -6   | 29  | Watch      | -4 token-progress jargon · -2 flat Part-vs-Chapter hierarchy                |

**Audio** (start: 40)

| Step | Screen                       | Prev | Δ    | Cum | Severity | Top drivers                                                                |
| ---- | ---------------------------- | ---- | ---- | --- | -------- | -------------------------------------------------------------------------- |
| 1    | 05-audio-firstvisit          | 40   | -7   | 33  | OK       | -4 single-CTA contradicts Instant copy · -3 unexplained Web Speech chip     |
| 2    | 06-audio-difference (modal)  | 33   | -3   | 30  | Watch    | engine-named heading, not outcome-named                                     |
| 3    | 07-audio-generate-clicked    | 30   | -8   | 22  | Watch    | -5 ambiguous "3.6 min" estimate · -3 all-checked default                   |
| 4    | 08-audio-settings            | 22   | -3   | 19  | Watch    | "Spike findings" jargon                                                     |

Severity legend: cumulative `< 0` Bounce risk; `< 20` Watch; single-step Δ `< -20` Cliff.

## Appendix B — MSF

| Journey | Motivation | Satisfaction | Friction (interaction · cognitive · emotional)                          |
| ------- | ---------- | ------------ | ------------------------------------------------------------------------ |
| Quiz    | 4/5        | **1/5**      | clicks=1 to dead-end · cognitive 2 (token cap, theme purpose) · emotional **3** (silent failure breaks trust) |
| Audio   | 3/5        | n/a (couldn't reach end-state) | clicks=2 to commit · cognitive 3 (engine concept · time/MB ambiguity · all-checked) · emotional 1 (mild "did I just commit 54 MB?") |

## Appendix C — Raw findings

26 findings total: 11 high, 11 medium, 4 low (excluding the deferred QnA cluster).

Captured screenshots and snapshots live alongside this report in `screenshots/`.
