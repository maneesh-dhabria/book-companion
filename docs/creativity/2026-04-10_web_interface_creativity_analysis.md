# Web Interface Creativity Analysis

**Date:** 2026-04-10
**Source:** [V1.1 Web Interface Requirements](../requirements/2026-04-10_web_interface_v1_requirements.md)
**Method:** 20 creativity techniques applied across 12 user journeys (5 batches), evaluated against 4 personas

---

## Personas

| Persona | Mode | Depth | Key Scenarios |
|---------|------|-------|---------------|
| **New User** | First session, wants value fast | Deep | (a) First upload + quick skim, (b) Exploring what's possible |
| **Power User** | 30+ books, advanced features | Deep | (a) Research session across library, (b) Batch operations |
| **Mobile Reader** | Phone/tablet, away from desk | Light | (a) Quick section reference, (b) Annotate on couch |
| **Quality Reviewer** | QA mode post-summarization | Light | (a) Review evals + compare versions, (b) Re-import + stale data |

---

## Journey Batches

| Batch | Journeys | Ideas Generated |
|-------|----------|-----------------|
| A: Onboarding & Upload | 4.1 Upload, 4.2 Summarize | 20 |
| B: Reading & Learning | 4.3 Read Section, 4.4 Annotate, 4.5 Ask AI | 20 |
| C: Discovery & Organization | 4.6 Search, 4.7 Library Views, 4.8 Reader Settings | 40 |
| D: Quality & Trust | 4.10 Compare Summaries, 4.11 Evaluate | 20 |
| E: Access & Data | 4.9 Mobile Access, 4.12 Export & Backup | 20 |
| **Total** | **12 journeys** | **120 ideas** |

---

## Consolidated Ideas by Technique

### Batch A: Onboarding & Upload (J4.1, J4.2)

| # | Technique | Journey | Idea | Affected Screen | Persona Impact |
|---|-----------|---------|------|-----------------|----------------|
| A1 | Add Constraints | 4.1 | Limit Quick Upload to books <50MB / <30 sections; force full wizard for complex books | Upload Step 1 | New+++ Power+ |
| A2 | Remove Constraints | 4.2 | Allow summarization to start before structure review is finalized — process sections in parallel | Book Detail + Progress | New++ Power+++ |
| A3 | Combine | 4.1 | Duplicate detection becomes "re-summarize with different preset?" workflow entry point | Duplicate Dialog | New+++ Power++ |
| A4 | Solve Multiple | 4.1 | Structure review shows quality warnings AND token cost per section in one pass | Upload Step 3 | Power+++ Quality+++ |
| A5 | Do Opposite | 4.2 | Auto-run default preset immediately; offer "Try different preset" post-hoc — results first | Preset Picker / Book Detail | New+++ Mobile+++ |
| A6 | Much Bigger | 4.1 | First-visit Library = entire viewport is drag-drop zone with ghost book spines | Library (empty) | New+++ |
| A7 | Much Smaller | 4.2 | Collapse summarize flow to single FAB — tap, auto-select last preset, confirm chip, go | Book Detail | Power+++ Mobile+++ |
| A8 | Only Thing | 4.1 | Step 2 metadata: full-screen focus mode, only cover/title/author/tags visible | Upload Step 2 | New+++ |
| A9 | Remove Friction | 4.1 | Auto-populate metadata from EPUB, default state is "looks good, continue" — single tap | Upload Step 2 | New+++ Power+++ Mobile+++ |
| A10 | Add Friction | 4.1 | Require at least one tag before Quick Upload completes | Upload Step 1 | Power++ |
| A11 | Reduce Anxiety | 4.2 | Show "This will take ~4 min" with section count breakdown before starting | Preset Picker (pre-start) | New+++ Mobile+++ |
| A12 | Feel Smarter | 4.1 | Post-clean-structure insight: "18 chapters, well-structured. No edits needed." | Upload Step 3 transition | New+++ Quality++ |
| A13 | Unnecessary | 4.1 | Eliminate Step 4: auto-select best preset by genre/length, show as confirmation chip | Upload Step 4 | New+++ Mobile+++ |
| A14 | Reframe | 4.2 | Rename "Summarize" to "Extract Knowledge" | Book Detail action | Power+++ |
| A15 | Distribution | 4.1 | "Share upload link" for resuming wizard across sessions/devices on LAN | Upload Step 1 | Mobile+++ |
| A16 | Unexpressed Need | 4.2 | "Sections worth reading in full" — flag high-compression sections during SSE progress | Progress Card | Power+++ Quality+++ |
| A17 | Surprise | 4.1 | Random "first insight" from ToC after upload: "Ch. 7 is probably the one you came for" | Upload Step 1→2 | New+++ |
| A18 | Bundle | 4.2 | Bundle preset + eval + auto-retry into single "Processing Profile" — one choice | Preset Picker | New+++ Mobile+++ |
| A19 | Unbundle | 4.1 | Separate "Add to library" from "Process book" — upload ends at library entry | Upload + Book Detail | Power+++ |
| A20 | Skeuomorphic | 4.1 | Structure review as visual ToC with indented hierarchy, styled like printed book | Upload Step 3 | New+++ |

