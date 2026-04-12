# Frontend Packaging for PyPI Distribution — Implementation Plan

**Date:** 2026-04-12
**Spec:** `docs/specs/2026-04-12-frontend-packaging-for-distribution-spec.md`
**Requirements:** `docs/requirements/2026-04-12-frontend-packaging-for-distribution.md`

---

## Overview

Bundle the Vue SPA inside the `bookcompanion` wheel so `pip install bookcompanion && bookcompanion serve` serves the UI out of the box. Work splits into runtime changes (relocate static dir to `backend/app/static/`, cwd-independent lookup, `--api-only` flag, cache headers) and build-time automation (custom hatch hook that runs `npm ci && npm run build` at wheel creation). Runtime tasks land first because they're testable without Node; the hatch hook lands last.

**Done when:** `uv build` produces a wheel containing `app/static/index.html` and hashed asset bundles; installing that wheel into a fresh venv and running `bookcompanion serve` from `/tmp` returns the Vue UI at `http://localhost:8000/`; running `bookcompanion serve` from a clean repo without built assets exits 1 with the dev-mode message; `bookcompanion serve --api-only` starts the API without the SPA; all new unit and build-hook tests pass; full test suite green.

**Execution order:**

```
T1 (static dir + runtime lookup)
  └─ T2 (cache headers)       [P after T1]
  └─ T3 (--api-only + checks) [P after T1]
       └─ T4 (hatch build hook)  — depends on T1's dir contract
            └─ T5 (manual wheel smoke)
                 └─ T6 (final verification)
```

---

## Decision Log

> Inherits spec D1–D8. Below are implementation-specific decisions.

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Runtime changes (T1–T3) land before the build hook (T4) | (a) Runtime first, (b) Hook first, (c) Interleaved | Runtime changes are testable without Node installed locally and unblock the app-factory contract the hook depends on. Hook-first would leave the wheel layout out of sync with runtime for one or more commits. |
| D2 | Cache headers implemented via a `StaticFiles` subclass, not FastAPI middleware | (a) Subclass `StaticFiles`, (b) `Response` middleware, (c) Per-route handlers | Middleware would touch every response (including `/api/*`) and require path matching to stay scoped. The subclass overrides `file_response` only for the mounted static tree — narrower blast radius, easier to test. |
| D3 | Asset-existence check lives in `serve_cmd.py` body (sync, pre-uvicorn) AND in `create_app()` (defensive, for `--reload` re-import) | (a) CLI-only, (b) App-factory-only, (c) Both | CLI-only misses the `--reload` child re-import case called out in FR-12. App-factory-only means the bad-path exits after uvicorn starts, producing confusing logs. Both places keeps the error surface consistent. |
| D4 | `WebConfig.static_dir` is retained with a deprecation docstring, not removed | (a) Remove field, (b) Keep + deprecate, (c) Keep + honor as override | Spec FR-10 mandates retention to avoid pydantic validation errors for users who already set `BOOKCOMPANION_WEB__STATIC_DIR`. No runtime code reads it after this change. |
| D5 | Build-hook tests live in new dir `backend/tests/build/` | (a) `tests/unit/`, (b) `tests/integration/`, (c) `tests/build/` | They exercise a Hatchling extension, not app code; neither unit nor integration is a clean fit. Keeping them separate prevents the default `pytest tests/` run from requiring `hatchling` internals at import time if we ever prune it. |
| D6 | Hook uses `subprocess.run([...], check=True)` with explicit argv lists, not `shell=True` | (a) `shell=True`, (b) argv list | `shell=True` complicates argument quoting on Windows and opens injection surface. Argv-list is portable and testable via monkeypatch. |
| D7 | `.gitignore` adds `backend/app/static/` (not `app/static/`) | (a) Repo-relative path, (b) Wildcard `**/static/` | Exact path avoids accidentally ignoring other `static/` dirs (e.g., frontend public assets). |
| D8 | No change to `serve_cmd.py`'s auto-init logic | — | Out of scope; the auto-init runs `bookcompanion init` when `library.db` is missing, unrelated to static-asset handling. |

---

## Code Study Notes

- **`backend/app/api/main.py:140-144`** — current static mount: `Path(os.getcwd()) / settings.web.static_dir`, mounted AFTER all routers at line 122–138. Mount ordering (FR-11a) already satisfied by construction; our change is the path resolution and addition of cache headers via a subclass.
- **`backend/app/cli/commands/serve_cmd.py`** — simple sync Typer command, calls `uvicorn.run("app.api.main:app", ...)`. Adding `--api-only` + env-var parsing + asset check is a ~20-line change. Uses `get_settings()` from `app/cli/deps.py`.
- **`backend/app/config.py:71-73`** — `WebConfig` has `static_dir: str = "static"`. We keep the field, add a docstring noting deprecation.
- **`backend/pyproject.toml`** — `[tool.hatch.build.targets.wheel] packages = ["app"]` already auto-includes anything under `app/`. Adding a `[tool.hatch.build.targets.wheel.hooks.custom]` section registers `backend/hatch_build.py` as a custom build hook. Hatchling resolves the module relative to `pyproject.toml`.
- **Frontend state:** `frontend/dist/` exists today (built); `frontend/package-lock.json` exists — `npm ci` path is live. Vite emits `dist/index.html` + `dist/assets/<name>-<hash>.{js,css}`.
- **Test layout:** `backend/tests/unit/`, `backend/tests/integration/`, `backend/tests/e2e/`. `conftest.py` sets up async fixtures. Pattern for API tests: `httpx.AsyncClient` against `create_app()` or direct `TestClient`.
- **CLAUDE.md gotchas apply:** `expire_on_commit=False`, `selectinload`, WAL mode — none touched by this plan; we only modify app construction and add a CLI flag.

---

## Prerequisites

