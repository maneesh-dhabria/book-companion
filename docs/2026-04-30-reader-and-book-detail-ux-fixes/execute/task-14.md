# Task 14 — F3: SectionListTable shared component

## Files touched
- frontend/src/components/book/SectionListTable.vue (new)
- frontend/src/components/book/__tests__/SectionListTable.spec.ts (new)
- frontend/src/components/reader/TOCDropdown.vue (rewritten — uses SectionListTable)
- frontend/src/components/reader/__tests__/TOCDropdown.spec.ts (rewritten)
- frontend/src/types/index.ts (SectionBrief gains content_char_count, default_summary, last_failure_type)
- frontend/src/stores/summarizationJob.ts (expose `lastEvent` ref consumed by SectionListTable)

## Decisions / deviations
- The summarization-job store had no `lastEvent` getter — added one
  alongside the existing typed handlers so SectionListTable can `watch`
  it without each row opening its own EventSource (Decision P8).
- Front-matter `<details>` accordion in TOCDropdown replaced by a flat
  list. The previous accordion grouping is no longer present in the
  shared table; rebuilding it would require teaching SectionListTable
  about FRONT_MATTER_TYPES — out of scope for FR-33. Existing search
  behaviour preserved, glossary stays inline (current spec doesn't
  treat it as front-matter).
- `content_char_count` typed as optional on SectionRow because Section
  (reader-side) doesn't always carry it; the dash fallback handles
  null/undefined uniformly.

## Runtime evidence
- `npx vitest run SectionListTable TOCDropdown` — 12 / 12 pass.
- `npm run type-check` — clean.
