# Rework Brief — match the actual app chrome

The first wireframe pass invented chrome that doesn't exist in Book Companion. This brief gives the real layouts so re-skins are accurate.

## 1. Real reader chrome (replaces the dark left sidebar)

The reader has NO dark sidebar. Layout is a single column with a horizontal header on top.

```html
<header class="reader-header">
  <div class="reader-breadcrumb">
    <a class="breadcrumb-link" href="/">Library</a>
    <span class="breadcrumb-sep">/</span>
    <a class="breadcrumb-link" href="/books/1">Thinking, Fast and Slow</a>
    <span class="breadcrumb-sep">/</span>
    <!-- TOCDropdown — a button "Section 3 · System 1 and System 2 ▾" -->
    <button class="toc-dropdown">System 1 and System 2 ▾</button>
    <!-- SectionTagRow inline: small pills "chapter · 4,820 chars · summarized" -->
  </div>
  <div class="reader-controls">
    <button class="nav-btn" aria-label="Previous section">←</button>
    <!-- ContentToggle: Original | Summary -->
    <div class="content-toggle">
      <button>Original</button>
      <button class="active">Summary</button>
    </div>
    <button class="nav-btn" aria-label="Next section">→</button>
    <!-- slot for actions (NEW: play button goes here) -->
    <button class="nav-btn play-action" aria-label="Play summary audio">▶</button>
  </div>
</header>
```

CSS classes already exist: `.reader-header`, `.reader-breadcrumb`, `.breadcrumb-link`, `.breadcrumb-sep`, `.reader-controls`, `.nav-btn`. They use `--color-border`, `--color-text-secondary`, `--color-bg-primary`, `--color-bg-secondary`. Replicate these in the wireframe with inline styles using the house-style.css tokens (`var(--wf-text)`, `var(--wf-muted)`, `var(--wf-border)`, `var(--wf-surface)`).

Below the header, the reader content area is a centered column (max-w-4xl) of summary markdown with generous prose typography. NO sidebar.

The right side has an optional `ContextSidebar` (annotations / AI chat) that toggles via a button — show it as collapsed/iconified by default in the wireframe.

## 2. Real BookDetail / BookOverviewView chrome

Tabs are exactly: **Overview | Summary | Sections** (and now adding **Audio** as a 4th, **Annotations** as a 5th per req doc).

```html
<header class="book-header">
  <div class="cover" style="width:140px;height:200px;background:#eee">cover</div>
  <div>
    <h1>Thinking, Fast and Slow</h1>
    <p class="byline">Daniel Kahneman</p>
    <div class="action-row">
      <a class="btn-primary">Read</a>
      <button class="overflow-menu">⋯</button>
    </div>
  </div>
</header>

<nav class="book-tabs" role="tablist">
  <button class="book-tab active">Overview</button>
  <button class="book-tab">Summary</button>
  <button class="book-tab">Sections</button>
  <button class="book-tab">Audio <span class="mock-pill">NEW</span></button>
  <button class="book-tab">Annotations</button>
</nav>
```

Tab styling: underline (border-bottom 2px transparent → accent on active), no background fill. Use this CSS literally (paste into a `<style>` block in the wireframe):

```css
.book-tabs { display:flex; gap:.25rem; border-bottom:1px solid var(--wf-border); margin-top:1rem }
.book-tab { background:none; border:none; padding:.6rem 1rem; font-size:.9rem; font-weight:500;
            color:var(--wf-muted); cursor:pointer; border-bottom:2px solid transparent;
            margin-bottom:-1px }
.book-tab:hover { color:var(--wf-text) }
.book-tab.active { color:var(--wf-accent); border-bottom-color:var(--wf-accent) }
.book-header { display:flex; gap:1.25rem; align-items:flex-start }
.book-overview { max-width:48rem; margin:0 auto; padding:2rem 1.25rem;
                 display:flex; flex-direction:column; gap:1.5rem }
.cover { width:140px; height:200px; flex:0 0 140px }
```

## 3. Sections tab table (existing — `SectionListTable`)

Columns: `# | Title | Type | Chars | Summary | Compression`.
For audiobook mode add: `Audio` (status pill), `Audio actions` (Play / Regenerate / Delete inline icons).

## 4. Unified playbar contract (canonical visual across files 01, 02, 06)

EVERY playbar uses this structure — no inline speed-control on the pre-play CTA, no transport drift across files:

```html
<div class="bc-playbar" style="background:#0f172a;color:#f8fafc;border-radius:14px;
                                padding:12px 20px;display:flex;gap:12px;align-items:center">
  <button class="icon-btn" aria-label="Previous sentence" title="Prev sentence">⏮</button>
  <button class="icon-btn icon-btn--primary" aria-label="Pause">⏸</button>
  <button class="icon-btn" aria-label="Next sentence" title="Next sentence">⏭</button>

  <div class="flex-1 px-3 min-w-0">
    <div class="text-sm font-medium truncate">{{section or playlist title}}</div>
    <div class="text-xs opacity-70 truncate">{{book title}} · 2:14 / 6:08 · sentence 17 of 47</div>
    <div class="h-1 rounded mt-1" style="background:rgba(255,255,255,.15)">
      <div class="h-1 rounded" style="background:var(--wf-accent);width:36%"></div>
    </div>
  </div>

  <select class="speed-select" aria-label="Playback speed">
    <option>1x</option><option selected>1.25x</option><option>1.5x</option>
  </select>
  <span class="bc-engine-chip">Kokoro · af_bella</span>   <!-- or bc-engine-chip--web -->
  <button class="icon-btn" aria-label="Close player">✕</button>
</div>
```

**Pre-play CTAs** (e.g., the "Listen" button on the book summary page, the "Play as audio" button on the annotations tab) are PLAIN BUTTONS with NO inline speed dropdown. Speed lives on the playbar only, post-press.

## 5. Removed-file rule

`05_audio-files-list_*.html` has been deleted — the new Audio tab on Book Detail (file 03) is the canonical surface for the per-book audio file list. Do not reference the old file paths. Update the index file count to 14 (was 14; same — we add 08 and remove 05 → still 14 wireframes if 5 is replaced by 8).
