# Wireframe Generation Brief — AI Comprehension Quiz

**You are generating wireframes for the AI Comprehension Quiz feature in the Book Companion app.**

## Files you MUST read before writing anything

1. `/Users/maneeshdhabria/Desktop/Projects/personal/book-companion/docs/features/2026-05-08-ai-comprehension-quiz/01_requirements.md` — full feature spec, especially the Solution Direction, User Journeys, Empty States table, and Design Decisions D1–D41.
2. `/Users/maneeshdhabria/Desktop/Projects/personal/book-companion/frontend/DESIGN.md` — design system (light theme, indigo accent, anti-patterns).
3. `/Users/maneeshdhabria/Desktop/Projects/personal/book-companion/frontend/COMPONENTS.md` — existing component inventory.
4. `/Users/maneeshdhabria/.claude-personal/plugins/cache/pmos-toolkit/pmos-toolkit/2.30.0/skills/wireframes/reference/html-template.md` — HTML skeleton you MUST follow.
5. `/Users/maneeshdhabria/Desktop/Projects/personal/book-companion/docs/features/2026-05-08-ai-comprehension-quiz/wireframes/assets/wireframe.css` — the vocabulary you can use; do NOT duplicate its rules.

## Output

Write your file(s) to:
`/Users/maneeshdhabria/Desktop/Projects/personal/book-companion/docs/features/2026-05-08-ai-comprehension-quiz/wireframes/{NN}_{slug}_{device}.html`

- One file per (component × device). You are responsible for **both desktop-web AND mobile-web** variants of your assigned component.
- Use the file index assigned in your prompt (NN starts at 01 and is unique across all components).
- Total files in this folder will be 18 — use "File NN of 18" in the footer.

## Hard requirements

- Link `./assets/wireframe.css` then `./assets/design-overlay.css` (in that order) in `<head>`. Tailwind via `<script src="https://cdn.tailwindcss.com"></script>`.
- State-switcher tabs at top — emit one `<button class="wf-tab">` per state your component has, plus the Annotations toggle.
- One `<section class="wf-state" data-state="...">` per state. Only the first has `.active`.
- Use **realistic domain copy** drawn from the requirements doc. The reference book throughout the req doc is **Daniel Kahneman, "Thinking, Fast and Slow"**. Real example concepts: System 1 / System 2, anchoring, availability heuristic, loss aversion, prospect theory, endowment effect, cognitive ease. Use these — NOT Lorem ipsum, NOT "Concept A".
- **Layout anchor:** `book-detail` (sidebar + top-bar + book-header + tab-strip + tab-content). Quiz is the **6th tab** alongside Overview / Summary / Sections / Audio / Annotations. Show the tab strip on every desktop-web wireframe so the Quiz tab's selected state is visible. Mobile uses top-bar + scrollable tab strip + bottom-tab-bar (Library / Search / Settings).
- Sidebar: dark `#1e1e2e` (use `--bc-sidebar-bg`), 240px on desktop, hidden on mobile (replaced by hamburger top-bar + bottom tab bar).
- Indigo accent only — no second blue. Status pills use neutral grey OR indigo-tint (`--bc-indigo-bg` / `--bc-indigo-border` / `--bc-indigo-text`). Empty states get an icon + sentence + CTA, NO illustrations.
- Buttons rectangular, 8px radius. Chips pill-rounded. Min 36px desktop / 44px mobile touch targets.
- Every short-label / icon-only `<button>` MUST have an `aria-label`.
- Footer format EXACTLY: `File 03 of 18` (leading-zero on file index, no leading-zero on total) and `Generated 2026-05-09`.
- Add `class="wf-anno" data-note="…"` to elements whose interaction is non-obvious (Skip, Explain, Override, Already-asked link, budget bar, self-assessment buttons, etc.).

## Anti-patterns (from DESIGN.md — DO NOT violate)

- No second accent color, no marketing imagery / stock illustrations.
- No Lorem ipsum, no "Book A / Concept B" placeholders.
- No destructive actions in dropdowns without confirmation.
- No exclamation marks or emoji in product copy.
- No slide-up drawers on desktop — modals are centered.
- Date format: `May 9, 2026`. Datetime: `May 9, 2026 · 2:14pm`.

## Quiz-specific glossary (use this language verbatim in copy)

- Tab title: **Quiz**. Page header copy when empty: "Quiz me on this book. Pick a scope to start."
- Scope option labels:
  - "All Summaries (book summary + every chapter summary)"
  - "Specific Chapters (full text of selected chapters)"
- Optional theme field placeholder: `e.g., focus on prospect theory`
- Self-assessment buttons (in this order, left-to-right): **Got it · Partial · Missed**
- Per-turn controls: **Skip**, **Explain**, **Override**, **Already asked** (link)
- Loading copies (verbatim):
  - "Reading the book to draft your question…"
  - "Reading your answer alongside the book…"
- Tally formats:
  - Session: `Session: 1 partial · Lifetime: 1 partial`
  - Lifetime: `Lifetime: 23 Q · 14 Got it / 6 Partial / 3 Missed across 3 sessions`