### Batch B: Reading & Learning (J4.3, J4.4, J4.5)

| # | Technique | Journey | Idea | Affected Screen | Persona Impact |
|---|-----------|---------|------|-----------------|----------------|
| B1 | Add Constraints | 4.5 | Limit AI threads to one book's context by default; cross-book requires explicit opt-in | AI Chat sidebar | Power++ Quality++ |
| B2 | Remove Constraints | 4.4 | Allow annotations on Summary view (already in requirements, but emphasized as first-class) | Reader Summary view | New++ Mobile++ |
| B3 | Combine | 4.3+4.5 | Concept chip click opens AI tab with auto-seeded thread: "Explain [concept] in this section" | Concept tooltip + AI Chat | New+++ Power++ |
| B4 | Solve Multiple | 4.4+4.5 | "Save AI response" also creates concept tag + searchable freeform note on section | AI Chat sidebar | Power+++ Quality++ |
| B5 | Do Opposite | 4.3 | Show Summary first by default, let users reveal Original on demand | Book Detail toggle | New+++ Mobile+++ |
| B6 | Much Bigger | 4.5 | Full-screen "Deep Research" mode: AI as main panel, TOC as left panel | AI Chat → full-screen | Power+++ |
| B7 | Much Smaller | 4.4 | Single-tap highlight on mobile; long-press for other actions (Note, AI, Link, Copy) | Floating toolbar (mobile) | Mobile+++ |
| B8 | Only Thing | 4.3 | Focus Mode (`f` key): collapse header, hide sidebar, leave only reading area + arrow nav | Book Detail | Power++ |
| B9 | Remove Friction | 4.5 | Auto-create first AI thread on tab open — no "New Thread" click needed | AI Chat sidebar | New+++ Mobile+++ |
| B10 | Add Friction | 4.4 | 2-step delete: "Archive instead?" first, then "Delete permanently" | Annotation delete | Power++ Quality++ |
| B11 | Reduce Anxiety | 4.3 | Replace pass/fail count with plain language: "This summary is solid — 14/16 checks passed" | Eval banner | New+++ Mobile++ |
| B12 | Feel Smarter | 4.5 | "What you figured out" card: auto-summary of thread conclusions at top of thread list | AI Chat thread list | New++ Power++ |
| B13 | Unnecessary | 4.3 | Auto-advance sections on scroll completion — reading a whole book becomes passive | Book Detail reading area | New+++ Mobile+++ |
| B14 | Reframe | 4.4 | Rename "Annotations" to "Your Notes" across all UI | Annotations sidebar + page | New+++ |
| B15 | Distribution | 4.5 | "Share this thread" exports AI conversation as Markdown for Obsidian/Notion/clipboard | AI Chat thread actions | Power+++ |
| B16 | Unexpressed Need | 4.3 | Re-entry card on section open after gap: "Last time, you highlighted: '...'" | Book Detail header | Power+++ Mobile+++ |
| B17 | Surprise | 4.3 | Concept chip clicked 3+ times across books shows: "You keep returning to this — 4 books" | Concept tooltip | Power+++ |
| B18 | Bundle | 4.3+4.4 | "Study Mode": summary left, notes right, AI prompt bar bottom — one unified panel | Book Detail layout | Power+++ Quality++ |
| B19 | Unbundle | 4.4 | Annotations page: split into "Browse" (filter/group) and "Review" (flashcard-style) modes | Annotations page | Power+++ Mobile++ |
| B20 | Skeuomorphic | 4.4 | Highlights as hand-drawn marker strokes (SVG clip path), sidebar cards as sticky notes | Reader + Annotations sidebar | New+++ |

