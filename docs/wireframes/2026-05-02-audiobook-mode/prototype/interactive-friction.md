# Interactive Friction Pass

Generated: 2026-05-02
Prototype folder: `docs/wireframes/2026-05-02-audiobook-mode/prototype/`
Journeys analyzed: 4 (cap 5)
Device walked: desktop-web (mobile-web friction noted inline where divergent)

This pass measures **operational cost** of completing each journey through the running prototype. Motivation/satisfaction analysis lives in `psych-findings.md` and `msf-findings.md` from `/wireframes`. This file does not duplicate those.

---

## Journey 1: Listen to a section summary right now

**Type:** daily-flow
**Source:** Primary Journey 1 (req doc lines 108–116)
**Entry route:** `#/` → click book in sidebar → `#/books/bk-thinking-fast-slow/section/sec-tfs-2`

| Step | Screen | Clicks | Keystrokes | Decisions | Modal interrupts | Latency (ms) |
|------|--------|--------|------------|-----------|------------------|--------------|
| 1 | Library (default route) | 1 (book in sidebar) | 0 | 0 | 0 | 0 |
| 2 | Reader · Section player | 1 (Listen) | 0 | 0 | 0 | 200–800 |
| 3 | Playbar appears, audio "plays" | 0 | 0 | 0 | 0 | 0 |

**Totals:** clicks=2, keystrokes=0, decisions=0, transitions=2, est. time ≈ 3 s + latency

**Flags:** none — well under the daily-flow threshold (≤6 clicks, ≤1 form step, no modal interruptions).

**Notes:**
- The sticky Playbar is reachable from any screen, so resume/skip-sentence/speed are 1 click each from the player after step 3.
- Resume affordance currently only renders in the `paused` state-tab (finding D6) — when fixed, it adds 0 clicks (the resume button replaces the play button).

---

## Journey 2: Pre-generate audio for a whole book

**Type:** daily-flow (planned action; not first-value because user already has a library)
**Source:** Primary Journey 2 (req doc lines 119–125)
**Entry route:** `#/` → click *Atomic Habits* → Audio tab → Generate audio modal

| Step | Screen | Clicks | Keystrokes | Decisions | Modal interrupts | Latency (ms) |
|------|--------|--------|------------|-----------|------------------|--------------|
| 1 | Library | 1 (book) | 0 | 0 | 0 | 0 |
| 2 | Book Audio Tab (no-audio state) | 1 (Generate audio) | 0 | 0 | 0 | 200–800 |
| 3 | Generate Audio Modal | 1 (Generate) | 0 | 1 (voice picker default OK; 3 content checkboxes default ON) | 1 (this modal — but user-opened) | 0 |
| 4 | Modal dismissed; ProcessingBar / Audio tab generating state | 0 | 0 | 0 | 0 | ~6 s simulated |
| 5 | Audio tab full state | 0 | 0 | 0 | 0 | 0 |

**Totals:** clicks=3, keystrokes=0, decisions=1, transitions=3, est. time ≈ 8 s + 6 s simulated job

**Flags:** none — the modal is user-opened (not an interrupt), and a single decision (voice/content choice) is well under the daily-flow threshold (>3 decisions per screen = flag).

**Notes:**
- Cost-estimate copy ("~12 min · ~140 MB for 47 sections") gives the user the friction-cost preview *before* clicking Generate. Good.
- Per finding M9, the estimate over-counts already-generated sections — for partial books like *Deep Work*, the estimate is misleading. Doesn't change the friction count but erodes trust. Spec should fix.

---

## Journey 3: Listen to annotations playlist

**Type:** daily-flow
**Source:** Primary Journey 3 (req doc lines 127–132)
**Entry route:** `#/` → book → Annotations tab → Listen to all

