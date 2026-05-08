---
date: 2026-05-08
status: Draft
tier: 3 — Feature (multi-cluster bundle)
related:
  - docs/2026-05-08_design_crit/design-crit.md
  - docs/2026-05-08_design_crit/eval-findings.json
  - docs/2026-05-08_design_crit/psych-msf.md
  - docs/requirements/2026-05-08-audio-playback-fix.md
  - docs/requirements/2026-05-03-summary-and-audio-ux-fixes.md
---

# Design-Crit Followups (Library, Book, Section, Audio) — Requirements

## Problem

A live design crit on the local app surfaced **26 findings across 6 surfaces** (Library, BookSummaryPage Overview / Summary / Sections / Audio tabs, SectionDetail toolbar, Audio Playbar). Five high-severity issues either block accessibility, deliver anti-value at the dominant CTA, or break the document outline. The remaining 21 findings cluster into information-architecture and dark-mode-token gaps that compound to make the app *feel* unfinished even though every shipped feature works on the backend.

Concrete symptoms (verified live on `http://localhost:8000` against book id 1, 2026-05-08):

1. **Tag chips on `/books/:id` are unreadable in dark mode** — measured contrast ≈ 1.1 : 1 (WCAG AA needs 4.5 : 1). The chips render as featureless rectangles, indistinguishable from skeleton-loading placeholders. Same root cause (light-mode-only chip styling) hits the audio Playbar's engine chip and likely several other badges.
2. **The "Read" CTA on `/books/:id` and the Library "Continue reading" banner both route to the Copyright section.** `BookOverviewView.vue:199` picks `sections[0]` regardless of `section_type`; `BookSummaryTab.vue:165–170` repeats the bug. The most prominent action on the page delivers a 2,498-char copyright notice as its payoff.
3. **The Overview tab is dead air.** It renders a single sentence ("Use the Summary tab…") in the entire fold below the cover hero — wasting the default landing impression on every book.
4. **The Summary tab is a wall of unbroken markdown** with no TOC, no anchors, no back-to-top, and no metadata strip (preset / generated-at / eval pass-rate are invisible while the user is reading).
5. **The page document outline is broken** — two `<h1>` elements (banner = "Book Companion", main = book title) on every book / section page. Screen-reader users hear the brand twice.

The cluster of medium findings (Sections-tab dev-grade columns, no row affordance, toolbar overload, audio-player dead clock, missing resume-listening dock, icon-only Library glyphs) compound the same theme: functional features hidden behind fields that don't anchor decisions and chrome that doesn't match the user's mental model.

### Who experiences this?

The single user of this personal tool — a non-fiction reader running Book Companion locally to summarize and revisit books. The user enters the app warm (books exist, summaries exist), with high intent ("I want to resume a book / look up a concept / listen on the move"). Every friction in this report degrades that warm-intent experience.

There is no second persona. This is a solo-builder tool — there is no support burden, no onboarding flow, no marketing surface. That cuts the requirements but raises the bar on first-impression friction: the user IS the builder, and "looks unfinished" is felt acutely.

### Why now?

