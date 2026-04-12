# Frontend Packaging for PyPI Distribution — Spec

**Date:** 2026-04-12
**Status:** Draft
**Tier:** 2 — Enhancement
**Requirements:** `docs/requirements/2026-04-12-frontend-packaging-for-distribution.md`

---

## 1. Problem Statement

`pip install bookcompanion && bookcompanion serve` boots the API but serves a 404 at `/` because the built Vue SPA lives in `frontend/dist/` (outside the Python package) and the API looks for it at `Path(os.getcwd()) / "static"`. A PyPI-installed user has neither a `frontend/dist` nor a correct `cwd`, so the primary interface is invisible. Success = a fresh `pip install` followed by `bookcompanion serve` renders the Vue UI at `http://localhost:8000/` from any working directory.

---

## 2. Goals

| # | Goal | Success Metric |
|---|------|---------------|
| G1 | Frontend ships inside the wheel | `unzip -l bookcompanion-*.whl \| grep 'app/static/index.html'` returns a match |
| G2 | Wheel build auto-compiles frontend | `uv build` from a clean checkout (no prior `npm run build`) produces a wheel containing built assets |
| G3 | `serve` works from any cwd on a PyPI install | `cd /tmp && bookcompanion serve` serves the UI at `/` |
| G4 | Dev-from-clone without built assets gets a clear error | Missing `app/static/index.html` → actionable error + non-zero exit (unless `--api-only`) |

---

## 3. Non-Goals

- Pure-Python release pipeline without Node — Node is required at wheel-build time only.
- Runtime `npm run build` when assets are missing — would force Node on end users.
- Hot reload via `bookcompanion serve` — devs continue using `npm run dev`.
- CDN / separate frontend host — single-process local-only.
- Version-checking `app/static/` against the installed package version.

---

## 4. Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Static files live in `backend/app/static/` | (a) `backend/app/static/`, (b) `app.static` subpackage via `importlib.resources`, (c) keep `backend/static/` + hatch `package-data` | Idiomatic Python-packaging pattern. Hatchling's `packages = ["app"]` auto-includes everything under `app/`. Keeps the runtime lookup trivial. |
| D2 | Runtime lookup via `Path(__file__).parent.parent / "static"` (from `app/api/main.py` → `app/static/`) | (a) `Path(__file__)`, (b) `importlib.resources.files('app')`, (c) `os.getcwd()` | Works for both editable (`pip install -e`) and wheel installs, cwd-independent, no extra deps. Matches user decision. |
| D3 | Custom `hatch_build.py` implementing `BuildHookInterface` | (a) Custom hook, (b) `hatch-build-scripts` plugin, (c) Makefile | Zero external build deps, ~30 lines, full control. User-selected. |
| D4 | Build hook always rebuilds (no mtime skip) | (a) Always rebuild, (b) Skip when `app/static/index.html` newer than `frontend/src/` | Deterministic wheels; npm build is ~5s. Avoids accidentally shipping stale assets. User-selected. |
| D5 | `--api-only` is a permanent, documented CLI flag | (a) Permanent flag, (b) `BOOKCOMPANION_API_ONLY=1` env var | Supports headless / API-integration use cases beyond dev; surfaces in `--help`. User-selected. |
| D6 | Dev-mode missing-asset handling: clear error + exit unless `--api-only` | (a) Error + exit, (b) Auto-run npm, (c) Silent API-only | Explicit > magical. Auto-run npm requires Node on every dev machine. |
| D7 | `backend/app/static/` is git-ignored | (a) Ignore (build artifact), (b) Commit the dist | Build artifact; committing creates noisy diffs and merge conflicts on every frontend change. Wheel build regenerates it. |
| D8 | Build hook targets `wheel` only, not `sdist` | (a) Wheel-only, (b) Both, (c) Sdist-only | Sdist carries source; wheel is the distributable artifact that end users install. Sdist consumers (rare) can run the build themselves. |

---

## 5. User Journeys

Covered in requirements §User Journeys. Key technical implication per journey:

- **PyPI install + serve:** wheel must contain `app/static/index.html` and referenced assets; `serve` must resolve static dir relative to module, not cwd.
- **Release build (`uv build`):** hatch `initialize` hook must fail the build if `npm` or `node` is missing, or if `npm run build` exits non-zero. No half-built wheels.
- **Cloned repo dev:** `serve` probes for `app/static/index.html` and either serves, exits with instructions, or runs API-only based on `--api-only`.

---

## 6. Functional Requirements

### 6.1 Packaging