### Batch C: Discovery & Organization (J4.6, J4.7, J4.8)

| # | Technique | Journey | Idea | Affected Screen | Persona Impact |
|---|-----------|---------|------|-----------------|----------------|
| C1 | Add Constraints | 4.6 | Hard cap at 3 results/category in palette + "Why this result?" tooltip (BM25/semantic) | Command palette | Power++ |
| C2 | Add Constraints | 4.7 | Cap saved views at 5 ("Bookshelf Slots") — forces intentional curation | View tab bar | Power+ |
| C3 | Remove Constraints | 4.6 | Cmd+K works offline against locally cached BM25 index | Command palette | Mobile++ |
| C4 | Remove Constraints | 4.8 | Replace popover with persistent slim settings bar docked to reader bottom | Reader page | Mobile++ New+ |
| C5 | Combine | 4.6+4.8 | Cmd+K accepts commands: "set font Serif", "Night Reading" — search + settings unified | Command palette | Power+++ |
| C6 | Combine | 4.7+4.6 | Saved views appear as results in Cmd+K ("Open Research Session view") | Command palette + Library | Power++ |
| C7 | Solve Multiple | 4.7 | Active library filters scope Cmd+K search — browse and search share context | Filter row + Command palette | Power+++ Quality+ |
| C8 | Solve Multiple | 4.8 | Attach reading presets to Section Types (Compact→Glossary, Night→long chapters) | Reader settings | Power++ |
| C9 | Do Opposite | 4.6 | "What should I read next?" card on empty search — system searches for user | Search empty state | New++ Mobile+ |
| C10 | Do Opposite | 4.7 | Start with all filters applied, user "allows" books through — subtractive model | Library filter row | Power++ |
| C11 | Much Bigger | 4.6 | "Research Mode": two-panel search+scratchpad, drag results into notes | Full search results | Power+++ |
| C12 | Much Bigger | 4.7 | Table mode "Spreadsheet Expand": full-screen editable grid with inline eval/tags/presets | Book table | Power+++ Quality++ |
| C13 | Much Smaller | 4.8 | Single "Density" slider controls font size + line spacing + width as coordinated system | Reader settings | New+++ Mobile+++ |
| C14 | Much Smaller | 4.7 | Collapse saved views to single dropdown on mobile (no horizontal scroll tabs) | Library (mobile) | Mobile++ |
| C15 | Only Thing | 4.6 | "Search Mode" toggle replaces library page with full-screen search interface | Library page | Power++ |
| C16 | Remove Friction | 4.6 | Auto-submit Cmd+K after 800ms no-typing (no Enter required) | Command palette | Mobile++ New+ |
| C17 | Remove Friction | 4.7 | One-click "Save current view" when filters differ from default; auto-names by filter | View tab bar | Power++ New+ |
| C18 | Remove Friction | 4.8 | Detect system dark mode on first launch, pre-select matching background swatch | Reader settings | New++ Mobile+ |
| C19 | Add Friction | 4.7 | Type view name to confirm deletion — prevents losing complex filter sets | View delete confirm | Power+ |
| C20 | Add Friction | 4.6 | "Low confidence" badge on semantic results below threshold; click to expand | Full search results | Quality++ |
| C21 | Reduce Anxiety | 4.7 | Live "X books match" count inside each filter dropdown option before applying | Library filter row | New+++ Power+ |
| C22 | Reduce Anxiety | 4.8 | Persistent "Reset to default" link in popover footer — experimentation feels safe | Reader settings | New++ |
| C23 | Feel Smarter | 4.6 | Post-search summary: "You explored 4 books, 12 sections" | Full search results | Power+ |
| C24 | Feel Smarter | 4.7 | Mini sparkline of eval scores in Table mode Eval column | Book table | Quality++ Power+ |
| C25 | Unnecessary | 4.8 | Auto-detect time-of-day + system dark mode, silently apply appropriate preset | Reader settings | New++ Mobile++ |
| C26 | Unnecessary | 4.7 | Auto-generate "Recently Active" view based on last-opened books | Library view tabs | Power++ New+ |
| C27 | Reframe | 4.7 | Rename "Filter" to "Lens" — views as perspectives, not search parameters | Library filter/view UX | New+ |
| C28 | Reframe | 4.6 | Empty state: "First to explore this" instead of "No results" | Search empty state | New++ |
| C29 | Distribution | 4.6 | "Share search" copies URL with query + filters encoded | Full search results | Power+ |
| C30 | Distribution | 4.7 | "Export this view" generates portable JSON filter spec | View tab actions | Power+ |
| C31 | Unexpressed Need | 4.6 | "Surprise me" button returns random high-eval section user hasn't visited recently | Search empty state | New++ Mobile++ |
| C32 | Unexpressed Need | 4.8 | "Suggest a setting" nudge after 10 sessions: "You read after 9pm — try Night Reading?" | Reader settings | New+ Mobile+ |
| C33 | Surprise | 4.8 | OLED swatch selection triggers brief star-field particle animation (1.5s) | Reader settings | New+ |
| C34 | Surprise | 4.6 | Weekly "Rediscovery" pin in Cmd+K: section from 30+ days ago matching current query | Command palette | Power++ Mobile+ |
| C35 | Bundle | 4.7+4.8 | "Reading Context": one saved item captures library filters + reader display settings | Library + Reader settings | Power+++ |
| C36 | Bundle | 4.6+4.7 | "Search within Library" mode: search results inline on library page, scoped by filters | Library + Search results | Power++ |
| C37 | Unbundle | 4.7 | Separate display mode (Grid/List/Table) from saved views — display is global preference | Library views | Power+ New+ |
| C38 | Unbundle | 4.8 | Separate typography (font/size/spacing) from theme (background/color) in settings | Reader settings | New++ Mobile+ |
| C39 | Skeuomorphic | 4.7 | "Spine view" toggle in grid mode: books as vertical spines on a shelf | Library grid | New++ |
| C40 | Skeuomorphic | 4.8 | Content width slider as a tiny open-book icon that widens as you slide | Reader settings | New+ |

