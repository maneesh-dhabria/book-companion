# Cross-Surface UX Cohesion Bundle — Requirements

**Date:** 2026-05-01
**Status:** Draft
**Tier:** 2 — Enhancement bundle

## Problem

Browsing the app surfaces a recurring pattern: small UX defects, dead controls, and inconsistent component choices that erode trust in the polish of an otherwise solid tool. The defects span the **Book Detail page**, the **Section Reader**, the app shell, and four **Settings** pages — they are individually small but collectively make the product feel stitched together. Several controls look interactive but do nothing, several read-outs lie (char counts of `0`, migration status of `FAILED:`), and two settings pages diverge in look-and-feel from the rest of the app.

### Who & Why Now
- **Persona:** the primary user (Maneesh) actively browsing and using the app for book reading + summarization.
- **Why now:** an exploratory pass through `/books/3`, the section reader, and `/settings/*` produced 18 distinct issues in a single session — a strong signal that a focused UX cohesion pass is overdue. The two preceding bundles (`2026-04-30-reader-and-book-detail-ux-fixes`, `2026-04-30-reader-settings-popover-consolidation`) closed earlier debt; this one closes the next layer surfaced once those landed.

## Goals & Non-Goals

### Goals
- Every button and menu item on the affected surfaces either does what its label promises or is removed.
- The Book Detail page presents a clear, **first-principles toolbar**: one primary CTA, one overflow menu, no orphaned controls.
- The Book Detail page is the single, obvious home for both **reading** and **reading the book summary** — including a clear path to *generate* the book summary when one does not exist.
- The Section Reader's summary tab renders Markdown (bullets, tables) legibly and provides a clear way to move between adjacent sections without returning to the index.
- The TOC dropdown shows accurate per-section character counts (matching the Book Detail table).
- The Annotations and AI Chat side panels visually belong to the same surface as the reader they sit beside (theme-aware).
- All Settings pages share the same form/layout vocabulary; each settings table uses the same data-table component.
- The Presets settings page lets the user **create, edit, and delete user presets** and **inspect prompt templates of system presets** without opening a terminal.
- The Reading Settings preset pills look and behave the same as the equivalent component in the reader settings popover.
- All `cosmetic` defects (clickable home links, compression formatting, alternate-row stripes) are corrected.

### Non-Goals
- **NOT** redesigning the reader, book detail, or settings information architecture beyond what's listed — because this bundle is a polish/cohesion pass, not an IA rework.
- **NOT** introducing a new design system or component library — because the existing CSS-variable + scoped-style pattern (used by every settings page except LLM) is the de-facto standard and we should converge on it.
- **NOT** building preset *sharing/import/export* — because the immediate gap is local CRUD, and import/export is a separable concern.
- **NOT** changing how summaries are generated, evaluated, or stored — because every issue here is a presentation/control bug, not a model or pipeline bug.
- **NOT** reworking the annotation highlight engine itself — because the gap is whether highlights *appear* in the summary tab; if the engine is correct the fix is wiring it on the summary content, not redesigning it.

## Solution Direction

Group the 18 items into **6 workstreams** that match the affected surfaces. Each workstream is a coherent set of changes a single contributor can land in one PR.

```
1. Book Detail toolbar reshape       (items 1, 3)
2. Book Detail data presentation     (item 5 — compression formatting in Sections table)
3. Book summary placement + CTA      (item 2 — adds "Summary" tab to Book Detail)
4. Section Reader polish             (items 4, 6, 7, 8, 9, 10, 12)
5. App shell navigation              (item 11)
6. Settings cohesion pass            (items 13, 14, 17, 18)
7. Preset management UI              (items 15, 16)
```

Visual sketch of the reshaped Book Detail toolbar:

```
Before:
[ Read ] [ Read Summary (disabled, dead link) ] [ Export Markdown ▾ ]  Customize…  [ ⋯ ]
                                                                        ^ floats outside menu

After:
[ ▶ Read ]   [ ⋯ ]
              ├─ Generate book summary  (or "Read book summary" when present)
              ├─ Customize text…
              ├─ Customize reader…
              ├─ Edit structure
              ├─ Re-import
              ├─ Export Markdown
              └─ Delete book
```

