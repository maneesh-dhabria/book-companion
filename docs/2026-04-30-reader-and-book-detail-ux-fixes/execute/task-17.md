# Task 17 — F9a: BookOverviewView action row + section list + popover

## Files touched
- frontend/src/views/BookOverviewView.vue (action row rebuild, SectionListTable swap, popover mount)
- frontend/src/views/__tests__/BookOverviewView.spec.ts (5 new F9a assertions)
- frontend/src/views/__tests__/BookOverviewView.export.spec.ts (selectors retargeted to data-role=body)

## Decisions / deviations
- Kept the `Customize…` link + `ExportCustomizeModal` in the action row
  even though they aren't in the F9a spec component list — they predate
  this work and removing them would be FR-21 scope-creep. They sit
  alongside Edit Structure inside OverflowMenu rather than getting
  duplicated.
- Read Summary is implemented as a router-link with click-prevent on
  disabled state rather than a conditional <button> — keeps the visual
  treatment consistent with Read.
- ReaderSettingsPopover relies on the existing
  `useReaderSettingsStore().popoverOpen` flag (same pattern as
  BookDetailView), so OverflowMenu just flips the flag.

## Runtime evidence
- `npx vitest run BookOverviewView` — 9 / 9 pass.
- Full suite — 278 / 278 pass.
- `npm run type-check` — clean.