| ID | Requirement |
|----|-------------|
| FR-01 | `backend/app/static/` exists as a directory inside the `app` Python package at wheel-build time and contains `index.html` + all Vite-emitted assets. |
| FR-02 | The built wheel (`bookcompanion-*.whl`) includes every file under `backend/app/static/` via hatchling's default `packages = ["app"]` include rule (no MANIFEST or extra config beyond the hook). |
| FR-03 | A custom `backend/hatch_build.py` implements `hatchling.builders.hooks.plugin.interface.BuildHookInterface`, registered in `pyproject.toml` under `[tool.hatch.build.targets.wheel.hooks.custom]`. |
| FR-04 | The hook's `initialize()` runs on `target_name == "wheel"` only; for `sdist` it is a no-op. |
| FR-05 | The hook resolves the frontend directory as `Path(self.root).parent / "frontend"` (where `self.root` is `backend/`, the directory containing `pyproject.toml`). It executes `npm ci` if `frontend/package-lock.json` exists, else `npm install`; then `npm run build`. Both commands run with `cwd=<frontend-dir>`. The hook always runs install (no skip-if-node_modules-exists heuristic) to keep wheels deterministic per D4. |
| FR-06 | After `npm run build` succeeds, the hook copies `frontend/dist/` recursively into `backend/app/static/`, replacing any prior contents. |
| FR-07 | If `npm` is not on `$PATH`, the hook raises a clear error: `"npm is required to build the frontend for the wheel. Install Node.js >=18 or build without the wheel target."` and exits non-zero. |
| FR-08 | If `npm install` or `npm run build` exit non-zero, the hook propagates the failure and surfaces stdout/stderr in the build log. |
| FR-09 | `backend/app/static/` is added to `.gitignore`. |

### 6.2 Runtime

| ID | Requirement |
|----|-------------|
| FR-10 | `app/api/main.py` computes `static_dir = Path(__file__).resolve().parent.parent / "static"` (i.e., `<app>/static/`), ignoring `Settings.web.static_dir` for path resolution. The settings field is **retained but marked deprecated** in its docstring (`"Deprecated: no longer honored; static dir is resolved relative to the app package."`) to avoid pydantic validation errors for users with `BOOKCOMPANION_WEB__STATIC_DIR` already set in their env. No code reads the field after this change. |
| FR-11a | Mount order: `/api/*`, `/events/*`, `/health`, `/docs` routers are registered BEFORE the `StaticFiles` mount at `/`, so API routes always match first. `StaticFiles(html=True)` then handles SPA client-side routes (unknown paths fall back to `index.html`). This preserves current ordering in `app/api/main.py`. |
| FR-11 | If `static_dir / "index.html"` exists, mount `StaticFiles(directory=str(static_dir), html=True)` at `/` as today. |
| FR-12 | If `static_dir / "index.html"` is missing and `--api-only` was not passed: the Typer command body performs a synchronous check and calls `sys.exit(1)` with the dev-mode error (§10) BEFORE `uvicorn.run()`. When `--reload` is in use, the same check runs in the reload child on re-import (check lives at app-factory boundary, not only in the parent). |
| FR-13 | If `--api-only` was passed (or `BOOKCOMPANION_API_ONLY=1`): `serve` logs `"Running in API-only mode; no static assets mounted at /."` and starts uvicorn without mounting `/`. |
| FR-14 | API routes (`/api/*`, `/events/*`, `/health`, `/docs`) remain functional whether or not static files mount. |

### 6.3 CLI

| ID | Requirement |
|----|-------------|
| FR-15 | `bookcompanion serve` gains a `--api-only / --no-api-only` Typer flag, default `False`. Help text: `"Start only the JSON API; do not require or mount the Vue SPA."`. |
| FR-16 | The flag may also be set via env var `BOOKCOMPANION_API_ONLY=1` (parsed by the CLI command, not by pydantic-settings, to avoid widening the config surface). |
| FR-17 | `bookcompanion serve --help` documents both the flag and the env var. |

---

## 7. API Changes

None. No route signatures, request/response shapes, SSE events, or auth change. The only behavioral change is the mount-point for `/` (present / absent based on asset availability and `--api-only`).

---

## 8. Frontend Design

None. The build output format is unchanged — this spec only relocates where the output lands and how it's loaded.

---

## 9. Edge Cases