### Batch D: Quality & Trust (J4.10, J4.11)

| # | Technique | Journey | Idea | Affected Screen | Persona Impact |
|---|-----------|---------|------|-----------------|----------------|
| D1 | Add Constraints | 4.10 | Lock comparison to same section only — no cross-section diffs | Comparison view | Quality+++ |
| D2 | Remove Constraints | 4.10 | Allow cross-book comparison for thematically similar sections | Comparison view | Power+++ |
| D3 | Combine | 4.11 | Failed assertion → sticky note annotation on eval detail (QA journal) | Eval detail page | Quality+++ |
| D4 | Solve Multiple | 4.11 | "Fix & Re-eval": pre-scroll to problem span, edit, auto-trigger re-eval — one action | Eval detail + Summary editor | Quality+++ Power++ |
| D5 | Do Opposite | 4.10 | Highlight what stayed the same: "stable concepts" strip above diff | Comparison view | Power++ New++ |
| D6 | Much Bigger | 4.11 | "Eval Wall" full-screen: all 16 assertions as large cards, no accordion | Eval detail page | Quality+++ |
| D7 | Much Smaller | 4.10 | Single-row "diff bar" showing % overlap, tooltip with top 3 divergences — inline | Summary list view | Mobile+++ New++ |
| D8 | Only Thing | 4.11 | Library-level "Trust Dashboard": every book's trust badge in a sortable grid | New library screen | Quality+++ Power++ |
| D9 | Remove Friction | 4.10 | Auto-select two most recent summaries when comparison opens — no dropdown needed | Comparison view | New+++ Mobile+++ |
| D10 | Add Friction | 4.11 | Require one-sentence note before dismissing a yellow "Review" eval | Eval trust badge | Quality+++ |
| D11 | Reduce Anxiety | 4.11 | "What this means" tooltip on every assertion name — plain English | Eval detail page | New+++ Quality++ |
| D12 | Feel Smarter | 4.11 | Score animation + glow on trust badge after re-eval improves score | Eval detail + trust badge | Quality+++ New++ |
| D13 | Unnecessary | 4.10 | "Notable change" badge on summary list when new version differs meaningfully | Summary list view | Power+++ Mobile++ |
| D14 | Reframe | 4.11 | Rename "Evaluate" to "Verify" throughout — user verifying AI, not AI grading itself | All eval surfaces | New+++ |
| D15 | Distribution | 4.10 | "Share comparison" exports self-contained HTML diff + concept map | Comparison view | Power+++ |
| D16 | Unexpressed Need | 4.11 | Book-level "Consistency score" — variance across section evals, not just averages | Book detail eval banner | Quality+++ Power++ |
| D17 | Surprise | 4.10 | Auto-generated "What changed?" one-sentence explanation at >60% divergence | Comparison view | New+++ Mobile++ |
| D18 | Bundle | 4.11 | Include eval scorecard appendix in summary exports (Markdown/PDF) | Export flow | Power+++ Quality++ |
| D19 | Unbundle | 4.10 | Standalone "Concepts" tab for concept divergence, separate from full comparison | Section reader | Power+++ Mobile++ |
| D20 | Skeuomorphic | 4.11 | Trust badge as rubber-stamp aesthetic: "TRUSTED" / "UNDER REVIEW" / "FLAGGED" | Eval trust badge | New+++ Quality++ |

