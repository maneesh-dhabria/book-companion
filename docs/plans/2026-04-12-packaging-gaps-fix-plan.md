# Packaging Gaps Fix — Implementation Plan

**Date:** 2026-04-12
**Parent work:** `feature/frontend-packaging` (bundled Vue SPA in wheel)
**Gaps surfaced during:** `/verify` post-implementation gate

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 (self-review) | (a) T1 proposed `cfg.set_main_option("sqlalchemy.url", ...)` but `env.py:40` reads `Settings()` directly and ignores Config URL — cargo-cult line. (b) `test_hook_builds_for_sdist` body was an ellipsis, not runnable. (c) Plan didn't note `get_settings()` may be `lru_cache`'d, affecting the env-var test. (d) Plan didn't empirically verify sdist inclusion behavior for gitignored hook-built files. (e) Rollout section left choice open when user had already picked B. | (a) Removed the override line; added D8 explaining why. (b) Fleshed out the test with full fake_run + assertion. (c) Added cache_clear() with a conditional note. (d) Confirmed via `uv build --sdist` with and without `app/static/` on disk; documented finding in Code Study. (e) Rewrote Rollout to commit to option B; added D9. |
| 2 (deeper self-review + user question "how do we verify without PyPI?") | (a) `get_settings` is NOT `lru_cache`'d — it uses a module-level `_settings = None` sentinel (`app/cli/deps.py:88-90`). My test's `get_settings.cache_clear()` would fail. More importantly, `env.py` calls `Settings()` directly (not `get_settings()`), so the cache is irrelevant. (b) `importlib.resources.files("app.migrations")` requires `app/migrations/__init__.py` to exist — forgot to list this file. (c) T3 commands hard-code `bookcompanion-0.1.0-*.whl`; should use globs so version bumps don't break the runbook. (d) The real risk of `pip install <sdist>` is the PEP 517 isolated build env — our hook must only import stdlib + hatchling (both already satisfied). Worth an explicit note. (e) No local-PyPI verification strategy at all — plan relies entirely on `curl` against a running server. Added full T5. | (a) Simplified the test to just set the env var; no cache manipulation needed. Added code-study note. (b) Added `app/migrations/__init__.py` to File Map and Step 1 of T1. (c) Replaced hard-coded versions with globs. (d) Added a Risks row + a note under T3 Step 5. (e) Added a new **T5: Creative packaging verification** task with `twine check`, `pipx`-style isolated install, Docker clean-room, optional local PyPI mirror via `pypiserver`, and a slow pytest regression test. |

## Overview

The frontend-packaging branch shipped successfully but `/verify` surfaced two packaging gaps that block a clean PyPI release:

1. **`uv build` fails on the sdist→wheel step.** The custom Hatchling hook assumes `../frontend/` is reachable from the package root. When `uv build` first builds an sdist and then builds the wheel by extracting that sdist to a tmp dir, the frontend tree is no longer a sibling, so the hook `FileNotFoundError`s. Today we have to use `uv build --wheel`, which skips PyPI's standard "install from sdist" fallback path.
2. **`bookcompanion init` breaks on installed wheels.** `init_cmd.py` shells out to `uv run alembic upgrade head`, relying on `uv` being installed and on `shutil.which("alembic")` to decide `cwd`. An installed wheel has no `alembic.ini` or `alembic/` directory at all — migrations simply can't run. The command happens to muddle through in dev because `uv` is always present there; it's broken everywhere else.

Both issues are on the critical path for `pip install bookcompanion && bookcompanion serve` actually working end-to-end. Fixing them together keeps the "zero-dependency install" narrative whole.

**Done when:**
- `uv build` (default — builds sdist AND wheel) succeeds on a clean checkout with Node installed.
- The resulting sdist contains pre-built `app/static/` and enough migration files that a wheel built from the sdist needs no Node.
- The resulting wheel ships `app/migrations/` (renamed from `alembic/`) and an in-package `alembic.ini` next to it; no external config file lookup.
- `pip install bookcompanion-*.whl` into a fresh venv + `bookcompanion init` (no `uv`, no PATH manipulation) runs migrations cleanly and creates `library.db`.
- Full test suite green.

**Execution order:**

```
T1 (migrations into app/, programmatic alembic)
  └─ T2 (hatch hook: sdist-aware, prebuilt-detection)
        └─ T3 (pyproject wheel/sdist config + verification)
             └─ T5 (creative packaging verification — ladder + regression test)
                  └─ T4 (docs + changelog + final smoke)
```

