# Annotation System — Management View Design Decision

**Date:** 2026-04-01
**Choice:** Option B (Grouped by Book) as default, with configurable grouping and sorting

## Layout

Annotations page accessible from the icon sidebar. Configurable view with grouping and sorting controls.

## View Controls (top bar)

- **Group by** dropdown: Book (default) | Tag | Section | None (chronological feed)
- **Sort by** dropdown: Newest first (default) | Oldest first | Book order | Recently edited
- **Filter by tag**: Tag pills with add/remove
- **Filter by type**: Highlight | Note | Linked | All
- **Export** button

## Grouped View (default: by Book)

- Collapsible accordion sections, one per group (book / tag / etc.)
- Group header shows: group name + annotation count
- Within each group: annotation cards ordered by sort preference
- Each card shows:
  - Source context (book > section) as breadcrumb
  - Highlighted text in a quote block with left border (if text-anchored)
  - User's note
  - Tags as colored pills
  - Linked annotation count + preview (expandable)
  - Date + edit action
- Freeform notes (no text anchor) shown without quote block, labeled "Section-level note"

## Ungrouped View (Group by: None)

- Chronological feed of all annotations
- Same card format as grouped view
- Left sidebar with filter panel (by book, by tag, by type) — appears when ungrouped

## Annotation Card Actions

- Edit note text
- Add/remove tags
- Create cross-book link (opens a picker to search for another annotation)
- Delete
- Navigate to source (opens Section Reader at the highlighted passage)

## Key Behaviors

- View preference (grouping + sort) persisted in local storage
- Clicking source breadcrumb navigates to the section with the annotation highlighted
- Cross-book links shown as expandable preview at bottom of card
- When accessed from Book Detail page ("Annotations" in left panel), automatically filtered to that book