Visual sketch of Book Detail tabs:

```
[ Overview ]  [ Summary ]  [ Sections ]
              └─ Empty state when no book summary:
                   "No book summary yet. Generate one from the section
                    summaries you already have."  [ Generate book summary ]
              └─ Populated state: rendered Markdown + "Regenerate" + "Read in reader" actions.
```

## User Journeys

### Primary: User browses to a book and wants the book summary
1. User navigates to `/books/:id` → sees Overview tab by default.
2. User clicks **Summary** tab.
3. If a book summary exists → renders Markdown summary inline.
4. If no book summary exists → empty state explains why (e.g., "X of Y sections summarized; book summary needs all sections done" OR "click Generate to produce one") + a single **Generate book summary** CTA.
5. Generation kicks off the existing job, shows progress, and on completion the tab refreshes to show the summary.

### Primary: User opens overflow menu on Book Detail
1. User clicks `⋯`.
2. Menu shows: Generate/Read book summary · Customize text · Customize reader · Edit structure · Re-import · Export Markdown · Delete.
3. Clicking **Customize reader** opens the reader settings popover **anchored to the menu trigger** (or the centered modal variant) — themes load successfully — user adjusts theme/font/etc.

### Primary: User reads a section summary and wants the next chapter
1. User on `/books/3/sections/46?tab=summary` finishes reading.
2. Scrolls to bottom of summary content.
3. Sees a footer nav: `← Previous: <prev section title>`  ·  `Next: <next section title> →`.
4. Clicks Next → routes to next section's summary tab.
5. Same footer pattern present on the Original tab (uses the same prev/next).

### Primary: User opens TOC dropdown to jump sections
1. User clicks the TOC trigger in the reader.
2. Dropdown lists every section with: number, title, **real character count** (matching Book Detail), summary indicator (✓ / —).
3. User picks a section → navigates.

### Primary: User creates a custom preset
1. User on `/settings/presets` clicks **New preset**.
2. Form opens with fields: name, label, description, four facet pickers (style, audience, compression, content_focus).
3. User saves → new preset appears in list with **Edit** and **Delete** affordances.
4. Clicking a system preset opens a read-only detail panel showing description, facets, and the **rendered prompt template** (same prompt the LLM sees) so the user understands what the preset does.

### Primary: User adjusts reader theme and expects side panels to follow
1. User in section reader picks "Dark" or "Sepia" theme via reader settings.
2. Reader content area changes background/text immediately.
3. **Annotations panel** and **AI Chat panel** background, text, and border colors also switch — they no longer look like a white island next to a dark page.

### Edge / Error Cases