(Task numbers reflect the order they were added to the plan, not the execution order. T5 slots before T4 so the docs describe a verification story that actually runs.)

---

## Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Move `alembic/` → `app/migrations/` and bundle `alembic.ini` inside `app/` | (a) Ship `alembic.ini` + `alembic/` at wheel root via `force-include`, (b) Move inside `app/`, (c) Use declarative `metadata.create_all()` and drop Alembic | (b) keeps everything importable as `app.migrations`, resolvable via `importlib.resources`, and avoids hatchling `force-include` semantics that change across versions. Dropping Alembic (c) loses migration history; not worth it. |
| D2 | Call Alembic programmatically (`alembic.command.upgrade`) instead of subprocess | (a) `subprocess.run(["alembic", ...])`, (b) `subprocess.run([sys.executable, "-m", "alembic", ...])`, (c) `alembic.command.upgrade(Config(...), "head")` | (c) is portable, has no PATH dependency, no shell injection surface, and gives us a real Python exception on failure instead of a `returncode`. |
| D3 | Hatch hook runs for **both** sdist and wheel targets; logic branches on `target_name` + prebuilt detection | (a) Wheel-only + require `uv build --wheel`, (b) Sdist-only and let wheel trust prebuilt assets, (c) Both, with prebuilt detection | (c) matches the common pattern for Python packages with compiled frontend assets (e.g., Jupyter extensions). Sdist-time build produces a self-contained sdist; wheel-from-sdist path sees no `../frontend` and correctly falls back to prebuilt `app/static/`. |
| D4 | Prebuilt detection key: `app/static/index.html` exists AND `../frontend/package.json` does NOT exist | (a) Env-var override, (b) File-presence heuristic, (c) `target_name`-only | (b) is zero-config and correct for both real scenarios (fresh source tree → build; sdist extract → trust prebuilt). Env-var override adds a knob we don't need yet. |
| D5 | Register hook as `[tool.hatch.build.hooks.custom]` (global) rather than per-target | (a) Per-target duplicated config, (b) Global + `target_name` branching | Global registration is less config drift; behavior is already `target_name`-branched inside the hook. |
| D6 | Keep `subprocess.run(["bookcompanion", "init"])` auto-invocation in `serve_cmd.py` unchanged | — | Out of scope for this plan; serve's auto-init is a separate UX pattern. T1 fixes what `init` does internally, which is what matters. |
| D7 | No database schema changes; this plan is pure packaging plumbing | — | The migration file itself is unchanged — only its location and how it's invoked. Schema version stays at `e152941ea209`. |
| D8 | `_run_migrations()` does NOT override `sqlalchemy.url` via `Config.set_main_option` | (a) Set it anyway "just in case", (b) Rely on `env.py`'s existing Settings() call | `backend/alembic/env.py:40` reads `Settings().database.url` directly in online mode and ignores the Config URL. Setting it via Config would be cargo-cult. Tests monkeypatch `BOOKCOMPANION_DATABASE__URL`, which Settings() picks up — that's the correct knob. |
| D9 | Fold these changes into `feature/frontend-packaging` (rollout option B) | (a) Stack as separate PR, (b) Fold into same branch | No external user has seen the parent branch yet. Reviewer sees one coherent "bundle everything needed for `pip install`" story. Lower coordination cost. |

---

## Code Study Notes