- Node.js ≥18 installed locally (required by T4 and T5; T1–T3 do not need it).
- `frontend/package-lock.json` present in the repo (it is).
- Clean working tree on branch `feature/zero-dependency-packaging`.
- `uv sync --dev` already run in `backend/`.
- `cd frontend && npm install` already run (or `npm ci` — produces `node_modules/`).

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `.gitignore` | Add `backend/app/static/` (build artifact) |
| Create | `backend/app/api/static_files.py` | `CachingStaticFiles(StaticFiles)` subclass (FR-18/FR-20) + `_resolve_static_dir()` + `_assets_present()` helpers. Path logic lives here (not in `main.py`) to keep `serve_cmd.py` from transitively importing `create_app()`. |
| Modify | `backend/app/api/main.py:140-144` | Import `CachingStaticFiles`, `_resolve_static_dir`, `_assets_present` from `app.api.static_files`; replace cwd-based lookup + mount block |
| Modify | `backend/app/config.py:71-73` | Add deprecation docstring to `WebConfig.static_dir`; field stays for backward compat |
| Modify | `backend/app/cli/commands/serve_cmd.py` | Add `--api-only` flag, `BOOKCOMPANION_API_ONLY` env var, asset-existence check with installed-vs-dev mode detection, dev/installed error messages |
| Create | `backend/hatch_build.py` | Custom `BuildHookInterface` running `npm ci`/`npm install` + `npm run build`, copying `frontend/dist/` → `backend/app/static/` for wheel target only |
| Modify | `backend/pyproject.toml` | Register the custom build hook under `[tool.hatch.build.targets.wheel.hooks.custom]` |
| Create | `backend/tests/unit/test_static_files.py` | Tests for `CachingStaticFiles` header behavior |
| Create | `backend/tests/unit/test_api_main_static.py` | Tests for static-dir resolution, mount presence/absence |
| Create | `backend/tests/unit/test_serve_cmd.py` | Tests for `--api-only`, env var, asset-check exit paths |
| Create | `backend/tests/integration/test_static_serving.py` | Integration: `/` serves `index.html`, SPA fallback for unknown paths, `/api/*` unaffected |
| Create | `backend/tests/build/__init__.py` | Package marker |
| Create | `backend/tests/build/test_hatch_build_hook.py` | Tests for hook sdist no-op, npm-missing error, successful copy |
| Modify | `docs/changelog.md` | User-facing entry for this change |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Hatchling API changes between versions break the custom hook | Low | Pin `hatchling` version in build-system requires; tests in T4 exercise the hook in isolation |
| `npm ci` fails on CI due to Node version mismatch | Medium | Spec §13.1.1 requires `actions/setup-node@v4` with `node-version: "20"`; document in release runbook |
| `CachingStaticFiles` subclass breaks on a future Starlette release (private method signature change) | Low | Unit tests in T2 exercise the overridden method directly; Starlette pin in lockfile catches breakage at upgrade time |
| Developers miss the new dev-mode error on first run after pull | Low | Message is explicit with two workflows; `--api-only` escape hatch works immediately |
| Wheel build on a machine with a stale `node_modules/` produces mismatched bundles | Medium | D4 always runs `npm ci`/`npm install`; release runbook says "clean checkout for publish" |

---

## Rollback

- **If T1–T3 land and break `serve`:** `git revert <commit>` restores cwd-based lookup. No data migrations involved.
- **If T4 lands and `uv build` breaks:** revert the `pyproject.toml` hook registration and `hatch_build.py`. Runtime code is unaffected. No wheels have been published yet on this branch.
- **Post-publish rollback:** `pip install bookcompanion==<prev-version>` — no DB or data migrations touched.

---

## Tasks

### T1: Package-local static dir + runtime lookup

**Goal:** Move the runtime static-dir resolution from `cwd` to the `app` package, mount after routers (preserving FR-11a), git-ignore the new dir.
**Spec refs:** FR-09, FR-10, FR-11, FR-11a, FR-21, D1 (spec), D2 (spec).

**Files:**
- Modify: `.gitignore`
- Create: `backend/app/api/static_files.py` (path helpers only; `CachingStaticFiles` added in T2)
- Modify: `backend/app/api/main.py:140-144`
- Modify: `backend/app/config.py:71-73`
- Create: `backend/tests/unit/test_api_main_static.py`

**Steps:**

- [ ] Step 1: Add `.gitignore` entry.
  Append to `.gitignore`:
  ```
  # Built SPA bundled at wheel-build time by hatch_build.py
  backend/app/static/
  ```

- [ ] Step 2: Add deprecation docstring to `WebConfig.static_dir`.
  In `backend/app/config.py`, update `WebConfig`:
  ```python
  class WebConfig(BaseModel):
      show_cost_estimates: bool = False
      static_dir: str = "static"
      """Deprecated: no longer honored. Static dir is resolved relative to the
      `app` package (`app/static/`). Field retained to avoid validation errors
      for users with BOOKCOMPANION_WEB__STATIC_DIR already set."""
  ```
  Note: pydantic v2 doesn't attach Python docstrings to fields at runtime; this is a reader-facing comment. Acceptable.

- [ ] Step 3: Write failing test for static-dir resolution.
  Create `backend/tests/unit/test_api_main_static.py`:
  ```python
  from pathlib import Path

  import pytest

  from app.api import static_files
  import app.api.main as api_main


  @pytest.fixture(autouse=True)
  def _clear_api_only(monkeypatch):
      monkeypatch.delenv("BOOKCOMPANION_API_ONLY", raising=False)


  def test_static_dir_resolves_to_package(tmp_path, monkeypatch):
      """Static dir must resolve relative to the app package, not cwd."""
      monkeypatch.chdir(tmp_path)
      resolved = static_files._resolve_static_dir()
      assert resolved.is_absolute()
      assert resolved.parts[-2:] == ("app", "static")
      # Must NOT be cwd-relative
      assert not str(resolved).startswith(str(tmp_path))


  def test_assets_present_false_when_index_missing(tmp_path, monkeypatch):
      monkeypatch.setattr(static_files, "_resolve_static_dir", lambda: tmp_path)
      assert static_files._assets_present() is False


  def test_assets_present_true_when_index_exists(tmp_path, monkeypatch):
      (tmp_path / "index.html").write_text("<html></html>")
      monkeypatch.setattr(static_files, "_resolve_static_dir", lambda: tmp_path)
      assert static_files._assets_present() is True


  def test_create_app_mounts_static_when_present(tmp_path, monkeypatch):
      (tmp_path / "index.html").write_text("<html></html>")
      monkeypatch.setattr(static_files, "_resolve_static_dir", lambda: tmp_path)
      app = api_main.create_app()
      static_mounts = [r for r in app.routes if getattr(r, "name", "") == "static"]
      assert len(static_mounts) == 1


  def test_create_app_skips_mount_when_missing(tmp_path, monkeypatch):
      monkeypatch.setattr(static_files, "_resolve_static_dir", lambda: tmp_path)
      app = api_main.create_app()
      static_mounts = [r for r in app.routes if getattr(r, "name", "") == "static"]
      assert len(static_mounts) == 0
  ```

  **Note:** `create_app()` runs full router registration and instantiates `Settings()`. If this fails in your local env (e.g., `Settings()` file probing), fall back to asserting mount behavior on a minimal Starlette app that calls only the mount block, not the whole factory.

