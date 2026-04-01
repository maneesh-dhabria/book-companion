# Concepts Explorer — Design Decision

**Date:** 2026-04-01
**Choice:** Configurable grouping + sorting (consistent with Annotation system) with list + detail panel layout

## Layout

Two-panel layout (consistent with Book Detail):
- **Left panel**: Concept list with configurable grouping/sorting + search filter
- **Right panel**: Selected concept detail — definition, all appearances across books, related concepts, edit actions

## View Controls (top of left panel or toolbar)

**Group by** dropdown:
- Book (default) — concepts grouped by source book
- First letter — alphabetical dictionary view
- Related concepts — cluster related concepts together
- None — flat list

**Sort by** dropdown:
- Alphabetical (default)
- Most sections — concepts appearing across most sections/books surface first
- Recently added
- Book order — order of first encounter during summarization

**Filters:**
- Search/filter input (instant filtering as you type)
- Filter by book dropdown
- Toggle: show user-edited only

## Concept Detail Panel (right)

- **Term** (h2) with Edit button
- **User-edited badge** if modified by user
- **Definition** (editable)
- **Appears in**: List of all sections across all books where this concept appears (clickable → navigates to section)
- **First mentioned**: highlighted entry showing where the concept was first introduced
- **Related concepts**: Clickable chips that navigate to those concepts
- **Annotations**: Any annotations tagged with or mentioning this concept

## Key Behaviors

- View preference (grouping + sort) persisted in local storage
- Clicking a concept in the list loads detail in right panel
- Related concept chips in detail panel navigate within the same explorer
- "Appears in" section links navigate to the Section Reader
- When accessed from Book Detail ("Concepts" tab), auto-filtered to that book
- User can add new concepts manually via "+ Add Concept" button

## Design Consistency

This follows the same pattern as:
- **Annotations**: Configurable group + sort with filter sidebar
- **Book Detail**: Two-panel (list left + detail right)
- **Library**: Configurable view (grid/list toggle)

All browsable collections in the app share the same interaction pattern: configurable grouping/sorting with persisted preferences.
