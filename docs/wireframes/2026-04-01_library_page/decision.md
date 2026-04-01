# Library Page — Design Decision

**Date:** 2026-04-01
**Choice:** Option C — Switchable Grid + List Toggle

## Layout

- **Grid view (default)**: Card grid with book cover art, title, author, tags as colored pills, processing status, section count. Hover reveals summary preview overlay.
- **List view**: Sortable table with columns: Title, Author, Status, Tags, Sections, Last Accessed. Information-dense for large libraries.
- **Toggle button** in top-right toolbar (grid/list icons). Preference persisted in local storage.

## Key Elements

- Header: "Library" title + book count
- Tag filter pills: horizontal scrollable bar below header (All, psychology, productivity, etc.) with counts
- Cmd+K search hint button
- "+ Add Book" primary action button
- Processing states shown on cards: "Summarized" (green), "Summarizing 5/12..." (amber), "Parsed only" (gray)

## Book Card (Grid View)

- Cover art background with book cover centered
- Hover: summary preview overlay at bottom of cover area
- Below cover: title, author, tag pills
- Footer: status indicator + section count
- Click navigates to Book Detail page
- Active border highlight on hover (indigo)

## Options Considered

| Option | Description | Why Not |
|--------|-------------|---------|
| A. Card Grid only | Visual bookshelf with covers | Not information-dense enough for large libraries |
| B. Compact List only | Sortable table | No visual appeal; feels like a spreadsheet |
| **C. Switchable (chosen)** | Grid + List toggle | Best of both; grid for browsing, list for scanning |