- [ ] Step 4: Run tests, expect failures.
  Run: `cd backend && uv run pytest tests/unit/test_api_main_static.py -v`
  Expected: FAIL — `_resolve_static_dir` / `_assets_present` don't exist.

- [ ] Step 5: Create `backend/app/api/static_files.py` with path helpers (T2 will add `CachingStaticFiles` to this same file).
  ```python
  """Static-asset path resolution + SPA-friendly cache headers.

  Path helpers live here (not in main.py) so the CLI can import them without
  triggering create_app() as a side effect.
  """
  from __future__ import annotations

  from pathlib import Path


  def _resolve_static_dir() -> Path:
      """Resolve static dir relative to the app package, cwd-independent.

      __file__ = .../app/api/static_files.py
              -> parent = .../app/api
              -> parent.parent = .../app
      """
      return Path(__file__).resolve().parent.parent / "static"


  def _assets_present() -> bool:
      return (_resolve_static_dir() / "index.html").is_file()
  ```

- [ ] Step 6: Update `backend/app/api/main.py`.
  Replace lines 140–144 (and `import os` if unused afterward — verify with `grep`):
  ```python
  from app.api.static_files import _assets_present, _resolve_static_dir
  ```
  In `create_app()` replace the mount block:
  ```python
      # Serve built Vue SPA if assets are present. Mounted AFTER routers
      # so /api/*, /health, /docs always match first (FR-11a).
      if _assets_present():
          static_dir = _resolve_static_dir()
          app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
  ```
  (T2 will swap `StaticFiles` for `CachingStaticFiles`.)

- [ ] Step 7: Run tests, expect pass.
  Run: `cd backend && uv run pytest tests/unit/test_api_main_static.py -v`
  Expected: 5 passed.

- [ ] Step 8: Commit.
  ```bash
  git add .gitignore backend/app/api/main.py backend/app/api/static_files.py backend/app/config.py backend/tests/unit/test_api_main_static.py
  git commit -m "feat(packaging): resolve static dir relative to app package"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/main.py app/config.py tests/unit/test_api_main_static.py` — no lint errors.
- `cd backend && uv run pytest tests/unit/test_api_main_static.py -v` — 5 passed.
- `grep -n "os.getcwd" backend/app/api/main.py` — no matches (the old cwd lookup is gone).

---

### T2: Cache-control headers for static assets

**Goal:** Subclass `StaticFiles` to emit `Cache-Control: no-cache` on `index.html` and `public, max-age=31536000, immutable` under `assets/`.
**Spec refs:** FR-18, FR-20.

**Files:**
- Modify: `backend/app/api/static_files.py` (append `CachingStaticFiles` — file created in T1)
- Modify: `backend/app/api/main.py` (swap `StaticFiles` → `CachingStaticFiles` in the mount)
- Create: `backend/tests/unit/test_static_files.py`

**Steps:**

- [ ] Step 1: Write failing tests for `CachingStaticFiles`.
  Create `backend/tests/unit/test_static_files.py`:
  ```python
  import pytest
  from starlette.requests import Request
  from starlette.testclient import TestClient
  from starlette.applications import Starlette
  from starlette.routing import Mount

  from app.api.static_files import CachingStaticFiles


  @pytest.fixture
  def static_tree(tmp_path):
      (tmp_path / "index.html").write_text("<html>hi</html>")
      assets = tmp_path / "assets"
      assets.mkdir()
      (assets / "app-abc123.js").write_text("console.log('x')")
      (assets / "app-abc123.css").write_text("body{}")
      return tmp_path


  def _client(static_tree):
      app = Starlette(routes=[
          Mount("/", CachingStaticFiles(directory=str(static_tree), html=True), name="static")
      ])
      return TestClient(app)


  def test_index_html_has_no_cache(static_tree):
      client = _client(static_tree)
      r = client.get("/")
      assert r.status_code == 200
      assert r.headers["cache-control"] == "no-cache"


  def test_index_html_direct_path_has_no_cache(static_tree):
      client = _client(static_tree)
      r = client.get("/index.html")
      assert r.status_code == 200
      assert r.headers["cache-control"] == "no-cache"


  def test_hashed_asset_is_immutable(static_tree):
      client = _client(static_tree)
      r = client.get("/assets/app-abc123.js")
      assert r.status_code == 200
      assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


  def test_hashed_css_is_immutable(static_tree):
      client = _client(static_tree)
      r = client.get("/assets/app-abc123.css")
      assert r.status_code == 200
      assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


  def test_spa_fallback_for_unknown_path_has_no_cache(static_tree):
      """html=True falls back to index.html for unknown paths — must get no-cache too."""
      client = _client(static_tree)
      r = client.get("/library/some-id")
      assert r.status_code == 200
      assert r.headers["cache-control"] == "no-cache"
  ```

- [ ] Step 2: Run tests, expect failures.
  Run: `cd backend && uv run pytest tests/unit/test_static_files.py -v`
  Expected: FAIL — `CachingStaticFiles` doesn't exist.

