# Section Reader — Design Decision

**Date:** 2026-04-01
**Choice:** Option A — Toggle Tabs: Content | Summary

## Layout

Within the right panel of the Book Detail two-panel layout:
- **Breadcrumb**: Library > Book Title > Section Name
- **Two tabs**: "Original Content" (default) | "Summary" (with eval status badge, e.g., "✓ 16/16")
- **Full-width content area** below tabs, max-width ~720px for readability
- **Prev/Next section navigation** buttons in the header area

## Annotation Interaction

- On **text selection**, a floating toolbar appears above the selection with actions:
  - Annotate (add note)
  - Tag (add tags to the annotation)
  - Link (link to another annotation)
  - Copy (copy selected text)
- Existing annotations shown as **highlighted spans** with a small indicator (note count, icon)
- Clicking an existing annotation highlight shows the note in a popover

## Summary Tab

- Shows structured summary: Key Concepts (bullets), Summary (prose), Key Quotes, Image References
- Eval status displayed (16/16 passed, or specific failures highlighted)
- Actions: Edit Summary, Copy, Export, Re-generate

## Key Behaviors

- Tab state persists per section (if user was on Summary tab for section 3, opening section 4 resets to Content tab)
- Images rendered inline in original content (resolved from blob UUIDs)
- Markdown content rendered with proper formatting (headings, lists, code, emphasis)
- Text selection + annotation works only on the Content tab (summaries can have freeform section-level notes but not text-anchored highlights)

## Why Not the Others

| Option | Why Not |
|--------|---------|
| B. Side-by-Side | Creates three panels (sidebar + content + summary) — too cramped. Splits reading focus. |
| C. Collapsible Drawer | Adds UI complexity (drawer state management). Content area shrinks when drawer is open. |
| **A. Tabs (chosen)** | Simplest. Full-width reading. Clean mental model (reading OR reviewing). Works well within the existing two-panel Book Detail layout. |