### Batch E: Access & Data (J4.9, J4.12)

| # | Technique | Journey | Idea | Affected Screen | Persona Impact |
|---|-----------|---------|------|-----------------|----------------|
| E1 | Add Constraints | 4.9 | Mobile = read-only by default with banner; changes sync from desktop only | Mobile navigation | Mobile++ Power+ |
| E2 | Remove Constraints | 4.12 | Allow export during summarization — partial export with "processing" watermark | Export dialog | Power++ |
| E3 | Combine | 4.9+4.12 | QR code offers "Open App" OR "Download today's export" | Settings QR area | Mobile++ |
| E4 | Solve Multiple | 4.12 | "Send to self": 60-second LAN URL auto-triggers download on any LAN device | Export dialog | Mobile+++ Power++ |
| E5 | Do Opposite | 4.9 | "Cast to nearby device" pushes current page URL to detected LAN phones | Settings > General | Mobile++ New++ |
| E6 | Much Bigger | 4.9 | Full offline-first: every book auto-cached for mobile, syncs deltas on reconnect | Mobile + service worker | Mobile+++ Power++ |
| E7 | Much Smaller | 4.12 | "Quick snapshot": one tap in breadcrumb exports current section summary as plain text | Breadcrumb actions | Mobile+++ New++ |
| E8 | Only Thing | 4.9 | Mobile opens directly to most recently read section, full-screen, no nav chrome | Mobile reader (first load) | Mobile+++ New++ |
| E9 | Remove Friction | 4.12 | Remember last export settings per book — pre-fill on next open | Export dialog | Power++ |
| E10 | Add Friction | 4.12 | Restore: show diff summary + require typing "RESTORE" to confirm | Backup restore | Power++ Quality++ |
| E11 | Reduce Anxiety | 4.12 | "Last backup: 3 days ago" badge in Settings nav + growth nudge | Settings sidebar | Power++ New+ |
| E12 | Feel Smarter | 4.12 | Post-export stats card: "28 books, 340 summaries, 1240 concepts — 3 years of reading" | Export success state | New++ Power+ |
| E13 | Unnecessary | 4.12 | Auto-backup on schedule (daily/weekly) with silent background pg_dump | Settings > Backup | Power+++ New++ |
| E14 | Reframe | 4.9 | Rename "Allow LAN Access" to "Read on your phone" | Settings > General | New+++ |
| E15 | Distribution | 4.12 | "Share summary": self-contained HTML page of one book's summary + concepts | Export dialog | Mobile++ New+ |
| E16 | Unexpressed Need | 4.9 | Cross-device reading position continuity: "Continue where you left off: Ch. 4" | Mobile reader first load | Mobile+++ Power++ |
| E17 | Surprise | 4.12 | Post-export "Reading Report": top themes, most-annotated authors, concept frequency | Export success state | Power++ New+ |
| E18 | Bundle | 4.9+4.12 | "Mobile Setup Kit": one action enables LAN, QR, backup, caches 5 recent books | Settings > General | New+++ |
| E19 | Unbundle | 4.12 | Split backup (shield, danger zone) from export (arrow-out, library) — distinct flows | Settings restructure | Quality++ Power+ |
| E20 | Skeuomorphic | 4.12 | Export dialog as tabbed manila folder — each include option is a physical tab | Export dialog | New++ Mobile+ |

