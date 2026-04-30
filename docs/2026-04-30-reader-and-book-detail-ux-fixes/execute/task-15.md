# Task 15 — F5: ExportSplitButton + OverflowMenu

## Files touched
- frontend/src/components/book/ExportSplitButton.vue (new)
- frontend/src/components/book/OverflowMenu.vue (new)
- frontend/src/components/book/__tests__/ExportSplitButton.spec.ts (new — 7 tests)
- frontend/src/components/book/__tests__/OverflowMenu.spec.ts (new — 5 tests)

## Decisions / deviations
- Two distinct components per Decision P10 — different ARIA roles and
  trigger semantics, no parameterized share.
- ExportSplitButton accepts `loading` prop (used by F9b) so the F9b
  250 ms-floor wiring doesn't need to fork the component.

## Runtime evidence
- `npx vitest run ExportSplitButton OverflowMenu` — 12 / 12 pass.
- `npm run type-check` — clean.
