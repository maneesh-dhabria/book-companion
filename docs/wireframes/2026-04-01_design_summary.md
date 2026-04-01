# Web Interface Design Summary

**Date:** 2026-04-01
**Status:** Wireframed — ready for implementation

## All Design Decisions

| # | Screen | Choice | Key Pattern |
|---|--------|--------|-------------|
| 1 | App Shell & Navigation | Hybrid collapsible icon sidebar + Cmd+K command palette | Icon rail (56px) expands on hover; Cmd+K for search/navigation |
| 2 | Library Page | Switchable grid + list toggle | Grid (default) for visual browsing, list for power users; persisted preference |
| 3 | Book Detail Page | Two-panel: section TOC + content | Left: metadata + TOC navigation. Right: selected content. Sidebar becomes book's TOC. |
| 4 | Section Reader | Toggle tabs: Content \| Summary | Full-width reading within right panel. Annotation toolbar on text selection. |
| 5 | Search Experience | Command palette → full results page | Cmd+K instant suggestions; Shift+Enter for full grouped results with source filters |
| 6 | Upload & Processing | Modal wizard → progress on Book Detail | Wizard: upload → metadata → TOC review. Then Book Detail with progress card. |
| 7 | Annotation System | Grouped view with configurable group/sort | Group by: book/tag/section/none. Sort by: date/book order/edited. Filter by tag/type. |
| 8 | Concepts Explorer | Configurable group/sort + list/detail panel | Group by: book/letter/related/none. Sort by: alpha/most sections/recent/book order. |

## Emergent Design Patterns

Three core patterns emerged that should be codified as design system principles:

### 1. Two-Panel Layout (List + Detail)
Used in: Book Detail, Concepts Explorer, Annotation Management (when grouped)

```
┌──────────────┬─────────────────────────────────┐
│  List/Nav    │  Detail/Content                  │
│  (scrollable)│  (scrollable, max-width ~720px)  │
│              │                                   │
│  Grouped or  │  Full content of selected item    │
│  flat list   │  with action buttons              │
└──────────────┴─────────────────────────────────┘
```

### 2. Configurable Collection Views
Used in: Library (grid/list), Annotations (group+sort), Concepts (group+sort)

All browsable collections share:
- **Group by** dropdown with 3-4 options
- **Sort by** dropdown with 3-4 options
- **Filter** controls (tags, type, book, search)
- **Persisted preference** in local storage
- **Consistent card/row format** within the collection

### 3. Progressive Disclosure
Used in: Cmd+K palette (instant → full results), Section Reader (content → summary tab), Upload (wizard → progress card), Concepts (list → detail panel)

Information is revealed in layers:
- **Layer 1**: Quick overview (palette suggestions, card grid, list items)
- **Layer 2**: Full detail (full search page, detail panel, expanded content)
- **Layer 3**: Actions (edit, export, link, annotate — available in detail view)

## Requirement Implications

These design decisions surface the following additions/changes to the requirements:

1. **Configurable views pattern**: Add to web interface requirements — all collection views (library, annotations, concepts) support configurable grouping/sorting with persisted preferences
2. **Cmd+K command palette**: Add as a first-class web UI component with keyboard navigation, instant results, and transition to full search
3. **Two-panel consistency**: Codify as a design principle — detail views always use the list+detail two-panel pattern
4. **Progress card component**: The upload wizard → progress card handoff needs a reusable progress card component
5. **Annotation toolbar**: Text selection triggers a floating toolbar with Annotate/Tag/Link/Copy actions — needs to be a core design system component

## Wireframe Files

All decisions saved with detailed specifications:
- `2026-04-01_app_shell/decision.md`
- `2026-04-01_library_page/decision.md`
- `2026-04-01_book_detail/decision.md`
- `2026-04-01_section_reader/decision.md`
- `2026-04-01_search_experience/decision.md`
- `2026-04-01_upload_processing/decision.md`
- `2026-04-01_annotation_system/decision.md`
- `2026-04-01_concepts_explorer/decision.md`