| # | Scenario | Condition | Expected Behavior |
|---|----------|-----------|-------------------|
| E1 | PyPI install, no Node on user machine | `pip install bookcompanion && bookcompanion serve` | UI loads from `<site-packages>/app/static/`. Node never invoked at runtime. |
| E2 | `uv build` on machine without Node | `npm` not on `$PATH` | Build fails with FR-07 error; no wheel produced. |
| E3 | `npm run build` fails mid-build | Exit code ≠ 0 | Hook propagates; `uv build` fails; `backend/app/static/` may be partially written but is git-ignored. Next build retries cleanly after the hook clears the dir before copy. |
| E4 | Developer runs `bookcompanion serve` from repo without prior `npm run build` | `backend/app/static/index.html` missing, no `--api-only` | Exit 1 with dev-mode instructions (§10). |
| E5 | Developer runs `bookcompanion serve --api-only` from repo without build | Flag set | Starts uvicorn; `/` returns 404 (no mount); `/api/*` works; `/docs` works. |
| E6 | Installed wheel somehow lacks `index.html` (packaging bug) | `Path(__file__).parent.parent / "static" / "index.html"` missing in a non-editable install | Print packaging-bug message (§10) and exit 1 unless `--api-only`. Detect "installed" vs "dev" via presence of `pyproject.toml` two directories above the `app` package. |
| E7 | `cd /tmp && bookcompanion serve` after PyPI install | cwd is unrelated to package location | Works — static lookup is `__file__`-relative. |
| E8 | Editable install (`pip install -e backend/`) after local `npm run build` | `app/static/` populated | Works identically to wheel install. |
| E9 | `frontend/package-lock.json` absent | Fresh clone that deleted lockfile | Hook falls back to `npm install`. Build succeeds but wheel is non-deterministic across machines. Release path assumes the lockfile is committed (it is today); drifting from that should be caught in review. |
| E10 | Running `uv build --sdist` only | No wheel target | Hook's `initialize()` is a no-op (FR-04). Sdist ships without built assets (consumer runs the build themselves). |

---

## 10. Error Messages

### Dev-mode (repo checkout, asset missing) — FR-12

```
Frontend assets not found at <resolved-path>.

This usually means you're running from a cloned repo without a built frontend.
Two valid workflows:

  1. Build the SPA once, then run the server:
       cd frontend && npm install && npm run build
       bookcompanion serve

  2. Run API-only and use the Vite dev server for the UI:
       bookcompanion serve --api-only
       (in another terminal) cd frontend && npm run dev
       open http://localhost:5173

Or pass --api-only to suppress this check.
```

### Packaging-bug (installed wheel, asset missing) — E6

```
Frontend assets missing from the installed package at <resolved-path>.
This is a packaging bug — please report it at https://github.com/<owner>/book-companion/issues
including your installed version (bookcompanion --version) and platform.

Running with --api-only will start the API without the web UI.
```

The "installed vs dev" distinction: check whether `"site-packages"` appears in `Path(__file__).resolve().parts`. If yes → **installed mode** (wheel or editable install into site-packages); use the packaging-bug message. If no → **dev mode** (running from a source checkout without pip install); use the dev-mode message. This is more reliable than walking parents for `pyproject.toml`, which misclassifies editable installs.

---

## 11. Configuration & Feature Flags

| Variable / Flag | Default | Purpose |
|-----------------|---------|---------|
| `--api-only` (CLI) | `False` | Start API without requiring or mounting SPA |
| `BOOKCOMPANION_API_ONLY` | unset | Env-var equivalent of `--api-only`; CLI flag wins if both set |
| `Settings.web.static_dir` | retained, ignored | Kept in the pydantic model (marked deprecated in docstring) so existing `BOOKCOMPANION_WEB__STATIC_DIR` env vars don't trigger validation errors. No code reads it. Remove in a future major version. |

---

## 12. Testing & Verification Strategy

### 12.1 Unit tests

- `tests/unit/test_api_main.py::test_static_dir_resolves_to_package` — assert `static_dir` path ends with `app/static` and is absolute, regardless of `os.chdir('/tmp')`.
- `tests/unit/test_api_main.py::test_mount_skipped_when_index_missing` — with a tmpdir-isolated package copy and no `index.html`, asserting `StaticFiles` is not mounted.
- `tests/unit/test_api_main.py::test_mount_present_when_index_exists` — with a fake `index.html` in place, asserting `/` returns 200.
- `tests/unit/test_serve_command.py::test_serve_exits_when_assets_missing` — patch asset check, invoke Typer command, assert `SystemExit(1)` and expected stderr.
- `tests/unit/test_serve_command.py::test_serve_api_only_skips_asset_check` — `--api-only` short-circuits the check.
- `tests/unit/test_serve_command.py::test_api_only_env_var` — `BOOKCOMPANION_API_ONLY=1` equivalent to flag.

### 12.2 Integration tests

