# Frontend Packaging for PyPI Distribution — Requirements

**Date:** 2026-04-12
**Status:** Draft
**Tier:** 2 — Enhancement

## Problem

The zero-dependency migration shipped `bookcompanion serve` as the single install-and-run command for the web UI, but the Vue SPA isn't actually bundled with the Python package. Today, `pip install bookcompanion && bookcompanion serve` starts the API but the web UI at `http://localhost:8000/` returns `{"detail":"Not Found"}` because:

- The frontend lives in `frontend/dist/` (created by `npm run build`), completely separate from the Python package
- The API code looks for static files at `Path(os.getcwd()) / "static"` — only works if the user happens to `cd backend/` and has manually copied the dist there
- Hatchling's `packages = ["app"]` means only `backend/app/` ships in the wheel — no frontend assets

The result is a broken promise: the zero-dependency packaging works for the API and CLI, but the web UI (which is the primary interface) is invisible to any user who installs from PyPI.

### Who & Why Now

**Target audience:** End users installing via `pip install bookcompanion` or `uv tool install bookcompanion`. They don't have Node.js, have never seen the `frontend/` directory, and expect `bookcompanion serve` to just work.

**Why now:** The zero-dependency packaging work is complete except for this final gap. The tool is ready to publish to PyPI, but shipping today would produce a broken install experience on every user's first run.

## Goals & Non-Goals

### Goals

- **Frontend ships inside the wheel** — `pip install bookcompanion` installs everything needed to run the web UI; no npm, no manual copy steps
- **Build happens automatically at package time** — running `uv build` / `hatch build` triggers the frontend build and bundles the output into the wheel; no separate workflow step
- **Runtime lookup is location-independent** — `bookcompanion serve` works from any directory, not just `backend/`
- **Dev mode is honest about missing assets** — when running from a git clone without a built frontend, users get a clear error with instructions rather than a silent 404

### Non-Goals

- NOT supporting pure-Python installs without a Node.js build step at release time — building the frontend requires Node, but this is a release-engineering concern, not an end-user concern
- NOT auto-running `npm run build` at runtime when assets are missing — this would require Node.js on end-user machines, defeating the whole point
- NOT supporting hot-reload in `bookcompanion serve` — developers can keep using `npm run dev` (Vite dev server) for frontend work, with the API proxied
- NOT serving the frontend from a CDN or separate host — the whole point is single-process, local-only installation
- NOT version-checking `app/static/` against the installed Python package version — if a developer or release script copies a mismatched build in, they'll see stale UI but the system won't detect it. Adds complexity for a problem that doesn't exist in the PyPI install path.

## Solution Direction

Three connected changes:

### 1. Move static files inside the Python package

Relocate the frontend's built output to `backend/app/static/` — inside the Python package namespace. Hatchling automatically includes everything under `app/` in the wheel, so no manifest changes are needed beyond ensuring the directory exists at build time.

The API code looks up static files relative to the `app` module's `__file__`, not the current working directory. This makes `bookcompanion serve` work from anywhere.

### 2. Automate the frontend build at wheel creation

Add a build hook to `pyproject.toml` that runs `npm install && npm run build` in `frontend/` and copies the result into `backend/app/static/` before hatchling packages the wheel. This means:

- Running `uv build` or `hatch build` produces a wheel with the latest frontend
- Release pipelines (including GitHub Actions for PyPI publish) require no extra steps
- Developers building locally get a working wheel automatically

The build hook requires Node.js at build time only — end users never need it.

### 3. Clear dev-mode feedback

When `bookcompanion serve` starts and detects that `app/static/index.html` is missing (typical dev-from-clone scenario), print a clear error message explaining the two valid workflows:

- For testing the production build: `cd frontend && npm run build && cp -r dist ../backend/app/static`
- For frontend development: `bookcompanion serve --api-only` + `cd frontend && npm run dev` in another terminal

Optionally, `--api-only` flag suppresses the error and serves only the API.

## User Journeys

### Primary: Install from PyPI and run

