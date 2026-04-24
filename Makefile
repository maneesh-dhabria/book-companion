# Makefile — front door for the Book Companion dev loop.
#
# See docs/specs/2026-04-25-makefile-dev-loop-spec.md for the contract.
# The Makefile handles dev-loop commands natively (stop/migrate/build-fe/dev/reset)
# and delegates the verification ladder (fast/ladder/slow/all/serve) to ./test.sh.
# Run `make help` for the full list.

# --- Windows guard (spec E8) ------------------------------------------------
# Lazy `=` assignment — $(error) must fire only when referenced inside a recipe,
# never at parse time. Using `:=` would crash `make help` on Windows, which spec
# E8 requires to stay usable.
ifeq ($(OS),Windows_NT)
$(warning Windows detected — this Makefile targets macOS / Linux only.)
WINDOWS_BAIL = $(error Windows is not supported; run commands directly — see ./test.sh)
endif

# --- Variables --------------------------------------------------------------
PORT ?= 8000
STATIC_INDEX := backend/app/static/index.html
NODE_LOCK := frontend/node_modules/.package-lock.json
BACKEND := backend
FRONTEND := frontend

.DEFAULT_GOAL := help

# --- help -------------------------------------------------------------------
help:  ## Show this help
ifeq ($(OS),Windows_NT)
	@echo "Windows: run commands directly; see ./test.sh"
else
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[1;36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif
.PHONY: help

# --- Verification delegations (./test.sh) ----------------------------------
test:  ## Fast lint + full unit/integration pytest (delegates to ./test.sh fast)
	@:$(WINDOWS_BAIL)
	BC_PORT=$(PORT) ./test.sh fast
.PHONY: test

lint:  ## Backend lint only (uv run ruff check .)
	@:$(WINDOWS_BAIL)
	cd $(BACKEND) && uv run ruff check .
.PHONY: lint

verify: verify-ladder  ## Alias for verify-ladder (cheap desk-side verification)
.PHONY: verify

verify-ladder:  ## Packaging verification ladder (delegates to ./test.sh ladder)
	@:$(WINDOWS_BAIL)
	./test.sh ladder
.PHONY: verify-ladder

verify-slow:  ## End-to-end pytest (delegates to ./test.sh slow)
	@:$(WINDOWS_BAIL)
	./test.sh slow
.PHONY: verify-slow

verify-all:  ## fast + ladder + slow (delegates to ./test.sh all)
	@:$(WINDOWS_BAIL)
	./test.sh all
.PHONY: verify-all

serve-fresh:  ## Build wheel, install into /tmp/bc, run it (delegates to ./test.sh serve)
	@:$(WINDOWS_BAIL)
	BC_PORT=$(PORT) ./test.sh serve
.PHONY: serve-fresh

# --- Dev-loop stubs (filled in by T3–T8) -----------------------------------
stop:  ## Kill any bookcompanion serve on $(PORT) + stale Playwright MCP chrome
	@:$(WINDOWS_BAIL)
	@pids="$$(lsof -ti:$(PORT) 2>/dev/null || true)"; \
	if [ -n "$$pids" ]; then \
	  kill $$pids 2>/dev/null || true; \
	  sleep 1; \
	  pids="$$(lsof -ti:$(PORT) 2>/dev/null || true)"; \
	  [ -n "$$pids" ] && kill -9 $$pids 2>/dev/null || true; \
	  echo "  killed :$(PORT)"; \
	else \
	  echo "  nothing listening on :$(PORT)"; \
	fi
	@pw="$$(pgrep -f 'ms-playwright/mcp-chrome' 2>/dev/null || true)"; \
	if [ -n "$$pw" ]; then \
	  kill $$pw 2>/dev/null || true; \
	  echo "  killed stale Playwright MCP chrome pids: $$pw"; \
	fi
.PHONY: stop

migrate:  ## Apply Alembic migrations against the real data dir
	@:$(WINDOWS_BAIL)
	cd $(BACKEND) && uv run alembic -c app/migrations/alembic.ini upgrade head
.PHONY: migrate

build-fe: $(STATIC_INDEX)  ## Rebuild frontend into backend/app/static if src has changed
.PHONY: build-fe

force-build-fe:  ## Force rebuild the frontend unconditionally
	@:$(WINDOWS_BAIL)
	@echo "not yet implemented — see T6b in docs/plans/2026-04-25-makefile-dev-loop-implementation-plan.md"
.PHONY: force-build-fe

clean-fe:  ## rm -rf backend/app/static (full wipe for next build)
	@:$(WINDOWS_BAIL)
	@echo "not yet implemented — see T6b in docs/plans/2026-04-25-makefile-dev-loop-implementation-plan.md"
.PHONY: clean-fe

dev:  ## Refresh: stop, migrate, build FE if needed, serve on $(PORT)
	@:$(WINDOWS_BAIL)
	@echo "not yet implemented — see T7 in docs/plans/2026-04-25-makefile-dev-loop-implementation-plan.md"
.PHONY: dev

reset:  ## ⚠ destructive: backup data dir + re-init (requires CONFIRM=1 if non-TTY)
	@:$(WINDOWS_BAIL)
	@echo "not yet implemented — see T8 in docs/plans/2026-04-25-makefile-dev-loop-implementation-plan.md"
.PHONY: reset

# --- File targets ----------------------------------------------------------

$(NODE_LOCK): $(FRONTEND)/package-lock.json
	@:$(WINDOWS_BAIL)
	cd $(FRONTEND) && npm ci
	@touch $@

# $(shell find ...) is parse-time; keep the prerequisite list explicit.
FRONTEND_SRC := $(shell find $(FRONTEND)/src -type f 2>/dev/null)

$(STATIC_INDEX): $(FRONTEND_SRC) $(FRONTEND)/index.html $(FRONTEND)/vite.config.ts $(FRONTEND)/package.json | $(NODE_LOCK)
	@:$(WINDOWS_BAIL)
	cd $(FRONTEND) && npm run build
	@mkdir -p $(@D)
	cp -R $(FRONTEND)/dist/. $(dir $@)
	@echo "  deployed $$(ls $(dir $@)assets 2>/dev/null | grep '^index-' | head -1)"