- `tests/integration/test_static_serving.py::test_root_serves_index_html` — create `app/static/index.html` fixture, start FastAPI TestClient, GET `/` returns 200 with `text/html`.
- `tests/integration/test_static_serving.py::test_spa_fallback_for_client_routes` — `StaticFiles(html=True)` serves `index.html` for unknown paths; GET `/library` returns the index.
- `tests/integration/test_static_serving.py::test_api_routes_unaffected_by_mount` — `/api/v1/books` returns JSON even with `/` mounted.

### 12.3 Build tests

- `tests/build/test_hatch_build_hook.py` (new dir):
  - `test_hook_no_op_for_sdist` — instantiate hook, call `initialize("standard", {})` with `target_name="sdist"`, assert `backend/app/static/` unchanged.
  - `test_hook_raises_when_npm_missing` — monkey-patch `shutil.which("npm")` → `None`, expect `RuntimeError` with FR-07 message.
  - `test_hook_copies_dist_on_success` — monkey-patch subprocess calls to simulate a successful `npm run build` that populates a temp `frontend/dist/`, assert files land in `backend/app/static/`.

### 12.4 Verification commands (manual pre-release checklist)

These are NOT CI-gated — the wheel build + fresh-venv install cycle is run by hand before each PyPI publish. Automating into CI is a follow-up if release cadence increases.

Run before declaring the task done:

```bash
# 1. Clean any prior build artifacts
rm -rf backend/app/static backend/dist

# 2. Build the wheel (exercises hatch_build.py → npm install → npm run build → copy)
cd backend && uv build

# 3. Inspect wheel contents
unzip -l dist/bookcompanion-*.whl | grep 'app/static/index.html'
# Expect: a matching line

unzip -l dist/bookcompanion-*.whl | grep 'app/static/assets/' | head
# Expect: JS/CSS bundles present

# 4. Install into a fresh venv and serve from /tmp
python -m venv /tmp/bc-test && /tmp/bc-test/bin/pip install backend/dist/bookcompanion-*.whl
cd /tmp && /tmp/bc-test/bin/bookcompanion init
/tmp/bc-test/bin/bookcompanion serve &
sleep 3

# 5. Hit the root
curl -sI http://localhost:8000/ | head -1
# Expect: HTTP/1.1 200 OK

curl -s http://localhost:8000/ | grep -o '<title>[^<]*</title>'
# Expect: <title>Book Companion</title> (or whatever the SPA sets)

curl -s http://localhost:8000/api/v1/books | head -c 50
# Expect: JSON, not HTML

kill %1

# 6. Dev-mode error path
rm -rf backend/app/static
cd backend && uv run bookcompanion serve
# Expect: exit 1, dev-mode error message

cd backend && uv run bookcompanion serve --api-only &
sleep 2
curl -s http://localhost:8000/api/v1/books | head -c 50
# Expect: JSON; / returns 404
kill %1
```

### 12.5 Playwright smoke (manual, post-wheel install)

- Install wheel in fresh venv, `bookcompanion init`, `bookcompanion serve`.
- Open `http://localhost:8000/` in browser. Verify: library list renders, navigation works, no console errors referencing missing assets.

---

## 13. Rollout & Updates

- No DB migration. No config migration needed (removed setting silently ignored).
- Ship in the next release. Version bump per existing semver policy.
- First PyPI publish cannot happen until this spec lands — it's the blocker.

### 13.1 User update flow

1. `pip install -U bookcompanion` (or `uv tool upgrade bookcompanion`) fetches the new wheel.
2. pip atomically replaces `<site-packages>/app/` — including `app/static/` — with the new wheel's contents. Old hashed asset bundles are removed; new ones land alongside the updated `index.html`.
3. Next `bookcompanion serve` loads new assets. Vite's content-hashed filenames (`index-<hash>.js`, `index-<hash>.css`) guarantee the browser fetches the updated bundles; the only thing the browser may cache is `index.html` itself.
4. **Browser cache edge case:** serve `index.html` with `Cache-Control: no-cache` (or `max-age=0, must-revalidate`) so the browser always revalidates the entry point. Hashed assets keep the default long-lived cache headers FastAPI's `StaticFiles` emits. Implement via a middleware or a small subclass of `StaticFiles` that overrides the response for `index.html`.