- [ ] Step 3: Append `CachingStaticFiles` to `backend/app/api/static_files.py` (the file T1 created with the path helpers).
  Add imports at top:
  ```python
  from fastapi.staticfiles import StaticFiles
  from starlette.responses import Response
  from starlette.types import Scope
  ```
  Append below the helpers:
  ```python
  _IMMUTABLE = "public, max-age=31536000, immutable"
  _NO_CACHE = "no-cache"


  class CachingStaticFiles(StaticFiles):
      """Emit no-cache on index.html and long-lived immutable on assets/."""

      async def get_response(self, path: str, scope: Scope) -> Response:
          response = await super().get_response(path, scope)
          if response.status_code == 200:
              if path.startswith("assets/"):
                  response.headers["cache-control"] = _IMMUTABLE
              else:
                  # index.html, SPA fallback, and any other top-level file
                  response.headers["cache-control"] = _NO_CACHE
          return response
  ```

- [ ] Step 4: Swap mount class in `app/api/main.py`.
  Add import: `from app.api.static_files import CachingStaticFiles`
  In `create_app()`, change:
  ```python
  app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
  ```
  to:
  ```python
  app.mount("/", CachingStaticFiles(directory=str(static_dir), html=True), name="static")
  ```
  Remove the now-unused `from fastapi.staticfiles import StaticFiles` if nothing else uses it.

- [ ] Step 5: Run tests, expect pass.
  Run: `cd backend && uv run pytest tests/unit/test_static_files.py tests/unit/test_api_main_static.py -v`
  Expected: 10 passed total (5 from T1 still green, 5 new).

- [ ] Step 6: Commit.
  ```bash
  git add backend/app/api/static_files.py backend/app/api/main.py backend/tests/unit/test_static_files.py
  git commit -m "feat(packaging): cache-control headers for SPA assets"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/static_files.py app/api/main.py tests/unit/test_static_files.py` — no lint errors.
- `cd backend && uv run pytest tests/unit/test_static_files.py -v` — 5 passed.
- Manual: create a fake `backend/app/static/index.html`, run `uv run bookcompanion serve`, then:
  `curl -sI http://localhost:8000/ | grep -i cache-control` → `cache-control: no-cache`
  Clean up the fake file afterward.

---

### T3: `--api-only` flag + asset check + dev/installed error messages

**Goal:** Add `--api-only` Typer flag and `BOOKCOMPANION_API_ONLY` env var to `serve`; exit with a clear message if assets are missing unless the flag is set; distinguish dev vs installed mode via the `site-packages` parts check.
**Spec refs:** FR-12, FR-13, FR-14, FR-15, FR-16, FR-17, E4, E5, E6.

**Files:**
- Modify: `backend/app/cli/commands/serve_cmd.py`
- Modify: `backend/app/api/main.py` (add defensive check for `--reload` re-import path)
- Create: `backend/tests/unit/test_serve_cmd.py`

**Steps:**

- [ ] Step 1: Write failing tests.
  Create `backend/tests/unit/test_serve_cmd.py`:
  ```python
  import os
  from pathlib import Path

  import pytest
  from typer.testing import CliRunner

  from app.cli.main import app as cli_app
  import app.cli.commands.serve_cmd as serve_cmd


  runner = CliRunner()  # Typer's CliRunner merges stderr/stdout into result.output


  @pytest.fixture(autouse=True)
  def _clear_api_only(monkeypatch):
      """Ensure env-var state doesn't leak between tests."""
      monkeypatch.delenv("BOOKCOMPANION_API_ONLY", raising=False)


  @pytest.fixture(autouse=True)
  def _no_uvicorn(monkeypatch):
      """Prevent uvicorn from actually starting in tests."""
      calls = []
      monkeypatch.setattr(serve_cmd.uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))
      monkeypatch.setattr(serve_cmd, "_auto_init_if_needed", lambda settings: None)
      return calls


  def test_is_installed_mode_detection():
      # Path containing site-packages → installed
      assert serve_cmd._is_installed_mode(Path("/x/site-packages/app/api/main.py")) is True
      # Plain dev path → not installed
      assert serve_cmd._is_installed_mode(Path("/home/dev/repo/backend/app/api/main.py")) is False


  def test_serve_exits_when_assets_missing_dev_mode(monkeypatch, _no_uvicorn):
      monkeypatch.setattr(serve_cmd, "_assets_present", lambda: False)
      monkeypatch.setattr(serve_cmd, "_is_installed_mode", lambda p=None: False)
      result = runner.invoke(cli_app, ["serve"])
      assert result.exit_code == 1
      assert "Frontend assets not found" in result.output
      assert "npm run build" in result.output
      assert _no_uvicorn == []  # uvicorn.run was never called


  def test_serve_exits_when_assets_missing_installed_mode(monkeypatch, _no_uvicorn):
      monkeypatch.setattr(serve_cmd, "_assets_present", lambda: False)
      monkeypatch.setattr(serve_cmd, "_is_installed_mode", lambda p=None: True)
      result = runner.invoke(cli_app, ["serve"])
      assert result.exit_code == 1
      assert "packaging bug" in result.output.lower()
      assert _no_uvicorn == []


  def test_serve_api_only_skips_asset_check(monkeypatch, _no_uvicorn):
      monkeypatch.setattr(serve_cmd, "_assets_present", lambda: False)
      result = runner.invoke(cli_app, ["serve", "--api-only"])
      assert result.exit_code == 0
      assert _no_uvicorn, "uvicorn.run should have been called"


  def test_serve_api_only_env_var(monkeypatch, _no_uvicorn):
      monkeypatch.setattr(serve_cmd, "_assets_present", lambda: False)
      monkeypatch.setenv("BOOKCOMPANION_API_ONLY", "1")
      result = runner.invoke(cli_app, ["serve"])
      assert result.exit_code == 0
      assert _no_uvicorn


  def test_serve_starts_when_assets_present(monkeypatch, _no_uvicorn):
      monkeypatch.setattr(serve_cmd, "_assets_present", lambda: True)
      result = runner.invoke(cli_app, ["serve"])
      assert result.exit_code == 0
      assert _no_uvicorn


  def test_serve_help_documents_api_only():
      result = runner.invoke(cli_app, ["serve", "--help"])
      assert result.exit_code == 0
      assert "--api-only" in result.stdout
      assert "BOOKCOMPANION_API_ONLY" in result.stdout
  ```

