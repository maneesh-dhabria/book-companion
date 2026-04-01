# Search Experience — Design Decision

**Date:** 2026-04-01
**Choice:** Option A — Command Palette → Full Results Page

## Command Palette (Cmd+K)

- Centered overlay modal (~560px wide) with search input at top
- **Instant results** as user types, grouped by source type:
  - Books (title + author match)
  - Sections (title + content match)
  - Concepts (term + definition match)
  - Annotations (note + selected text match)
- Each result shows: icon by type, title, subtitle (book + context), arrow
- Keyboard navigation: ↑↓ to navigate, Enter to open result directly, Shift+Enter for full results page, ESC to close
- Footer shows keyboard shortcuts

## Full Results Page (Shift+Enter or deep search)

- Search bar at top (pre-filled with query from palette)
- **Left sidebar filters**: Source Type with counts (All, Content, Summaries, Concepts, Annotations)
- **Results grouped by book**: Book title as group header with result count, individual results below
  - Each result shows: source type badge (colored), title, snippet with highlighted matches
  - Collapsed after top 2-3 results: "+ N more results from this book"
- Click any result → navigates to that section/concept/annotation in context

## Key Behaviors

- Palette opens instantly on Cmd+K from any page
- Search is hybrid: BM25 + semantic results merged via RRF
- Results update as user types (debounced ~300ms)
- Recent searches shown when palette opens with empty query
- Palette remembers last query within the session

## Options Considered

| Option | Why Not |
|--------|---------|
| B. Dedicated page only | No quick navigation; always a full page load for simple lookups |
| C. Two separate tools | Cognitive overhead of remembering two shortcuts; fragmented experience |
| **A. Palette → Full page (chosen)** | Unified entry point; fast lane (palette) + deep lane (full page) with seamless transition |
