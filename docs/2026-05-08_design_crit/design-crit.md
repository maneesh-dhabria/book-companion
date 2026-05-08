# Design Crit — Book Companion (library / book / section / audio)

Generated: 2026-05-08
Source: http://localhost:8000/ (live local app)
Journeys reviewed: 3 (Library → Book, Book → Section, Audio playback)
Screens captured: 8

## TL;DR (top 5 recommendations)

1. **[high] Tag pills on /books/:id are invisible in dark mode ([A1])** — measured contrast ≈ 1.1:1 (WCAG AA needs 4.5:1). They look like loading skeletons, which makes the page read as "still loading". Add a `dark:` variant on the chip token: `dark:text-slate-100 dark:bg-indigo-500/25` (or reuse the badge token already used by "All N sections summarized"). Verify ≥ 4.5:1 in both themes.
2. **[high] "Read" CTA and "Continue reading" banner both route to `/books/1/sections/1` = Copyright ([N5])** — the page's most prominent action delivers anti-value: a 2,498-char copyright notice. Skip front-matter `section_type`s (`copyright`, `acknowledgments`, `about_author`, `notes`) when picking the default destination, and only persist a read-position after the user has actually scrolled past 25% / spent > 5 s on a section.
3. **[high] BookSummaryPage Overview tab is one filler sentence ([F1, V6])** — the default landing surface is empty below the hero. Replace with an at-a-glance dashboard: last-read + Continue, top 3-5 concepts, recent annotations, eval pass-rate badge, preset in use. This is the highest-leverage screen to invest in — every subsequent journey starts here.
4. **[high] Book Summary tab is a wall of markdown with no in-page navigation ([V6, J3])** — long, unbroken bullet hierarchy across many viewport heights. Add a sticky right-hand outline (h2/h3 from the markdown), anchor IDs, a back-to-top FAB, and optionally collapse very long sub-sections behind disclosure. Without this, the summary is a worse reading experience than the original chapters.
5. **[high] Two h1 elements on /books/:id ([A4])** — banner h1 = "Book Companion", main h1 = book title. Screen readers announce the brand twice; the document outline is broken. Demote the banner heading to a wordmark (`<span>` or `role="img"`); reserve h1 for the page subject.

---

## Recommendations by journey

### Journey 1 — Library → Book Summary
*PSYCH cum. 38 (Watch); friction: 1 click, 0 keystrokes, 1 emotional jolt (broken-looking pills + anti-value Read).*