- [ ] Step 2: Run tests, expect failures.
  Run: `cd backend && uv run pytest tests/unit/test_serve_cmd.py -v`
  Expected: FAIL — helpers don't exist, flag not defined.

- [ ] Step 3: Implement in `backend/app/cli/commands/serve_cmd.py`.
  Rewrite the file (keeping auto-init behavior):
  ```python
  """bookcompanion serve — start the web server."""
  import os
  import socket
  import subprocess
  import sys
  from pathlib import Path

  import typer
  import uvicorn
  from rich.console import Console

  from app.api.static_files import _assets_present, _resolve_static_dir
  from app.cli.deps import get_settings

  console = Console()


  DEV_MODE_ERROR = """\
  Frontend assets not found at {path}.

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
  """

  INSTALLED_MODE_ERROR = """\
  Frontend assets missing from the installed package at {path}.
  This is a packaging bug — please report it with your installed version
  (bookcompanion --version) and platform.

  Running with --api-only will start the API without the web UI.
  """


  def _is_installed_mode(static_dir: Path | None = None) -> bool:
      """Distinguish installed (site-packages) vs dev (source checkout) mode."""
      path = static_dir if static_dir is not None else _resolve_static_dir()
      return "site-packages" in path.resolve().parts


  def _auto_init_if_needed(settings) -> None:
      db_path = Path(settings.data.directory) / "library.db"
      if not db_path.exists():
          console.print("[yellow]First run detected, initializing...[/yellow]")
          subprocess.run(["bookcompanion", "init"], check=False)


  def serve(
      port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
      host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
      api_only: bool = typer.Option(
          False,
          "--api-only/--no-api-only",
          help=(
              "Start only the JSON API; do not require or mount the Vue SPA. "
              "Also settable via BOOKCOMPANION_API_ONLY=1."
          ),
      ),
  ) -> None:
      """Start the Book Companion web server."""
      # CLI flag wins over env var
      if not api_only and os.environ.get("BOOKCOMPANION_API_ONLY", "") not in ("", "0", "false", "False"):
          api_only = True

      settings = get_settings()
      _auto_init_if_needed(settings)

      if not api_only and not _assets_present():
          static_dir = _resolve_static_dir()
          if _is_installed_mode(static_dir):
              msg = INSTALLED_MODE_ERROR.format(path=static_dir)
          else:
              msg = DEV_MODE_ERROR.format(path=static_dir)
          console.print(msg, style="red")
          raise typer.Exit(code=1)

      if api_only:
          console.print("[yellow]Running in API-only mode; no static assets mounted at /.[/yellow]")

      console.print(f"\n[bold]Book Companion[/bold] — serving at http://localhost:{port}")
      try:
          hostname = socket.gethostname()
          for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
              ip = info[4][0]
              if not ip.startswith("127."):
                  console.print(f"  Also available at: http://{ip}:{port}")
                  break
      except Exception:
          pass

      # Propagate --api-only to the app factory for the reload-child case (FR-12).
      # uvicorn.run() stays in-process, so this env mutation ends with the process.
      # Kept even though the `serve` command doesn't expose --reload today — future-proofs
      # per Decision D3 so a reloaded app factory sees the same mode as the parent CLI.
      if api_only:
          os.environ["BOOKCOMPANION_API_ONLY"] = "1"

      console.print()
      uvicorn.run("app.api.main:app", host=host, port=port)
  ```

- [ ] Step 4: Update `create_app()` in `backend/app/api/main.py` to respect `BOOKCOMPANION_API_ONLY` on re-import (FR-12 reload child):
  Change the mount block to:
  ```python
      api_only = os.environ.get("BOOKCOMPANION_API_ONLY", "") not in ("", "0", "false", "False")
      if not api_only and _assets_present():
          static_dir = _resolve_static_dir()
          app.mount("/", CachingStaticFiles(directory=str(static_dir), html=True), name="static")
  ```
  Re-add `import os` if it was removed. Update the existing T1 tests if they rely on `create_app()` always mounting when present — add an explicit `monkeypatch.delenv("BOOKCOMPANION_API_ONLY", raising=False)` at test top or set `autouse` fixture. Preferred: in `test_api_main_static.py`, add an autouse fixture that clears the env var:
  ```python
  @pytest.fixture(autouse=True)
  def _clear_api_only(monkeypatch):
      monkeypatch.delenv("BOOKCOMPANION_API_ONLY", raising=False)
  ```

- [ ] Step 5: Run all affected tests.
  Run: `cd backend && uv run pytest tests/unit/test_serve_cmd.py tests/unit/test_api_main_static.py tests/unit/test_static_files.py -v`
  Expected: all green (7 + 5 + 5 = 17 passed).

- [ ] Step 6: Manual smoke — dev-mode error path.
  ```bash
  rm -rf backend/app/static
  cd backend && uv run bookcompanion serve
  ```
  Expected: exit 1, dev-mode message printed, mentions `npm run build` and `--api-only`.

  Then: `cd backend && uv run bookcompanion serve --api-only &` → expect uvicorn starts; `curl -s http://localhost:8000/api/v1/books` returns JSON; `curl -sI http://localhost:8000/` returns 404. `kill %1`.

- [ ] Step 7: Commit.
  ```bash
  git add backend/app/cli/commands/serve_cmd.py backend/app/api/main.py backend/tests/unit/test_serve_cmd.py backend/tests/unit/test_api_main_static.py
  git commit -m "feat(packaging): --api-only flag and asset-check error messages"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/cli/commands/serve_cmd.py app/api/main.py tests/unit/test_serve_cmd.py` — no lint errors.
- `cd backend && uv run pytest tests/unit/test_serve_cmd.py -v` — 7 passed.
- `cd backend && uv run bookcompanion serve --help | grep -- "--api-only"` — the flag appears with env-var mention.

---

### T4: Custom hatch build hook

**Goal:** Automate frontend build at wheel creation: `npm ci` (or `npm install`), `npm run build`, copy `frontend/dist/` → `backend/app/static/`. Sdist is a no-op. Fail loudly if `npm` is missing or the build fails.
**Spec refs:** FR-01 – FR-08, E2, E3, E9, E10.