- **`backend/alembic.ini:1-3`** — `script_location = alembic` (relative path). After move, becomes `script_location = %(here)s/migrations` or we construct the `Config` object programmatically and never read the INI at all.
- **`backend/alembic/env.py:10-11, 40`** — imports `app.config.Settings` and `app.db.models.Base`; `run_migrations_online()` calls `Settings()` and uses `settings.database.url` to build the async engine. It **does not** read `sqlalchemy.url` from the Alembic Config in online mode. Works identically under `app/migrations/env.py` after moving — Settings is env-driven, not path-driven.
- **Sdist inclusion behavior (verified empirically with hatchling 1.29.0):** `uv build --sdist` includes files present on disk under `app/` even when they are `.gitignore`d, as long as they exist at sdist-creation time. Empirically confirmed by running `uv build --sdist` with and without `app/static/` pre-populated and comparing the tarball contents. This means the hook running at sdist time + the existing `packages = ["app"]` rule is sufficient — no `artifacts = [...]` config needed. (If a future hatchling tightens this, add `[tool.hatch.build] artifacts = ["app/static/**"]`.)
- **`backend/app/cli/commands/init_cmd.py:45-50`** — the `cwd="backend" if not shutil.which("alembic") else None` branch is the fragility source. Will be replaced wholesale.
- **`backend/app/cli/deps.py:87-92`** — `get_settings()` uses a **module-level `_settings` sentinel**, NOT `functools.lru_cache`. There's no `.cache_clear()` method. Test code that wants a fresh Settings should either (a) not call `get_settings()` at all — env.py already doesn't — or (b) reassign `app.cli.deps._settings = None`. Since env.py uses `Settings()` directly in `run_migrations_online()`, tests only need to set the env var.
- **`importlib.resources.files("app.migrations")`** requires `app/migrations/` to be a proper Python package (`__init__.py` present). Empirically verified: `files("app.db")` works because `app/db/__init__.py` exists. Need to `touch app/migrations/__init__.py` as part of the move.
- **`backend/hatch_build.py:14-18`** — `self.target_name != "wheel": return`. Extend to handle `sdist` + add prebuilt detection.
- **`backend/pyproject.toml:77-84`** — `[tool.hatch.build.targets.wheel] packages = ["app"]`. Moving migrations into `app/migrations/` means they're auto-included; no extra config needed. `alembic.ini` becomes `app/migrations/alembic.ini` and is a package data file.
- **Existing migration file `alembic/versions/e152941ea209_initial_sqlite_schema.py`** — self-contained, imports `sqlalchemy` and `alembic.op`. Move is a `git mv` with no code changes.

---

## Prerequisites

- Branch `feature/frontend-packaging` merged OR base this on top of it (decision for the user; see "Rollout" below).
- Node.js ≥18, npm on PATH (same as parent plan).
- No existing user data to migrate — this is pre-release, no one has run migrations from the installed wheel yet.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Move | `backend/alembic/` → `backend/app/migrations/` | Ship migrations inside the package |
| Create | `backend/app/migrations/__init__.py` (empty) | Make `app.migrations` a proper Python package so `importlib.resources.files()` resolves it |
| Move | `backend/alembic.ini` → `backend/app/migrations/alembic.ini` | Ship config inside the package |
| Modify | `backend/app/migrations/alembic.ini` | `script_location = %(here)s` so it resolves to its own dir wherever installed |
| Modify | `backend/app/cli/commands/init_cmd.py` | Replace `subprocess.run(["uv", "run", "alembic", ...])` with programmatic `alembic.command.upgrade(Config(...), "head")` using `importlib.resources` to locate the config |
| Modify | `backend/hatch_build.py` | Run on both sdist and wheel; skip when `../frontend/package.json` is missing AND `app/static/index.html` is present (prebuilt path) |
| Modify | `backend/pyproject.toml` | Switch to `[tool.hatch.build.hooks.custom]` (global); add `app/migrations/alembic.ini` to wheel include if needed |
| Create | `backend/tests/unit/test_init_migrations.py` | Test that programmatic migration path works end-to-end against a tmp SQLite URL |
| Modify | `backend/tests/build/test_hatch_build_hook.py` | Add 2 tests: sdist branch builds, wheel-from-sdist branch detects prebuilt and skips |
| Modify | `docs/changelog.md` | Note: `uv build` works end-to-end; `bookcompanion init` no longer needs `uv` |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Moving `alembic/` breaks existing user checkouts mid-development | Low | Pre-release — no external users yet. Internal devs: git pull, re-run `bookcompanion init`. |
| `importlib.resources.files("app.migrations")` path API differs across Python versions | Low | Using 3.12+ only per `requires-python`; `.files()` API is stable there. |
| Alembic `Config` object programmatic construction misses an env var the INI used to inject | Medium | T1 test runs `alembic upgrade head` end-to-end against a tmp SQLite DB and asserts tables exist — catches any missing config. |
| Sdist-built wheels include an `app/static/` that's weeks old when building from an old sdist | Medium | Acceptable: sdists are per-release artifacts, rebuilt on every version bump. Document in release runbook. |
| Global hook (D5) runs for unexpected third-party targets (e.g., wheel-via-uv-build-backend detection) | Low | Hook's first check is `target_name in ("wheel", "sdist")`; anything else is a no-op. |
| PEP 517 build isolation breaks because the hook imports something outside `[build-system].requires` | Low | Current hook imports only stdlib (`shutil`, `subprocess`, `pathlib`) + `hatchling.builders.hooks.plugin.interface`. No `app.*` imports. Catch future regressions via T5 Layer 3 (fresh-venv install from sdist runs the hook under isolation). |
| fastembed / ONNX Runtime pulls glibc-linked native deps that break on `python:3.12-slim` without `libstdc++6` | Low | T5 Layer 5 Docker test catches this before release. If it fails, either document a minimum OS baseline or switch the Docker base image to `python:3.12`. |

