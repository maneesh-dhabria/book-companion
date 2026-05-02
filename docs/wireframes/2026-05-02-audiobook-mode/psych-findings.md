# PSYCH Walkthrough — Audiobook Mode

Generated: 2026-05-02
Wireframes folder: `docs/wireframes/2026-05-02-audiobook-mode/`
Tier: 3
Entry-context default: Medium-intent (40) — user has already invested in summarizing this library; audio is an additive re-encounter channel, not a discovery flow.
Journeys analyzed: 3 of 3 primary journeys (CLI alternate journey is non-UI, excluded).

## Threshold legend

- Cumulative `< 20`  → **Watch**
- Cumulative `< 0`   → **Bounce risk**
- Single-screen Δ drop `> 20` → **Cliff** (flagged regardless of cumulative)

---

## Journey 1: Listen to a section summary right now   (start: 40, Medium-intent)

Sparkline: 40→49→71→76   ▁▃▆▇  (no danger; strong upward curve)

### Element table (audit)

| Screen | Element | ± Psych | Running Total | Notes |
|--------|---------|---------|---------------|-------|
| 01_reader-section-player (default) | Play button in section header next to existing toggle | +6 | 46 | Primary affordance; immediately actionable (Reward) |
| 01_reader-section-player (default) | Engine chip "Web Speech (instant)" | +3 | 49 | Sets expectation: no install, no wait (Motivational boost) |
| 01_reader-section-player (default) | Headphones icons on pre-gen sections in sidebar | +2 | 51 | Visible audio coverage signal (Progress indicator) |
| 01_reader-section-player (default) | "Show full content" toggle adjacent to Play | -2 | 49 | Minor decision: read or listen? (Decision) |
| 01_reader-section-player (playing) | Audio starts within 200ms (Web Speech) | +8 | 57 | "Aha" moment; near-instant gratification (Reward) |
| 01_reader-section-player (playing) | `bc-sentence-active` highlight + auto-scroll | +9 | 66 | Combined: visible progress, no manual tracking (Motivational + Reward) |
| 01_reader-section-player (playing) | Playbar with familiar transport controls | +4 | 70 | Pattern transfer from any audio app (Familiarity) |
| 01_reader-section-player (playing) | Auto-advance to next section toggle (default ON) | +2 | 72 | Matches "walk away from screen" intent (Motivational) |
| 01_reader-section-player (playing) | Engine chip "Web Speech" reminder mid-playback | -1 | 71 | Subtle reminder a higher-quality engine exists (Question) |
| 01_reader-section-player (paused-with-resume) | "Resume from sentence 12 of 47 · 2 hours ago" | +6 | 77 | Respect for time invested; pickup-where-you-left-off (Reward) |
| 01_reader-section-player (paused-with-resume) | Device-context disclaimer ("on this device") | -1 | 76 | Slight cognitive load — what does "this device" mean? (Question) |

### Screen table (stakeholder rollup)

| Step | Screen | Previous | Δ | Cumulative | Severity | Top 2 Drivers |
|------|--------|----------|---|------------|----------|----------------|
| 1 | 01_reader-section-player (default) | 40 | +9 | 49 | OK | +6 (Play CTA), +3 (engine chip clarity) |
| 2 | 01_reader-section-player (playing) | 49 | +22 | 71 | OK | +8 (instant start), +9 (highlight + scroll combo) |
| 3 | 01_reader-section-player (paused-with-resume) | 71 | +5 | 76 | OK | +6 (resume position), -1 (device-context disclaimer) |

---

## Journey 2: Pre-generate audio for a whole book   (start: 40, Medium-intent)

Sparkline: 40→48→58→73→86→91   ▁▂▄▆▇▇  (no danger; steady climb, strong reward arc)

### Element table (audit)