**Files:**
- Create: `backend/hatch_build.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/tests/build/__init__.py`
- Create: `backend/tests/build/test_hatch_build_hook.py`

**Steps:**

- [ ] Step 1: Write failing hook tests.
  Create `backend/tests/build/__init__.py` (empty).
  Create `backend/tests/build/test_hatch_build_hook.py`:
  ```python
  import shutil
  import subprocess
  from pathlib import Path

  import pytest

  # Import path — hatch_build.py lives in backend/, so add it to sys.path in conftest
  # or import via importlib. We'll use importlib.
  import importlib.util


  HOOK_PATH = Path(__file__).resolve().parents[2] / "hatch_build.py"


  def _load_hook():
      spec = importlib.util.spec_from_file_location("hatch_build", HOOK_PATH)
      mod = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(mod)
      return mod


  def _make_hook(root: Path, target_name: str):
      """Bypass BuildHookInterface.__init__ (signature varies across Hatchling versions).

      Tests only exercise `initialize()`, which reads `self.root` and `self.target_name`.
      Instantiating via __new__ keeps the test stable across Hatchling upgrades.
      """
      hook_mod = _load_hook()
      hook = hook_mod.FrontendBuildHook.__new__(hook_mod.FrontendBuildHook)
      hook.root = str(root)
      hook.target_name = target_name
      return hook


  @pytest.fixture
  def fake_repo(tmp_path):
      """Simulate backend/ + frontend/ layout."""
      backend = tmp_path / "backend"
      frontend = tmp_path / "frontend"
      backend.mkdir()
      (backend / "app").mkdir()
      frontend.mkdir()
      (frontend / "package.json").write_text('{"name":"bc","scripts":{"build":"echo"}}')
      (frontend / "package-lock.json").write_text("{}")
      return tmp_path


  def test_hook_no_op_for_sdist(fake_repo, monkeypatch):
      hook = _make_hook(fake_repo / "backend", "sdist")
      called = []
      monkeypatch.setattr(subprocess, "run", lambda *a, **kw: called.append((a, kw)))
      hook.initialize("standard", {})
      assert called == []
      assert not (fake_repo / "backend" / "app" / "static").exists()


  def test_hook_raises_when_npm_missing(fake_repo, monkeypatch):
      hook = _make_hook(fake_repo / "backend", "wheel")
      monkeypatch.setattr(shutil, "which", lambda cmd: None)
      with pytest.raises(RuntimeError, match="npm is required"):
          hook.initialize("standard", {})


  def test_hook_copies_dist_on_success(fake_repo, monkeypatch):
      frontend = fake_repo / "frontend"
      dist = frontend / "dist"

      def fake_run(argv, cwd=None, check=True, **kw):
          # Simulate npm run build populating dist/
          if argv[:2] == ["npm", "run"]:
              dist.mkdir(exist_ok=True)
              (dist / "index.html").write_text("<html>built</html>")
              (dist / "assets").mkdir(exist_ok=True)
              (dist / "assets" / "app-x.js").write_text("x")
          return subprocess.CompletedProcess(argv, 0)

      monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)
      monkeypatch.setattr(subprocess, "run", fake_run)

      hook = _make_hook(fake_repo / "backend", "wheel")
      hook.initialize("standard", {})

      static_dir = fake_repo / "backend" / "app" / "static"
      assert (static_dir / "index.html").read_text() == "<html>built</html>"
      assert (static_dir / "assets" / "app-x.js").read_text() == "x"


  def test_hook_replaces_stale_static_dir(fake_repo, monkeypatch):
      """A prior wheel build's app/static/ must be fully replaced, not merged."""
      frontend = fake_repo / "frontend"
      dist = frontend / "dist"
      static_dir = fake_repo / "backend" / "app" / "static"

      # Seed stale contents — a file that should NOT survive the rebuild.
      static_dir.mkdir(parents=True)
      (static_dir / "stale.js").write_text("old")
      (static_dir / "index.html").write_text("<html>stale</html>")

      def fake_run(argv, cwd=None, check=True, **kw):
          if argv[:2] == ["npm", "run"]:
              dist.mkdir(exist_ok=True)
              (dist / "index.html").write_text("<html>fresh</html>")
          return subprocess.CompletedProcess(argv, 0)

      monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)
      monkeypatch.setattr(subprocess, "run", fake_run)

      hook = _make_hook(fake_repo / "backend", "wheel")
      hook.initialize("standard", {})

      assert (static_dir / "index.html").read_text() == "<html>fresh</html>"
      assert not (static_dir / "stale.js").exists(), "stale files must be removed"


  def test_hook_raises_when_build_emits_no_index(fake_repo, monkeypatch):
      """npm run build succeeds but no index.html → hook must raise, not ship empty wheel."""
      monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)

      def silent_run(argv, cwd=None, check=True, **kw):
          # Simulate a build that succeeded but produced no output.
          return subprocess.CompletedProcess(argv, 0)

      monkeypatch.setattr(subprocess, "run", silent_run)
      hook = _make_hook(fake_repo / "backend", "wheel")
      with pytest.raises(RuntimeError, match="index.html is missing"):
          hook.initialize("standard", {})


  def test_hook_raises_when_npm_build_fails(fake_repo, monkeypatch):
      monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)

      def failing_run(argv, cwd=None, check=True, **kw):
          raise subprocess.CalledProcessError(1, argv, stderr=b"build failed")

      monkeypatch.setattr(subprocess, "run", failing_run)

      hook = _make_hook(fake_repo / "backend", "wheel")
      with pytest.raises(subprocess.CalledProcessError):
          hook.initialize("standard", {})
  ```

- [ ] Step 2: Run tests, expect failures.
  Run: `cd backend && uv run pytest tests/build/ -v`
  Expected: FAIL — `hatch_build.py` doesn't exist.

