#!/usr/bin/env bash
# Convenience wrapper for local verification of the packaging pipeline.
# Run from repo root:  ./test.sh [fast|ladder|slow|serve|all]
#
#   fast    — lint + full unit/integration test suite (~30s)
#   ladder  — packaging verification: build + install in fresh venvs + smoke (~90s)
#   slow    — end-to-end pytest regression (same coverage as ladder layer 3b, ~30s)
#   serve   — build, install into /tmp/bc, run `bookcompanion serve` on :8000
#   all     — fast + ladder + slow  (everything short of Docker)
#
# Env:
#   VERIFY_DOCKER=1   — `ladder` and `all` also run the Docker clean-room layer

set -eo pipefail

cmd="${1:-all}"
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$REPO_ROOT/backend"

log() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }

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

serve() {
  log "Building wheel"
  ( cd "$BACKEND" && rm -rf dist/ && uv build --wheel )

  log "Installing into /tmp/bc"
  rm -rf /tmp/bc
  python3 -m venv /tmp/bc
  /tmp/bc/bin/pip install --quiet --no-cache-dir "$BACKEND"/dist/*.whl

  log "Initializing"
  PATH="/tmp/bc/bin:$PATH" /tmp/bc/bin/bookcompanion init

  log "Starting server — open http://localhost:8000 (Ctrl-C to stop)"
  PATH="/tmp/bc/bin:$PATH" /tmp/bc/bin/bookcompanion serve --port 8000
}

case "$cmd" in
  fast)   fast ;;
  ladder) ladder ;;
  slow)   slow ;;
  serve)  serve ;;
  all)    fast && ladder && slow ;;
  *)      echo "usage: $0 [fast|ladder|slow|serve|all]" >&2; exit 2 ;;
esac
