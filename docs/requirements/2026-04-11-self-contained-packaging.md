# Zero-Dependency Packaging — Requirements

**Date:** 2026-04-11
**Status:** Draft
**Tier:** 2 — Enhancement

## Problem

Book Companion currently requires **three external services** to function: PostgreSQL + pgvector (Docker), Ollama (separate process), and Claude CLI (host binary). For a personal tool aimed at technical open-source users, this dependency stack creates significant first-time friction:

- **PostgreSQL in Docker** — users must have Docker installed and running, manage ports, handle volume persistence, and run manual migrations
- **Ollama** — users must install it separately, pull the `nomic-embed-text` model, and keep the server running for semantic search to work
- **Claude/Codex CLI** — the only truly necessary external dependency, but currently hardcoded to Claude CLI only

The net effect: what should be a `pip install && run` experience requires orchestrating three separate services before the tool does anything useful.

### Who & Why Now

**Target audience:** Technical users and open-source adopters who want a self-hosted book summarization tool. They expect a clean install experience with minimal prerequisites.

**Why now:** The web interface is complete (Phases 1-3 shipped). The tool is feature-complete enough to distribute, but the packaging story requires Docker expertise and multiple running services, which is a barrier to adoption. The tool has not been published yet, so this is a clean break with no migration burden.

## Goals & Non-Goals

### Goals

- **Single install, zero services** — `pip install bookcompanion` (or `uv tool install`) is the only step. No Docker, no external databases, no background processes. Data stored in a local file.
- **In-process semantic search** — embedding generation runs via a bundled Python library (no Ollama), vector storage via an embedded database (no pgvector/PostgreSQL)
- **Multi-provider LLM support** — auto-detect available coding agent CLIs (Claude, Codex) on `$PATH`. If both are present, prompt the user to choose a default. Configurable from the web UI settings page (command path + config directory).
- **Transparent degradation** — when no LLM CLI is detected, the UI/CLI clearly communicates that summarization is unavailable and guides the user to install one. All other features (library, search, reading, annotations, export) work without an LLM.
- **LAN accessibility** — the web UI is accessible from other devices on the same network without manual CORS configuration
- **Simple, reliable backups** — periodic backup of the SQLite database to a configurable directory. If that directory is a cloud sync folder (Google Drive, Dropbox, iCloud), users get cloud backup for free with no API integration.

### Non-Goals

- NOT replacing CLI-based LLM providers with direct API calls because CLI tools handle authentication, context, and model selection — reimplementing that adds complexity with no user benefit
- NOT adding GPU support for embeddings because the target model (all-MiniLM-L6-v2, ~23MB) runs efficiently on CPU and GPU support adds package complexity
- NOT keeping PostgreSQL or Docker as a supported deployment option because maintaining two database backends doubles the testing and migration surface, and the tool has no published users requiring backward compatibility
- NOT building a desktop GUI (Electron/Tauri) because the web UI served by the Python process is sufficient and avoids a separate packaging ecosystem
- NOT integrating directly with cloud backup APIs (Google Drive, Dropbox) because a configurable backup directory achieves cloud backup when pointed at a sync folder, with no OAuth complexity

## Solution Direction

Three connected changes that eliminate all external service dependencies:

### 1. Replace PostgreSQL with SQLite

Swap the PostgreSQL + asyncpg stack for **SQLite + aiosqlite**. All data lives in a single file (e.g., `~/.local/share/bookcompanion/library.db`).

Key equivalences:
- **pgvector → sqlite-vec** — SQLite extension for vector similarity search with cosine distance
- **tsvector + GIN → FTS5** — SQLite's built-in full-text search with BM25 ranking
- **asyncpg → aiosqlite** — async SQLite driver, compatible with SQLAlchemy 2.0 async
- **pg_dump backups → file copy** — back up to a user-configured directory on a schedule. If that directory is a cloud sync folder, users get cloud backup automatically.

SQLAlchemy's abstraction layer means most repository code is portable. The changes concentrate in: vector column types, full-text search queries, and Alembic/migration setup.

Remove all Docker-related files (`Dockerfile`, `docker-compose.yml`, `.env.example`) and Docker-specific code paths from the codebase.

### 2. Replace Ollama with fastembed

Swap the Ollama HTTP dependency for **fastembed**, an ONNX-based Python library that runs embedding models in-process. Default model: **all-MiniLM-L6-v2** (384-dim, ~23MB, ~2ms/query on CPU).

- No external server process needed
- Model weights cached in the user's cache directory on first run (~23MB one-time download)
- The `EmbeddingService` interface stays the same — only the implementation of `embed_text()` changes
- Embedding dimension changes from 768 → 384

### 3. Streamline packaging and first-run experience

- **Install:** `pip install bookcompanion` or `uv tool install bookcompanion`
- **First run:** `bookcompanion init` creates the data directory, initializes the SQLite database, downloads the embedding model
- **Web UI:** `bookcompanion serve` starts the FastAPI server on `localhost:8000`
- **CORS:** Auto-detect network interfaces and allow origins from the same subnet for LAN access
- **Data location:** `~/.local/share/bookcompanion/` (XDG-compliant) containing `library.db`, config, and backups
- **Backups:** Configurable backup directory with periodic automated file copies of `library.db`. Default: `~/.local/share/bookcompanion/backups/`

## User Journeys

### Primary: First-time install and use