| Screen | Element | ± Psych | Running Total | Notes |
|--------|---------|---------|---------------|-------|
| 03_book-detail-audio (no-audio) | "No audio generated yet" + clear primary CTA | +6 | 46 | Decisive next step (Reward) |
| 03_book-detail-audio (no-audio) | Audio panel sits beside familiar "Generate summaries" pattern | +3 | 49 | Mental-model transfer (Familiarity) |
| 03_book-detail-audio (no-audio) | No cost preview (time/disk) on the CTA | -3 | 46 | Unknown cost — "how long? how big?" (Question) |
| 03_book-detail-audio (no-audio) | Single button surface, no decisions yet | +2 | 48 | Easy entry (Low effort) |
| 04_generate-audio-modal (default) | Estimate "~12 min · ~140 MB" line | +5 | 53 | Resolves cost question — big reward (Reward) |
| 04_generate-audio-modal (default) | 3 content checkboxes (sections / book / annotations) | -3 | 50 | Decision burden, though defaults sensible (Decision) |
| 04_generate-audio-modal (default) | Voice selector with Sample button | +4 | 54 | Preview before commit (Reward) |
| 04_generate-audio-modal (default) | Speed pill row default 1x | -1 | 53 | Minor decision visible (Decision) |
| 04_generate-audio-modal (default) | "Generate audio" primary CTA | +4 | 57 | Clear, decisive close (Motivational) |
| 04_generate-audio-modal (default) | Annotations-checkbox educational annotation | +1 | 58 | Hover-explanation reduces ambiguity (Reward) |
| 03_book-detail-audio (generating) | Live SSE progress bar 18/47 + ETA "~6 min" | +9 | 67 | Combined: visible progress + bounded wait (Motivational + Progress indicator) |
| 03_book-detail-audio (generating) | Recently-completed sections fade list | +3 | 70 | Ongoing reward / completion cues (Reward) |
| 03_book-detail-audio (generating) | Pause / Cancel buttons | +2 | 72 | Control over running job (Autonomy) |
| 03_book-detail-audio (generating) | Active section name "The Two Selves" | +1 | 73 | Subtle interest signal — "from my book" (Positive emotion) |
| 03_book-detail-audio (full-audio) | "Audio: 47 of 47 + book summary + annotations · 100%" | +8 | 81 | Completion cue, large reward (Reward) |
| 03_book-detail-audio (full-audio) | Listen primary CTA | +5 | 86 | Clear next action — go consume (Motivational) |
| 03_book-detail-audio (full-audio) | 4 buttons in row (Listen / Files / Regenerate / Delete) | -2 | 84 | Decision burden post-success (Decision) |
| 03_book-detail-audio (full-audio) | "Last generated · 142 MB on disk" transparency | +2 | 86 | Builds trust (Credibility signal) |
| 05_audio-files-list (populated) | Catalog feel — 47 rows w/ track #, duration, size | +4 | 90 | Library artifact feels valuable (Reward) |
| 05_audio-files-list (populated) | "ID3 tagged ✓" pill | +2 | 92 | Signals "ready for podcast app" (Credibility) |
| 05_audio-files-list (populated) | Per-row Download inline | +3 | 95 | Clear export path (Reward) |
| 05_audio-files-list (populated) | 47-row scroll density | -3 | 92 | Scrolling, density (Physical effort) |
| 05_audio-files-list (populated) | Top Regenerate / Delete-all actions | -1 | 91 | Minor decisions; user past them (Decision) |

### Screen table (stakeholder rollup)

| Step | Screen | Previous | Δ | Cumulative | Severity | Top 2 Drivers |
|------|--------|----------|---|------------|----------|----------------|
| 1 | 03_book-detail-audio (no-audio) | 40 | +8 | 48 | OK | +6 (clear CTA), -3 (unknown cost) |
| 2 | 04_generate-audio-modal (default) | 48 | +10 | 58 | OK | +5 (cost preview resolves), +4 (voice sample) |
| 3 | 03_book-detail-audio (generating) | 58 | +15 | 73 | OK | +9 (progress + ETA), +3 (completion cues) |
| 4 | 03_book-detail-audio (full-audio) | 73 | +13 | 86 | OK | +8 (100% completion), +5 (Listen CTA) |
| 5 | 05_audio-files-list (populated) | 86 | +5 | 91 | OK | +4 (catalog), +3 (download per row) |

---

## Journey 3: Listen to annotations from a book   (start: 40, Medium-intent)

Sparkline: 40→51→63   ▁▄▇  (2-screen journey; no danger)

### Element table (audit)

| Screen | Element | ± Psych | Running Total | Notes |
|--------|---------|---------|---------------|-------|
| 06_annotations-player (default-list) | Familiar annotations tab + highlight cards | +3 | 43 | Familiarity from existing reader pattern |
| 06_annotations-player (default-list) | "Play as audio" CTA top-right | +4 | 47 | Clear new affordance (Motivational) |
| 06_annotations-player (default-list) | Yellow `bc-highlight` styled passages | +2 | 49 | Visual continuity with reader (Familiarity) |
| 06_annotations-player (default-list) | 6–8 annotation cards visible — value preview | +3 | 52 | Content already visible; pre-listening reward (Reward) |
| 06_annotations-player (default-list) | Section pills preserve context | +1 | 53 | Context preserved (Credibility) |
| 06_annotations-player (default-list) | No duration estimate before pressing Play | -2 | 51 | Unknown playlist length (Question) |
| 06_annotations-player (playing) | Active sentence highlight on card #3 | +5 | 56 | "Where am I" visible signal (Motivational) |
| 06_annotations-player (playing) | Playbar w/ skip-prev/next-annotation, "3 of 18" | +5 | 61 | Position clear; skip-by-annotation matches mental model (Reward) |
| 06_annotations-player (playing) | Half-second tonal cue between highlight and note | +2 | 63 | Delight detail; signals craft (Positive emotion) |
| 06_annotations-player (playing) | Tap any card to jump playback | +2 | 65 | Random access, control (Autonomy) |
| 06_annotations-player (playing) | Engine chip Kokoro implies pre-gen needed | -2 | 63 | Slight surprise — "did I generate this?" (Question) |
| 06_annotations-player (playing) | `bc-engine-chip` Kokoro | +1 | 64 | Quality signal |
| 06_annotations-player (playing) | 18 total — only "3 of 18" (no end ETA) | -1 | 63 | Mild unknown remaining (Question) |

