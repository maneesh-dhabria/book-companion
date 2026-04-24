# Makefile Dev-Loop Front Door — Implementation Plan

**Date:** 2026-04-25
**Spec:** `docs/specs/2026-04-25-makefile-dev-loop-spec.md`
**Requirements:** synthesized inside spec §1 (no separate requirements doc)

---

## Overview

Land a thin `Makefile` at the repo root that becomes the new front door for the dev loop. `make help` (default target) prints an aligned menu of every target. Dev-loop commands (`stop`, `migrate`, `build-fe`, `force-build-fe`, `clean-fe`, `dev`, `reset`) become Makefile-native — `build-fe` in particular becomes a file target with mtime prereqs so it skips cleanly when source hasn't changed. Verification-ladder commands (`test`, `lint`, `verify`, `verify-ladder`, `verify-slow`, `verify-all`, `serve-fresh`) delegate verbatim to `./test.sh`. `test.sh` is not modified. `CLAUDE.md` gets one discoverability sentence.

**Done when:**
- `Makefile` exists at repo root; `make help` prints an aligned list of every canonical target; every smoke case in spec §6.1 passes; `backend/tests/build/test_makefile_contract.py` passes; `CLAUDE.md` points at `make help` as the front door; `./test.sh all` still runs unchanged.

**Execution order:**

```
T1 (failing contract test)
  └─ T2 (Makefile skeleton: help + test.sh delegations + target stubs + E8 Windows guard)  ← T1 goes green here
       ├─ T3 (stop — native)                            ─────┐
       ├─ T4 (migrate — native)                         ─────┤
       ├─ T5 (node_modules/.package-lock.json file target)   │
       │    └─ T6a (static/index.html file target + build-fe alias) ──┐
       │         └─ T6b (force-build-fe + clean-fe)                   │
       │                                                              ├── T7 (dev orchestrator: depends on T3+T4+T6a)
       ├─ T8 (reset — TTY/CONFIRM guard, cross-platform data dir)     │
       └─ T9 (CLAUDE.md front-door sentence)                          │
            └─ TN (full verification: smoke 1-10 + pytest contract + VERIFY_DOCKER pass-through)
```

