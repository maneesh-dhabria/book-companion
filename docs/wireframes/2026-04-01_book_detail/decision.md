# Book Detail Page — Design Decision

**Date:** 2026-04-01
**Choice:** Option C — Two-Panel: Section TOC + Content

## Layout

- **Left panel (280px)**: Book metadata (cover thumbnail, title, author, tags, stats) + navigation links (Summary, Concepts, Annotations, External) + collapsible section TOC with nested hierarchy
- **Right panel (flex)**: Content area showing whatever is selected in the left panel. Max-width ~720px for readability. Action buttons (Edit, Copy, Export) in the content header.
- The icon sidebar's expanded state transforms into this book's TOC when a book is open

## Left Panel Navigation

1. Book Summary (default on entry)
2. Concepts (count)
3. Annotations (count)
4. External References (count)
5. Divider
6. Sections list: nested, collapsible (Part > Chapter > Sub-section), with eval status indicators

## Right Panel Content States

| Selected | Right Panel Shows |
|----------|------------------|
| Book Summary | Quick summary + full summary + key frameworks. Edit/Copy/Export actions. |
| A section | Toggle between original content and section summary (tabbed). Annotation creation enabled. |
| Concepts | Concept cards with term, definition, first-mentioned section, related concepts. Editable. |
| Annotations | Filtered annotation list for this book. Grouped by section. |
| External | Curated external summary/review links with snippets. |

## Key Behaviors

- Clicking a section in the TOC loads it in the right panel
- Active section highlighted in TOC
- TOC shows eval status per section (green check / amber warning)
- Right panel scrolls independently from left panel
- Breadcrumb at top of right panel: Library > Book Title > Section Name

## Options Considered

| Option | Description | Why Not |
|--------|-------------|---------|
| A. Tabbed Layout | Horizontal tabs for each content type | Tabs hide section navigation; can't see TOC while reading summary |
| B. Single Scrollable | Everything on one page | Gets very long; hard to navigate for books with 15+ sections |
| **C. Two-Panel (chosen)** | TOC left + content right | Persistent navigation; leverages sidebar pattern; familiar (docs sites) |