1. User runs `pip install bookcompanion` (has Claude or Codex CLI already installed)
2. Runs `bookcompanion init` — creates `~/.local/share/bookcompanion/`, initializes SQLite database, downloads embedding model (~23MB)
3. Runs `bookcompanion serve` — starts web UI at `localhost:8000`
4. Opens browser, sees empty library
5. Uploads an EPUB or PDF — book is parsed, sections extracted, embeddings generated in-process
6. Searches their library — hybrid search (BM25 via FTS5 + semantic via sqlite-vec) works immediately
7. Clicks "Summarize" — Claude/Codex CLI generates summaries

### LLM provider detection

1. On startup, the app checks for `claude` and `codex` on `$PATH`
2. **One found:** auto-selects it. Logs: "Detected Claude CLI, using as LLM provider."
3. **Both found:** settings page prompts user to choose a default
4. **Neither found:** summarization disabled. Banner: "No LLM provider detected. Install Claude CLI or Codex CLI to enable summarization." Library, search, reading, annotations, and export all work.
5. User can override via settings page (command path + config directory) or `config.yaml`

### Backup configuration

1. User opens settings page in the web UI
2. Sets backup directory to their Google Drive sync folder (e.g., `~/Google Drive/bookcompanion-backups/`)
3. Sets backup frequency (e.g., daily)
4. App copies `library.db` to the configured directory on schedule
5. Google Drive automatically syncs the backup to the cloud — no API integration needed
6. To restore: user copies the backup file back to the data directory

### LAN access: Reading on a tablet

1. Book Companion running on desktop via `bookcompanion serve`
2. User opens `http://<desktop-ip>:8000` on tablet
3. CORS allows the request (same subnet auto-detected)
4. Full functionality available

### Error: No LLM CLI installed

1. User uploads a book — parsing, section extraction, and embedding work normally
2. User clicks "Summarize"
3. UI shows: "Summarization requires Claude CLI or Codex CLI. [Learn more]"
4. All other features continue to work

### Edge case: Running serve without init

1. User installs the package, skips `init`, runs `bookcompanion serve`
2. App detects no database file exists
3. Auto-runs initialization (create data dir, init DB, download model) with a log message: "First run detected, initializing..."
4. Server starts normally

### Error: MOBI upload without Calibre

1. User uploads a `.mobi` file
2. Backend checks for `ebook-convert` binary — not found
3. Clear error: "MOBI format requires Calibre's ebook-convert. Install Calibre or convert to EPUB first."

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Replace PostgreSQL with SQLite + sqlite-vec + FTS5 | (a) SQLite — embedded, zero config, single file, (b) Keep PostgreSQL in Docker, (c) DuckDB — embedded but OLAP-focused | SQLite eliminates the Docker dependency entirely. sqlite-vec provides vector search, FTS5 provides BM25. Single-file storage is simpler to back up and distribute. DuckDB is optimized for analytics, not the OLTP workload pattern here. |
| D2 | Use fastembed with all-MiniLM-L6-v2 as default model | (a) fastembed — in-process ONNX, no server, (b) sentence-transformers — needs PyTorch (~2GB), (c) Ollama sidecar | fastembed is purpose-built for this: lightweight (~23MB model), CPU-efficient, no external process. sentence-transformers pulls in PyTorch. |
| D3 | Change embedding dimension from 768 → 384 | (a) Keep 768 with nomic-embed-text, (b) Switch to 384 with MiniLM | MiniLM is 5x smaller, 5x faster, and 384-dim is sufficient for personal library search. |
| D4 | Auto-detect LLM CLI providers (Claude, Codex) with settings override | (a) Hardcode Claude CLI only, (b) Auto-detect + configurable, (c) Require manual config | Auto-detect is frictionless. Supporting both future-proofs against ecosystem changes. Settings page gives power users control. |
| D5 | Auto-detect LAN for CORS instead of wildcard | (a) Auto-detect subnet, (b) Allow all origins, (c) Configurable env var | Auto-detect balances security and convenience for a personal tool. |
| D6 | XDG-compliant data directory (`~/.local/share/bookcompanion/`) | (a) XDG path, (b) `~/.bookcompanion/`, (c) Configurable only | XDG compliance is the standard on Linux. macOS equivalent is `~/Library/Application Support/`. Configurable via env var for non-standard setups. |
| D7 | SQLite with WAL mode for concurrency | (a) WAL mode — concurrent reads, serialized writes, (b) Default journal mode — exclusive lock on write | WAL mode allows the web UI to serve reads while background tasks (re-indexing, summarization) write. Serialized writes are acceptable for a single-user personal tool. |
| D8 | Clean break — remove all Docker and PostgreSQL code | (a) Clean break, (b) Keep Docker as optional, (c) Maintain both backends | No published users means no migration burden. Maintaining two backends doubles testing surface. Clean break keeps the codebase simple. |
| D9 | Backup via configurable directory + periodic file copy | (a) Configurable directory, (b) Google Drive API integration, (c) Both | A configurable directory achieves cloud backup when pointed at a sync folder (Google Drive, Dropbox, iCloud). No OAuth, no API keys, works with any sync service. |

## Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Should the embedding model be user-configurable via config, or hardcoded to MiniLM? Configurability adds complexity (dimension changes trigger re-index). | Maneesh | Before spec |
| 2 | What's the Alembic story for SQLite? Alembic supports SQLite but with limitations (no ALTER COLUMN, limited ALTER TABLE). Need to decide: Alembic with batch mode, or a simpler versioned-schema approach. | Maneesh | Before spec |
| 3 | Should `bookcompanion serve` auto-open the browser, or just print the URL? | Maneesh | Before spec |
