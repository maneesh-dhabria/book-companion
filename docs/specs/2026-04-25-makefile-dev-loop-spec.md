# Makefile Dev-Loop Front Door — Spec

**Date:** 2026-04-25
**Status:** Draft
**Tier:** 1 (Minor Enhancement)
**Requirements:** synthesized in §1 (no separate requirements doc — scope is session-captured)

---

## 1. Problem Statement

During the v1.5 Reader UX + Features session (2026-04-24), the same setup commands had to be repeated from memory on every interactive verification round: kill the dev server, apply migrations, rebuild the frontend, copy `dist` into `backend/app/static`, restart `bookcompanion serve`. Commit `93c2f19` added those commands as `./test.sh dev|stop|migrate|build-fe|reset`, which works but misses three things a `Makefile` would provide for free:

1. **Tab completion** (`make <TAB>`) across bash/zsh.
2. **Native mtime-based "rebuild only when source changed"** via file targets (`backend/app/static/index.html: frontend/src/**/*`). The shell version emulates this via `find -newer`, which is correct but opaque.
3. **`make help` discoverability** — self-documenting via a standard `##` comment convention.

The goal is a **thin front-door `Makefile`** that gives the dev loop those three affordances without losing the shell-shaped verification ladder (`fast`/`ladder`/`slow`/`serve`), which stays in `test.sh`.

**Primary success metric:** zero instances of "what was that command again?" on the dev loop during the next feature session.

---

## 2. Background & Rationale

Prior session recommendation (2026-04-24 conversation): "A Makefile is the standard alternative; it buys tab completion, help output, and mtime dependency rules. At this size the shell script is lower-friction — but if you find yourself asking about commands repeatedly, that's the signal." The user reported exactly that pattern, so we graduate to a Makefile.

**Why not full-replace `test.sh`:** the verification ladder is a multi-step shell pipeline (`fast` = lint + pytest, `ladder` = bash script, `slow` = pytest with specific pytest overrides, `serve` = wheel build + venv install + init + serve). Porting those into Makefile syntax adds `\` continuation lines and per-step `set -e` ceremony with no payoff. The Makefile calls `./test.sh <cmd>` for those.

**What moves to Makefile-native:** the dev-loop commands (`dev`, `stop`, `migrate`, `build-fe`, `reset`) — specifically `build-fe` benefits meaningfully from being a **file target** with mtime-based prerequisites, which `make` handles idiomatically.

---

## 3. Fix Approach

### 3.1 Single new file

`Makefile` at repo root. GNU make syntax (default on macOS ≥14 / all Linux). No external deps.

### 3.2 Target split

| Target | Type | Implementation |
|--------|------|----------------|
| `help` | `.PHONY` | Default target. Parses `##` comments on target lines and prints an aligned menu. |
| `dev` | `.PHONY` | Orchestrates `stop` → `migrate` (unless `BC_SKIP_MIGRATE=1`) → `backend/app/static/index.html` (file target — mtime-skipped) → `bookcompanion serve`. |
| `stop` | `.PHONY` | Kills any PID on `$(PORT)` (default 8000) + stray `ms-playwright/mcp-chrome` processes. |
| `migrate` | `.PHONY` | `uv run alembic -c app/migrations/alembic.ini upgrade head` in `backend/`. |
| `build-fe` | `.PHONY` | Skip-aware alias: declared as `build-fe: backend/app/static/index.html`. `make` only runs the recipe when the file target's prerequisites are newer. No env-var magic. |
| `force-build-fe` | `.PHONY` | Unconditional rebuild: `rm -f backend/app/static/index.html` then depends on the file target. |
| `backend/app/static/index.html` | File target | Prerequisites: `$(shell find frontend/src -type f)`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/package.json`, **order-only** `\| frontend/node_modules/.package-lock.json`. Recipe: `npm run build` + `cp -R frontend/dist/. backend/app/static/`. `make` skips when the target is newer than every non-order-only prerequisite. |
| `frontend/node_modules/.package-lock.json` | File target | Prerequisites: `frontend/package-lock.json`. Recipe: `cd frontend && npm ci`. Triggers only when `node_modules` is missing or `package-lock.json` changed. |
| `reset` | `.PHONY` | Destructive. Timestamp-backs the data dir, runs `bookcompanion init`. Prompts before proceeding (TTY check). |
| `clean-fe` | `.PHONY` | `rm -rf backend/app/static` — forces the next `make build-fe` to rebuild from scratch. |
| `test`, `lint`, `verify-ladder`, `verify-slow`, `verify-all`, `serve-fresh` | `.PHONY` | Delegate to: `test` → `./test.sh fast`; `lint` → `cd backend && uv run ruff check .`; `verify-ladder` → `./test.sh ladder`; `verify-slow` → `./test.sh slow`; `verify-all` → `./test.sh all`; `serve-fresh` → `./test.sh serve`. |

### 3.3 Environment variables

Passed through verbatim to `test.sh` and recipes:

| Var | Default | Purpose |
|-----|---------|---------|
| `PORT` | `8000` | Port used by `dev`, `stop`, `serve-fresh`. Exported as `BC_PORT` when invoking `test.sh`. |
| `BC_SKIP_MIGRATE` | unset | When `1`, `dev` skips the `migrate` prerequisite. |
| `VERIFY_DOCKER` | unset | Pass-through to `test.sh ladder`/`all`. |
| `CONFIRM` | unset | When `1`, `reset` proceeds without the interactive confirm prompt (for non-TTY contexts — see E5). |

### 3.4 `help` convention

Each `.PHONY` target is tagged with a `##` trailing comment. `help` extracts them via a single `awk` one-liner:

