# Task 12 — F4: FontListbox + CustomEditor wiring

## Files touched
- frontend/src/components/settings/FontListbox.vue (new)
- frontend/src/components/settings/__tests__/FontListbox.spec.ts (new)
- frontend/src/components/settings/CustomEditor.vue (replace native select)
- frontend/src/components/settings/__tests__/CustomEditor.spec.ts (test rewritten for listbox)

## Decisions / deviations
- Reuse the same FALLBACK_CHAINS table from readerSettings.ts so option
  labels render in the same fallback stack the reader will resolve at
  runtime. (Could've imported but a dependency-free local copy keeps the
  component self-contained — 6 entries.)

## Runtime evidence
- `npx vitest run FontListbox CustomEditor` — 14 / 14 pass.
- `npm run type-check` — clean.
