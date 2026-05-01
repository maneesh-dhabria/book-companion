# Task 13 — F6: ThemeGrid typography preview

## Files touched
- frontend/src/components/settings/ThemeCard.vue (add previewFont + previewSize props)
- frontend/src/components/settings/ThemeGrid.vue (thread typography from preset)
- frontend/src/components/settings/__tests__/ThemeGrid.spec.ts (FR-36 assertion)

## Decisions / deviations
- Plan suggested fetching `/api/v1/presets` directly inside ThemeGrid; we
  already get presets via the readerSettings store (which fetches at app
  init), so we read p.font_family / p.font_size_px from there instead.
  Avoids a duplicate fetch and a second source of truth.
- ThemeCard owns its own FALLBACK_CHAINS table (small duplication with
  FontListbox + readerSettings) so the preview swatch never depends on
  parent CSS resolving the bare family name.

## Runtime evidence
- `npx vitest run ThemeGrid ThemeCard` — 16 / 16 pass.
- `npm run type-check` — clean.