```
dev: stop migrate $(STATIC_INDEX)  ## Refresh: stop, migrate, build FE if needed, serve
```

```
help:
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[1;36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
```

---

## 4. File Layout

```
./
├── Makefile              ← NEW (this spec)
└── test.sh               ← keep as-is; Makefile delegates to it
```

The existing `./test.sh` keeps its current contract. No changes required there. The `CLAUDE.md` "Interactive verification" section gets one new sentence pointing at `make help` as the top-level entry point.

---

## 5. Edge Cases

| # | Scenario | Condition | Expected Behavior |
|---|----------|-----------|-------------------|
| E1 | Port already free on `stop` | `lsof -ti:$(PORT)` empty | Print "nothing listening on :$(PORT)" and exit 0. No error. |
| E2 | Concurrent `make dev` runs | Two invocations racing | `stop` handles the port contention (second `make dev` kills the first's server on startup). No explicit lock needed. |
| E3 | `build-fe` while src under active edit | File saved mid-build | Acceptable — Vite reads source synchronously at build start. Worst case: one extra rebuild on the next `make dev`. |
| E4 | `reset` on missing data dir | Fresh checkout, no `~/.../bookcompanion/` | Skip the backup step, go straight to `bookcompanion init`. |
| E5 | `reset` without TTY | CI / piped input | Refuse to proceed unless `CONFIRM=1` is set. Prevents accidental destruction in non-interactive contexts. |
| E6 | Linux data dir vs. macOS data dir | Host platform | Detect via `uname -s` and `$XDG_DATA_HOME`/`~/.local/share/bookcompanion/` (Linux) or `~/Library/Application Support/bookcompanion/` (macOS). |
| E7 | `frontend/node_modules` missing | Fresh clone, `npm install` not run | `backend/app/static/index.html` has an **order-only** prerequisite on `frontend/node_modules/.package-lock.json`, which has its own recipe (`npm ci`). `make` installs deps only when `node_modules` is missing or `package-lock.json` changed, and order-only semantics prevent reinstall from triggering a frontend rebuild. |
| E8 | Windows developer | Unsupported for now | `help` prints "Windows: run commands directly; see `test.sh`". Bail out of other targets with a clear message. |
| E9 | Stale `backend/app/static` from a deleted file in `frontend/src` | Source file removed but static still has old chunk | Acceptable — Vite's build always clears `frontend/dist/` first, and we `cp -R dist/.` which overlays. Stale asset filenames (hashed) are harmless. A `make clean-fe` target removes `backend/app/static/` explicitly for full resets. |

---

## 6. Testing Strategy

### 6.1 Smoke verification (manual, one-time after landing)

| # | Command | Expected |
|---|---------|----------|
| 1 | `make help` | Prints the target list aligned, one per `##` line. Exit 0. |
| 2 | `make build-fe` | Runs `npm run build`, `cp -R`. `backend/app/static/index.html` exists. |
| 3 | `make build-fe` immediately again | Skips the build ("is up to date"). Exit 0. |
| 4 | `touch frontend/src/main.ts && make build-fe` | Rebuilds (the file target is older than a prerequisite). |
| 5 | `make force-build-fe` | Rebuilds unconditionally (deletes the file target first). |
| 6 | `make stop` (with nothing listening) | Prints "nothing listening on :8000", exit 0. |
| 7 | `PORT=8765 make dev`, open http://localhost:8765 | App renders. `lsof -ti:8765` returns a PID. |
| 8 | `make stop PORT=8765` | Server dies, port frees. |
| 9 | `make test` | Delegates to `./test.sh fast`, same output as running it directly. |
| 10 | `make reset CONFIRM=1` (with a fresh backup in hand) | Backs up existing data dir, re-initializes. |

### 6.2 Automated check

Add one lightweight shell test under `backend/tests/build/test_makefile_contract.py` (new, marked `@pytest.mark.slow`):

```python
def test_makefile_help_lists_canonical_targets():
    out = subprocess.run(["make", "help"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10)
    assert out.returncode == 0
    for target in ("dev", "stop", "migrate", "build-fe", "reset", "test", "verify-ladder"):
        assert target in out.stdout, f"make help missing target: {target}"
```

### 6.3 Verification commands (run after implementation)

```bash
make help                           # discoverability
make build-fe && make build-fe      # mtime-skip verification
PORT=8765 make dev                  # full loop on free port
make stop PORT=8765                 # teardown
pytest backend/tests/build/test_makefile_contract.py
./test.sh all                       # regression: test.sh still works standalone
```

---

## 7. Rollout

1. Land the `Makefile` + the one-line `CLAUDE.md` update in a single commit.
2. Announce to self in a session log: `make help` is the new front door; `test.sh` is still there for the deep/verification flows.
3. No code depends on the Makefile, so there's no rollback concern — `git revert` removes it cleanly.

---

## 8. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Should `make verify` be an alias for `verify-all` or for `verify-ladder` (the cheaper of the two)? Lean toward `verify-ladder` because `all` is rarely the one you want at your desk. | author | during implementation |
| 2 | Do we want a `make ci` target that mirrors what the future CI pipeline will run? Deferrable until CI exists. | — | deferred |

---

## 9. Non-Goals

- **Replacing `test.sh` entirely.** The verification ladder stays script-shaped (§2).
- **Cross-shell completion beyond bash/zsh.** Fish users get `make help`; no bespoke completion file.
- **Windows support.** The repo targets macOS + Linux; Windows users are out-of-scope and handled with a clear early-exit message (E8).
- **Replacing `bookcompanion serve` with a Makefile-managed process (launchd/systemd).** The Makefile keeps `serve` in the foreground — intentionally; daemon management belongs to `launchd` or `systemd`, not `make`.

---

## 10. Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 (self) | `build-fe` was both "skip-aware alias" AND "force rebuilder" — contradictory with smoke tests 3 and 5. Also `test` and `lint` both delegated to `./test.sh fast`, which isn't lint-only. And node_modules auto-install was mentioned in E7 without being wired into the target graph. | Split into `build-fe` (skip-aware, depends on file target) and `force-build-fe` (unconditional rebuild). `lint` now delegates to `cd backend && uv run ruff check .` directly. Added `frontend/node_modules/.package-lock.json` as a file target with an order-only prerequisite edge into the static build. Dropped `BC_FORCE_FE` from the env var table (superseded by the `force-build-fe` target), added `CONFIRM` for non-TTY `reset`. Added `clean-fe` target for full static wipes (§3.2) so users have an explicit reset path. |