---

## Prioritized Recommendations

*Status: AGREED — cherry-picked by user on 2026-04-10. Dropped items noted inline.*

### MUST (High impact, addresses core UX gaps) — ALL 8 ACCEPTED

| ID | Idea | Source | Journeys | Screens | Effort | Rationale |
|----|------|--------|----------|---------|--------|-----------|
| M1 | **Summary-first default**: Show Summary view by default when summaries exist; Original on demand | B5 | 4.3 | Book Detail toggle | Low | Core value proposition is summaries — current default forces an extra click to see them |
| M2 | **Auto-populate metadata + single-tap advance**: Pre-fill title/author/cover from EPUB, treat Step 2 as confirmation not form | A9 | 4.1 | Upload Step 2 | Low | Biggest friction reducer in upload wizard; 90% of metadata is correct from EPUB |
| M3 | **Plain-language eval labels**: "What this means" tooltips on assertion names + "This summary is solid" phrasing on banner | B11, D11 | 4.3, 4.11 | Eval banner + detail page | Low | Eval is core differentiator but unusable for New Users without jargon translation |
| M4 | **Auto-create first AI thread on tab open**: Skip "New Thread" click, seed with current section | B9 | 4.5 | AI Chat sidebar | Low | First-contact activation barrier kills adoption of highest-value feature |
| M5 | **Live filter counts**: Show "X books match" inside dropdown options before applying | C21 | 4.7 | Library filter row | Low | Standard UX pattern; prevents dead-end empty states that erode trust |
| M6 | **Auto-backup on schedule**: Silent daily/weekly pg_dump to local folder | E13 | 4.12 | Settings > Backup | Medium | Single-machine knowledge base without auto-backup is a data loss risk |
| M7 | **"Read on your phone" rename + bundled setup**: Friendly label, one-action LAN+QR+cache | E14, E18 | 4.9 | Settings > General | Low | Technical label blocks adoption of mobile use case |
| M8 | **Rename "Evaluate" to "Verify"**: User verifies AI, not AI grading itself | D14 | 4.11 | All eval surfaces | Low | Small copy change, large mental model shift — increases eval engagement |

### SHOULD (Strong UX improvements, moderate effort) — 9/10 ACCEPTED

| ID | Idea | Source | Journeys | Screens | Effort | Rationale |
|----|------|--------|----------|---------|--------|-----------|
| S1 | **Concept chip as AI on-ramp**: Click concept → AI thread seeded with "Explain [concept]" | B3 | 4.3, 4.5 | Concept tooltip + AI Chat | Medium | Collapses reading+concepts+AI into one gesture; highest-leverage interaction |
| S2 | **Processing Profile bundle**: Merge preset+eval+auto-retry into single named choice | A18 | 4.2 | Preset Picker | Medium | Reduces 3 decisions to 1; reusable across books |
| S3 | **Re-entry card**: "Last time in Ch.3, you highlighted: '...'" on section open after gap | B16 | 4.3 | Book Detail header | Medium | Solves re-entry amnesia with existing annotation data |
| S4 | **Cross-device reading position**: "Continue where you left off" on mobile first load | E16 | 4.9 | Mobile reader | Medium | Core expectation for multi-device; absence erodes mobile use case |
| S5 | **Filter-scoped search**: Active library filters constrain Cmd+K results | C7 | 4.6, 4.7 | Filter row + Command palette | Medium | Unifies browse and search contexts — stops mental model mismatch |
| ~~S6~~ | ~~"Sections worth reading in full": Flag high-compression sections during SSE progress~~ | ~~A16~~ | ~~4.2~~ | ~~Progress Card~~ | ~~Low~~ | **DROPPED** |
| S7 | **Annotations: Browse vs Review modes**: Split into filter/group + flashcard-style review | B19 | 4.4 | Annotations page | Medium | Two genuinely different mental models; Review mode is mobile-native |
| S8 | **Auto-select recent summaries in comparison**: No dropdown needed for first diff | D9 | 4.10 | Comparison view | Low | Removes friction on a screen that should be fast to scan |
| S9 | **Book-level consistency score**: Variance across section evals, not just averages | D16 | 4.11 | Book detail eval banner | Medium | Solves unexpressed need: whole-book trust vs per-section scores |
| S10 | **Detect system dark mode on first launch**: Pre-select matching background swatch | C18 | 4.8 | Reader settings | Low | Zero-config correct default for 50%+ of users |