- [ ] Step 3: Implement `backend/hatch_build.py`.
  ```python
  """Custom Hatchling build hook: build the Vue SPA and bundle it into the wheel."""
  from __future__ import annotations

  import shutil
  import subprocess
  from pathlib import Path

  from hatchling.builders.hooks.plugin.interface import BuildHookInterface


  class FrontendBuildHook(BuildHookInterface):
      PLUGIN_NAME = "frontend-build"

      def initialize(self, version: str, build_data: dict) -> None:
          # Only run for wheel target. Sdist ships source; consumers build themselves.
          if self.target_name != "wheel":
              return

          backend_root = Path(self.root)  # backend/
          frontend_dir = backend_root.parent / "frontend"
          dist_dir = frontend_dir / "dist"
          static_dir = backend_root / "app" / "static"
          lockfile = frontend_dir / "package-lock.json"

          if shutil.which("npm") is None:
              raise RuntimeError(
                  "npm is required to build the frontend for the wheel. "
                  "Install Node.js >=18 or build without the wheel target."
              )

          install_cmd = ["npm", "ci"] if lockfile.exists() else ["npm", "install"]
          subprocess.run(install_cmd, cwd=str(frontend_dir), check=True)

          # Clear dist/ before build so a mid-build failure can't leave stale
          # files that silently get copied into the wheel on retry.
          if dist_dir.exists():
              shutil.rmtree(dist_dir)
          subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)

          # Sanity check: the build must have produced an index.html.
          # Guards against Vite outDir drift or a no-op build script.
          if not (dist_dir / "index.html").is_file():
              raise RuntimeError(
                  f"npm run build completed but {dist_dir / 'index.html'} is missing. "
                  "Check frontend/vite.config.* for a non-default outDir."
              )

          # Replace app/static/ atomically-ish: remove + copy.
          if static_dir.exists():
              shutil.rmtree(static_dir)
          shutil.copytree(dist_dir, static_dir)
  ```