- **[high] Tag pills unreadable in dark mode ([A1])** — measured 1.1:1. *Fix:* add `dark:` variant; verify ≥ 4.5:1.
- **[high] "Read" CTA routes to Copyright ([N5])** — see TL;DR #2.
- **[high] Two h1s on the page ([A4])** — see TL;DR #5.
- **[medium] Overview tab is dead air ([F1])** — replace with dashboard tiles (TL;DR #3).
- **[medium] Library "Continue reading" banner shows last position as "Copyright" ([N1])** — same root cause as the Read CTA bug. Pick the same fix: don't persist read-positions on front-matter / brief visits.
- **[medium] Library view-mode toggle uses three opaque glyphs (▦, ☰, ▤) without labels or tooltips ([C5])** — the third in particular is unrecoverable without trial. *Fix:* swap to labelled icons (Tabler/Lucide grid/list/compact) with `aria-label="Grid view"` etc.; persist selection in localStorage.
- **[low] Per-card checkboxes appear before bulk-edit mode is entered ([N6])** — there's no visible "what does selecting do?" hint. *Fix:* hide checkboxes until a "Select" toolbar button is clicked; show a sticky bulk-action bar when active.
- **[low] J1 click-economy ([J1])** — 1 click from / to /books/1, well under the daily-flow threshold (≤ 6). No action needed at the journey level — issue is the destination quality.

### Journey 2 — Book → Section Detail
*PSYCH cum. 44 (OK); friction: 2 clicks, 2 decisions, 0 modal interrupts.*

- **[high] Summary tab needs a TOC + anchors ([V6])** — see TL;DR #4.
- **[medium] Sections tab surfaces dev-grade columns ("Chars", "Compression %") instead of decision-anchored values ([F1, F3])** — a user can't decide "read this vs that" from char count or compression ratio. *Fix:* replace Chars with "Read time" (≈ chars / 1100 chars/min ≈ chapter minutes); move Compression into a hover detail or remove from list view; demote Type to a leading icon.
- **[medium] Sections list interleaves front-matter, chapters, and back-matter as flat rows ([G1])** — Copyright/Acknowledgments and About-the-Author sit beside Chapters 1-7. *Fix:* group under "Front matter / Chapters / Back matter" subheaders with front+back collapsed by default.
- **[medium] Section rows have no hover affordance and no inline actions ([C3])** — *Fix:* row-as-button with hover bg, `cursor-pointer`, inline ▶ Listen / 📖 Read / ⋯ More icons revealed on hover, trailing chevron.
- **[medium] Section toolbar packs 7 controls in one undivided row ([V5])** — *Fix:* group into nav (← →) | mode (Original|Summary) | actions (Listen, ⚙) with subtle dividers; move the section drawer ☰ to a left-edge rail or merge with the breadcrumb dropdown.
- **[medium] Prev/Next arrows are single-character buttons under 24×24 ([A2])** — *Fix:* increase hit area to ≥ 40×40; aria-label "Previous section" / "Next section"; tooltip showing destination section title.
- **[medium] BookSummaryPage has no clear single primary CTA per intent ([J2])** — Read CTA + 5 tabs split the user's "where do I go to read the summary" decision. *Fix:* either default to Summary tab on warm books, or rename "Read" → "Read original" and add a primary "Read summary" / "Listen" pair.
- **[medium] Summary tab has no metadata strip ([S4])** — preset, generated-at, eval pass-rate, default-summary-id are invisible while reading. *Fix:* metadata strip above the markdown with chips for preset + relative time + eval badge + actions (Regenerate, Switch preset, Compare versions).
- **[medium] Three icon-only chrome buttons (☰, ⚙, ⋯) ([C5])** — ☰ in particular has no visible aria-label. *Fix:* add aria-label + tooltip; show icon+label at this viewport (sidebar has horizontal slack).

### Journey 3 — Audio playback
*PSYCH cum. 48 (OK); friction: 1 click, 0 decisions, 1 emotional ("Limited controls?").*

- **[medium] "Limited controls" amber badge is non-actionable ([N9])** — *Fix:* tooltip / link: "Web Speech can't seek/scrub. Install Kokoro for full controls →" pointing at /settings or a docs popover.
- **[medium] Player shows fake "0:00 / 0:00" timestamp on Web Speech ([F2])** — *Fix:* hide time display when engine = web-speech; show real time only when Kokoro is engaged. Optionally show qualitative estimate ("≈ 4 min").
- **[medium] Audio empty state lacks engine choice and time estimate ([S1])** — *Fix:* empty state with engine chip, estimated synthesis time, content scope ("summaries vs originals"), and a "What's the difference?" link.
- **[medium] No "Resume listening" indicator after navigating away ([J6])** — closing the player ✕ or navigating to another page leaves no docked indicator of where playback was. *Fix:* docked "Resume listening — Introduction · sentence 5 of 17" bar mirroring the "Continue reading" pattern.
- **[low] No sentence-progress bar in the player ([J5])** — *Fix:* thin 17-segment progress bar, completed sentences shaded.
- **[low] No keyboard shortcut hints (Space, ←, →) ([N7])** — *Fix:* tooltips with shortcut hints; reachable `?` overlay.
- **[low] Audio engine chip ("Web Speech") has no dark-mode variant ([A1])** — `bg-slate-100 text-slate-700` only. *Fix:* add `dark:bg-slate-700 dark:text-slate-100`.

---

## Recommendations by component

- **Tag chip** ([A1]) — needs dark-mode token. Highest-leverage component fix; same chip class is reused in Concepts / Annotations / Library and likely fails contrast there too. Audit every place this class is used.
- **Section row** ([C3]) — see Journey 2; one component change covers the whole Sections tab and the Annotations list.
- **Engine chip** ([A1]) — light-mode-only; collapse into the existing badge token.
- **Primary button** ([C2, low]) — pale indigo fill with white text is borderline for normal text size (~3.0:1). *Fix:* deepen primary fill in dark mode (indigo-500/600) or invert to white-bg/indigo-text for the secondary variant.

---

## Cross-cutting patterns

These recur across ≥ 2 surfaces — highest leverage to fix once.

- **Dark-mode contrast regressions** — tag chip (A1, high), engine chip (A1, medium), primary button (C2, low). Suggests the design tokens / dark theme were not audited end-to-end. Run a Stark/Axe pass against the deployed dark mode and gate further token additions on a contrast check.
- **Front-matter pollution** — `section_type` is recorded but never used to filter or group surfaces. Affects Library "Continue reading" banner, BookSummaryPage Read CTA, and Sections list grouping. Treat front/back-matter as a first-class concept the UI knows how to demote.
- **Decision-anchored fields** ([F1]) — multiple surfaces show metrics that don't anchor a user decision: Chars / Compression on Sections tab; (no metadata at all on Summary tab — opposite problem). Run an F1 audit on every list/card/badge: name the user decision it informs in one sentence; if you can't, replace or remove.
- **Icon-only chrome without labels** ([C5]) — Library view-toggle (▦/☰/▤), Section ☰ drawer, sometimes ⋯. *Fix:* require every icon-only button to have either aria-label + tooltip, or icon + text at ≥ md viewport. Add an ESLint rule for `<button>` containing only emoji/single-char text.

---

## Deferred

(none — user dispositioned all surfaced findings as "Apply as proposed")

---

## Appendix A — PSYCH journey scores

See `psych-msf.md` for full tables. Headline:

| Journey | Cumulative | Severity | Worst step |
|---------|-----------:|----------|-----------|
| J1 Library → Book | 38 | Watch | 02_book_overview (-10) — broken pills + Overview filler + wrong Read |
| J2 Book → Section | 44 | OK | 02_book_overview (-8) — same as above |
| J3 Listen | 48 | OK | 06_listen_clicked (-3) — "Limited controls" reads as broken |

MSF Friction: J1 emotional 1, cognitive 1, interaction 1. J3 emotional 1.

---

## Appendix B — Raw findings

26 findings recorded in `eval-findings.json` (12 dispositioned as Apply, 14 medium/low surfaced in this report's body).

Screenshots in `screenshots/` — `01_library`, `02_book_summary_above_fold/full`, `03_book_sections_tab`, `04_book_audio_tab`, `05_section_detail_above_fold/full`, `06_listen_clicked_immediate`, `07_audio_playing`, `08_book_summary_tab_full`. Page snapshots (a11y trees) co-located.