### NICE-TO-HAVE (Creative enhancements, lower priority) — 10/14 ACCEPTED

| ID | Idea | Source | Journeys | Screens | Effort | Rationale |
|----|------|--------|----------|---------|--------|-----------|
| N1 | **Cmd+K as command surface**: Accept "set font Serif", "Night Reading" etc. | C5 | 4.6, 4.8 | Command palette | High | Power user accelerator; complex to implement well |
| N2 | **"What changed?" auto-explanation**: One-sentence diff summary at >60% divergence | D17 | 4.10 | Comparison view | Medium | Saves synthesis effort on comparison screen |
| ~~N3~~ | ~~Rediscovery pin in Cmd+K: Weekly pin of old semantically-relevant section~~ | ~~C34~~ | ~~4.6~~ | ~~Command palette~~ | ~~Med~~ | **DROPPED** |
| ~~N4~~ | ~~Study Mode layout: Summary left, notes right, AI prompt bottom~~ | ~~B18~~ | ~~4.3-4.5~~ | ~~Book Detail~~ | ~~High~~ | **DROPPED** |
| N5 | **Focus Mode** (`f` key): Collapse all chrome, leave only reading area + arrow nav | B8 | 4.3 | Book Detail | Low | Clean reading experience; minimal implementation |
| N6 | **"Quick snapshot" export**: One tap in breadcrumb copies section summary as text | E7 | 4.12 | Breadcrumb actions | Low | Fastest path to sharing a single section |
| N7 | **Skeuomorphic highlights**: Hand-drawn marker strokes via SVG clip path | B20 | 4.4 | Reader highlights | Medium | Distinctive visual identity; reduces "cold database" feel |
| N8 | **Score animation on re-eval improvement**: Counter animates up, badge glows | D12 | 4.11 | Eval detail + badge | Low | Micro-celebration for quality improvement |
| N9 | **Export stats card**: "28 books, 1240 concepts — 3 years of reading" | E12 | 4.12 | Export success | Low | Emotional reward that reinforces product value |
| N10 | **"Surprise me" button on empty search**: Random high-eval unvisited section | C31 | 4.6 | Search empty state | Low | Discovery feature for growing libraries |
| N11 | **Rename "Annotations" to "Your Notes"**: Personal knowledge framing | B14 | 4.4 | All annotation surfaces | Low | Reduces intimidation; signals personal knowledge capture |
| N12 | **Fix & Re-eval one-click**: Pre-scroll to problem, edit, auto-retrigger eval | D4 | 4.11 | Eval detail + editor | High | Tight QA feedback loop; complex editor integration |
| ~~N13~~ | ~~Restore diff + typed confirmation: Show data counts + require "RESTORE"~~ | ~~E10~~ | ~~4.12~~ | ~~Backup restore~~ | ~~Low~~ | **DROPPED** |
| ~~N14~~ | ~~Reading Context bundle: library filters + reader settings together~~ | ~~C35~~ | ~~4.7-4.8~~ | ~~Library + Reader~~ | ~~High~~ | **DROPPED** |

---

## Cross-Cutting Themes

| Theme | Ideas | Insight |
|-------|-------|---------|
| **Results before configuration** | A5, A9, A13, B5, B9, D9 | Users want value immediately; defer decisions until after they've seen output |
| **Plain language over jargon** | B11, B14, D11, D14, E14 | Every technical label is a barrier for New Users; rename for the mental model, not the implementation |
| **Existing data as UX signals** | A16, B16, B17, D13, D16 | The system already knows things (compression ratios, annotation history, eval variance) — surface them proactively |
| **One gesture, multiple outcomes** | B3, B4, C7, A18, E18 | The best features collapse 3 separate interactions into 1 intentional action |
| **Mobile as continuation, not recreation** | E8, E16, C14, B7 | Phone use is about continuing desktop work, not starting from scratch — context handoff is essential |
