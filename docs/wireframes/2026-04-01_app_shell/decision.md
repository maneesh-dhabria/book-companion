# App Shell & Navigation — Design Decision

**Date:** 2026-04-01
**Choice:** Option C — Hybrid Collapsible Icon Sidebar + Cmd+K Command Palette

## Layout Structure

- **Thin icon sidebar** (56px collapsed) on the left with icons for: Library, Search, Annotations, Concepts, Settings
- Sidebar **expands on hover/click** to show labels and contextual content (e.g., book TOC when reading)
- **Cmd+K command palette** for global search, navigation, and quick actions
- **Near-full-width content area** to the right of the icon rail
- Tag filters displayed as horizontal pill bar at the top of content area

## Key Behaviors

- Icon sidebar is always visible (never fully hidden)
- Expanded sidebar overlays content (doesn't push it)
- When reading a book, expanded sidebar shows the section TOC for that book
- Cmd+K palette supports: search across books, navigate to book/section, quick actions (add book, export)
- Dark theme by default (consistent with mockup)

## Options Considered

| Option | Description | Why Not |
|--------|-------------|---------|
| A. Fixed Sidebar | Full sidebar always visible (Notion-style) | Consumes too much horizontal space; feels heavy for small libraries |
| B. Top Navigation | Horizontal nav bar (Linear-style) | No persistent book list; section TOC needs separate panel; nav competes with search |
| **C. Hybrid (chosen)** | Icon rail + Cmd+K | Best of both: near-full width, quick nav, power-user friendly, expandable for TOC |