| ID | Requirement |
|----|-------------|
| FR-18 | Responses for `index.html` set `Cache-Control: no-cache` so updated wheels take effect on next page load without a manual hard refresh. |
| FR-20 | Responses for files under `app/static/assets/` (Vite's hashed-bundle output directory) set `Cache-Control: public, max-age=31536000, immutable`. Hashed filenames make long-lived caching safe; `index.html` (FR-18) is the only non-cached entry point. Implemented via a `StaticFiles` subclass overriding `file_response` / `get_response` to set headers based on path. |
| FR-21 | `app/static/` is served via Starlette's `StaticFiles`, which rejects traversal (`..`) and absolute paths. No custom file-serving code is introduced; we rely on upstream hardening. |

### 13.1.1 CI runner requirements

Any GitHub Actions workflow (or other CI) that runs `uv build` for the PyPI publish must:

- Install Node.js ≥18 (e.g., `actions/setup-node@v4` with `node-version: "20"`).
- Cache `frontend/node_modules/` keyed on `hashFiles('frontend/package-lock.json')` to keep wheel builds fast despite D4's "always install" rule.
- Fail fast if `npm ci` fails — do not publish a wheel without the built SPA (FR-07/08 already enforce this inside the hook).

### 13.1.2 Uninstall & reinstall

- `pip uninstall bookcompanion` removes `<site-packages>/app/` (including `app/static/`). User data at `~/Library/Application Support/bookcompanion/` (or platform equivalent) is **preserved** — out of scope for this change, but worth noting so reinstall resumes where uninstall left off.
- Reinstalling a different version writes a fresh `app/static/` tree; no manual cleanup needed.

### 13.1.3 Wheel size impact

Adding the built SPA grows the wheel by ~1–3 MB (Vite bundles compressed). Before: ~200 KB Python-only wheel; after: ~2–4 MB including assets. Well within PyPI's 60 MB per-file limit and acceptable for a local tool. `fastembed` model weights (~23 MB) are still downloaded on first `init`, not bundled.

### 13.2 Rollback

- `pip install bookcompanion==<prev-version>` restores the prior wheel (code + SPA) atomically.
- No data migrations touched by this spec → no DB rollback concerns.
- If a release's frontend is broken but API is fine, users can run `bookcompanion serve --api-only` as a temporary workaround while a patch release is prepared.

---

## 14. Research Sources

| Source | Type | Key Takeaway |
|--------|------|-------------|
| `backend/pyproject.toml` | Existing code | `packages = ["app"]` auto-includes subdirs; no MANIFEST needed |
| `backend/app/api/main.py:140-144` | Existing code | Current cwd-based static lookup; the bug site |
| `backend/app/config.py:73` | Existing code | `Settings.web.static_dir = "static"` — to be removed |
| Hatchling docs: Build hooks | External | `BuildHookInterface.initialize(version, build_data)` + `target_name` attribute for wheel/sdist discrimination |
| Vite `build.outDir` default | External | `frontend/dist/` is the canonical output; copy source for the hook |
| Django / Flask-packaged-SPA patterns (e.g., `django-spa`, `flask-vite`) | External | `importlib`-based or `__file__`-relative lookup is standard; CDN/separate-host is the alternative we explicitly reject |
| PEP 517 build-time deps | External | Node is not a PEP 517 backend requirement; treating it as a release-engineering prereq is accepted practice (see e.g., `pyarrow`, `cryptography`) |

---

## 15. Open Questions

None — all three from the requirements doc resolved in §4 (D3/D4/D5).

---

## 16. Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| — | Initial draft | — |
| 1 | FR-05 lacked explicit cwd resolution + install command choice; FR-10 vs §11 inconsistent on whether `Settings.web.static_dir` is removed or ignored; no mount-ordering requirement; no CI runner guidance; E9 wording underplayed determinism risk. | Tightened FR-05 with `Path(self.root).parent / "frontend"` and `npm ci`/`npm install` split. Reconciled FR-10 + §11 to "retained but deprecated + ignored" to avoid pydantic validation errors. Added FR-11a for mount ordering. Added §13.1.1 for CI runner setup. Strengthened E9. |
| 2 | Asset caching headers undefined for hashed bundles; FR-12 vague on `--reload` interaction; E6 dev-vs-installed heuristic (`pyproject.toml` walk) misclassifies editable installs; no note on uninstall/user-data persistence, wheel size delta, Starlette traversal protection, or CI-gating of the verification commands. | Added FR-20 (`Cache-Control: public, max-age=31536000, immutable` for `assets/`) and FR-21 (Starlette traversal protection). Tightened FR-12 to specify synchronous check in Typer body + reload-child re-entry. Replaced E6 heuristic with `"site-packages" in parts` check. Added §13.1.2 (uninstall preserves user data) and §13.1.3 (~1–3 MB wheel size increase). Clarified §12.4 is a manual pre-release checklist, not CI-gated. |