- Fatigue prompt copy: "Want to keep going or wrap up here?"
- Warm-up banner: "Last time you marked **anchoring effect** as Missed and **availability heuristic** as Partial — let's revisit."
- Budget bar: "52% of budget used" with the inline rejection copy "Would exceed budget — deselect a chapter to add."
- Citation chip example: `Source: Chapter 1`
- Question shapes: MCQ, Open-ended, Spot the error.

## Layout anchor reference HTML (desktop-web — use as the chrome for screen-level wireframes)

```html
<div class="wf-row" style="height:100%; align-items:stretch;">
  <!-- Sidebar -->
  <aside style="width:240px; background:var(--bc-sidebar-bg); color:var(--bc-sidebar-text); padding:16px; flex-shrink:0;">
    <div style="font-weight:600; font-size:13px; opacity:.7; letter-spacing:.04em; text-transform:uppercase;">Book Companion</div>
    <nav style="margin-top:24px; display:flex; flex-direction:column; gap:4px;">
      <a style="padding:8px 12px; border-radius:6px;">Library</a>
      <a style="padding:8px 12px; border-radius:6px;">Search</a>
      <a style="padding:8px 12px; border-radius:6px;">Settings</a>
    </nav>
  </aside>
  <!-- Main -->
  <div class="wf-stack" style="flex:1; min-width:0;">
    <header style="height:56px; border-bottom:1px solid var(--wf-border); display:flex; align-items:center; padding:0 24px; gap:16px; background:var(--wf-bg);">
      <span class="wf-muted">Library</span>
      <span class="wf-muted">›</span>
      <span>Thinking, Fast and Slow</span>
    </header>
    <!-- Book header -->
    <section style="padding:24px 32px 16px; display:flex; gap:20px; align-items:flex-start;">
      <div class="mock-img" style="width:72px; height:104px; border-radius:6px;"></div>
      <div class="wf-stack" style="gap:6px;">
        <h1 style="font-size:24px; font-weight:600; line-height:1.2;">Thinking, Fast and Slow</h1>
        <div class="wf-muted" style="font-size:14px;">Daniel Kahneman · 2011 · 499 pages · 38 sections</div>
      </div>
    </section>
    <!-- Tab strip -->
    <nav role="tablist" style="border-bottom:1px solid var(--wf-border); padding:0 32px; display:flex; gap:24px; font-size:14px;">
      <a role="tab" aria-selected="false" style="padding:12px 0;">Overview</a>
      <a role="tab" aria-selected="false" style="padding:12px 0;">Summary</a>
      <a role="tab" aria-selected="false" style="padding:12px 0;">Sections</a>
      <a role="tab" aria-selected="false" style="padding:12px 0;">Audio</a>
      <a role="tab" aria-selected="false" style="padding:12px 0;">Annotations</a>
      <a role="tab" aria-selected="true"
         style="padding:12px 0; border-bottom:2px solid var(--wf-accent); color:var(--wf-text); font-weight:500;">Quiz</a>
    </nav>
    <!-- Tab content -->
    <main style="padding:24px 32px; flex:1; overflow:auto;">
      <!-- COMPONENT-SPECIFIC CONTENT GOES HERE -->
    </main>
  </div>
</div>
```

For mobile-web, replace the sidebar with a `top-bar` (hamburger + title) and add a bottom tab bar; the book-header collapses to one row and the tab strip becomes horizontally scrollable.

## State-switcher pattern (required)

```html
<header class="wf-chrome">
  <div class="wf-chrome__inner">
    <span class="wf-chrome__title">{COMPONENT_NAME}</span>
    <span class="wf-chrome__device">{desktop-web|mobile-web}</span>
    <nav class="wf-tabs" aria-label="State switcher">
      <button class="wf-tab" aria-selected="true"  data-state="default">Default</button>
      <button class="wf-tab" aria-selected="false" data-state="state2">…</button>
    </nav>
    <button id="toggle-anno" class="wf-tab" aria-pressed="true">Annotations</button>
  </div>
</header>
```

Plus the JS at bottom (copy from html-template.md verbatim).

## Footer (required, exact format)

```html
<footer class="wf-footer">
  <div class="wf-footer__inner">
    <span>{COMPONENT_NAME}</span>
    <span class="mock-pill">{desktop-web|mobile-web}</span>
    <span>File NN of 18</span>
    <span>Generated 2026-05-09</span>
    <a class="wf-grow" style="text-align:right;color:var(--wf-accent)" href="./index.html">Back to index</a>
  </div>
</footer>
```

Replace NN with the index from your prompt.

## What you produce

- Two HTML files (desktop + mobile) for your assigned component.
- No commentary, no extra files. The HTML must be self-contained (links to ./assets/wireframe.css and ./assets/design-overlay.css only).
- Add a `<!-- Review Log -->` HTML comment near the top so refinement loops can append findings.

If you have ambiguity, use the most likely interpretation from the requirements doc and add a `wf-anno` annotation flagging the assumption.