---

## Rollback

- **If T1 breaks migrations:** revert the move commit, restore `backend/alembic/` and `backend/alembic.ini`, revert `init_cmd.py`. No data impact (pre-release).
- **If T2/T3 breaks `uv build --wheel`:** revert the hook + pyproject commits; the wheel-only path keeps working as it does today on `feature/frontend-packaging`.

---

## Tasks

### T1: Relocate migrations into the package + programmatic invocation

**Goal:** Ship `alembic/` and `alembic.ini` inside the installed wheel; replace the fragile subprocess-based migration call with `alembic.command.upgrade()`.
**Spec refs:** Gap #2 from `/verify`.

**Files:**
- Move: `backend/alembic/` → `backend/app/migrations/`
- Move: `backend/alembic.ini` → `backend/app/migrations/alembic.ini`
- Modify: `backend/app/migrations/alembic.ini` (`script_location = %(here)s`)
- Modify: `backend/app/cli/commands/init_cmd.py`
- Create: `backend/tests/unit/test_init_migrations.py`

**Steps:**

- [ ] Step 1: `git mv backend/alembic backend/app/migrations` and `git mv backend/alembic.ini backend/app/migrations/alembic.ini`. Then `touch backend/app/migrations/__init__.py` so `importlib.resources.files("app.migrations")` resolves. (Alembic loads `env.py` via `exec()`, not via Python's import system, so the `__init__.py` does not interfere with alembic's own machinery.)
- [ ] Step 2: Update `script_location = %(here)s` in the moved `alembic.ini` so the config works from any install location.
- [ ] Step 3: Verify `backend/app/migrations/env.py` still imports cleanly (should be unchanged — only location moved).
- [ ] Step 4: Write failing test `backend/tests/unit/test_init_migrations.py`:
  ```python
  from sqlalchemy import create_engine, inspect

  from app.cli.commands.init_cmd import _run_migrations


  def test_run_migrations_creates_tables(tmp_path, monkeypatch):
      db_path = tmp_path / "library.db"
      # env.py reads Settings() which reads BOOKCOMPANION_DATABASE__URL — that's the
      # knob we turn, NOT Config.set_main_option, which env.py ignores in online mode.
      monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")

      _run_migrations()

      sync_engine = create_engine(f"sqlite:///{db_path}")
      tables = inspect(sync_engine).get_table_names()
      assert "books" in tables
      assert "book_sections" in tables
      assert "alembic_version" in tables
  ```
  Run: `uv run pytest tests/unit/test_init_migrations.py -v` — expect FAIL (`_run_migrations` doesn't exist).
  **Note:** `get_settings()` in `app/cli/deps.py:87` uses a module-level `_settings` sentinel, not `lru_cache`. But `env.py` calls `Settings()` directly, not `get_settings()`, so the cache is irrelevant here — the `monkeypatch.setenv` is sufficient.

- [ ] Step 5: Refactor `init_cmd.py`:
  ```python
  # Replace the subprocess block with:
  def _run_migrations() -> None:
      from importlib.resources import files
      from alembic.command import upgrade
      from alembic.config import Config

      ini_path = files("app.migrations") / "alembic.ini"
      cfg = Config(str(ini_path))
      # env.py's run_migrations_online() reads Settings().database.url directly;
      # no sqlalchemy.url override needed here (D8). Settings is env-driven.
      upgrade(cfg, "head")
  ```
  And in `init()`:
  ```python
  console.print("\nInitializing database...")
  try:
      _run_migrations()
      console.print("  [green]✓[/green] Database initialized")
  except Exception as e:
      console.print(f"  [yellow]⚠[/yellow] Migration warning: {e}")
  ```
  Remove the `shutil` import if unused elsewhere in the file.

- [ ] Step 6: Re-run the test, expect pass. Then run full suite: `uv run pytest -q` — no regressions.

- [ ] Step 7: Manual smoke (dev venv):
  ```bash
  rm -f ~/Library/Application\ Support/bookcompanion/library.db
  uv run bookcompanion init
  ls ~/Library/Application\ Support/bookcompanion/library.db  # exists
  ```

- [ ] Step 8: Commit.
  ```bash
  git add -A && git commit -m "refactor(packaging): bundle migrations in app/, run alembic programmatically"
  ```

**Inline verification:**
- New test green.
- Full suite still passes (~462 + 1 new).
- Fresh install smoke: `library.db` created, has `books`/`alembic_version` tables.

---

### T2: Hatch hook handles sdist + detects prebuilt assets

**Goal:** Make the hook run for both wheel and sdist; skip the npm step when assets are already built and the frontend source tree is absent (wheel-from-sdist case).
**Spec refs:** Gap #1 from `/verify`.

**Files:**
- Modify: `backend/hatch_build.py`
- Modify: `backend/tests/build/test_hatch_build_hook.py`

**Steps:**

- [ ] Step 1: Write failing tests.
  Add to `test_hatch_build_hook.py`:
  ```python
  def test_hook_builds_for_sdist(fake_repo, monkeypatch):
      """Sdist target should also trigger the frontend build so the sdist is self-contained."""
      frontend = fake_repo / "frontend"
      dist = frontend / "dist"

      def fake_run(argv, cwd=None, check=True, **kw):
          if argv[:2] == ["npm", "run"]:
              dist.mkdir(exist_ok=True)
              (dist / "index.html").write_text("<html>sdist-built</html>")
          return subprocess.CompletedProcess(argv, 0)

      monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)
      monkeypatch.setattr(subprocess, "run", fake_run)

      hook = _make_hook(fake_repo / "backend", "sdist")
      hook.initialize("standard", {})

      static_dir = fake_repo / "backend" / "app" / "static"
      assert (static_dir / "index.html").read_text() == "<html>sdist-built</html>"


  def test_hook_skips_when_prebuilt_and_no_frontend(tmp_path, monkeypatch):
      """Wheel-from-sdist: no ../frontend present, but app/static/index.html exists → skip."""
      backend = tmp_path / "backend"
      (backend / "app" / "static").mkdir(parents=True)
      (backend / "app" / "static" / "index.html").write_text("<html>prebuilt</html>")
      # Deliberately do NOT create tmp_path/frontend

      called = []
      monkeypatch.setattr(subprocess, "run", lambda *a, **kw: called.append(a))
      monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)

      hook = _make_hook(backend, "wheel")
      hook.initialize("standard", {})

      assert called == []  # npm must not have been invoked
      assert (backend / "app" / "static" / "index.html").read_text() == "<html>prebuilt</html>"


  def test_hook_raises_when_no_frontend_and_no_prebuilt(tmp_path):
      """No ../frontend and no app/static → unbuildable, must raise."""
      backend = tmp_path / "backend"
      (backend / "app").mkdir(parents=True)
      hook = _make_hook(backend, "wheel")
      with pytest.raises(RuntimeError, match="cannot build frontend"):
          hook.initialize("standard", {})
  ```

- [ ] Step 2: Update `hatch_build.py`:
  ```python
  def initialize(self, version: str, build_data: dict) -> None:
      if self.target_name not in ("wheel", "sdist"):
          return

      backend_root = Path(self.root)
      frontend_dir = backend_root.parent / "frontend"
      dist_dir = frontend_dir / "dist"
      static_dir = backend_root / "app" / "static"
      lockfile = frontend_dir / "package-lock.json"
      frontend_available = (frontend_dir / "package.json").is_file()
      prebuilt = (static_dir / "index.html").is_file()

      # Wheel-from-sdist path: no source, but prebuilt assets are already in-tree.
      if not frontend_available:
          if prebuilt:
              return
          raise RuntimeError(
              f"cannot build frontend: {frontend_dir} is missing and no prebuilt "
              f"assets at {static_dir}. If building from sdist, the sdist is malformed."
          )

      # Fresh source path: build.
      if shutil.which("npm") is None:
          raise RuntimeError(
              "npm is required to build the frontend for the wheel/sdist. "
              "Install Node.js >=18."
          )

      install_cmd = ["npm", "ci"] if lockfile.exists() else ["npm", "install"]
      subprocess.run(install_cmd, cwd=str(frontend_dir), check=True)

      if dist_dir.exists():
          shutil.rmtree(dist_dir)
      subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)

      if not (dist_dir / "index.html").is_file():
          raise RuntimeError(
              f"npm run build completed but {dist_dir / 'index.html'} is missing."
          )

      if static_dir.exists():
          shutil.rmtree(static_dir)
      shutil.copytree(dist_dir, static_dir)
  ```

- [ ] Step 3: Update the existing `test_hook_no_op_for_sdist` — it no longer applies (sdist now builds). Replace with `test_hook_builds_for_sdist` (already added above); delete the old no-op test or rename it to `test_hook_no_op_for_unknown_target` with a target name like `"editable"`.

- [ ] Step 4: Run the build tests. Expect 7 passed (was 6).

- [ ] Step 5: Commit.
  ```bash
  git add -A && git commit -m "fix(packaging): hatch hook runs for sdist and detects prebuilt assets"
  ```

**Inline verification:**
- `uv run pytest tests/build/ -v` — all green.
- `uv run ruff check hatch_build.py tests/build/` — no errors.

---

### T3: `pyproject.toml` + end-to-end `uv build` verification

**Goal:** Register the hook globally (not per-target), verify `uv build` (sdist + wheel) succeeds end-to-end, and verify both artifacts are functional.
**Spec refs:** Gap #1.

**Files:**
- Modify: `backend/pyproject.toml`

**Steps:**

- [ ] Step 1: Change `[tool.hatch.build.targets.wheel.hooks.custom]` → `[tool.hatch.build.hooks.custom]`.
  ```toml
  [tool.hatch.build.hooks.custom]
  path = "hatch_build.py"
  ```

- [ ] Step 2: Clean and build both artifacts.
  ```bash
  rm -rf dist/ backend/app/static/
  cd backend && uv build
  ls dist/
  # Expect: bookcompanion-*-py3-none-any.whl AND bookcompanion-*.tar.gz
  ```

- [ ] Step 3: Verify sdist contents.
  ```bash
  tar -tzf dist/bookcompanion-*.tar.gz | grep -E "app/static/index.html|app/migrations/alembic.ini|app/migrations/env.py" | sort -u
  # Expect: all three lines
  ```

- [ ] Step 4: Verify wheel contents.
  ```bash
  unzip -l dist/bookcompanion-*.whl | grep -E "app/static/index.html|app/migrations/alembic.ini|app/migrations/versions/"
  # Expect: index.html, alembic.ini, at least one migration file
  ```

- [ ] Step 5: Install the sdist in a fresh venv (this is the critical path — proves wheel-from-sdist works on a machine with no Node).
  ```bash
  python3 -m venv /tmp/bc-sdist && /tmp/bc-sdist/bin/pip install dist/bookcompanion-*.tar.gz
  PATH=/tmp/bc-sdist/bin:$PATH /tmp/bc-sdist/bin/bookcompanion init
  (cd /tmp && /tmp/bc-sdist/bin/bookcompanion serve --port 8765 &) && sleep 4
  curl -sI http://localhost:8765/ | head -1          # 200 OK
  curl -s http://localhost:8765/api/v1/health        # JSON
  pkill -f "bookcompanion serve --port 8765"
  rm -rf /tmp/bc-sdist
  ```
  **PEP 517 build isolation note:** When `pip install <tarball>` runs, pip creates an isolated venv with only `[build-system].requires` installed (hatchling). Our hook must import only stdlib + `hatchling.builders.hooks.plugin.interface` — no `app.*` imports. Already satisfied by the current hook.

  **Path taken:** The hook fires with `target_name=wheel` but `../frontend/package.json` is missing (sdist has no frontend/ tree) and `app/static/index.html` is present (bundled during sdist creation) → prebuilt branch, no npm invocation.

- [ ] Step 6: Commit.
  ```bash
  git add -A && git commit -m "fix(packaging): register build hook globally so uv build sdist+wheel works"
  ```

**Inline verification:**
- `uv build` exits 0 and produces both artifacts.
- sdist + wheel both contain migrations and static assets.
- Sdist install in venv with no Node can still `serve` the UI and run migrations.

---

### T5: Creative packaging verification (local, no PyPI)

**Goal:** Answer the question "how do we know this actually works the way PyPI would?" without uploading anything. Build a layered set of checks that each catch a different class of bug.

This is the highest-leverage task in the plan. If it passes, we have real confidence the release works; if it fails, we catch issues before the upload button.

**Files:**
- Create: `backend/scripts/verify_packaging.sh` — one-shot script running the ladder below
- Create: `backend/tests/build/test_end_to_end_packaging.py` — slow pytest (marked `@pytest.mark.slow`) that runs `uv build` + pip install in a tmp venv

**The five-layer verification ladder** (run them in order; each catches a different bug class):

#### Layer 1 — Metadata sanity: `twine check`

```bash
uv run --with twine twine check dist/*
```
Catches: missing README, malformed Markdown description, bad classifier, missing license metadata. PyPI rejects these at upload; catching locally avoids wasted uploads.

#### Layer 2 — Wheel layout lint: `check-wheel-contents`

```bash
uv run --with check-wheel-contents check-wheel-contents dist/*.whl
```
Catches: duplicate files, empty `app/static/`, top-level `tests/` accidentally shipped, `.pyc` files in wheel, missing `.dist-info` metadata.

#### Layer 3 — Fresh-venv install from wheel AND sdist

```bash
# Wheel path — should be the common case for end users
python3 -m venv /tmp/bc-wheel
/tmp/bc-wheel/bin/pip install --no-cache-dir dist/*.whl
PATH=/tmp/bc-wheel/bin /tmp/bc-wheel/bin/bookcompanion --help
PATH=/tmp/bc-wheel/bin /tmp/bc-wheel/bin/bookcompanion init
(cd /tmp && /tmp/bc-wheel/bin/bookcompanion serve --port 8871 &) && sleep 4
curl -sf http://localhost:8871/api/v1/health
curl -sf http://localhost:8871/ | grep -q '<title>'
pkill -f "bookcompanion serve --port 8871"

# Sdist path — proves offline install (no Node) works
python3 -m venv /tmp/bc-sdist
/tmp/bc-sdist/bin/pip install --no-cache-dir dist/*.tar.gz
# ... same smoke as above on port 8872 ...
```
Catches: missing package data, broken entry points, import-time crashes, missing runtime dependencies, wheel-from-sdist path failures.

#### Layer 4 — Isolated CLI install (`pipx` / `uv tool`)

```bash
# pipx simulates how most end users install a CLI tool
uv tool install --from dist/*.whl bookcompanion
bookcompanion --help
bookcompanion init
bookcompanion serve --port 8873 &; sleep 4
curl -sf http://localhost:8873/api/v1/health
pkill -f "bookcompanion serve --port 8873"
uv tool uninstall bookcompanion
```
Catches: entry-point issues only visible in a tool-isolated venv, environment-variable assumptions that leak from the dev shell, `~/.config` / `~/.local/share` side effects.

#### Layer 5 — Clean-room Docker install (optional but highest-signal)

```bash
# Catches: any assumption about the host's Python, system libs, PATH, user dir layout
docker run --rm -v "$PWD/dist:/dist:ro" python:3.12-slim bash -c '
    pip install --no-cache-dir /dist/*.whl &&
    bookcompanion --help &&
    bookcompanion init &&
    (bookcompanion serve --port 8874 &) && sleep 4 &&
    curl -sf http://localhost:8874/api/v1/health
'

# And the sdist variant — this is the real test:
docker run --rm -v "$PWD/dist:/dist:ro" python:3.12-slim bash -c '
    pip install --no-cache-dir /dist/*.tar.gz &&
    bookcompanion init &&
    bookcompanion --help
'
```
Catches: accidental reliance on system-Python paths, macOS-specific `platformdirs` values baked into the wheel, missing `libstdc++` or other glibc-linked deps from wheels we depend on (fastembed pulls ONNX Runtime which is glibc-linked), subtle locale/encoding assumptions.

#### (Optional) Layer 6 — Local PyPI mirror

If you want to simulate the full `pip install bookcompanion` UX without TestPyPI:

```bash
# In one terminal:
uv run --with pypiserver pypi-server run -p 9090 -a . -P . dist/

# In another:
python3 -m venv /tmp/bc-mirror
/tmp/bc-mirror/bin/pip install --index-url http://localhost:9090/simple/ --trusted-host localhost bookcompanion
```
Catches: version resolution bugs, prefix/suffix issues in the wheel filename that pypiserver would reject. Not worth automating, but great for a manual pre-release dry-run.

**Steps:**

- [ ] Step 1: Create `backend/scripts/verify_packaging.sh` that runs Layers 1–4 (Docker optional, gate behind a flag). The script should exit non-zero on any failure and clean up processes/venvs it created, including on Ctrl-C (trap EXIT).

- [ ] Step 2: Create `backend/tests/build/test_end_to_end_packaging.py`. One test, marked `@pytest.mark.slow`. It runs `uv build`, creates a tmp venv, pips the sdist into it, execs `bookcompanion --help`, asserts exit 0 and a known substring. This is THE regression test — if this breaks, packaging is broken. Keep it out of the default `pytest` run (add `@pytest.mark.slow` + a `pytest.ini` marker definition + `-m "not slow"` default if not already there).
  ```python
  import subprocess
  import sys
  import venv
  from pathlib import Path

  import pytest


  @pytest.mark.slow
  def test_built_sdist_installs_and_runs(tmp_path):
      repo = Path(__file__).resolve().parents[2]
      dist = tmp_path / "dist"
      subprocess.run(
          ["uv", "build", "--out-dir", str(dist)], cwd=str(repo), check=True
      )
      sdists = list(dist.glob("*.tar.gz"))
      assert len(sdists) == 1, f"expected one sdist, got {sdists}"

      env_dir = tmp_path / "venv"
      venv.create(str(env_dir), with_pip=True)
      pip = env_dir / "bin" / "pip"
      bc = env_dir / "bin" / "bookcompanion"

      subprocess.run([str(pip), "install", "--no-cache-dir", str(sdists[0])], check=True)
      result = subprocess.run([str(bc), "--help"], capture_output=True, text=True)
      assert result.returncode == 0
      assert "bookcompanion" in result.stdout.lower()
  ```

- [ ] Step 3: Run the ladder end-to-end:
  ```bash
  rm -rf dist/ app/static/
  uv build
  bash scripts/verify_packaging.sh
  uv run pytest tests/build/test_end_to_end_packaging.py -v -m slow
  ```
  Expect all layers green.

- [ ] Step 4: Commit.
  ```bash
  git add scripts/verify_packaging.sh tests/build/test_end_to_end_packaging.py
  git commit -m "test(packaging): layered local verification (twine, wheel-contents, venv, docker)"
  ```

**Inline verification:**
- `scripts/verify_packaging.sh` exits 0 on a good build and non-zero on a synthesized failure (e.g., after `rm app/static/index.html`).
- Slow pytest passes with `-m slow` and is skipped without it.

---

### T4: Docs + final verification

**Goal:** Update the release runbook / changelog, run the full verification gate, wrap up.

**Files:**
- Modify: `docs/changelog.md`
- Optionally: `CLAUDE.md` (distribution section) if commands drift

**Steps:**

- [ ] Step 1: Add a changelog entry:
  ```markdown
  ## 2026-04-12 — Packaging Hardening

  - `uv build` now produces both sdist and wheel in one invocation; users installing from sdist (e.g., on platforms without a prebuilt wheel) no longer need Node.js — the SPA is prebuilt at sdist creation time.
  - `bookcompanion init` now runs migrations programmatically; no dependency on `uv` or a specific `$PATH` layout. Migrations, Alembic config, and the CLI all ship inside the installed package.
  ```

- [ ] Step 2: Full verification:
  ```bash
  cd backend
  uv run ruff check .
  uv run pytest -q
  rm -rf dist/ app/static/
  uv build
  ls dist/
  tar -tzf dist/bookcompanion-*.tar.gz | grep app/static/index.html
  unzip -l dist/bookcompanion-*.whl | grep app/migrations/alembic.ini
  ```

- [ ] Step 3: Fresh-venv sdist-install smoke (same as T3 Step 5) — record outputs.

- [ ] Step 4: Cleanup:
  ```bash
  rm -rf dist/
  # keep app/static/ built so local dev can run serve
  ```

- [ ] Step 5: Commit docs.
  ```bash
  git add docs/changelog.md && git commit -m "docs: changelog for packaging hardening"
  ```

---

## Rollout

**Chosen: fold into `feature/frontend-packaging`.** All T1–T4 commits land on that same branch. The PR retitles to something like "packaging: bundle SPA, migrations, and build hooks for one-shot pip install." Rationale captured in D9.

Practically this means:
- Work continues in `.worktrees/frontend-packaging` (the existing worktree).
- New commits go on top of the current `feature/frontend-packaging` HEAD.
- No rebase/cherry-pick dance.
- When the combined branch merges, it supersedes the draft parent work in one go.

### Editable installs

`[tool.hatch.build.hooks.custom]` (global) also fires for `pip install -e .`. That's once at install time, not per-reload, so it's an acceptable cost. Developers who already have `npm run dev` running don't need to think about it. If this ever becomes annoying, an `editable` target check (`if self.target_name == "editable": return`) is a one-line addition.

---

## Open Questions

None blocking.

Nice-to-haves for a future plan:
- GitHub Actions workflow that runs `scripts/verify_packaging.sh` on each push, catching packaging regressions at PR time.
- A `make release` target that wires `uv build` + `verify_packaging.sh` + `twine upload`, so the release itself is a one-command dry-run-then-ship.
- `[project.urls]` metadata (Homepage, Issues, Source) — not required to install but improves the PyPI page when we get there.