- A live design crit was just run (2026-05-08) producing 26 findings; this doc is the followup pipeline anchor.
- Prior cycles (`2026-04-30-reader-and-book-detail-ux-fixes`, `2026-05-03-summary-and-audio-ux-fixes`, today's `2026-05-08-audio-playback-fix`) have hardened the **functional** layer. The remaining defects are presentation-layer — the right kind of work for the next cycle.
- The dark-mode contrast bug is shippable-quality risk: anyone who scrolls past the cover thinks the page hasn't loaded.

## Goals & Non-Goals

### Goals

- **G1.** A first-time visitor to `/books/:id` sees a complete, scannable Overview dashboard within the fold — never a one-sentence filler — measured by **manual /verify pass + Playwright snapshot diff vs the design-crit screenshot**.
- **G2.** Clicking **Read** (anywhere — book card, Continue banner, BookSummaryPage CTA) lands on the first section whose `section_type ∈ SUMMARIZABLE_TYPES` — never on `copyright`/`acknowledgments`/`dedication`/`title_page`/`table_of_contents`/`colophon`/`cover`/`part_header`/`license` — measured by **Vitest unit test on the firstChapter helper + a seeded e2e against a book whose `sections[0].section_type === "copyright"`**.
- **G3.** Every chip/badge on `/`, `/books/:id`, `/books/:id/sections/:id`, `/concepts`, and `/annotations` passes WCAG AA contrast in **both** light and dark themes — measured by **Playwright + axe-core sweep run from the /verify ladder**. (Audit and verify scopes match — the cross-cutting risk is closed everywhere chips render.)
- **G4.** The Summary tab renders a sticky outline matching every `<h2>` and `<h3>` in the markdown, with anchor IDs that scroll to within ±32 px of the target — measured by **a Vitest test asserting anchor presence + an e2e click test on every outline entry**.
- **G5.** The Sections tab columns are decision-anchored only (`# | Title | Read time | Summary status`), with `section_type` shown as a leading icon, grouped under "Front matter / Chapters / Back matter" subheaders (front+back collapsed by default) — measured by a **DOM-structural Vitest assertion + manual visual review**.
- **G6.** Each `/books/:id` page has exactly one `<h1>` (the book title); each `/books/:id/sections/:id` has exactly one `<h1>` (the section title — promoted from today's breadcrumb-only treatment) — measured by **Playwright `page.locator("h1").count() === 1` assertion on both routes** plus a screen-reader smoke that announces the section title at landing.
- **G7.** Read-time on the Sections tab and the Overview Sections tile uses the formula **`ceil(content_char_count / 1100)` minutes** (≈ 250 wpm × 4.5 chars/word) — measured by **Vitest snapshot of the formatter**. The Sections tile aggregates by summing the per-section minutes and rendering as `Nh Mm`.

### Non-Goals (explicit scope cuts)

- **NOT** rebuilding the audio engine, fixing the Web Speech silent-Play bug, or redesigning the audio generation pipeline — *because* `2026-05-08-audio-playback-fix.md` owns the Playbar wiring and `2026-05-02-audiobook-mode` owns the synthesis path. This doc only addresses **audio chrome polish** (Limited-controls actionability, dead 0:00/0:00 timestamp, empty-state framing, ResumeAffordance wiring, sentence progress, engine-chip dark variant).
- **NOT** redesigning the Concepts or Annotations pages — *because* the crit only sampled 3 journeys. They likely have their own findings; defer to a future crit.
- **NOT** adding new summarization presets or eval assertions — *because* this is presentation-layer work; the model layer is intentionally untouched.
- **NOT** introducing real-time collaborative features, offline-first PWA support, or any cloud sync — *because* the tool is single-user-by-design (CLAUDE.md, V1 spec).
- **NOT** cleaning up the stale `SectionType` enum in `backend/app/db/models.py` (it diverges from `section_classifier.SECTION_TYPE_PATTERNS` — copyright/dedication/title_page/etc. aren't enum members) — *because* the source of truth is already the classifier and the DB column is `Mapped[str]`. Track as a hygiene chore in a follow-up; do not bundle into a UX doc.
- **NOT** redesigning the global navigation sidebar (BC wordmark, emoji icons) — *because* it works adequately; design-crit only flagged the wordmark obscurity (low). Defer.
- **NOT** fixing the Library "+ New View" feature, saved views, or the bulk-selection toolbar — *because* the crit's only Library findings (view-toggle labels + bulk-select chrome) are low-medium; bundle them into this doc but don't expand scope to the saved-views feature itself.

## User Experience Analysis

### Motivation

- **Job to be done:** "Open the app, find the book / section / concept I care about right now, and resume reading or listening with one obvious next click." Secondary jobs: "Glance at this book and feel oriented" (Overview tab), "Find what's in the summary without reading every word" (Summary tab TOC).
- **Importance:** High. The user opened the app *intentionally* — they're already past the install-and-onboard hurdle. Friction at the resumption surface is felt sharply; users abandon to the source EPUB or another tool when "Read" delivers Copyright.
- **Alternatives:** Reading the source EPUB in Apple Books / Calibre; using Readwise for highlights; listening via OS-level TTS on the source PDF. Book Companion's only edge is the *summary + concepts + annotations + audio* loop. Every friction in that loop reduces the marginal value over the alternatives.

### Friction Points

| Friction Point | Cause | Mitigation (covered by this doc) |
|---|---|---|
| "Did the page even load?" | Tag pills render as low-contrast rectangles in dark mode (1.1 : 1). | Full chip/badge dark-mode audit (D1). |
| "I clicked Read and got Copyright." | `firstSection = sections[0]` — no `section_type` filter. | First-chapter helper using `SUMMARIZABLE_TYPES` (D2). |
| "What's on this Overview tab?" | Tab is filler text. | 4-tile dashboard (Continue, Book summary, Top concepts, Sections meta) (D4). |
| "Where am I in this 200-bullet summary?" | No TOC / anchors / back-to-top. | Sticky right-rail outline + anchor IDs + FAB (D7). |
| "Which section should I read first / next?" | Sections tab shows raw chars + compression %, not read time; no grouping. | Read-time column + front/chapter/back grouping (D5). |
| "Is this row clickable?" | No hover, no chevron, no inline actions. | Row-as-button + hover bg + inline Listen/Read/More + chevron (D6). |
| "What does ☰ do?" | Icon-only, no aria-label. | Aria-label + tooltip + icon-text pair at md+ viewports (D8, D13). |
| "Why are my controls limited?" | "Limited controls" badge is non-actionable. | Tooltip + link to settings explaining Web Speech vs Kokoro (D10). |
| "What does 0:00 / 0:00 mean while audio is playing?" | Dead clock when engine is Web Speech (no duration API). | Hide on Web Speech; show real time on Kokoro (D11). |
| "Where was I in playback after I closed the player?" | No persistent resume affordance. | Finish wiring `ResumeAffordance` + dock on related pages (D12). |

### Satisfaction Signals

- The Overview tab is the first thing seen on every book — when it shows useful tiles, the user feels "this app knows my book."
- "Read" delivers a real chapter, every time.
- Tag chips read as actual tags, in either theme.
- The summary's outline reads like a magazine article, not a single column of bullets.
- Audio playback has either a clean clock (Kokoro) or a clean sentence counter (Web Speech), never an embarrassing fake clock.

## Solution Direction

The work splits into 6 clusters that share theme but are independently shippable. **Cluster A is shippable independently** (it touches the design-token system); Clusters C–F that introduce new chips/badges (Overview tiles, Sections row inline actions, Audio empty-state engine chip, Library view-toggle labels) **depend on Cluster A's chip-token fix**. Cluster B (read-position correctness) and the IA-only parts of C/D (TOC, toolbar regrouping, section-row affordance, Sections columns) have no Cluster-A dependency and can ship in parallel.

```
Cluster A — Dark-mode token audit
  └── tag-chip + engine-chip + primary-button + cross-cutting
       └── adds Playwright+axe sweep to /verify

Cluster B — Read-position correctness
  └── firstChapter helper (replace `sections[0]` 2 sites)
  └── purge stale "Copyright" continue-reading rows on next book load
  └── one h1 per page (banner heading → wordmark span)

Cluster C — BookSummaryPage IA
  └── Overview tab: 4-tile dashboard
  └── Summary tab: sticky right-rail TOC + anchor IDs + back-to-top FAB
  └── Sections tab: read-time column, front/chapter/back grouping, row affordance + inline actions
  └── (Summary tab metadata strip: preset / generated-at / eval pass-rate)

Cluster D — SectionDetail toolbar regrouping
  └── 3-cluster (nav | mode | actions) with subtle dividers
  └── Prev/next hit-area ≥40×40 + aria-label "Previous section: <title>"
  └── ☰ drawer relocate / aria-label
  └── Reader settings ⚙ keep (already labelled)

Cluster E — Audio polish (chrome only — playback bug owned elsewhere)
  └── Empty-state engine chip + estimate + scope + diff link
  └── Limited-controls tooltip + /settings link
  └── Hide 0:00/0:00 on Web Speech
  └── Finish wiring ResumeAffordance.vue + dock on book/section pages
  └── Sentence-progress bar
  └── Keyboard-shortcut tooltips + ? overlay

Cluster F — Library polish
  └── View-toggle: labelled icons + aria-label, persist selection
  └── Bulk-select checkboxes hidden until "Select" mode entered
```

Reusable infrastructure already present (per code recon — these change the implementation cost, not the requirements):

- `FRONT_MATTER_TYPES` and `SUMMARIZABLE_TYPES` exported from `frontend/src/stores/reader.ts`, mirrored in `backend/app/services/parser/section_classifier.py`, with a contract test enforcing parity.
- `TOCDropdown.vue` already exists for `SectionDetail`; pattern to extend to `BookSummaryTab`.
- `EngineChip.vue` is its own component (1-file dark variant change).
- `ResumeAffordance.vue` is partially scaffolded with empty function bodies — finish wiring rather than rebuild.
- `OverflowMenu.vue` available for row-level "More" affordance.

## User Journeys

### Primary Journey — "Continue reading" (warm user, one click)

1. User lands on `/`. The "Continue reading" banner shows the **last real chapter** they were reading (never Copyright).
2. They click **Continue** → routes to `/books/:id/sections/:lastSectionId`.
3. Section detail loads with the saved tab (`original` or `summary`) and the section content. Toolbar groups (nav | mode | actions) are visually distinct.
4. The user can resume reading (scroll), switch mode (Original | Summary), or click **Listen**.

### Primary Journey — "Open a book from the library"

1. User clicks a book card on `/`.
2. `/books/:id` loads showing **Overview** as the default tab. Tags are readable in dark mode.
3. The fold below the cover hero shows 4 tiles:
   - **Continue** — `Resume reading: § 4 · Chapter 1: Competition` (or `Start reading: Introduction` for first-time books).
   - **Book summary** — `Available · last generated 2 days ago · open Summary tab`.
   - **Top concepts** — 3–5 concept chips linking to the Concepts page filtered to this book.
   - **Sections** — `17 sections · ≈ 4h 20m read · See all`.
4. The user clicks any tile and lands on the right tab/page.

### Primary Journey — "Browse summary by heading"

1. User clicks the **Summary** tab on `/books/:id`.
2. The Summary tab renders the markdown with a sticky right-rail outline showing every H2 and H3.
3. User clicks an outline entry — page scrolls to within ±32 px of the heading.
4. Back-to-top FAB appears once the user has scrolled past the first viewport; click returns to top.

### Primary Journey — "Listen to a section"

1. User on `/books/:id/sections/:id` clicks **Listen** in the toolbar's actions cluster.
2. Playbar appears with the engine chip ("Web Speech" or "Kokoro"), sentence counter, and — if Web Speech — **no** dead `0:00/0:00` (hidden); on Kokoro, real time.
3. If "Limited controls" is shown, hovering it reveals: "Web Speech can't seek. Install Kokoro for full controls →" linking to /settings.
4. The user closes the player → a docked **Resume listening** strip appears at the bottom of the next page they navigate to ("Resume — Introduction · sentence 5 of 17"). Clicking re-opens the Playbar at that sentence.

### Alternate Journeys

- **Empty audio tab.** User opens `/books/:id?tab=audio` on a book with no audio. Empty state shows: "Generate audio for this book — engine: Web Speech (offline) / Kokoro (better quality, ~338 MB) — covers the 12 chapter summaries — ≈ 7 min on Kokoro / ≈ instant on Web Speech — [What's the difference?]". Clicking Generate posts the job; UI swaps to progress.
- **Empty Overview state (no summaries, no concepts, no annotations).** Tiles still render but each shows its empty CTA: Continue tile shows "Start reading: Introduction" if a SUMMARIZABLE section exists; Book summary tile shows "No book summary — Generate"; Top concepts tile shows "No concepts mined yet — Run extraction"; Sections tile is always populated.
- **Continue tile when no SUMMARIZABLE section exists** (book is mid-parse, or pure front-matter). Tile renders disabled with copy "Waiting for the first chapter to parse" — same wording as the disabled Read CTA. Symmetric across surfaces.
- **Section[0] is a chapter.** firstChapter helper still routes to `sections[0]` because the filter passes; behaviour identical to today.

### Error Journeys

- **Stale "Copyright" continue-reading row in DB** (legacy). On next call to `getContinueReading`, backend (or frontend filter) detects the row's `section_type` is in `FRONT_MATTER_TYPES` and either nulls it or rewrites it to the most recent non-front-matter position. Banner shows "Start reading" instead of an outdated landing.
- **Section[0] is a part_header / cover only (no chapters yet)** — book is partially parsed. Overview tile says "Parsing — N of M sections ready". Read CTA disabled with hint: "Waiting for the first chapter to parse."
- **Markdown summary has no H2s.** Sticky outline shows a single "Top" entry; back-to-top FAB still appears. Don't crash on empty outline.

### Empty States & Edge Cases

| Scenario | Condition | Expected Behavior |
|---|---|---|
| Book with no chapters yet | All `sections[*].section_type` ∈ `FRONT_MATTER_TYPES` ∪ `OTHER` | Read CTA disabled with copy "No chapter to open yet"; firstChapter falls back to `sections[0]` only when `SUMMARIZABLE_TYPES.find` is null AND book status is `parsed` |
| Tag chip in light theme | n/a | Existing styling unchanged; verify ≥4.5:1 |
| Tag chip in dark theme | n/a | New `dark:` variant active; verify ≥4.5:1 |
| Section with no summary | `default_summary_id` is null | Sections tab summary-status column shows ✕; row "Listen" inline action disabled |
| Audio Playbar on Web Speech | `engine === 'web-speech'` | 0:00/0:00 timestamp hidden; sentence counter shown |
| Audio Playbar on Kokoro | `engine === 'kokoro'` | Real time + sentence counter shown |
| User has scrolled past first viewport on Summary tab | `window.scrollY > viewportHeight` | Back-to-top FAB visible (bottom-right, dark variant) |
| User has not yet entered Library bulk-select mode | Default | Per-card checkboxes hidden |

## Design Decisions

> **Note for solo workflow:** Decisions intentionally cite specific file paths / component names where they materially clarify the bug site or reuse target. This is a doctrine bend (Tier 3 normally keeps these out) — justified because the spec/plan/execute cycle is single-author and the cost of re-finding the sites at /spec time outweighs the purity gain.

| # | Decision | Options Considered | Rationale |
|---|---|---|---|
| D1 | **Full chip/badge dark-mode audit, not just the 3 named.** Add a Playwright + axe sweep to `/verify`. | (a) Fix only tag/engine/primary-button. (b) Fix the 3 + token-test snapshot. (c) Audit all chip/badge components and add a Playwright sweep gate. | Option (c) — dispositioned in the design-crit interview. The root cause is a missing dark variant on the chip token; piecemeal fixes invite regression. The /verify gate is cheap (1 Playwright run) and catches future tokens that ship without a dark variant. |
| D2 | **Read CTA picks first SUMMARIZABLE section, falls back to `sections[0]` only if none qualify.** Same helper used by BookOverviewView, BookSummaryTab, ContinueBanner. | (a) Hard-code "first chapter" by `section_type === "chapter"`. (b) Use SUMMARIZABLE_TYPES (chapter, introduction, preface, foreword, epilogue, conclusion). (c) Use NOT-FRONT_MATTER (broader). | Option (b) — the SUMMARIZABLE_TYPES set is already exported and contract-tested. Introduction is a valid first read. Skipping back-matter (glossary/notes/about_author) avoids the symmetric "Read → About the Author" failure mode without inventing a new set. |
| D3 | **Demote banner heading from `<h1>` to a wordmark span/role=img.** Reserve h1 for the page subject. | (a) Keep banner as h1, add `aria-hidden` to main h1. (b) Demote banner to span. (c) Drop the banner heading entirely. | Option (b) — the banner serves a wordmark function (brand recognition + home link), not a heading function. Dropping it would lose the home-link affordance; aria-hidden a real heading hides content from AT users. A `<span class="wordmark">` with the link wrapping it cleanly resolves the duplicate-h1 issue without UI change. |
| D4 | **Overview tab = 4-tile dashboard:** Continue, Book summary, Top concepts, Sections meta. No metadata strip on Overview (lives on Summary tab only). | (a) 5+ tiles (add Recent annotations, Eval pass-rate). (b) 4 tiles as listed. (c) 3 tiles (drop Sections meta). (d) Replace Overview with default-redirect to Summary tab. | Option (b) — dispositioned in the brainstorm. Recent annotations dilutes focus on resumption; eval pass-rate belongs with the Summary it grades. The 4 tiles each answer a distinct user decision (resume / read summary / look up concepts / browse chapters). |
| D5 | **Sections columns = `# | Title | Read time | Summary status`. Type as leading icon. Group rows under Front matter / Chapters / Back matter subheaders (front+back collapsed by default).** | (a) Keep current columns + Type. (b) Read-time + Summary + Audio-status columns. (c) Title-only with chips on the right. (d) Read-time + Summary, with grouping. | Option (d) — dispositioned. Audio-status mixes a future feature (every section needs audio) with an Overview signal; defer. Chars/Compression are pure dev metrics; remove. Front/back collapsed by default puts the chapters in the natural F-scan position. |
| D6 | **Section row = button-style with hover bg, cursor-pointer, inline ▶ Listen + 📖 Read + ⋯ More icons revealed on hover, trailing chevron.** | (a) Whole row as `<button>`. (b) Title-as-link with hover but no inline actions. (c) Always-visible inline actions (no hover gating). | Option (a) — matches the affordance the design-crit prescribed. Hover-revealed actions keep the row scannable; always-visible actions clutter at 17+ rows. The wrapping element is a `<RouterLink>` (default route = read summary), with inline actions as nested buttons — pattern already used by `OverflowMenu`. |
| D7 | **Summary tab = sticky right-rail TOC (h2 + h3) + anchor IDs on every heading + back-to-top FAB after first-viewport scroll. Metadata strip above the markdown.** | (a) Top-of-page tab strip (one tab per H2). (b) Sticky right-rail TOC. (c) Floating left-edge accordion. (d) No nav, just back-to-top. | Option (b) — matches established reading-app conventions (Notion right rail, GitBook right rail) and is the only option that scales to 12+ headings without hiding the body. Anchor IDs derive from heading text + slugify (collision-safe with `-1`/`-2` suffixes). |
| D8 | **SectionDetail toolbar = 3 visually grouped clusters: nav (← →) | mode (Original/Summary segmented) | actions (Listen, ⚙). Drop the ☰ drawer entirely; the breadcrumb dropdown becomes the canonical sections picker, enriched with per-row read/summary/audio progress chips.** | (a) Keep flat row, add dividers only. (b) 3-cluster split, drawer in actions group. (c) 3-cluster split, drawer to left rail. (d) 3-cluster split, drawer merges into breadcrumb. (e) 3-cluster split, drawer dropped — breadcrumb is the picker. | Option (e) — single source of truth for jumping between sections. The drawer and the breadcrumb dropdown overlapped in purpose; the breadcrumb already has natural placement and just needs richer rows. Drops one button + one panel from the chrome. |
| D9 | **Audio empty state = engine chip + estimated synthesis time + content scope + "What's the difference?" link.** This decision **supersedes** any prior empty-state spec in `docs/requirements/2026-05-02-audiobook-mode-requirements.md`; the audiobook-mode doc's status header should be updated to flag this doc as the active source for the Audio-tab empty state. | (a) Status quo. (b) Add engine chip only. (c) Full empty-state framing as proposed. | Option (c) — Kokoro = ~338 MB + ffmpeg + espeak-ng install cost is invisible until the user starts; surface it in the empty state, the only place it's seen before the click. Single-owner supersession avoids divergence between the two docs. |
| D10 | **Limited-controls badge = tooltip + link.** Hover/focus reveals: "Web Speech can't seek/scrub. Install Kokoro for full controls →" linking to `/settings`. | (a) Static badge. (b) Inline expansion below the player. (c) Tooltip + link. | Option (c) — minimal chrome; uses existing tooltip pattern; one click recovers (no modal interrupt). |
| D11 | **Hide `0:00/0:00` timestamp when engine is Web Speech; show real time when engine is Kokoro.** | (a) Hide on Web Speech. (b) Replace with qualitative estimate ("≈ 4 min"). (c) Keep dead clock. | Option (a) — sentence counter already conveys progress; fake clock erodes trust more than missing clock. Qualitative estimate adds engineering for marginal value. |
| D12 | **Finish wiring `ResumeAffordance.vue` (currently scaffolded with empty function bodies). Dock at bottom of `/`, `/books/:id`, `/books/:id/sections/:id` when audio is paused/closed but a position is known.** Do NOT mount on `/concepts` or `/annotations` — list pages stay clean. | (a) Keep ResumeAffordance scaffold dormant; spec a new component. (b) Finish the existing component, mount on 3 reading-context pages. (c) Finish + mount on all 5 surfaces. | Option (b) — the file is scaffolded, the prop contract (`contentType`, `contentId`, `audioStatus`, `totalSentences`) already matches the audioPosition API. Cheaper to finish than to introduce a parallel component. List pages excluded to keep them browsing-focused. |
| D15 | **Sentence-progress bar = thin segmented strip above the Playbar.** N segments (one per sentence), completed-state shaded, current-state outlined. Renders on both Web Speech and Kokoro. | (a) Drop — counter is enough. (b) Continuous percentage bar (no segments). (c) Segmented N-of-N bar. | Option (c) — segments map 1:1 to the sentence counter, so user can correlate "sentence 5 of 17" with the visual. Continuous bar would be misleading on Web Speech where time is unknown. Decision row formalises what was previously only mentioned in Solution Direction. |
| D16 | **ContinueBanner (reading) and ResumeAffordance (listening) coordinate on `/` via most-recent-action-wins.** A single banner renders, picking whichever has the more recent `last_action_at` timestamp; the banner shows a leading icon (book = reading, headphones = listening) so the modality is unambiguous. | (a) Stack both banners. (b) Reading-only on `/`. (c) Listening-only on `/`. (d) Most-recent-action wins. | Option (d) — single resume affordance avoids chrome stacking; user always sees their most recent activity, which is what "Continue / Resume" means. Requires both stores to expose a comparable timestamp. |
| D13 | **Library view-toggle = labelled icon buttons (Tabler/Lucide grid / list / compact) with `aria-label` and persisted selection in localStorage.** | (a) Add aria-label only, keep glyphs. (b) Replace glyphs with proper icon set + aria-label. (c) Drop the toggle entirely. | Option (b) — a11y fix and visual fix in one. The glyphs (▦, ☰, ▤) are not from any icon library; replacing them removes a unique a11y-tax surface. |
| D14 | **Library bulk-select checkboxes hidden until user enters "Select" mode via toolbar button. When active, show sticky bulk-action bar.** | (a) Always-visible checkboxes. (b) Hidden until "Select" toggle. (c) Drop bulk-select entirely. | Option (b) — eliminates the "what does this checkbox do" cognitive cost on the default browse experience. Bulk select is rarely used; gating its UI behind explicit intent matches the 80/20. |

## Success Metrics

| Metric | Baseline (2026-05-08) | Target | Measurement |
|---|---|---|---|
| WCAG AA contrast violations on `/`, `/books/:id`, `/books/:id/sections/:id` (dark mode) | ≥ 1 (tag chip = 1.1 : 1) | 0 | Playwright + axe-core sweep on the 3 surfaces in dark mode; gate added to `/verify`. |
| `/books/:id` pages with `<h1>` count > 1 | 100 % | 0 % | Playwright `page.locator("h1").count()` assertion in the cross-surface e2e. |
| Read-CTA destinations whose `section_type ∈ FRONT_MATTER_TYPES ∪ {glossary, notes, appendix, bibliography, index, about_author, other}` | unknown but observed in the wild | 0 | Vitest unit test on the firstChapter helper covering all `SectionType` values; e2e against a seeded book whose `sections[0].section_type === "copyright"`. |
| Summary-tab anchors that scroll their heading into the viewport | 0 (no anchors today) | 100 % | Vitest assertion that anchor IDs exist for every H2/H3 in rendered markdown; e2e click test on every outline entry asserts heading is within ±32 px of viewport top. |
| Sections-tab columns matching the allowlist `["#", "Title", "Read time", "Summary"]` | partial (Chars + Compression present, Read time absent) | exact match | DOM-structural Vitest assertion against `SectionListTable` rendered output. |

## Research Sources

| Source | Type | Key Takeaway |
|---|---|---|
| `docs/2026-05-08_design_crit/design-crit.md` | Internal — design-crit report | 26 findings; this doc is the requirements anchor for the 6-cluster bundle. |
| `docs/2026-05-08_design_crit/eval-findings.json` | Internal — raw rubric findings | Per-finding rubric IDs (N/V/G/A/S/F/C/J), severity, evidence, suggested fix. |
| `docs/2026-05-08_design_crit/psych-msf.md` | Internal — PSYCH/MSF | J1 cum=38 (Watch); BookSummaryPage Overview is the worst step (-10). |
| `backend/app/services/parser/section_classifier.py` (FRONT_MATTER_TYPES, SUMMARIZABLE_TYPES) | Existing code | Authoritative section-type sets; mirrored on FE; contract-tested. Drives D2. |
| `frontend/src/stores/reader.ts:8-26` | Existing code | FE mirror of the section-type sets; ready to consume in firstChapter helper. |
| `frontend/src/views/BookOverviewView.vue:199` | Existing code | `firstSection = sections[0]` — the bug site. |
| `frontend/src/components/book/BookSummaryTab.vue:165-170` | Existing code | Same bug pattern in `readSectionSummaries`. |
| `frontend/src/components/audio/ResumeAffordance.vue` | Existing code | Scaffolded with empty function bodies — finish wiring (D12). |
| `frontend/src/components/reader/TOCDropdown.vue` | Existing code | TOC component already used in section-detail header; pattern extends to Summary tab. |
| `frontend/src/components/audio/EngineChip.vue` | Existing code | Stand-alone chip component — single-file dark-variant change. |
| `docs/requirements/2026-05-08-audio-playback-fix.md` | Adjacent requirements | Owns the silent-Play wiring bug; this doc only addresses audio chrome polish. |
| `docs/requirements/2026-05-03-summary-and-audio-ux-fixes.md` | Adjacent requirements | Prior cycle on the same surfaces; this doc handles findings the prior cycle did not. |
| Notion / GitBook right-rail TOC pattern | External (industry) | Sticky right-rail TOC for long-form reading is the established pattern (D7). |
| Linear / GitHub chip-with-dark-variant token system | External (industry) | Confirms D1 — "chip dark variant" is a token-system concern, not a component-by-component fix. |
| WCAG 2.2 SC 1.4.3, 2.4.6, 2.4.10 | External (standards) | Contrast (4.5 : 1 normal text), heading hierarchy, section landmarks — three standards this bundle aligns to. |

## Open Questions

| # | Question | Owner | Needed By |
|---|---|---|---|
| Q1 | "Top concepts" Overview tile — should it show concepts whose `book_id` matches this book only, or include cross-book concepts that *appear* in this book (i.e., concept linked via `concept_book_links`)? | Maneesh | Before /spec |
| Q2 | Sections-tab grouping — collapse front+back by default; do we persist the user's expand state per-book in localStorage, or reset every visit? | Maneesh | Before /spec |
| Q3 | "What's the difference?" link in audio empty state — does it open `/settings#audio-engines` (assumes a section exists) or a docs popover (no `/docs/...` route exists today)? | Maneesh | Before /spec |
| Q6 | Stale "Copyright" continue-reading rows — fix server-side (one-shot purge migration filtering FRONT_MATTER_TYPES) or client-side (banner ignores those rows on render)? Server-side is correct but adds an alembic migration. | Maneesh | Before /spec |

## Review Log

| Loop | Findings | Changes Made |
|---|---|---|
| 1 | (a) G6 ambiguous on SectionDetail h1; (b) Read-time formula referenced but undefined (Q4); (c) D8 drawer-vs-breadcrumb merge underspecified; (d) D9 overlaps with `2026-05-02-audiobook-mode-requirements`; (e) Implementation-detail leakage in Decisions; (f) Continue-tile empty state not specified. | (a) G6 promoted SectionDetail h1 + screen-reader smoke. (b) Added G7 with `ceil(chars/1100)` formula; struck Q4. (c) D8 rewritten — drawer dropped, breadcrumb dropdown is canonical picker. (d) D9 marked as superseding the audiobook-mode empty-state spec; status-header update tracked as a doc cleanup. (e) Added "Note for solo workflow" leading the Decisions table to acknowledge file-path inclusion as a deliberate doctrine bend. (f) Added explicit empty-state row for the Continue tile in Empty States table. |
| 2 | (a) D12 contradicted Q5 on ResumeAffordance dock surfaces; (b) G3 verification scope (3 surfaces) didn't match Cluster A audit scope (all chips); (c) Sentence-progress bar mentioned in Solution Direction but no Decision row; (d) ContinueBanner + ResumeAffordance both surface "resume" on `/` — uncoordinated. | (a) D12 narrowed to library + book + section; Q5 struck. (b) G3 extended to /concepts + /annotations; audit and verify scopes now match. (c) Added D15 — segmented sentence-progress bar. (d) Added D16 — most-recent-action-wins banner with modality icon. |
