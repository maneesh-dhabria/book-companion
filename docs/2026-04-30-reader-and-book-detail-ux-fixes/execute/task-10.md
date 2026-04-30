# Task 10 — F2: Theme CSS coverage for night/paper/contrast

## Files touched
- frontend/src/assets/theme.css

## Decisions / deviations
- Followed existing vocabulary (the actual codebase uses
  `--color-text-muted`/`--color-text-accent`/`--color-accent-hover`/
  `--color-sidebar-text`/`--color-sidebar-active`, NOT the plan's
  `--color-text-tertiary`/`--color-text-inverted`/`--color-bg-muted`).
  Plan explicitly says "actual file's vocabulary wins."
- Backfilled `--highlight-saved-bg` + `--highlight-saved-fg` on dark + sepia
  so all 6 themes ship identical 20-var contracts. Without this the parity
  check was 18/18/18 vs 20/20/20.

## Runtime evidence
- Coverage grep returns 6.
- Python parity check: light/dark/sepia/night/paper/contrast all = 20 vars.
- `npm run type-check` — clean.

## Commit
`e0d9f9b feat(theme): add full CSS variables for night/paper/contrast themes`
