# Task 09 — F1: Bundle webfonts via @fontsource

## Files touched
- frontend/package.json (5 new @fontsource deps)
- frontend/package-lock.json
- frontend/src/assets/fonts.ts (new)
- frontend/src/main.ts (import './assets/fonts')
- frontend/src/stores/readerSettings.ts (FALLBACK_CHAINS + resolveFontFamily)

## Decisions / deviations
- Used latin-only subset imports (e.g. `latin-400.css`) instead of full
  per-weight files. The plan suggested `400.css` etc., which ship every
  unicode subset (cyrillic, vietnamese, latin-ext, greek, …) — total 838 KB
  woff2, well over the NFR-05 600 KB budget. Switching to latin subsets
  drops to 248 KB across 9 files while keeping every weight FR-40 calls
  for. If i18n requirements appear, swap the imports back.

## Runtime evidence
- `npm run build` — clean.
- `ls -l dist/assets/*.woff2` summed to 248 KB.
- `npx vitest run` — 237 / 237 pass (baseline).
- `npm run type-check` — clean.

## Commit
`8c786b6 feat(fonts): bundle reader webfonts via @fontsource with fallback chains`