| Step | Screen | Clicks | Keystrokes | Decisions | Modal interrupts | Latency (ms) |
|------|--------|--------|------------|-----------|------------------|--------------|
| 1 | Library | 1 (book) | 0 | 0 | 0 | 0 |
| 2 | Book Detail (default tab) | 1 (Annotations tab) | 0 | 0 | 0 | 0 |
| 3 | Annotations Player (default-list state) | 1 (Listen / Play all) | 0 | 0 | 0 | 200–800 |
| 4 | Annotations Player (playing state) | 0 | 0 | 0 | 0 | 0 |

**Totals:** clicks=3, keystrokes=0, decisions=0, transitions=3, est. time ≈ 4 s + latency

**Flags:** none — under threshold.

**Notes:**
- Per finding D3 / M3, the primary CTA reads "Play all" instead of "Listen to all" (button-verb contract violation). Doesn't change friction count; spec should fix copy.
- Per finding M3, on mobile the Listen button doesn't toggle to Pause — to stop, the user must click the Playbar pause control instead, adding 1 click for the interrupt-listening sub-journey.

---

## Journey 4: Delete audio for a book (recovery / housekeeping)

**Type:** recovery (destructive action; user must be sure)
**Source:** Goal in req doc line 29 ("delete generated audio for any book at any time")
**Entry route:** `#/books/bk-deep-work/audio` → Delete audio → type-to-confirm modal → Delete

| Step | Screen | Clicks | Keystrokes | Decisions | Modal interrupts | Latency (ms) |
|------|--------|--------|------------|-----------|------------------|--------------|
| 1 | Book Audio Tab (full state) | 1 (Delete audio) | 0 | 0 | 0 | 0 |
| 2 | Delete-confirm modal | 1 (Delete) | ~9 (type "Deep Work") | 1 (Cancel vs Delete) | 1 (this modal) | 0 |
| 3 | Audio tab no-audio state | 0 | 0 | 0 | 0 | 200–800 |

**Totals:** clicks=2, keystrokes=9, decisions=1, transitions=2, est. time ≈ 8 s + latency

**Flags:** none — the type-to-confirm gate is intentional (DESIGN.md `x-interaction.destructiveActions.confirmation: type-to-confirm`). It deliberately raises friction to prevent accidental deletion.

**Notes:**
- The 9 keystrokes are an explicit safety pad. For a book with a long title (e.g., "Thinking, Fast and Slow" = 22 keystrokes), this becomes a meaningful gate. Acceptable per DESIGN.md.
- Recovery thresholds: well under the `>8 clicks` / `>2 transitions` / dead-end criteria.

---

## Cross-journey patterns

1. **Play-and-walk-away is reachable in 2 clicks from cold-open.** This is the headline outcome of the feature; the prototype validates the flow doesn't accumulate gates.
2. **Generate-audio is a 3-click commit.** All friction-relevant decisions (voice, content scope) live in one modal with sensible defaults; the cost-estimate copy buys the user back a step they'd otherwise spend wondering "is this going to be slow?"
3. **Type-to-confirm only on destructive actions.** Generate, Listen, Regenerate, Save are all 1-click commits. Delete is the only friction-padded action — by design.
4. **No journey has any unintended modal interruption.** Every modal in the prototype is user-opened. Good.
5. **Mobile vs desktop click counts are identical** for all four journeys. The mobile sheet shells (top-bar, bottom tab nav) don't add navigation steps because the primary content surface is the same screen. Good.

## Aggregate

| Journey | Clicks | Decisions | Time est. | Threshold breach |
|---|---|---|---|---|
| Listen now | 2 | 0 | ~3 s | none |
| Pre-generate | 3 | 1 | ~8 s | none |
| Annotations | 3 | 0 | ~4 s | none |
| Delete audio | 2 | 1 | ~8 s | none (intentional friction) |

No high- or medium-severity friction flags. The prototype walks each journey within the daily-flow envelope. The eval-rubric findings (logged in `prototype-findings.md`) are about *quality of feedback* and *contract adherence*, not friction cost.