| Scenario | Condition | Expected Behavior |
|---|---|---|
| Book summary not yet generated | `book.summary_md` is null | Summary tab shows the empty-state CTA, not an error |
| Book summary generation in progress | active job exists | Summary tab shows progress indicator + cancel; CTA disabled |
| Section is first in book | `prev` is null | Footer shows only `Next: …`; no Previous button |
| Section is last in book | `next` is null | Footer shows only `← Previous: …` |
| Section has no summary | viewing summary tab | Existing empty state stays; prev/next footer still shown |
| Migrations endpoint returns error | backend alembic call fails | Database settings shows `Unknown` + an error icon with tooltip; never the literal string `FAILED:` |
| User preset delete | confirmation modal | Two-step confirm; system presets do not show Delete at all |
| New preset name collision | name matches existing | Inline form validation: "A preset with this name already exists" |
| Reader theme = default (light) on side panels | no theme override | Panels match light reader background — no perceptible regression |
| Annotation highlights on summary tab | annotations exist for a section | Highlighted spans render in the summary content the same way they do on the original tab |
| TOC dropdown for very long books | many sections | List remains scrollable; char counts still accurate |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|---|---|---|
| D1 | Book Detail toolbar = single primary CTA + overflow | (a) one CTA + overflow, (b) two CTAs (Read + Summary) + overflow, (c) keep current set | (a) — matches the "first principles" goal; the secondary "Read Summary" today is dead and confusing. The Summary tab (D2) gives the summary its own surface so it doesn't need a top-of-page CTA. |
| D2 | Book summary placement = dedicated **Summary** tab on Book Detail | (a) inline card with expand/collapse, (b) dedicated tab, (c) keep separate `/books/:id/summary` route + add CTA | (b) — keeps the user's mental model anchored on the book ("everything about this book lives at /books/:id"), supports both populated and empty states naturally, and matches the existing Sections tab pattern. The standalone route can stay as a deep-link alias if it already exists. **Overview tab keeps its current content unchanged** (cover, metadata, authors, parsing/summarization status, quality score) — only the book summary moves out into its own tab. |
| D3 | Compression display format | (a) keep `15.5%`, (b) `~15%` rounded to nearest 5, (c) bucket labels (Tight/Balanced/Loose) | (b) — user-explicit preference; the `~` prefix communicates approximation, the 5-pt bucket trims false precision, and the format stays compatible with sorting. |
| D4 | Bullet rendering in Markdown | (a) restore `list-style: disc`, (b) custom symbol (•, –), (c) numbered/styled-list utility classes | (a) — simplest fix; current `list-style: none` is the bug, default `disc` is what users expect from Markdown bullets. |
| D5 | Section navigation footer (prev/next) | (a) sticky bottom bar, (b) inline footer at end of content, (c) only on hover | (b) — keyboard arrows already work (per code search); the footer is a *discoverability* fix, not a primary navigation surface. Inline footer matches reader patterns in Notion/Substack/Linear's docs. |
| D6 | Preset management scope in this bundle | (a) view-only enhancements, (b) full CRUD for user presets + view for system, (c) defer entirely | (b) — user explicitly chose this; closes the gap fully; system presets stay read-only with prompt viewer. |
| D7 | LLM settings restyle target | (a) rewrite to scoped-style + CSS-variables pattern (matches other settings), (b) migrate other settings to Tailwind, (c) accept divergence | (a) — five settings pages already use the scoped-style pattern; one page (LLM) diverges; converging to the majority is cheaper and cohesive. |
| D8 | TOC dropdown char count source | (a) reuse `SectionBrief.content_char_count` (already returned), (b) add new field, (c) compute client-side | (a) — the API already provides this on the Book Detail table; the TOC component is reading the wrong field or a stale shape. Bug fix, not new contract. |
| D9 | Migration status "Failed" handling | (a) backend stops returning literal `"FAILED:"`, (b) frontend special-cases the string | (a) — the backend's alembic call is failing and leaking the error prefix into the value; the right fix is at the source. Frontend should treat any non-revision string as `Unknown` defensively. |
| D10 | Side panel theming approach | (a) move panels inside the reader theme scope, (b) duplicate CSS variables at panel root, (c) accept white | (a) — the reader theme variables already exist; the panels just need to be inside the scope (or read the same `--reader-bg` variable explicitly). Lowest risk. |
| D11 | Reading Settings pills component | (a) extract `ThemeCard` from `ReaderSettingsPopover` to a shared component used by both surfaces, (b) reuse in place via local import, (c) add hover/cursor to existing `<div>` and keep semantics, (d) full custom component | (a) — the working component already exists; extracting to `frontend/src/components/shared/` makes it the single source of truth and prevents drift. Adds a small refactor but eliminates the divergence permanently. |
| D12 | Settings tables row styling | (a) remove alt-row stripes, use single neutral row, (b) keep stripes everywhere consistently, (c) toggle | (a) — user preference; aligns with the "data table component with no alternate row colors" call-out. |

## Acceptance Criteria (per item)