- [ ] Step 4: Register the hook + pin Hatchling in `backend/pyproject.toml`.
  Update `[tool.hatch.build.targets.wheel]` and `[build-system]`:
  ```toml
  [tool.hatch.build.targets.wheel]
  packages = ["app"]

  [tool.hatch.build.targets.wheel.hooks.custom]
  path = "hatch_build.py"

  [build-system]
  requires = ["hatchling>=1.25,<2"]
  build-backend = "hatchling.build"
  ```
  Pinning the major version guards against Hatchling API drift breaking the custom hook between releases (Risk #1).

- [ ] Step 5: Run tests, expect pass.
  Run: `cd backend && uv run pytest tests/build/ -v`
  Expected: 6 passed.

- [ ] Step 6: Commit.
  ```bash
  git add backend/hatch_build.py backend/pyproject.toml backend/tests/build/__init__.py backend/tests/build/test_hatch_build_hook.py
  git commit -m "feat(packaging): hatch build hook to bundle Vue SPA into wheel"
  ```

**Inline verification:**
- `cd backend && uv run ruff check hatch_build.py tests/build/` — no lint errors.
- `cd backend && uv run pytest tests/build/ -v` — 6 passed.
- `cd backend && python -c "import importlib.util; s=importlib.util.spec_from_file_location('h','hatch_build.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.FrontendBuildHook.PLUGIN_NAME)"` — prints `frontend-build`.

---

### T5: Integration test + wheel smoke (pre-release checklist)

**Goal:** End-to-end integration coverage for static serving AND manual wheel smoke per spec §12.4.
**Spec refs:** FR-01, FR-02, FR-11, FR-14, §12.2, §12.4.

**Files:**
- Create: `backend/tests/integration/test_static_serving.py`

**Steps:**

- [ ] Step 1: Write integration tests.
  Create `backend/tests/integration/test_static_serving.py`:
  ```python
  import pytest
  from httpx import ASGITransport, AsyncClient

  import app.api.main as api_main


  @pytest.fixture
  def static_tree(tmp_path, monkeypatch):
      (tmp_path / "index.html").write_text("<!doctype html><title>Book Companion</title>")
      (tmp_path / "assets").mkdir()
      (tmp_path / "assets" / "main-deadbeef.js").write_text("console.log('ok')")
      monkeypatch.setattr(api_main, "_resolve_static_dir", lambda: tmp_path)
      monkeypatch.delenv("BOOKCOMPANION_API_ONLY", raising=False)
      return tmp_path


  @pytest.mark.asyncio
  async def test_root_serves_index_html(static_tree):
      app = api_main.create_app()
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as ac:
          r = await ac.get("/")
      assert r.status_code == 200
      assert "Book Companion" in r.text
      assert r.headers["cache-control"] == "no-cache"


  @pytest.mark.asyncio
  async def test_spa_fallback_for_client_routes(static_tree):
      app = api_main.create_app()
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as ac:
          r = await ac.get("/library/some-book-id")
      assert r.status_code == 200
      assert "Book Companion" in r.text


  @pytest.mark.asyncio
  async def test_hashed_asset_long_cache(static_tree):
      app = api_main.create_app()
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as ac:
          r = await ac.get("/assets/main-deadbeef.js")
      assert r.status_code == 200
      assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


  @pytest.mark.asyncio
  async def test_api_routes_unaffected_by_mount(static_tree):
      app = api_main.create_app()
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as ac:
          r = await ac.get("/health")
      assert r.status_code == 200
      # Health returns JSON, not the SPA
      assert "text/html" not in r.headers.get("content-type", "")
  ```

- [ ] Step 2: Run integration tests.
  Run: `cd backend && uv run pytest tests/integration/test_static_serving.py -v`
  Expected: 4 passed.

- [ ] Step 3: Manual wheel smoke (pre-release checklist from spec §12.4).
  ```bash
  cd backend
  rm -rf app/static dist
  uv build
  unzip -l dist/bookcompanion-*.whl | grep 'app/static/index.html'
  # Expect: a matching line
  unzip -l dist/bookcompanion-*.whl | grep 'app/static/assets/' | head
  # Expect: JS/CSS bundles present

  python3 -m venv /tmp/bc-test
  /tmp/bc-test/bin/pip install dist/bookcompanion-*.whl
  /tmp/bc-test/bin/bookcompanion init
  (cd /tmp && /tmp/bc-test/bin/bookcompanion serve) & SERVE_PID=$!
  sleep 3

  curl -sI http://localhost:8000/ | head -1
  # Expect: HTTP/1.1 200 OK
  curl -s http://localhost:8000/ | grep -o '<title>[^<]*</title>'
  # Expect: <title>...</title> (the SPA title)
  curl -sI http://localhost:8000/ | grep -i cache-control
  # Expect: cache-control: no-cache
  curl -s http://localhost:8000/api/v1/books | head -c 50
  # Expect: JSON

  kill $SERVE_PID
  rm -rf /tmp/bc-test
  ```
  Record the outputs of each `curl`/`unzip` command for the review.

- [ ] Step 4: Commit the integration test.
  ```bash
  git add backend/tests/integration/test_static_serving.py
  git commit -m "test(packaging): integration tests for SPA static serving"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_static_serving.py -v` — 4 passed.
- Manual wheel-smoke steps above all match "Expect" lines.

---

### T6: Final Verification

**Goal:** Verify the entire implementation works end-to-end and nothing regressed.

- [ ] **Lint & format:** `cd backend && uv run ruff check . && uv run ruff format --check .` — no errors.
- [ ] **Unit tests (new):** `cd backend && uv run pytest tests/unit/test_api_main_static.py tests/unit/test_static_files.py tests/unit/test_serve_cmd.py -v` — 17 passed.
- [ ] **Build-hook tests:** `cd backend && uv run pytest tests/build/ -v` — 6 passed.
- [ ] **Integration tests:** `cd backend && uv run pytest tests/integration/test_static_serving.py -v` — 4 passed.
- [ ] **Full suite regression:** `cd backend && uv run pytest` — all previously-passing tests still pass; expect the existing ~440 + 27 new = ~467 passing.
- [ ] **Wheel contains SPA:** `cd backend && rm -rf app/static dist && uv build && unzip -l dist/bookcompanion-*.whl | grep 'app/static/index.html'` — one match.
- [ ] **Fresh-venv install + serve from /tmp:**
  ```bash
  python3 -m venv /tmp/bc-final && /tmp/bc-final/bin/pip install backend/dist/bookcompanion-*.whl
  /tmp/bc-final/bin/bookcompanion init
  (cd /tmp && /tmp/bc-final/bin/bookcompanion serve) & SERVE_PID=$!
  sleep 3
  curl -sI http://localhost:8000/ | head -1   # HTTP/1.1 200 OK
  curl -s http://localhost:8000/api/v1/books | head -c 20   # JSON
  kill $SERVE_PID
  ```
- [ ] **Dev-mode error path:**
  ```bash
  rm -rf backend/app/static
  cd backend && uv run bookcompanion serve
  ```
  Expect exit 1, dev-mode message printed.
- [ ] **`--api-only` path:**
  ```bash
  cd backend && uv run bookcompanion serve --api-only & SERVE_PID=$!
  sleep 2
  curl -s http://localhost:8000/api/v1/books | head -c 20   # JSON
  curl -sI http://localhost:8000/ | head -1                  # 404
  kill $SERVE_PID
  ```
- [ ] **Env-var path:**
  ```bash
  cd backend && BOOKCOMPANION_API_ONLY=1 uv run bookcompanion serve & SERVE_PID=$!
  sleep 2
  curl -sI http://localhost:8000/ | head -1   # 404
  kill $SERVE_PID
  ```
- [ ] **Frontend Playwright smoke (manual):** With a built wheel installed in a fresh venv and `bookcompanion serve` running, open `http://localhost:8000/` in a browser. Verify: library list renders, navigation works, no console errors about missing assets. Take a screenshot.

**Cleanup:**
- [ ] Remove `/tmp/bc-test`, `/tmp/bc-final`.
- [ ] Kill any stray `bookcompanion serve` processes.
- [ ] `cd backend && rm -rf dist` (built wheels — artifact-only).
- [ ] Restore `backend/app/static/` for continued local dev: `cd frontend && npm run build && rsync -a --delete dist/ ../backend/app/static/` OR let the next `uv build` regenerate it. (`rsync -a` is idempotent whether the target exists or not; the trailing slashes matter.)
- [ ] Update `docs/changelog.md` with a user-facing entry ("`pip install bookcompanion` now ships with the web UI included").
- [ ] `git add docs/changelog.md && git commit -m "docs: changelog for bundled frontend wheel"`.

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| —    | Initial draft | — |
| 1    | T1 tests trigger full `create_app()`; T3 used `mix_stderr=False` (flaky across Typer versions) and leaked `BOOKCOMPANION_API_ONLY` between tests; T4 hook instantiation with positional kwargs breaks on Hatchling API changes; no Hatchling version pin; `pkill -f` in smoke commands could hit unrelated processes; env-var propagation in `serve_cmd` lacked a rationale comment. | Added fallback note to T1. T3: switched to `CliRunner()` + `result.output`, added autouse `_clear_api_only` fixture. T4: replaced direct constructor calls with `_make_hook()` helper that uses `__new__`; added `hatchling>=1.25,<2` pin in `[build-system]`. T5/T6: captured `SERVE_PID=$!` and use `kill $SERVE_PID`. Added comment in `serve_cmd.py` explaining the env-var propagation is for `--reload` future-proofing per D3. |
| 2    | Hatch hook could ship stale `dist/` contents on a retry; no post-build assertion for `dist/index.html`; no test for stale `app/static/` being replaced; `serve_cmd.py` importing from `app.api.main` would eagerly construct the FastAPI app on every CLI invocation (import side-effect); `cp -r` cleanup step not idempotent. | Hook now `rmtree`s `dist/` before `npm run build` and asserts `dist/index.html` exists after. Added T4 tests `test_hook_replaces_stale_static_dir` and `test_hook_raises_when_build_emits_no_index` (T4 count: 4 → 6). Moved `_resolve_static_dir` and `_assets_present` from `app/api/main.py` into the new `app/api/static_files.py` so `serve_cmd.py` imports path helpers without loading `create_app`. Updated T1/T2/T3 imports and tests accordingly. T6 cleanup uses `rsync -a --delete` instead of `cp -r`. |
