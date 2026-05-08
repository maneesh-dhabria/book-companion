# PSYCH + MSF pass

Entry context for all journeys: signed-in single user, warm (book exists, summaries done). Default starting score = **50** (high-intent: user opened the app to use it).

## Journey J1 — Library → BookSummaryPage

| Step | Screen        | Prev | Δ   | Cum | Severity | Top drivers |
|------|---------------|------|-----|-----|----------|-------------|
| 1    | 01_library    | 50   | -2  | 48  | OK       | -3 banner says "Copyright" (last-position confusion); +1 cover thumbs scannable |
| 2    | 02_book_overview | 48 | -10 | 38  | Watch    | -6 invisible tag pills (looks broken); -3 Overview tab is empty filler; -2 Read CTA → Copyright (anti-value); +1 cover hero is rich |

Severity: **Watch.** The Overview landing wastes attention; the broken tag chips read as "the page hasn't finished loading", which makes the user wait or refresh.

## Journey J2 — Book → SectionDetail

| Step | Screen           | Prev | Δ   | Cum | Severity | Top drivers |
|------|------------------|------|-----|-----|----------|-------------|
| 1    | 02_book_overview | 50   | -8  | 42  | OK       | -5 must guess to switch to Sections tab; -3 Read CTA wrong destination |
| 2    | 03_sections_tab  | 42   | -4  | 38  | OK       | -3 dev-grade columns (Chars, Compression); -2 no row affordance; +1 status ✓ scannable |
| 3    | 05_section_detail | 38  | +6  | 44  | OK       | +8 summary content is genuinely useful; -2 toolbar overload |

Severity: **OK.** The destination is the payoff (the summary itself), so once arrived the user recovers — but the Sections tab feels like a database view, not a reading interface.

## Journey J3 — Audio playback

| Step | Screen              | Prev | Δ   | Cum | Severity | Top drivers |
|------|---------------------|------|-----|-----|----------|-------------|
| 1    | 05_section_detail   | 50   | -1  | 49  | OK       | -1 Listen button buried in toolbar group |
| 2    | 06_listen_clicked   | 49   | -3  | 46  | OK       | -2 "Limited controls" + "0:00/0:00" reads as "broken"; -1 no progress bar |
| 3    | 07_audio_playing    | 46   | +2  | 48  | OK       | +3 audio actually starts immediately; -1 no speed/volume on the player |

Severity: **OK.** Web Speech's limitations leak into the chrome. Once playing, journey works.

---

## MSF scores (1-5)

| Journey | Motivation | Satisfaction | Friction (interaction / cognitive / emotional) |
|---------|-----------:|-------------:|-----------------------------------------------|
| J1 Library → Book | 4 — clear entry, books visible | 2 — Overview tab is dead air; broken-looking pills; Read goes to Copyright | 1 click / 1 decision (which tab) / 1 emotional jolt (broken pills) |
| J2 Book → Section | 3 — must guess Sections tab | 4 — content quality is high once landed | 2 clicks / 2 decisions / 0 modal |
| J3 Listen | 4 — clear button | 3 — playback works but chrome implies "limited" without recourse | 1 click / 0 decisions / 1 emotional ("Limited controls?") |

Friction-table flags:
- **J1**: cognitive (decoding broken-looking tags), emotional (anti-value Read CTA) — flagged.
- **J3**: emotional (limited-controls badge implies the tool is broken when it's actually a Web Speech limitation). Flagged.

Click-budget assessment (J1 thresholds for daily-flow ≤ 6 clicks): all three journeys pass on raw click count. **Friction is qualitative**, not click-count.