| # | Surface | Acceptance Criterion |
|---|---|---|
| 1 | Book Detail | Only one primary "Read" CTA. No button labeled "Read Summary" outside the overflow menu. No disabled link that points back to the same page. |
| 2 | Book Detail | A **Summary** tab exists. Empty state renders a `Generate book summary` CTA + a 1-sentence reason that includes "X of Y sections summarized so far — the book summary will reflect those." CTA is **enabled whenever at least one section summary exists** (no requirement that all sections are summarized first). Populated state renders the Markdown book summary. Generation kicks off the existing job. |
| 3 | Book Detail | "Customize text" option only appears inside the overflow menu — never as a floating control. |
| 4 | Book Detail / Reader Settings | Clicking **Customize reader** in the overflow menu opens the reader settings popover anchored to the trigger (or as a centered modal), themes load successfully, and the close affordance works. |
| 5 | Book Detail | Compression renders as `~N%` where N is rounded to the nearest 5 (e.g., `~15%`, `~25%`). |
| 6 | Section Reader / Markdown | Bullet lists in summary tab render with visible bullet markers (`disc` for top level, `circle` for nested) and consistent indentation. |
| 7 | Section Reader | Both Summary and Original tabs render a footer nav at the end of content with `← Previous: <title>` and `Next: <title> →`; first/last sections show only the available side. |
| 8 | Section Reader / TOC | TOC dropdown shows correct per-section character count for every section (matches the count shown in the Book Detail Sections table). |
| 9 | Section Reader | Annotations and AI Chat side panels visually adopt the active reader theme (light/sepia/dark/etc.). Specifically: with the reader on Dark theme, `.context-sidebar` background must NOT remain `rgb(255,255,255)` — it must read `var(--reader-bg)` (or equivalent in-scope variable). Border and text colors follow suit. Verified failure mode (2026-05-01): switching to Dark theme leaves the sidebar pure white while the reader area changes; this must no longer happen. |
| 10 | Section Reader / Markdown | Tables in summary content render with visible borders, header row distinction, and consistent cell padding — never as bare unstyled HTML. |
| 11 | App shell | The "Book Companion" title in the app bar AND the BC icon in the side rail are clickable and route to `/`. Both have hover/focus states + cursor: pointer. |
| 12 | Section Reader | Annotations whose `content_type = "summary"` (i.e. created against summary text) are highlighted on the Summary tab using the same overlay engine that already works on the Original tab. Verified failure mode (2026-05-01): for `/books/1/sections/6` the API returns 2 highlight annotations on `content_type=section_content`; the Original tab renders 2 `<span class="highlight">` elements, the Summary tab renders 0. After fix: creating a highlight while on the Summary tab persists with `content_type=summary` and re-renders on subsequent visits to that tab. (Cross-projecting an `original`-content highlight onto summary text is **out of scope** — different text, no offset mapping.) |
| 13 | Settings → Database | **Backend:** `GET /api/v1/settings/migration-status` must never embed the alembic error prefix into the `current` / `latest` revision fields. On underlying error, the response uses null (or a structured `{error: "..."}` field), not a string literal starting with `FAILED:`. **Frontend:** renders any null / non-revision value as `Unknown` with a tooltip surfacing the error detail when present. Verified failure mode (2026-05-01): live API returns `{"current":"FAILED:","latest":"FAILED:","is_behind":false}`; this exact response must no longer be possible. |
| 14 | Settings → Database | Stats table renders with no alternating row stripes; uses the same data-table component as other settings tables. |
| 15 | Settings → Presets | A **New preset** button opens a form (name, label, description, 4 facet pickers); save creates a user preset; user presets show inline Edit + Delete actions; system presets do not. |
| 16 | Settings → Presets | Selecting any preset (system or user) shows: description, facets, and the **raw Jinja prompt template source** (the unrendered template file content + which fragment files it composes). System presets are read-only. (Rendering with sample data is intentionally out of scope per D6 sub-decision.) |
| 17 | Settings → Reading | The `ThemeCard` button currently inlined in `ReaderSettingsPopover` is **extracted to a shared component** (e.g. `frontend/src/components/shared/ThemeCard.vue`). Both `ReaderSettingsPopover` and the Reading Settings page use this single component. Reading-preset pills therefore become `<button>` with `cursor: pointer`, hover state, focus ring, and ARIA-correct semantics — automatically matching the reader settings popover. |
| 18 | Settings → LLM | Page uses the same scoped-style + CSS-variable pattern as other settings pages (no `dark:` Tailwind utility classes). Form fields, buttons, and section headers visually match other settings pages side-by-side. |

