#!/usr/bin/env bash
# Layered local verification that the packaged artifacts actually install and run.
# Catches bugs that a plain `pytest` run misses. Intended for pre-release.
#
# Layers:
#   1. twine check            — PyPI metadata sanity
#   2. check-wheel-contents   — wheel layout lint
#   3. fresh-venv install     — wheel AND sdist, with CLI smoke
#   4. uv tool install        — isolated CLI (pipx-style) install
#   5. Docker clean-room      — opt-in via VERIFY_DOCKER=1
#
# Usage:
#   cd backend && bash scripts/verify_packaging.sh
#   VERIFY_DOCKER=1 bash scripts/verify_packaging.sh

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$BACKEND_DIR/dist"

# Unique ports per layer to avoid collisions with running dev servers.
PORT_WHEEL=8871
PORT_SDIST=8872
PORT_TOOL=8873
PORT_DOCKER=8874

VENVS=()
PIDS=()

# Kill any stale bookcompanion serve processes from an earlier aborted run.
# These hold ports 88XX and cause confusing false-pass (port is up, but the old
# wheel is answering). The trap below cleans up the current run's processes,
# but can't reach prior runs' PIDs.
pkill -9 -f "bookcompanion serve --port 887" 2>/dev/null || true

cleanup() {
  set +eu
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null
  done
  for venv in "${VENVS[@]:-}"; do
    [[ -n "$venv" ]] && rm -rf "$venv"
  done
  uv tool uninstall bookcompanion 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }
fail() { printf "\n\033[1;31mFAIL: %s\033[0m\n" "$*" >&2; exit 1; }

wait_for_port() {
  local port="$1" i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if curl -sf "http://localhost:$port/api/v1/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

cd "$BACKEND_DIR"

# Clean + build
log "Building artifacts"
rm -rf "$DIST_DIR" app/static/
uv build >/dev/null
ls "$DIST_DIR"
compgen -G "$DIST_DIR/*.whl" >/dev/null || fail "no wheel produced"
compgen -G "$DIST_DIR/*.tar.gz" >/dev/null || fail "no sdist produced"

# -------------------------- Layer 1: twine check --------------------------
log "Layer 1: twine check"
uv run --with twine twine check "$DIST_DIR"/* || fail "twine check failed"

# -------------------- Layer 2: check-wheel-contents ----------------------
log "Layer 2: check-wheel-contents"
# W005 ("common toplevel name 'app'") is intentional for this project — we own
# `app` and don't plan to publish on PyPI with a conflicting name. Ignoring
# the advisory-only check keeps the real errors visible.
uv run --with check-wheel-contents check-wheel-contents --ignore W005 "$DIST_DIR"/*.whl \
  || fail "check-wheel-contents failed"

# -------------------- Layer 3a: fresh-venv wheel install -----------------
log "Layer 3a: fresh venv install from WHEEL"
VENV_WHEEL=$(mktemp -d)
VENVS+=("$VENV_WHEEL")
python3 -m venv "$VENV_WHEEL"
"$VENV_WHEEL/bin/pip" install --quiet --no-cache-dir "$DIST_DIR"/*.whl
"$VENV_WHEEL/bin/bookcompanion" --help >/dev/null || fail "wheel: --help failed"

PATH="$VENV_WHEEL/bin:$PATH" "$VENV_WHEEL/bin/bookcompanion" init >/dev/null
( cd /tmp && PATH="$VENV_WHEEL/bin:$PATH" "$VENV_WHEEL/bin/bookcompanion" serve --port "$PORT_WHEEL" >/tmp/bc-wheel-serve.log 2>&1 ) &
PIDS+=($!)
wait_for_port "$PORT_WHEEL" || fail "wheel: server did not start on $PORT_WHEEL"
status=$(curl -sS -o /tmp/bc-wheel-root.html -w "%{http_code}" "http://localhost:$PORT_WHEEL/")
[[ "$status" == "200" ]] || fail "wheel: / returned HTTP $status. serve log: $(tail -15 /tmp/bc-wheel-serve.log)"
grep -q '<title>' /tmp/bc-wheel-root.html || fail "wheel: / body missing <title> (first 200 bytes: $(head -c 200 /tmp/bc-wheel-root.html))"
kill "${PIDS[${#PIDS[@]}-1]}" 2>/dev/null; sleep 1

# -------------------- Layer 3b: fresh-venv sdist install -----------------
log "Layer 3b: fresh venv install from SDIST (no Node required)"
VENV_SDIST=$(mktemp -d)
VENVS+=("$VENV_SDIST")
python3 -m venv "$VENV_SDIST"
"$VENV_SDIST/bin/pip" install --quiet --no-cache-dir "$DIST_DIR"/*.tar.gz
"$VENV_SDIST/bin/bookcompanion" --help >/dev/null || fail "sdist: --help failed"

PATH="$VENV_SDIST/bin:$PATH" "$VENV_SDIST/bin/bookcompanion" init >/dev/null
( cd /tmp && PATH="$VENV_SDIST/bin:$PATH" "$VENV_SDIST/bin/bookcompanion" serve --port "$PORT_SDIST" >/dev/null 2>&1 ) &
PIDS+=($!)
wait_for_port "$PORT_SDIST" || fail "sdist: server did not start on $PORT_SDIST"
status=$(curl -sS -o /tmp/bc-sdist-root.html -w "%{http_code}" "http://localhost:$PORT_SDIST/")
[[ "$status" == "200" ]] || fail "sdist: / returned HTTP $status"
grep -q '<title>' /tmp/bc-sdist-root.html || fail "sdist: / body missing <title>"
kill "${PIDS[${#PIDS[@]}-1]}" 2>/dev/null; sleep 1

# -------------------- Layer 4: uv tool install ---------------------------
log "Layer 4: uv tool install (isolated CLI)"
uv tool install --force --from "$DIST_DIR"/*.whl bookcompanion >/dev/null
bookcompanion --help >/dev/null || fail "uv tool: --help failed"
uv tool uninstall bookcompanion >/dev/null

# -------------------- Layer 5: Docker (opt-in) ---------------------------
if [[ "${VERIFY_DOCKER:-0}" == "1" ]]; then
  log "Layer 5: Docker clean-room install"
  docker run --rm -v "$DIST_DIR:/dist:ro" python:3.12-slim bash -c '
    set -e
    pip install --quiet --no-cache-dir /dist/*.whl
    bookcompanion --help >/dev/null
  ' || fail "Docker wheel install failed"

  docker run --rm -v "$DIST_DIR:/dist:ro" python:3.12-slim bash -c '
    set -e
    pip install --quiet --no-cache-dir /dist/*.tar.gz
    bookcompanion --help >/dev/null
  ' || fail "Docker sdist install failed"
fi

printf "\n\033[1;32mAll layers passed.\033[0m\n"