Hard-prerequisite convergence: **T3, T4, and T6a all feed T7** (T7's recipe requires `stop`, `migrate`, and `$(STATIC_INDEX)` to be real — not stubs). T6b depends on T6a (shares the `$(STATIC_INDEX)` file target). T5 precedes T6a (order-only prerequisite edge). T8 and T9 are independent; they can land in parallel with the T3→T7 chain and converge at TN.

---

## Decision Log

> Inherits architecture decisions from spec §3. Entries below are implementation-specific decisions made during planning.

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | TDD shape uses ONE automated contract test (`make help` lists canonical targets) plus per-task **smoke verification** via exact `make <target>` invocations. No per-target pytest suite. | (a) Pytest subprocess test per target (check exit code + stdout). (b) Bats/shellspec shell test framework. (c) One contract test + manual smoke + `make -n` dry-runs. | Spec §6.2 prescribes exactly one automated test; §6.1 prescribes 10 manual smoke steps. Adding a full pytest matrix for Makefile targets would balloon scope and duplicate `test.sh`'s own verification. Smoke + one contract test is proportional. |
| D2 | Task ordering: **skeleton first** (T2 passes the single automated test), then fill target recipes by subsystem (stop/migrate → FE pipeline → dev orchestrator → reset → CLAUDE.md → final verification). | (a) Skeleton-first (chosen). (b) One target per task in spec-table order. (c) All targets in one monolithic commit. | Skeleton-first gives the earliest possible green on the one automated test and lets the rest of the work proceed with the help-contract already locked. One target per task order (b) would delay the green until after all target work. Monolithic (c) loses task granularity and makes bisect impossible. |
| D3 | `make verify` aliases to `verify-ladder` (resolves spec Open Question #1). | (a) Alias → `verify-ladder`. (b) Alias → `verify-all`. (c) Omit `make verify` entirely. | User decision at intake: spec §8 already leaned this way (`all` is "rarely the one you want at your desk"). Matches desk-side ergonomics; `verify-all` is still reachable explicitly. |
| D4 | GNU Make **3.81** is the target (macOS default, confirmed via `make --version` on the dev machine). No 4.x-only features used. | (a) Require Make ≥ 4.0 and document it. (b) Target 3.81 (chosen). (c) Add a bootstrap step that `brew install make`. | Order-only prereqs (`\|`), `$(shell ...)`, `$(MAKEFILE_LIST)`, pattern rules, `.PHONY` — all work on 3.81. Requiring 4.x adds a prerequisite the spec doesn't call for. `test.sh` stays the escape hatch. All per-task verification runs against 3.81 on this machine. |
| D5 | T2 stubs non-skeleton targets (`stop`, `migrate`, `dev`, `reset`, `build-fe`, `force-build-fe`, `clean-fe`) with `@echo "not yet implemented"` recipes plus the real `## ...` help comment. T3-T8 replace stubs with real recipes. | (a) Stubbed recipes with `## ...` comments (chosen). (b) Leave targets undefined; `make help` lists via a separate comment block. (c) Implement every target in T2 and skip incremental tasks. | (a) keeps `make help` correct from T2 onwards (contract test stays green), preserves incremental task structure for bisect, and makes each follow-up task a clean recipe swap. (b) splits the target declaration from its comment, making `make help` parsing fragile. (c) violates the "bite-sized tasks" rule. |
| D6 | `reset`'s data-dir detection uses `uname -s` inline in the recipe. macOS path (`~/Library/Application Support/bookcompanion`) is quoted aggressively because of the embedded spaces. | (a) Inline `uname -s` switch (chosen). (b) Shell-out to a helper script. (c) Hardcode macOS path only and fail on Linux. | (a) keeps the Makefile self-contained (spec §4: single new file). (b) adds a file the spec doesn't call for. (c) violates spec §3 (cross-platform) and spec E6. |
| D7 | `CLAUDE.md` one-sentence update lands at the top of `## Commands` (above the backend subsection) — not inside the existing "Interactive verification" block — so developers see it as a front-door pointer before scrolling into specifics. | (a) Top of `## Commands` (chosen). (b) Inside `### Interactive verification (Playwright MCP)`. (c) A new `## Dev Loop` section. | (a) puts it where new readers land first. (b) buries it behind the Playwright-specific section. (c) adds sectional clutter for one sentence. Spec §4 says "one new sentence" — (a) is the minimum-ceremony placement. |
| D8 | The `backend/app/static/index.html` file target's recipe does NOT `rm -rf backend/app/static` before copying. E9 explains this is safe: Vite clears `frontend/dist/` at build start and produces hash-suffixed asset filenames, so stale assets under `backend/app/static/assets/` are content-addressed and harmless. A full wipe path is exposed via the `clean-fe` target. | (a) Copy-overlay (chosen, matches spec §3.2 + E9). (b) `rm -rf` before every copy (matches current `test.sh build_fe` behavior, line 100). | (a) preserves spec semantics and lets `make` treat `static/index.html` as a clean file target. (b) would leak unrelated files out of `backend/app/static/` on every build (`favicon.ico` etc. get nuked if not in dist) and doesn't match spec E9's rationale. `test.sh build_fe` does `rm -rf`, but that's incidental — the spec explicitly splits the "full wipe" into `clean-fe`. |
| D9 | Each new `.PHONY` target is declared with its **own** `.PHONY:` line (e.g., `.PHONY: stop`) rather than one consolidated `.PHONY: a b c ...` at top of file. | (a) Per-target `.PHONY:` lines (chosen). (b) One consolidated list. | (a) keeps each target self-contained across the T3-T8 diffs — adding a new target is a single contiguous block, not a cross-file edit. This matches GNU Make's own Makefile style guide and makes the T2→T8 diffs clean. |
| D10 | Windows detection (spec §5 E8) lands in T2 as an `ifeq ($(OS),Windows_NT)` guard at top of Makefile: `help` recipe prints the bail message, every other recipe fires `$(error Windows is not supported; see ./test.sh)` via a `@:$(WINDOWS_BAIL)` preamble. Assignment uses **lazy `=`** (not `:=`) so `$(error)` only fires on reference, never at parse time. | (a) Guard in T2 with lazy assignment (chosen). (b) Separate task. (c) Per-recipe early-exit. (d) Rely on native Make/shell errors without a guard. (e) Immediate `:=` assignment (rejected — crashes `make help` on Windows at parse time, violating E8). | (a) keeps the Makefile self-contained, puts the bail message in the right place (first error a Windows user sees), and the guard is three lines. The **lazy-expansion requirement** is non-obvious: `WINDOWS_BAIL := $(error ...)` fires at assignment time on Windows (blowing up even `make help`), while `WINDOWS_BAIL = $(error ...)` defers expansion until a recipe references it. This is why `help` — which does NOT reference `$(WINDOWS_BAIL)` — stays usable on Windows. (b) is more ceremony than the work deserves. (c) duplicates the guard across every recipe. (d) fails with confusing POSIX-isms (`lsof`, `uname -s`, etc.) instead of a clear message. |

---

## Code Study Notes

**Read in Phase 2:**

- `test.sh` (full, 160 lines): contract to delegate to. The Makefile's `test.sh` delegations must pass `BC_PORT`, `BC_SKIP_MIGRATE`, and `VERIFY_DOCKER` through verbatim — `test.sh` reads them as env vars, not flags (see `test.sh:34`, `test.sh:27`, `test.sh:12-26`). The `stop` / `migrate` / `build_fe` / `reset` / `dev` functions in `test.sh` are the reference behavior for the Makefile-native ports.
- `backend/tests/build/test_end_to_end_packaging.py` (header): `@pytest.mark.slow`, `BACKEND_DIR = Path(__file__).resolve().parents[2]`. The new `test_makefile_contract.py` uses the same pattern but `.parents[3]` to reach the repo root (Makefile lives one level up from `backend/`).
- `backend/tests/build/test_hatch_build_hook.py` (header): shows the plain `subprocess.run` + `capture_output=True` convention already in use — no bespoke test helper needed.
- `CLAUDE.md` §Commands (line ~50 onwards) and §"Interactive verification (Playwright MCP)" (line 278): confirmed there's no existing dev-loop front-door doc; the one-line addition slots cleanly above the backend commands block.
- `frontend/` layout: `package-lock.json` exists → `frontend/node_modules/.package-lock.json` file target has a real prerequisite; `node_modules` is populated locally.
- `make --version` → GNU Make 3.81. All spec features supported.

**Patterns to follow:**

- Existing `test.sh` already has color-coded `log()` / `warn()` helpers using `\033[1;34m` / `\033[1;33m`. Spec §3.4 uses `\033[1;36m` in the awk help printf — distinct from `test.sh`, so the two remain visually separable.
- `test.sh:30`: `REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"`. The Makefile runs from the repo root by definition (where the Makefile lives); recipes use relative paths for `backend/`, `frontend/`.
- `test.sh:57-78`: the `stop` function already handles "nothing listening" (prints message, exits 0) and cleans stray Playwright Chrome processes — replicate semantics exactly.

**Pipelines traced:**

- Write→read: N/A (no data pipeline; this is a build-tooling change).
- Source-to-artifact: `frontend/src/**` → `frontend/dist/**` (via `npm run build`) → `backend/app/static/**` (via `cp -R`). The file-target graph in spec §3.2 captures this correctly.

---

## Prerequisites

Before T1:

- Working directory: `/Users/maneeshdhabria/Desktop/Projects/personal/book-companion` (repo root).
- `GNU Make` installed (macOS default 3.81 is fine; `make --version` should succeed).
- `frontend/node_modules` already populated (from prior `npm install`). If missing on a fresh clone, T5's file target handles it — but for running TN verification locally, have it populated.
- `./test.sh` is executable (`chmod +x` already applied — verify with `ls -l test.sh`).
- No `Makefile` currently exists at repo root (confirmed during intake; a pre-existing Makefile would need to be consolidated first).
- Git branch: create a feature branch before T1: `git checkout -b feature/makefile-dev-loop`.

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `Makefile` | Repo-root front-door. Hosts help + every `.PHONY` + the two file targets. GNU Make 3.81+ syntax. |
| Create | `backend/tests/build/test_makefile_contract.py` | Single automated test per spec §6.2 — asserts `make help` lists the canonical targets. Marked `@pytest.mark.slow`. |
| Modify | `CLAUDE.md` (top of `## Commands` section, ~line 50) | Add one sentence: `make help` is the top-level front door; `./test.sh` stays for the packaging/verification ladder. |
| Unchanged | `test.sh` | The Makefile delegates to it for `test`/`lint`/`verify*`/`serve-fresh`. Contract preserved. |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Spec prescribes GNU Make syntax but someone runs a non-GNU make (e.g., BSD make on FreeBSD) | Low (macOS + Linux only per spec §2 Non-Goals) | TN adds an early `make --version` assertion in `test_makefile_contract.py` to confirm GNU is being invoked; E8 covers Windows exit. |
| `$(shell find frontend/src -type f)` is parse-time and breaks if `frontend/` doesn't exist (e.g., sparse checkout) | Very Low | T6a guards the `find` with `2>/dev/null` so a missing directory yields an empty list, and the file target's recipe then fails loudly on the first `npm run build` with a clear error — preferable to a silent no-op. |
| Order-only prerequisite for `frontend/node_modules/.package-lock.json` doesn't actually prevent re-install thrash on a fresh clone | Low | T5's smoke verification (`make build-fe` twice → second run no-ops) explicitly tests this. The order-only edge (`\|`) is GNU Make semantics since 3.80, predating our 3.81 target. |
| `reset` deletes data in a non-TTY context (e.g., piped invocation) | Low | Spec E5 + T8: recipe checks `[ -t 0 ]`; if non-TTY, refuses to proceed unless `CONFIRM=1` is set. Smoke step in T8 verifies refusal path. |
| `make dev` silently races a pre-existing `bookcompanion serve` on :8000 | Low | Spec E2: `dev` depends on `stop`, which kills any PID on `$(PORT)` before starting. Smoke step 7-8 verifies. |
| `cp -R frontend/dist/. backend/app/static/` leaves stale non-hashed files (D8) | Low | Spec E9: accepted risk; hash-suffixed assets make the issue cosmetic. `clean-fe` provides the escape hatch. |
| Breaking `./test.sh all` inadvertently | Very Low | `test.sh` is untouched; TN's final step runs `./test.sh all` to confirm no regression. |

---

## Rollback

Because no schema, migration, or deploy artifact is introduced, rollback is trivial:

- `git revert <commit-sha>` removes the Makefile, the new pytest, and the CLAUDE.md line. No code depends on the Makefile (`test.sh` is unchanged). No rollback script needed.
- If `backend/app/static/` ends up in a bad state during development (stale mixed assets from D8/E9), run `make clean-fe && make force-build-fe` — the plan ships both tools on purpose.

---

## Tasks

### T1: Write the failing Makefile contract test

**Goal:** Land the one automated test from spec §6.2. It fails now (no Makefile exists) and goes green in T2.
**Spec refs:** §6.2

**Files:**
- Create: `backend/tests/build/test_makefile_contract.py`

**Steps:**

- [ ] Step 1: Create `backend/tests/build/test_makefile_contract.py` with a single `@pytest.mark.slow` test that invokes `make help` at the repo root (`Path(__file__).resolve().parents[3]`), captures stdout, asserts exit 0, and asserts each of the canonical targets (`dev`, `stop`, `migrate`, `build-fe`, `force-build-fe`, `clean-fe`, `reset`, `test`, `lint`, `verify`, `verify-ladder`, `verify-slow`, `verify-all`, `serve-fresh`, `help`) appears as a substring in stdout. Use `subprocess.run` with `timeout=10`. Match the helper patterns in `test_end_to_end_packaging.py` / `test_hatch_build_hook.py` (plain `subprocess`, no bespoke fixture).

  **Test interface to implement:**
  ```python
  # file: backend/tests/build/test_makefile_contract.py
  import subprocess
  from pathlib import Path
  import pytest

  REPO_ROOT = Path(__file__).resolve().parents[3]
  CANONICAL_TARGETS = (
      "dev", "stop", "migrate", "build-fe", "force-build-fe", "clean-fe",
      "reset", "test", "lint", "verify", "verify-ladder", "verify-slow",
      "verify-all", "serve-fresh", "help",
  )

  @pytest.mark.slow
  def test_makefile_help_lists_canonical_targets():
      out = subprocess.run(
          ["make", "help"], cwd=str(REPO_ROOT),
          capture_output=True, text=True, timeout=10,
      )
      assert out.returncode == 0, f"make help failed: {out.stderr!r}"
      for target in CANONICAL_TARGETS:
          assert target in out.stdout, (
              f"make help missing target {target!r}. "
              f"stdout was:\n{out.stdout}"
          )
  ```

- [ ] Step 2: Run the test — it must fail because no Makefile exists yet.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: FAIL (returncode non-zero, stderr contains `No targets specified and no makefile found` or equivalent Make error).

- [ ] Step 3: Commit the failing test.
  ```bash
  git add backend/tests/build/test_makefile_contract.py
  git commit -m "test: add failing Makefile help-contract test"
  ```

**Inline verification:**
- `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v` — 1 failed, 0 passed, error identifies "no makefile found" (behavior proof that the test exercises the real `make` binary, not a stub).

---

### T2: Makefile skeleton — help target, test.sh delegations, .PHONY stubs, Windows guard

**Goal:** Create the Makefile with (a) a Windows-detection guard per E8, (b) a working `help` target, (c) real recipes for the `test.sh` delegation targets, and (d) `## ...` help comments for every `.PHONY` target so the contract test goes green. Dev-loop targets (`stop`, `migrate`, `build-fe`, `force-build-fe`, `clean-fe`, `dev`, `reset`) get stub recipes (`@echo "not yet implemented (see T3-T8)"`).
**Spec refs:** §3.1, §3.2 (test/lint/verify/verify-ladder/verify-slow/verify-all/serve-fresh rows), §3.4, §4, §5 E8

**Files:**
- Create: `Makefile` (repo root)

**Steps:**

- [ ] Step 1: Create `Makefile` with the following structure:

  1. **Header comment** (3-5 lines): points to `docs/specs/2026-04-25-makefile-dev-loop-spec.md` and says the Makefile is the front door; `test.sh` is delegated to for the verification ladder.
  2. **Windows guard** (per D10 / spec E8) — placed BEFORE the variable block so it short-circuits everything:
     ```
     ifeq ($(OS),Windows_NT)
     $(warning Windows detected — this Makefile targets macOS / Linux only.)
     WINDOWS_BAIL = $(error Windows is not supported; run commands directly — see ./test.sh)
     endif
     ```
     **Critical — lazy (`=`) not immediate (`:=`) assignment:** GNU Make evaluates the RHS of `:=` at assignment time, which would fire `$(error ...)` during Makefile parsing and crash `make help` on Windows — violating spec E8's requirement that `help` still prints a bail message. Using `=` defers expansion until `$(WINDOWS_BAIL)` is referenced (inside a recipe preamble). `help` does not reference it and stays usable on Windows. On non-Windows, `WINDOWS_BAIL` is undefined; `$(WINDOWS_BAIL)` expands to empty and the preamble `@:$(WINDOWS_BAIL)` collapses to the shell null-op `@:`.
  3. **Variables:**
     - `PORT ?= 8000`
     - `STATIC_INDEX := backend/app/static/index.html`
     - `NODE_LOCK := frontend/node_modules/.package-lock.json`
     - `BACKEND := backend`
     - `FRONTEND := frontend`
  4. **Default goal:** `.DEFAULT_GOAL := help`
  5. **`help` target** (verbatim recipe from spec §3.4) — note: on Windows, override so the recipe prints the bail message instead of aligned targets:
     ```
     help:  ## Show this help
     ifeq ($(OS),Windows_NT)
     	@echo "Windows: run commands directly; see ./test.sh"
     else
     	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[1;36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
     endif
     .PHONY: help
     ```
  6. **test.sh delegations** with real recipes (each followed by its own `.PHONY:` line per D9). Every recipe gains a `$(WINDOWS_BAIL)`-referencing preamble line — e.g., `@:$(WINDOWS_BAIL)` — which is a no-op on macOS/Linux (expands to `:` and does nothing) but trips the `$(error ...)` on Windows:
     - `test: ## Fast lint + full unit/integration pytest (delegates to ./test.sh fast)` → recipe: `@:$(WINDOWS_BAIL)` then `BC_PORT=$(PORT) ./test.sh fast`
     - `lint: ## Backend lint only (uv run ruff check .)` → recipe: `@:$(WINDOWS_BAIL)` then `cd $(BACKEND) && uv run ruff check .`
     - `verify: verify-ladder ## Alias for verify-ladder (cheap desk-side verification)` → no body; prereq chain does the work (prereq carries its own Windows guard). Per D3.
     - `verify-ladder: ## Packaging verification ladder (delegates to ./test.sh ladder)` → recipe: `@:$(WINDOWS_BAIL)` then `./test.sh ladder`
     - `verify-slow: ## End-to-end pytest (delegates to ./test.sh slow)` → recipe: `@:$(WINDOWS_BAIL)` then `./test.sh slow`
     - `verify-all: ## fast + ladder + slow (delegates to ./test.sh all)` → recipe: `@:$(WINDOWS_BAIL)` then `./test.sh all`
     - `serve-fresh: ## Build wheel, install into /tmp/bc, run it (delegates to ./test.sh serve)` → recipe: `@:$(WINDOWS_BAIL)` then `BC_PORT=$(PORT) ./test.sh serve`
  7. **Dev-loop target stubs** — each declares the `## ...` comment and has a stub recipe `@echo "not yet implemented — see T3-T8 in docs/plans/2026-04-25-makefile-dev-loop-implementation-plan.md"`. Stubs also include `@:$(WINDOWS_BAIL)` so the Windows bail applies even before the real recipe lands in T3-T8. Order matches spec §3.2 table:
     - `stop: ## Kill any bookcompanion serve on $(PORT) + stale Playwright MCP chrome`
     - `migrate: ## Apply Alembic migrations against the real data dir`
     - `build-fe: ## Rebuild frontend into backend/app/static if src has changed`
     - `force-build-fe: ## Force rebuild the frontend unconditionally`
     - `clean-fe: ## rm -rf backend/app/static (full wipe for next build)`
     - `dev: ## Refresh: stop, migrate, build FE if needed, serve on $(PORT)`
     - `reset: ## ⚠ destructive: backup data dir + re-init (requires CONFIRM=1 if non-TTY)`

     Each gets its own `.PHONY:` line per D9.

  8. **No file targets yet** — those land in T5 / T6a / T6b.

- [ ] Step 2: Confirm the Makefile parses and `make help` runs:
  Run: `make --version | head -1 && make help`
  Expected: `GNU Make 3.81` (or 4.x) on line 1; then an aligned list of every canonical target with its `## ...` description in cyan. Exit 0.

- [ ] Step 3: Run the contract test — it should now pass.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: 1 passed.

- [ ] Step 4: Spot-check one delegation works end-to-end.
  Run: `make lint`
  Expected: runs `cd backend && uv run ruff check .`, prints any lint findings, exits 0 if clean.

- [ ] Step 5: Spot-check the `verify` alias resolves correctly (D3):
  Run: `make -n verify 2>&1 | head -5`
  Expected: dry-run output shows `./test.sh ladder` (via the `verify-ladder` prerequisite), not `./test.sh all`.

- [ ] Step 6: Spot-check a stub.
  Run: `make stop`
  Expected: prints `not yet implemented — see T3-T8 ...`, exits 0.

- [ ] Step 7: Windows-guard smoke test (D10 / E8). Since the dev machine isn't Windows, simulate by forcing `OS=Windows_NT`. **This step is the behavioral proof of D10's lazy-expansion fix — if `WINDOWS_BAIL` were assigned with `:=`, `make help` would also crash at parse time.**
  Run (a): `OS=Windows_NT make help 2>&1; echo "exit=$?"`
  Expected (a): output contains `Windows: run commands directly; see ./test.sh` AND contains `Windows detected — this Makefile targets macOS / Linux only.` (the `$(warning)`), `exit=0`. **Critical: `make help` must NOT emit the `$(error ...)` text — if it does, `WINDOWS_BAIL` was assigned with `:=` instead of `=`.**
  Run (b): `OS=Windows_NT make test 2>&1 | tail -5; echo "exit=$?"`
  Expected (b): output contains `Windows is not supported; run commands directly — see ./test.sh`, `exit=2` (GNU Make's `$(error)` exit code).

- [ ] Step 8: Commit.
  ```bash
  git add Makefile
  git commit -m "feat(make): skeleton Makefile with help + test.sh delegations + Windows guard"
  ```

**Inline verification:**
- `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v` — 1 passed, 0 failed (red→green on the one automated test; behavioral — fails if any canonical target is missing from `make help` output).
- `make help | wc -l` — prints ≥ 15 (help + 14 targets).
- `make -n verify 2>&1` — expands to `./test.sh ladder`; behavioral proof that D3's alias is wired correctly.
- `OS=Windows_NT make test` — exits non-zero with the bail message (behavioral — proves E8 / D10 fires on a non-`help` target); `OS=Windows_NT make help` prints `Windows: run commands directly; see ./test.sh` (behavioral — proves the `help` target has its own platform branch).

---

### T3: Implement `stop` target

**Goal:** Replace the T2 stub with the real `stop` recipe — kill any PID on `$(PORT)`, then kill stray Playwright MCP Chrome. Semantics match `test.sh:57-78` exactly.
**Spec refs:** §3.2 (stop row), §5 E1

**Files:**
- Modify: `Makefile` (replace the `stop` stub recipe)

**Steps:**

- [ ] Step 1: Replace the `stop` stub with a recipe that:
  0. **First line must be `@:$(WINDOWS_BAIL)`** — preserve this preamble from the T2 stub so the Windows guard still fires (D10).
  1. Uses `lsof -ti:$(PORT) 2>/dev/null` to capture PIDs; if non-empty, `kill` them, sleep 1, then force-kill with `-9` any stragglers. If empty, print `nothing listening on :$(PORT)` and continue (exit 0 — spec E1).
  2. Uses `pgrep -f 'ms-playwright/mcp-chrome' 2>/dev/null` to capture stray Chrome PIDs; if non-empty, kill them and log which PIDs were killed. If empty, no message needed.
  3. Uses `@echo` / `@printf` for human-readable logs; no Make-level noise (`@`-prefix all commands that don't need to echo).

  Behavior must match `test.sh:57-78` — do not diverge. The recipe runs in `/bin/sh` by default; use POSIX `[ -n "$$pids" ]` (double-`$$` to escape Make's `$` expansion).

- [ ] Step 2: Smoke-verify "nothing listening" branch.
  Run: `make stop` (on a machine with nothing on :8000)
  Expected: output contains `nothing listening on :8000`, exit 0.

- [ ] Step 3: Smoke-verify "kill a PID" branch.
  Run (in a second terminal or background): `python3 -m http.server 8765 & sleep 1 && make stop PORT=8765`
  Expected: output contains `killed :8765` (or equivalent), exit 0, `lsof -ti:8765` now returns empty.

- [ ] Step 4: Smoke-verify the Makefile still parses and the contract test still passes.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: 1 passed.

- [ ] Step 5: Commit.
  ```bash
  git add Makefile
  git commit -m "feat(make): implement native stop target"
  ```

**Inline verification:**
- `make stop` (idle machine) → `nothing listening on :8000`, exit 0 (behavioral — proves E1).
- `python3 -m http.server 8765 &; sleep 1; make stop PORT=8765; lsof -ti:8765` → final `lsof` prints nothing (behavioral — proves the kill path works end-to-end with the `PORT` env override).

---

### T4: Implement `migrate` target

**Goal:** Replace the T2 stub with the real `migrate` recipe — `uv run alembic -c app/migrations/alembic.ini upgrade head` executed inside `backend/`. Mirrors `test.sh:80-82`.
**Spec refs:** §3.2 (migrate row)

**Files:**
- Modify: `Makefile` (replace the `migrate` stub recipe)

**Steps:**

- [ ] Step 1: Replace the stub with a two-line recipe:
  - Line 1: `@:$(WINDOWS_BAIL)` — preserve the preamble from the T2 stub so the Windows guard still fires (D10).
  - Line 2: `cd $(BACKEND) && uv run alembic -c app/migrations/alembic.ini upgrade head`.

  Keep the `## ...` help comment unchanged.

- [ ] Step 2: Smoke-verify (expects a working data dir; on this repo the real SQLite library exists).
  Run: `make migrate`
  Expected: alembic prints `INFO [alembic.runtime.migration] Context impl SQLiteImpl.` plus any migrations applied (or a no-op if already at head). Exit 0.

- [ ] Step 3: Re-run to confirm idempotency.
  Run: `make migrate`
  Expected: same prefix, no new migrations applied. Exit 0. (Behavioral proof that the recipe is a proper no-op on already-migrated DBs.)

- [ ] Step 4: Confirm contract test still passes.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: 1 passed.

- [ ] Step 5: Commit.
  ```bash
  git add Makefile
  git commit -m "feat(make): implement native migrate target"
  ```

**Inline verification:**
- `make migrate` twice → both exit 0, second run is a no-op (behavioral — proves idempotency, proves `-c` flag path is right, proves `uv run` picks up the right env).

---

### T5: Implement `frontend/node_modules/.package-lock.json` file target

**Goal:** Land the order-only prerequisite target so `npm ci` runs exactly when `frontend/node_modules` is absent or `frontend/package-lock.json` has changed — without triggering a frontend rebuild on install (spec E7).
**Spec refs:** §3.2 (node_modules row), §5 E7

**Files:**
- Modify: `Makefile` (append the new file target)

**Steps:**

- [ ] Step 1: Append the file target to the Makefile (below the `.PHONY` blocks, in a file-targets section):

  ```
  # --- File targets ---

  frontend/node_modules/.package-lock.json: frontend/package-lock.json
  	@:$(WINDOWS_BAIL)
  	cd $(FRONTEND) && npm ci
  	@touch $@
  ```

  Why `touch $@`: `npm ci` may rewrite `.package-lock.json` with a timestamp older than `frontend/package-lock.json`, defeating the mtime check on the next run. Explicit `touch` guarantees the target mtime moves forward. `@:$(WINDOWS_BAIL)` first-line preamble preserves the Windows guard (D10).

- [ ] Step 2: Smoke-verify the target is a no-op when `node_modules` is fresh.
  Run: `make frontend/node_modules/.package-lock.json`
  Expected: `make: Nothing to be done for 'frontend/node_modules/.package-lock.json'.` (assuming the lock file inside `node_modules` is newer than the top-level `package-lock.json`, which is the normal post-`npm-install` state). Exit 0.

- [ ] Step 3: Smoke-verify it re-runs when the top-level lock changes.
  Run: `touch frontend/package-lock.json && make -n frontend/node_modules/.package-lock.json`
  Expected: dry-run output shows `cd frontend && npm ci` (behavioral — the prerequisite is newer than the target, so the recipe fires).

- [ ] Step 4: Confirm contract test still passes.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: 1 passed.

- [ ] Step 5: Commit.
  ```bash
  git add Makefile
  git commit -m "feat(make): add node_modules file target for npm-ci gating"
  ```

**Inline verification:**
- `touch frontend/package-lock.json && make -n frontend/node_modules/.package-lock.json | grep 'npm ci'` — prints the recipe line (behavioral — proves the mtime dependency works correctly in the firing direction).
- `make frontend/node_modules/.package-lock.json` immediately after → `Nothing to be done` (behavioral — proves `touch $@` advances the target mtime past the prerequisite).

---

### T6a: Implement `backend/app/static/index.html` file target + `build-fe` alias

**Goal:** Land the core mtime-skipped FE build target and its `.PHONY` skip-aware alias. This is the headline feature — `make build-fe` becomes genuinely skippable when source hasn't changed.
**Spec refs:** §3.2 (build-fe row, static/index.html row), §5 E3, E7, E9, §6.1 smoke 2-4

**Files:**
- Modify: `Makefile` (append file target + replace `build-fe` stub)

**Steps:**

- [ ] Step 1: Append the file target in a new "File targets" section (after T5's node_modules target). Key points:

  ```
  # $(shell find ...) is parse-time; keep the prerequisite list explicit.
  FRONTEND_SRC := $(shell find $(FRONTEND)/src -type f 2>/dev/null)

  $(STATIC_INDEX): $(FRONTEND_SRC) $(FRONTEND)/index.html $(FRONTEND)/vite.config.ts $(FRONTEND)/package.json | $(NODE_LOCK)
  	@:$(WINDOWS_BAIL)
  	cd $(FRONTEND) && npm run build
  	@mkdir -p $(@D)
  	cp -R $(FRONTEND)/dist/. $(dir $@)
  	@echo "  deployed $$(ls $(dir $@)assets 2>/dev/null | grep '^index-' | head -1)"
  ```

  - The `|` splits the prerequisite list: the items after `|` are **order-only** (spec E7), so `npm ci` firing does NOT cascade into a FE rebuild just because `node_modules/.package-lock.json` got touched.
  - Recipe does NOT `rm -rf $(dir $@)` — per D8 + E9.
  - `$$(...)` is the Make-level escape for the shell `$(...)` command substitution in the final log line.
  - `@:$(WINDOWS_BAIL)` preamble line keeps the Windows guard consistent with T2's pattern.

- [ ] Step 2: Replace the `build-fe` stub with an alias:
  ```
  build-fe: $(STATIC_INDEX)  ## Rebuild frontend into backend/app/static if src has changed
  .PHONY: build-fe
  ```
  No recipe body — `build-fe` is just a phony pointer at the file target. `make` only fires the file target's recipe if needed.

- [ ] Step 3: Smoke-verify spec §6.1 step 2 — first build fires the recipe. (We haven't implemented `clean-fe` yet, so wipe static manually for this verification.)
  Run: `rm -rf backend/app/static && make build-fe`
  Expected: `npm run build` runs, `cp -R` copies, final line prints `deployed index-<hash>.js`. `backend/app/static/index.html` exists. Exit 0.

- [ ] Step 4: Smoke-verify spec §6.1 step 3 — second build is a no-op.
  Run: `make build-fe`
  Expected: `make: Nothing to be done for 'build-fe'.` or equivalent. No `npm run build` invocation. Exit 0. (Behavioral proof that mtime-skip works end-to-end.)

- [ ] Step 5: Smoke-verify spec §6.1 step 4 — touching a src file triggers rebuild.
  Run: `touch frontend/src/main.ts && make build-fe`
  Expected: `npm run build` runs again; new deployed-index line; exit 0. (Behavioral proof that the explicit prerequisite list picks up src edits.)

- [ ] Step 6: Smoke-verify E7 — order-only edge doesn't cascade.
  Run: `touch frontend/node_modules/.package-lock.json && make -n build-fe`
  Expected: dry-run shows no `npm run build` invocation (behavioral — the `| $(NODE_LOCK)` order-only prerequisite does NOT propagate its newer mtime into the file target's skip decision).

- [ ] Step 7: Confirm contract test still passes.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: 1 passed.

- [ ] Step 8: Commit.
  ```bash
  git add Makefile
  git commit -m "feat(make): native build-fe with mtime-skipped file target"
  ```

**Inline verification:**
- `rm -rf backend/app/static && make build-fe && make build-fe` — first build runs `npm run build`, second prints `Nothing to be done` (behavioral — this is the headline feature of the whole spec).
- `touch frontend/src/main.ts && make build-fe` rebuilds (behavioral — proves explicit src prereqs fire the recipe).
- `touch $(NODE_LOCK) && make -n build-fe` does NOT plan a `npm run build` call (behavioral — proves order-only semantics, spec E7).

---

### T6b: Implement `force-build-fe` and `clean-fe`

**Goal:** Land the two escape-hatch targets — `force-build-fe` (unconditional rebuild) and `clean-fe` (full wipe of `backend/app/static/`). Depends on T6a's file target.
**Spec refs:** §3.2 (force-build-fe row, clean-fe row), §5 E9, §6.1 smoke 5

**Files:**
- Modify: `Makefile` (replace two stubs)

**Steps:**

- [ ] Step 1: Replace the `force-build-fe` stub with:
  ```
  force-build-fe:  ## Force rebuild the frontend unconditionally
  	@:$(WINDOWS_BAIL)
  	@rm -f $(STATIC_INDEX)
  	@$(MAKE) $(STATIC_INDEX)
  .PHONY: force-build-fe
  ```
  Re-invoking `$(MAKE)` is the canonical pattern for "rebuild this file target even though the outer Make already parsed its mtime" — deleting the target and then recursing guarantees the sub-Make's prereq check fails and the recipe fires.

- [ ] Step 2: Replace the `clean-fe` stub with:
  ```
  clean-fe:  ## rm -rf backend/app/static (full wipe for next build)
  	@:$(WINDOWS_BAIL)
  	rm -rf $(BACKEND)/app/static
  .PHONY: clean-fe
  ```

- [ ] Step 3: Smoke-verify spec §6.1 step 5 — `force-build-fe` unconditionally rebuilds.
  Run: `make build-fe && make force-build-fe`
  Expected: first invocation is a no-op (or rebuilds if needed); second ALWAYS fires `npm run build`. Exit 0.

- [ ] Step 4: Smoke-verify `clean-fe` → subsequent `build-fe` rebuilds from scratch.
  Run: `make clean-fe && make build-fe`
  Expected: `clean-fe` removes `backend/app/static/` entirely; `build-fe` then fires `npm run build` (target doesn't exist) and re-creates the directory with `cp -R`. Verify: `test -f backend/app/static/index.html` exits 0. (Behavioral proof that `clean-fe` provides the explicit full-reset path from D8 / E9.)

- [ ] Step 5: Confirm contract test still passes.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: 1 passed.

- [ ] Step 6: Commit.
  ```bash
  git add Makefile
  git commit -m "feat(make): add force-build-fe and clean-fe escape hatches"
  ```

**Inline verification:**
- `make build-fe && make force-build-fe` — `force-build-fe` runs `npm run build` even when `build-fe` was just a no-op (behavioral — proves D8's split between skip-aware and unconditional).
- `make clean-fe; test -d backend/app/static` — exits non-zero (behavioral — proves the full wipe actually removed the directory).
- `make clean-fe && make build-fe && test -f backend/app/static/index.html` — exits 0 (behavioral — proves the clean→build cycle works end-to-end).

---

### T7: Implement `dev` orchestrator

**Goal:** Replace the stub with the real orchestrator: `stop` → (`migrate` unless `BC_SKIP_MIGRATE=1`) → `$(STATIC_INDEX)` → `bookcompanion serve`.
**Spec refs:** §3.2 (dev row), §3.3 (BC_SKIP_MIGRATE), §5 E2

**Files:**
- Modify: `Makefile` (replace the `dev` stub)

**Steps:**

- [ ] Step 1: Replace the `dev` stub with:

  ```
  ifeq ($(BC_SKIP_MIGRATE),1)
  DEV_MIGRATE_DEP :=
  else
  DEV_MIGRATE_DEP := migrate
  endif

  dev: stop $(DEV_MIGRATE_DEP) $(STATIC_INDEX)  ## Refresh: stop, migrate, build FE if needed, serve on $(PORT)
  	@:$(WINDOWS_BAIL)
  	@printf "\n\033[1;34m==> Starting bookcompanion serve on :$(PORT)\033[0m\n"
  	cd $(BACKEND) && exec uv run bookcompanion serve --port $(PORT)
  ```

  - Conditional prerequisite is the idiomatic GNU Make pattern for "optional prereq controlled by an env var." Semantics match `test.sh:105-111`.
  - `exec` replaces the shell so Ctrl-C reaches uvicorn directly (same as `test.sh:110`).
  - `@:$(WINDOWS_BAIL)` first-line preamble preserves the Windows guard (D10).

- [ ] Step 2: Smoke-verify dry-run on a fresh build state shows the full chain.
  Run: `make clean-fe && make -n dev 2>&1 | head -20`
  Expected: output shows recipes for `stop`, `migrate`, `npm run build`, `cp -R ...`, and `uv run bookcompanion serve --port 8000` in that order.

- [ ] Step 3: Smoke-verify `BC_SKIP_MIGRATE=1` removes migrate from the chain.
  Run: `BC_SKIP_MIGRATE=1 make -n dev 2>&1 | grep -c alembic`
  Expected: `0` (behavioral — the migrate prereq is excluded).

- [ ] Step 4: End-to-end smoke on a free port (interactive — kill with Ctrl-C after verifying).
  Run (in one terminal): `PORT=8765 make dev`
  Expected: stop logs "nothing listening on :8765", migrate runs, FE skips if already built, then `INFO: Uvicorn running on http://0.0.0.0:8765`.
  Probe (in another terminal): `curl -sf http://localhost:8765/api/v1/health | python3 -m json.tool` → prints a health JSON with `status` field.
  Cleanup: Ctrl-C the first terminal, then `make stop PORT=8765` (should report nothing listening now).

- [ ] Step 5: Confirm contract test still passes.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: 1 passed.

- [ ] Step 6: Commit.
  ```bash
  git add Makefile
  git commit -m "feat(make): implement dev orchestrator with BC_SKIP_MIGRATE"
  ```

**Inline verification:**
- `make -n dev 2>&1 | grep -E '(stop|alembic|npm run build|bookcompanion serve)'` — shows all four (behavioral — proves prereq graph is correct).
- `BC_SKIP_MIGRATE=1 make -n dev 2>&1 | grep alembic` — empty output, exit 1 from grep (behavioral — proves the env toggle works).
- `PORT=8765 make dev &` then `curl -sf http://localhost:8765/api/v1/health` returns 200 (behavioral — proves the whole chain actually serves traffic).

---

### T8: Implement `reset` target

**Goal:** Replace the stub with a guarded destructive recipe: detect the data dir per platform, timestamp-back it up, run `bookcompanion init`. Refuse in non-TTY contexts unless `CONFIRM=1`.
**Spec refs:** §3.2 (reset row), §3.3 (CONFIRM), §5 E4, E5, E6

**Files:**
- Modify: `Makefile` (replace the `reset` stub)

**Steps:**

- [ ] Step 1: Replace the `reset` stub with:

  ```
  reset:  ## ⚠ destructive: backup data dir + re-init (requires CONFIRM=1 if non-TTY)
  	@:$(WINDOWS_BAIL)
  	@set -eu; \
  	if [ "$$(uname -s)" = "Darwin" ]; then \
  	  data_dir="$$HOME/Library/Application Support/bookcompanion"; \
  	else \
  	  data_dir="$${XDG_DATA_HOME:-$$HOME/.local/share}/bookcompanion"; \
  	fi; \
  	printf "\033[1;33m!!  About to reset data dir: %s\033[0m\n" "$$data_dir"; \
  	if [ -t 0 ]; then \
  	  printf "Continue? [y/N] "; read -r reply; \
  	  case "$$reply" in y|Y) : ;; *) echo "aborted"; exit 1 ;; esac; \
  	elif [ "$(CONFIRM)" != "1" ]; then \
  	  echo "non-TTY without CONFIRM=1; refusing to proceed"; exit 2; \
  	fi; \
  	if [ -d "$$data_dir" ]; then \
  	  backup="$$data_dir.$$(date +%Y%m%d_%H%M%S).bak"; \
  	  mv "$$data_dir" "$$backup"; \
  	  echo "  backed up to $$backup"; \
  	fi; \
  	cd $(BACKEND) && uv run bookcompanion init
  ```

  - `@:$(WINDOWS_BAIL)` first-line preamble preserves the Windows guard (D10).
  - One big `@set -eu; \` block: `reset` is one atomic operation; splitting into multiple recipe lines loses the shell variables (`data_dir`) between commands.
  - `$$` doubles escape every shell `$` from Make expansion.
  - `[ -t 0 ]` detects TTY on stdin; non-TTY without `CONFIRM=1` exits 2 (spec E5).
  - Missing data dir skips the backup step (spec E4) — the `if [ -d "$$data_dir" ]` guard.
  - Linux branch respects `XDG_DATA_HOME` (spec E6).

- [ ] Step 2: Smoke-verify the non-TTY refusal path (E5).
  Run: `echo '' | make reset 2>&1 | tail -5; echo "exit=$?"`
  Expected: output contains `non-TTY without CONFIRM=1; refusing to proceed`, exit 2. (Behavioral — proves E5 without destroying any data.)

- [ ] Step 3: Smoke-verify the dry-run shows the right data-dir path.
  Run: `make -n reset 2>&1 | head -20`
  Expected: the recipe text echoes; visually confirm the Darwin/Linux branching is present in the rendered recipe.

- [ ] Step 4: Confirm contract test still passes.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: 1 passed.

- [ ] Step 5: **DO NOT** run `make reset CONFIRM=1` as part of T8 verification — it destroys local data. Defer the actual-reset smoke test to TN step 10, where the user has given explicit affordance.

- [ ] Step 6: Commit.
  ```bash
  git add Makefile
  git commit -m "feat(make): implement guarded reset target"
  ```

**Inline verification:**
- `echo '' | make reset` → exit 2, stderr/stdout contains `refusing to proceed` (behavioral — proves E5, proves no backup was actually created because stdin is non-TTY).
- `ls ~/Library/Application\ Support/bookcompanion.*.bak 2>/dev/null | wc -l` before and after the refusal test → unchanged (behavioral — proves the refusal fires BEFORE any `mv`).

---

### T9: Update CLAUDE.md front-door sentence

**Goal:** Add one discoverability sentence inside `## Commands`, per D7.
**Spec refs:** §4 (CLAUDE.md sentence), §7 (rollout)

**Files:**
- Modify: `CLAUDE.md` (insert sentence at top of `## Commands`)

**Steps:**

- [ ] Step 1: Find the `## Commands` heading in `CLAUDE.md` (around line 50). Insert **immediately after** the heading (before `### Backend (run from \`backend/\`)`):

  ```
  > **Front door:** `make help` lists every dev-loop and verification target. The Makefile delegates to `./test.sh` for the packaging/verification ladder (see `docs/specs/2026-04-25-makefile-dev-loop-spec.md`).
  ```

  Blockquote form keeps it visually distinct from the subsection headings without introducing a new `###`.

- [ ] Step 2: Verify the edit applied cleanly.
  Run: `grep -n "Front door" CLAUDE.md`
  Expected: one match near line 51-52.

- [ ] Step 3: Confirm contract test still passes.
  Run: `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v`
  Expected: 1 passed. (Sanity — CLAUDE.md is unrelated but re-running keeps the task self-sufficient.)

- [ ] Step 4: Commit.
  ```bash
  git add CLAUDE.md
  git commit -m "docs: point CLAUDE.md at make help as the dev-loop front door"
  ```

**Inline verification:**
- `grep -c "make help" CLAUDE.md` — ≥ 1 (behavioral — the front-door pointer is discoverable by grep).
- `grep -n "Front door" CLAUDE.md` — line number is inside the first 80 lines (behavioral — proves it was inserted at the top of Commands, not buried elsewhere).

---

### TN: Final Verification

**Goal:** Run every verification gate end-to-end before declaring the plan complete. Mirror spec §6.3.

- [ ] **Lint & format:** `cd backend && uv run ruff check . && uv run ruff format --check .` — 0 errors.
- [ ] **Makefile discoverability:** `make help` — prints an aligned, color-coded list of every canonical target (spec §6.1 smoke 1).
- [ ] **FE build — fire:** `make clean-fe && make build-fe` — runs `npm run build`, writes `backend/app/static/index.html`. Verify: `test -f backend/app/static/index.html && echo OK` → `OK` (spec §6.1 smoke 2).
- [ ] **FE build — skip:** `make build-fe` immediately again — `Nothing to be done for 'build-fe'.` Exit 0 (spec §6.1 smoke 3).
- [ ] **FE build — trigger on src edit:** `touch frontend/src/main.ts && make build-fe` — `npm run build` runs again (spec §6.1 smoke 4).
- [ ] **FE build — force:** `make force-build-fe` — `npm run build` runs unconditionally (spec §6.1 smoke 5).
- [ ] **Stop — idle:** `make stop` — prints `nothing listening on :8000`, exit 0 (spec §6.1 smoke 6).
- [ ] **Dev — full loop on a free port:** `PORT=8765 make dev &` in one terminal; in another: `curl -sf http://localhost:8765/api/v1/health | python3 -m json.tool` — JSON body includes `status`. (Spec §6.1 smoke 7.)
- [ ] **Stop — kill the dev server:** `make stop PORT=8765` — output reports killed PID; `lsof -ti:8765` returns empty (spec §6.1 smoke 8).
- [ ] **Delegation parity — test:** `make test` — same output as `./test.sh fast` directly. Exit 0 (spec §6.1 smoke 9).
- [ ] **Reset (optional — user decision):** user runs `make reset CONFIRM=1` manually only if they want to exercise the destructive path. Verify: backup `~/Library/Application Support/bookcompanion.YYYYMMDD_HHMMSS.bak` exists, and fresh data dir is re-initialized (spec §6.1 smoke 10). **The plan does NOT auto-run this step.**
- [ ] **Automated contract test:** `cd backend && uv run pytest -m slow tests/build/test_makefile_contract.py -v` — 1 passed.
- [ ] **Full suite regression:** `cd backend && uv run pytest` — expect no regressions from the Makefile change (backend tests should be unaffected; this confirms it).
- [ ] **test.sh regression:** `./test.sh all` — runs the full verification ladder as before. Exit 0. (Behavioral proof that `test.sh` is untouched and the delegation contract still holds.)
- [ ] **Frontend smoke test (Playwright MCP / manual):** per existing CLAUDE.md § Interactive verification — bring up `PORT=8765 make dev`, `browser_navigate http://localhost:8765`, verify the book list renders, check `browser_console_messages(level: 'error')` is empty, then `make stop PORT=8765`.
- [ ] **VERIFY_DOCKER pass-through (spec §3.3):** `VERIFY_DOCKER=1 make -n verify-ladder 2>&1 | grep -E "VERIFY_DOCKER|test.sh ladder"` — either the dry-run output includes `VERIFY_DOCKER=1` in the rendered command (if the recipe explicitly exports it) or, equivalently, `VERIFY_DOCKER=1 make verify-ladder` runs `./test.sh ladder` with the env var visible inside (GNU Make inherits and re-exports ambient env vars to recipe shells by default). Behavioral sanity: `VERIFY_DOCKER=1 bash -c 'env | grep VERIFY_DOCKER'` inside an ad-hoc `make` recipe invocation confirms propagation.
- [ ] **Windows-guard smoke (spec E8):** `OS=Windows_NT make test 2>&1 | tail -3` — contains the bail message and exits non-zero; `OS=Windows_NT make help 2>&1 | tail -3` — contains "Windows: run commands directly" and exits 0.

**Cleanup:**
- [ ] Kill any dev server still running: `make stop; make stop PORT=8765`.
- [ ] Remove `backend/app/static/` if `make clean-fe` left it empty and you want a proper rebuild before handoff: `make build-fe`.
- [ ] Confirm `git status` is clean (only committed changes are the Makefile, the new pytest, and the CLAUDE.md line).
- [ ] Update `docs/changelog.md` with a one-line entry (per project convention — see post-merge `/changelog` flow in CLAUDE.md § Session logging).

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 (self) | (1) Spec §5 E8 (Windows bail-out) not implemented in any task. (2) T6 bundled 4 distinct concerns (file target, `build-fe`, `force-build-fe`, `clean-fe`) — violates the ≥3-concern split rule from /plan learnings. (3) `VERIFY_DOCKER` env pass-through documented in spec §3.3 but not verified in any task. (4) Execution-order diagram understated T7's deps: shows only T6 → T7, but `dev` actually depends on stop (T3), migrate (T4), AND static/index.html (T6a). User dispositioned all four as "Fix as proposed." | Added **D10** decision entry for Windows guard. Folded `ifeq ($(OS),Windows_NT)` block into T2 Step 1 (new section 2) with `$(warning ...)` + `WINDOWS_BAIL := $(error ...)` pattern; help recipe branches on OS; every other recipe gets a `@:$(WINDOWS_BAIL)` preamble. Added T2 Step 7 smoke test for Windows guard. **Split T6 → T6a** (file target + `build-fe` alias, smoke tests 2-4 + E7) **and T6b** (`force-build-fe` + `clean-fe`, smoke test 5). Updated T7's spec reference and the Risk-table T6 reference to T6a. Added TN verification lines for VERIFY_DOCKER pass-through and Windows guard. Redrew execution-order diagram to show T3, T4, T6a all converging into T7; T6b depends on T6a; T5 precedes T6a. |
| 2 (self) | Semantic bug in the Windows-guard mechanism introduced by Loop 1: `WINDOWS_BAIL := $(error ...)` uses immediate (`:=`) expansion, which fires `$(error)` at Makefile parse time on Windows and would crash `make help` — violating spec E8's requirement that `help` still prints a bail message on Windows. Found via design-level self-critique (pressure-testing the mechanics). User dispositioned as "Fix as proposed." | Changed the assignment from `:=` to `=` in T2 Step 1 section 2. Added a **Critical** callout explaining the lazy-expansion requirement. Updated D10's Rationale to spell out why `:=` would break `help` on Windows (added rejection option `(e)` to the options-considered). Strengthened T2 Step 7 into two sub-runs (a) `OS=Windows_NT make help` must exit 0 with bail message only — NO `$(error)` text — and (b) `OS=Windows_NT make test` must exit 2 with the `$(error)` text. Sub-run (a) is the behavioral gate that catches the `:=` regression if it ever reappears. |
| 3 (final) | Coherence gap: T3, T4, T5, T7, T8 recipe definitions didn't explicitly carry the `@:$(WINDOWS_BAIL)` preamble line (only T2's stubs and T6a/T6b did). When T3-T8 replace the stub with a real recipe, the preamble could be silently dropped, losing the Windows guard on those targets. User dispositioned as "Fix as proposed." | Added an explicit first-line-of-recipe instruction to **T3 Step 1** (new sub-point 0), **T4 Step 1** (rewrote as two-line recipe), **T5 Step 1** (added the preamble line to the code block + prose note), **T7 Step 1** (added the preamble line inside the `dev` recipe block + callout in bullets), **T8 Step 1** (added the preamble line above `@set -eu` + note in the bullets). Each note cross-references D10. |