## Research Sources

| Source | Type | Key Takeaway |
|---|---|---|
| `frontend/src/views/BookOverviewView.vue:76,87-95` | Existing code | Confirmed two adjacent CTAs ("Read", "Read Summary" disabled) + floating "Customize…" outside overflow menu |
| `frontend/src/components/book/OverflowMenu.vue:106-113` | Existing code | "Customize Reader" handler exists but popover positioning is detached from trigger |
| `frontend/src/components/book/SectionListTable.vue:39,41-42` | Existing code | Compression rendered with `.toFixed(1)`; per-section char count works correctly here |
| `frontend/src/components/reader/MarkdownRenderer.vue` + `ReadingArea` | Existing code | `<ul>` styled with `list-style: none` (verified via DOM inspection); no table styling defined |
| `frontend/src/components/reader/TocDropdown.vue` (toc-dropdown / toc-list) | Live DOM inspection | TOC items show `0` for chars across all sections regardless of actual content length |
| `frontend/src/components/sidebar/ContextSidebar.vue:53`, `AIChatTab.vue:62-72` | Existing code | Use `var(--color-bg)` etc. but variables not in the reader-theme scope on this surface |
| `frontend/src/components/app/IconRail.vue:16-17` | Existing code | "BC" logo is plain `<span>` — no router-link |
| `frontend/src/components/settings/DatabaseSettings.vue:46-47,70-81,188` | Existing code + API | Frontend renders backend's literal string; alt-row stripes via `nth-child(even)` |
| `GET /api/v1/settings/migration-status` (live) | API response | Returns `{"current":"FAILED:","latest":"FAILED:","is_behind":false}` — backend leaking error prefix |
| `frontend/src/components/settings/PresetSettings.vue:36-72` | Existing code | Read-only list, no New / Edit / Delete affordances, no prompt template viewer |
| `frontend/src/components/settings/ReadingSettings.vue:63-69` vs `ReaderSettingsPopover` ThemeCard:41-60,74 | Existing code | Pills are `<div>` (no hover/cursor); the working equivalent is a `<button>` with full a11y |
| `frontend/src/components/settings/LlmSettings.vue:161-293` | Existing code | Uses inline Tailwind `dark:` classes; other settings pages use scoped-style + CSS-variable pattern |
| Live verification on `localhost:8000/books/3` and `/sections/46?tab=summary` (Playwright MCP) | Live DOM | Items 1, 3, 4 (popover anchored at `top:682,left:800` with "Couldn't load themes" error), 6, 8 directly observed |
| `docs/requirements/2026-04-30-reader-and-book-detail-ux-fixes.md`, `2026-04-30-reader-settings-popover-consolidation.md` | Prior docs | Two preceding bundles closed earlier UX debt; this bundle picks up the next layer |

## Open Questions

| # | Question | Owner | Needed By |
|---|---|---|---|
| 1 | For Decision D2, should the existing standalone book-summary route (if any) be removed or kept as a deep-link alias to `?tab=summary`? | Maneesh | before /spec |
| 2 | Compression bucketing edge cases — `~5%` for very tight, `~50%+` for very loose; do we cap at `~50%` or show actual? Single bucket size of 5 across the range, or wider buckets at extremes? | Maneesh | before /spec |
| 3 | "Customize text" vs "Customize reader" — are these two distinct surfaces (one for content typography, one for reader theme/layout)? Confirm scope; if overlapping, we should merge them into a single overflow item. | Maneesh | before /spec |
| 4 | When the reader-settings popover is opened from the **Book Detail** overflow (vs. from the reader), what should it apply to — book defaults, current/last-read section, or both? | Maneesh | before /spec |