1. User runs `pip install bookcompanion` (or `uv tool install bookcompanion`)
2. Runs `bookcompanion init` — creates data dir, runs migrations, downloads embedding model
3. Runs `bookcompanion serve` — starts the web server
4. Opens `http://localhost:8000` in browser — sees the Vue UI, not a 404
5. Full functionality available (library, search, reading, summarization if Claude/Codex CLI is installed)

### Release engineer: Publish a new version

1. Developer tags a release and runs `uv build` (or CI runs it)
2. The build hook automatically:
   - Runs `npm install` and `npm run build` in `frontend/`
   - Copies `frontend/dist/*` into `backend/app/static/`
   - Packages everything under `backend/app/` into the wheel
3. The resulting `bookcompanion-X.Y.Z-py3-none-any.whl` contains both the Python code and the built SPA
4. `twine upload` (or CI) publishes to PyPI
5. End users can `pip install` and get a working web UI immediately

### Developer: Cloned repo, first run

1. Developer clones the repo, runs `uv sync --dev`
2. Runs `bookcompanion serve` from any directory
3. **If `app/static/` exists** (they've built before): serve starts normally, UI works
4. **If `app/static/` is missing**: serve prints a clear error with two options and exits (or continues API-only with `--api-only` flag)

### Developer: Frontend development loop

1. Developer runs `bookcompanion serve --api-only` in one terminal
2. Runs `cd frontend && npm run dev` in another terminal
3. Opens `http://localhost:5173` — Vite dev server with hot reload, proxies `/api/*` to port 8000
4. Edits Vue components, sees changes instantly

### Developer: Backend smoke-test with real UI

1. Developer is iterating on backend code and wants to click through the UI to smoke-test a change
2. Runs `cd frontend && npm run build` once (~1 second) to populate `backend/app/static/`
3. Runs `bookcompanion serve` — full UI available at `http://localhost:8000`
4. If backend code is edited later, just restart `bookcompanion serve` — the already-built frontend keeps working
5. Only needs to re-run `npm run build` if frontend source changes

### Error: Running serve from an installed package with missing assets

1. User somehow installed the package but `app/static/index.html` is missing (e.g., building the wheel without the build hook — shouldn't happen in the happy path)
2. Serve starts and prints: "Frontend assets missing from the installed package. This is a packaging bug — please report it at <repo URL>."
3. API still works so the user isn't completely stuck

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Target end users installing from PyPI | (a) PyPI users only, (b) Git-clone devs only, (c) Both | The zero-dependency packaging explicitly targets PyPI users; shipping a broken web UI would contradict that goal. Dev experience is a secondary concern handled by D4. |
| D2 | Static files live in `backend/app/static/` | (a) Inside package, (b) app.static subpackage with importlib.resources, (c) Keep backend/static/ + package-data | Simplest idiomatic pattern. Hatchling auto-includes it. Runtime lookup via `Path(__file__).parent / "static"` is portable and cwd-independent. |
| D3 | Build hook in `pyproject.toml` triggers `npm build` at wheel creation | (a) Build hook, (b) Manual script, (c) CI-only, (d) Pre-built and committed | Build hook is zero manual steps for release and keeps the repo clean (no committed minified JS). Requires Node at build time only, which is acceptable for release engineering. CI-only locks releases to CI infrastructure unnecessarily. |
| D4 | Dev mode prints a clear error when static files missing | (a) Clear error + instructions, (b) Auto-run npm build, (c) Serve API-only silently | Explicit is better than magical. Auto-running npm requires Node on every dev machine and is slow. Silent 404 is what we have today and is confusing. Clear error + `--api-only` flag gives developers a good escape hatch. |

## Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Which `hatch-build-scripts` plugin should we use, or should we write a custom `hatch_build.py` hook? Need to evaluate at spec time. | Engineer | Before spec |
| 2 | Should the build hook skip npm if `app/static/index.html` already exists and is newer than `frontend/src/`? Would speed up incremental wheel builds but adds complexity. | Maneesh | Before spec |
| 3 | Should `--api-only` be a permanent CLI flag or just a dev workaround? If permanent, document it; if dev-only, consider `BOOKCOMPANION_API_ONLY=1` env var instead. | Maneesh | Before spec |
