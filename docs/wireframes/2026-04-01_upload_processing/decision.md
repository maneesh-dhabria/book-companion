# Book Upload & Processing — Design Decision

**Date:** 2026-04-01
**Choice:** Option C — Modal Wizard (Upload + TOC) → Progress on Book Detail

## Upload Wizard (Modal)

Steps with progress indicator at top:

1. **Upload**: Drag-and-drop zone or file picker. Accepts EPUB, MOBI, PDF. Shows file size and format detection.
2. **Metadata**: Parsed title, author(s) displayed for confirmation/editing. Cover image preview if available. Tag assignment.
3. **TOC Review**: Detected section structure displayed as a sortable, editable list. Drag to reorder, edit titles, delete sections, adjust nesting. Shows detection method used (TOC/heuristic/LLM).

Footer actions:
- "← Back" to previous step
- "Save without processing" — saves parsed book, user can summarize later
- "Confirm & Summarize →" — closes wizard, starts summarization, opens Book Detail page

## Progress on Book Detail Page

After wizard closes, the Book Detail page shows with a **progress card** pinned at the top:

- Progress bar with percentage
- Current section being processed + estimated time remaining
- Per-section status list: completed (with eval scores), processing, pending
- Completed sections are immediately browsable (click to read summary)
- Card auto-dismisses when all processing completes

User can navigate away — processing continues in background. A small indicator in the Library page card shows processing status.

## Options Considered

| Option | Why Not |
|--------|---------|
| A. Full modal wizard | Modal feels trapped during long processing; can't browse other content |
| B. Dedicated page | Upload steps don't need a full page; loses modal focus |
| **C. Hybrid (chosen)** | Wizard keeps upload focused; Book Detail is the natural home for progress; completed sections browsable immediately |