### Screen table (stakeholder rollup)

| Step | Screen | Previous | Δ | Cumulative | Severity | Top 2 Drivers |
|------|--------|----------|---|------------|----------|----------------|
| 1 | 06_annotations-player (default-list) | 40 | +11 | 51 | OK | +4 (Play CTA), +3 (value preview from visible cards) |
| 2 | 06_annotations-player (playing) | 51 | +12 | 63 | OK | +5 (active-sentence highlight), +5 (skip-by-annotation) |

---

## Summary

All three primary journeys land in **OK** territory across every screen — no Watch, no Bounce risk, no Cliffs. Lowest cumulative: 46 (J2 step 1, after the cost-unknown deduction). Drive-curve is dominated by:

- **Strong rewards** from instant start (J1 step 2), live progress (J2 step 3), and 100% completion (J2 step 4)
- **Familiarity transfer** from reader / annotations / job UI patterns
- **Cost transparency** when surfaced (J2 step 2 estimate; J2 step 4 disk usage)

Two consistent-across-journeys friction points emerged. Both are LOW severity, no-block:

1. **Pre-action cost unknowns** (J2 step 1: time/disk; J3 step 1: playlist duration) — resolved on the *next* screen, but the friction sits on the entry CTA where it can deter cautious users.
2. **Subtle device/engine ambiguity** (J1 device-context disclaimer; J3 Kokoro chip without explanation of pre-gen requirement) — single-line copy fixes.

## Findings (for disposition)

| # | Severity | Journey · Screen | Finding | Proposed fix |
|---|----------|------------------|---------|--------------|
| F1 | Low | J2 · 03_book-detail-audio (no-audio) | "Generate audio" CTA gives no time/disk preview; cost question lingers until modal opens | Add an inline meta line under the CTA: "~12 min · ~140 MB for 47 sections" computed from section count × heuristic |
| F2 | Low | J3 · 06_annotations-player (default-list) | "Play as audio" CTA gives no estimated playlist duration | Add subtitle on CTA: "Play as audio · ~9 min" using highlight count × heuristic |
| F3 | Low | J1 · 01_reader-section-player (paused-with-resume) | "last listened on this device" disclaimer raises a question without resolving it | Tighten copy to "last listened from this browser 2 hours ago" — disambiguates "device" and removes implicit cross-device promise |
| F4 | Low | J3 · 06_annotations-player (playing) | Engine chip "Kokoro" surprises users who didn't realize annotations playlist required pre-generation | Annotation in the engine-chip area: "Annotations playlist generates on first play if not pre-generated" OR ensure the annotations playlist plays via Web Speech as a fallback (consistent with D14) |

## Applied changes

| Journey | Screen | Finding | Fix | Status |
|---------|--------|---------|-----|--------|
| J2 | 03_book-detail-audio (no-audio) — desktop + mobile | F1 cost preview missing | Added meta line "Estimate: ~12 min · ~140 MB for 47 sections (Kokoro)" beneath the Generate audio CTA | Applied |
| J3 | 06_annotations-player (default-list) — desktop + mobile | F2 playlist duration missing | Stacked CTA: "Play as audio" + subtitle "~9 min · 18 highlights" | Applied |
| J1 | 01_reader-section-player (paused-with-resume) — desktop + mobile | F3 device-context disclaimer ambiguous | Copy: "last listened on this device" → "last listened from this browser" (matches D9 device_id semantics) | Applied |
| J3 | 06_annotations-player (playing) — desktop + mobile | F4 Kokoro chip surprise | Added explanatory annotation + "pre-generated" sub-label next to engine chip; references D14 fallback rule | Applied |

Note for /spec: F3 implies the user-facing copy should always say "browser" (per-browser device_id) unless and until cross-device handoff is built. F4 leaves open the larger architectural question — should annotations playlist support runtime Web Speech streaming when no pre-gen MP3 exists? Current wireframes assume yes (matches D14); confirm during /spec.