## Review Log

| Loop | Findings | Changes Made |
|---|---|---|
| 1 | (a) Items 9 & 12 ACs were too vague ("visually adopt theme", "render the same way"). (b) D2 didn't say what stays on Overview tab. (c) Item 16 AC contradicted Open Question #4 (raw vs. rendered template). (d) No sequencing note. | (a) Verified both in browser via Playwright MCP; tightened AC #9 (with verified Dark-theme failure mode + required `var(--reader-bg)` source) and AC #12 (with content_type=summary contract + 2-vs-0 measured highlight count). (b) D2 now states "Overview tab keeps current content unchanged". (c) Item 16 locked to raw Jinja template source per user decision; OQ #4 removed. (d) Sequencing intentionally left to /plan. |
| 2 | (a) Item 13 AC only described frontend behavior despite the verified backend root cause. (b) Item 2 AC was silent on the precondition for the Generate CTA. (c) D11 said "reuse ThemeCard" but the component isn't currently shared. | (a) Item 13 AC split into Backend + Frontend parts; backend must not embed `FAILED:` into revision fields. (b) Item 2 AC clarified — Generate enabled when ≥1 section summary exists; empty state shows X-of-Y progress. (c) D11 + AC #17 now require extracting `ThemeCard` to `frontend/src/components/shared/` and using it from both surfaces. |

## Wireframes

**Generated:** 2026-05-01
**Folder:** `docs/wireframes/2026-05-01-cross-surface-ux-cohesion-bundle/`
**Index:** `docs/wireframes/2026-05-01-cross-surface-ux-cohesion-bundle/index.html`
**PSYCH walkthrough:** `docs/wireframes/2026-05-01-cross-surface-ux-cohesion-bundle/psych-findings.md`

Scope (per /wireframes Phase 2 confirmation): only the 6 IA/flow items get wireframes; the other 12 items (visual tweaks, data-source fixes, refactors) skip wireframes — they're trivially specifiable directly from the AC table above.

| # | Component | Devices | States | File |
|---|---|---|---|---|
| 01 | Book Detail — Overview + reshaped toolbar (items 1, 3, 5, 11) | desktop-web | default · loading · error | `01_book-detail-overview_desktop-web.html` |
| 02 | Book Detail — Summary tab (item 2) | desktop-web | empty · in-progress · populated · error | `02_book-detail-summary-tab_desktop-web.html` |
| 03 | Reader Settings popover anchored (item 4) | desktop-web | themes-loaded · themes-loading · themes-error · default-active-empty | `03_reader-settings-popover_desktop-web.html` |
| 04 | Section Reader — footer prev/next nav (item 7) | desktop-web | summary-mid · original-mid · first-section · last-section · summary-no-content | `04_section-reader-footer-nav_desktop-web.html` |
| 05 | Preset — New / Edit form, 4-card facets (item 15) | desktop-web | new-empty · new-validating · editing · saving | `05_preset-create-edit-form_desktop-web.html` |
| 06 | Preset detail — system + user + raw Jinja viewer (item 16) | desktop-web | system-selected · user-selected · none-selected · template-loading | `06_preset-detail-system_desktop-web.html` |

**PSYCH summary** (Tier 2 mandatory walkthrough, 3 journeys):
- J1 (read book summary): healthy throughout (40 → 67)
- J2 (generate first book summary): healthy throughout (40 → 83); determinate progress bar is the load-bearing element
- J3 (create custom preset): single-screen Δ went negative on the New Preset form due to facet vocabulary jargon; fixed inline by adding plain-language subheads under each facet card

**MSF analysis:** skipped per user choice (single-user personal tool; persona-conditional analysis adds limited value over PSYCH).
