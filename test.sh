#!/usr/bin/env bash
# Convenience wrapper for local verification + dev workflow. Run from repo root.
#
#   ./test.sh [command]
#
# Verification (existing):
#   fast    — lint + full unit/integration test suite (~30s)
#   ladder  — packaging verification: build + install in fresh venvs + smoke (~90s)
#   slow    — end-to-end pytest regression (~30s)
#   all     — fast + ladder + slow  (everything short of Docker)
#
# Dev loop (v1.5 additions):
#   dev       — one-shot refresh: stop → migrate → build FE if needed → serve
#   stop      — kill any `bookcompanion serve` + stale Playwright MCP Chrome
#   migrate   — alembic upgrade head against the real data dir
#   build-fe  — npm run build, copy frontend/dist → backend/app/static
#                 (skips when static/index.html is newer than frontend/src/**)
#   reset     — ⚠️  destructive: back up the data dir + recreate from scratch
#   serve     — build, install into /tmp/bc, run wheel-installed `bookcompanion serve`
#
# Env:
#   BC_PORT=8000        — port for `dev` / `serve` / `stop`
#   VERIFY_DOCKER=1     — `ladder` / `all` also run the Docker clean-room layer
#   BC_SKIP_MIGRATE=1   — `dev` skips alembic (when you know it's current)
#   BC_FORCE_FE=1       — `dev` / `build-fe` rebuild even if static is fresh

set -eo pipefail

cmd="${1:-all}"
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$REPO_ROOT/backend"
FRONTEND="$REPO_ROOT/frontend"
STATIC="$BACKEND/app/static"
PORT="${BC_PORT:-8000}"

log() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m!!  %s\033[0m\n" "$*"; }

fast() {
  log "Lint"
  ( cd "$BACKEND" && uv run ruff check . | tail -3 )
  log "Full test suite"
  ( cd "$BACKEND" && uv run pytest -q )
}

ladder() {
  log "Packaging verification ladder"
  ( cd "$BACKEND" && bash scripts/verify_packaging.sh )
}

slow() {
  log "Slow end-to-end pytest"
  ( cd "$BACKEND" && uv run pytest -m slow --override-ini='addopts=' tests/build/test_end_to_end_packaging.py -v )
}

stop() {
  log "Stopping any bookcompanion serve on :$PORT"
  local pids
  pids="$(lsof -ti:"$PORT" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    kill $pids 2>/dev/null || true
    sleep 1
    # Force kill anything still listening
    pids="$(lsof -ti:"$PORT" 2>/dev/null || true)"
    [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
    echo "  killed :$PORT"
  else
    echo "  nothing listening on :$PORT"
  fi

  # Stray Playwright MCP Chrome from prior interactive runs
  local pw
  pw="$(pgrep -f 'ms-playwright/mcp-chrome' 2>/dev/null || true)"
  if [[ -n "$pw" ]]; then
    kill $pw 2>/dev/null || true
    echo "  killed stale Playwright MCP chrome pids: $pw"
  fi
}

migrate() {
  log "Applying Alembic migrations (target: real data dir)"
  ( cd "$BACKEND" && uv run alembic -c app/migrations/alembic.ini upgrade head )
}

# Rebuild the frontend into backend/app/static when any src file is newer than
# the deployed static/index.html. Always rebuilds when BC_FORCE_FE=1.
build_fe() {
  local marker="$STATIC/index.html"
  if [[ "${BC_FORCE_FE:-0}" != "1" && -f "$marker" ]]; then
    local newer
    newer="$(find "$FRONTEND/src" "$FRONTEND/index.html" "$FRONTEND/vite.config.ts" \
               -type f -newer "$marker" -print -quit 2>/dev/null || true)"
    if [[ -z "$newer" ]]; then
      log "Frontend static is up to date (skipping build — set BC_FORCE_FE=1 to override)"
      return 0
    fi
  fi
  log "Building frontend → backend/app/static"
  ( cd "$FRONTEND" && npm run build >/dev/null )
  rm -rf "$STATIC"
  cp -R "$FRONTEND/dist" "$STATIC"
  echo "  deployed $(ls "$STATIC/assets" | grep '^index-' | head -1)"
}

dev() {
  stop
  if [[ "${BC_SKIP_MIGRATE:-0}" != "1" ]]; then migrate; fi
  build_fe
  log "Starting bookcompanion serve on :$PORT"
  ( cd "$BACKEND" && exec uv run bookcompanion serve --port "$PORT" )
}

reset() {
  local data_dir="$HOME/Library/Application Support/bookcompanion"
  [[ -d "/Users/$(whoami)/.local/share/bookcompanion" ]] && data_dir="/Users/$(whoami)/.local/share/bookcompanion"
  warn "About to reset data dir: $data_dir"
  warn "A timestamped backup will be made before deletion."
  read -r -p "Continue? [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]] || { echo "aborted"; exit 1; }
  if [[ -d "$data_dir" ]]; then
    local backup="${data_dir%/}.$(date +%Y%m%d_%H%M%S).bak"
    mv "$data_dir" "$backup"
    echo "  backed up to $backup"
  fi
  log "Re-initializing"
  ( cd "$BACKEND" && uv run bookcompanion init )
}

serve() {
  log "Building wheel"
  ( cd "$BACKEND" && rm -rf dist/ && uv build --wheel )

  log "Installing into /tmp/bc"
  rm -rf /tmp/bc
  python3 -m venv /tmp/bc
  /tmp/bc/bin/pip install --quiet --no-cache-dir "$BACKEND"/dist/*.whl

  log "Initializing"
  PATH="/tmp/bc/bin:$PATH" /tmp/bc/bin/bookcompanion init

  log "Starting server — open http://localhost:$PORT (Ctrl-C to stop)"
  PATH="/tmp/bc/bin:$PATH" /tmp/bc/bin/bookcompanion serve --port "$PORT"
}

case "$cmd" in
  fast)     fast ;;
  ladder)   ladder ;;
  slow)     slow ;;
  serve)    serve ;;
  dev)      dev ;;
  stop)     stop ;;
  migrate)  migrate ;;
  build-fe) build_fe ;;
  reset)    reset ;;
  all)      fast && ladder && slow ;;
  -h|--help|help)
    sed -n '2,26p' "$0" | sed 's/^# //;s/^#//'
    ;;
  *)        echo "usage: $0 [fast|ladder|slow|all|dev|stop|migrate|build-fe|reset|serve|help]" >&2; exit 2 ;;
esac
