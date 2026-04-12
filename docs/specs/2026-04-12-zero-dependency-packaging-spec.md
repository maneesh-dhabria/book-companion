# Zero-Dependency Packaging — Spec

**Date:** 2026-04-12
**Status:** Draft
**Requirements:** `docs/requirements/2026-04-11-self-contained-packaging.md`

---

## 1. Problem Statement

Book Companion requires PostgreSQL (Docker), Ollama (background process), and Claude CLI to function. For a personal open-source tool, this should be a single `pip install`. This spec defines how to replace PostgreSQL with SQLite, Ollama with fastembed, add multi-provider LLM CLI support, and streamline the packaging to a zero-external-service install.

**Primary success metric:** A new user can `pip install bookcompanion && bookcompanion serve` and have a fully working application (minus LLM summarization if no CLI is installed).

---

## 2. Goals

| # | Goal | Success Metric |
|---|------|---------------|
| G1 | Zero-service install | `pip install bookcompanion` is the only install step. No Docker, no Ollama. |
| G2 | In-process semantic search | Embedding + vector search runs without external processes. Search quality equivalent to current. |
| G3 | Multi-provider LLM | Auto-detects Claude and Codex CLIs. User can configure via settings page. |
| G4 | Transparent degradation | When no LLM CLI is detected, all non-summarization features work. Clear UI messaging. |
| G5 | LAN accessibility | Web UI accessible from same-subnet devices without manual CORS config. |
| G6 | Reliable backups | Periodic file copy to configurable directory. Works with cloud sync folders. |

---

## 3. Non-Goals

- NOT supporting PostgreSQL as an alternative backend — clean break, single backend
- NOT making the embedding model user-configurable — hardcoded to all-MiniLM-L6-v2
- NOT adding GPU support for embeddings — CPU is sufficient for this model
- NOT integrating cloud backup APIs — configurable directory is sufficient
- NOT auto-opening browser on `bookcompanion serve` — print URL only

---

## 4. Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Hybrid ORM + raw SQL for FTS5/sqlite-vec | (a) Hybrid, (b) Custom SQLAlchemy types | FTS5 and sqlite-vec use virtual tables that don't map to ORM models. Search is already isolated in SearchRepo/SearchService. Raw SQL via `session.execute(text(...))` is pragmatic. |
| D2 | Single SearchIndex table + FTS5/vec shadow tables | (a) Single table + shadows, (b) Separate tables | SearchIndex stays as the ORM model for metadata. FTS5 virtual table (`search_fts`) and sqlite-vec virtual table (`search_vec`) reference SearchIndex rows by `rowid`. Fewer tables to sync. |
| D3 | Alembic with batch mode for SQLite | (a) Alembic batch, (b) Versioned schema, (c) Fresh-only | Alembic `render_as_batch=True` handles SQLite ALTER TABLE limitations. Keeps migration tooling for future schema changes. |
| D4 | Hardcode embedding model (all-MiniLM-L6-v2) | (a) Hardcode, (b) Configurable | Eliminates re-indexing complexity. Model change is a future code change. |
| D5 | Default pool for SQLite async engine | (a) Default (AsyncAdaptedQueuePool), (b) StaticPool, (c) NullPool | aiosqlite wraps pysqlite in a background thread per connection. SQLAlchemy's default async pool handles this correctly. Only need `connect_args={"check_same_thread": False}`. StaticPool is only needed for `:memory:` databases. |
| D6 | Fresh migration baseline — drop all PG migrations | (a) Fresh baseline, (b) Migrate existing | No published users. Start with a single clean migration for the SQLite schema. |
| D7 | LLM provider factory in `api/deps.py` | (a) Factory keyed on config, (b) Hard-instantiate per provider | Clean separation. `settings.llm.provider` drives which class is instantiated. New providers only need to implement `LLMProvider` ABC. |
| D8 | Print URL only on `bookcompanion serve` | (a) Print only, (b) Auto-open browser | Less surprising in headless/SSH environments. |

---

## 5. User Journeys

### 5.1 First-Time Install

1. `pip install bookcompanion` or `uv tool install bookcompanion`
2. `bookcompanion serve` → detects no DB → auto-inits (creates data dir, SQLite DB, downloads embedding model ~23MB) → starts uvicorn on `localhost:8000` → prints URL
3. User opens browser → empty library → uploads EPUB → book parsed, sections embedded in-process → searches work immediately
4. If Claude/Codex CLI on `$PATH`: "Summarize" works. If not: banner shown.

### 5.2 LLM Provider Detection

1. On app startup, check `$PATH` for `claude` and `codex` binaries via `shutil.which()`
2. If one found → auto-select, log message
3. If both found → use first detected, settings page shows choice
4. If neither found → set `settings.llm.provider = None`, disable summarization endpoints, show banner in UI

### 5.3 Backup

1. Settings page → set backup directory + frequency (hourly/daily/weekly)
2. APScheduler copies `library.db` to `{backup_dir}/bookcompanion-{timestamp}.db`
3. Keeps last N backups (configurable, default 5)
4. Restore: manual file copy back

---

## 6. Functional Requirements

### 6.1 Database Migration (PostgreSQL → SQLite)

| ID | Requirement |
|----|-------------|
| FR-01 | Replace `asyncpg` engine with `aiosqlite` engine. Use default pool (no explicit pool class). Set `connect_args={"check_same_thread": False}`. Remove `pool_size` and `max_overflow` args. |
| FR-02 | Enable WAL mode on connection: `PRAGMA journal_mode=WAL` via event listener on `connect` |
| FR-03 | Enable foreign keys on connection: `PRAGMA foreign_keys=ON` via event listener |
| FR-04 | Replace `JSONB` columns with `JSON` (SQLAlchemy `JSON` type works with SQLite, stored as TEXT) |
| FR-05 | Remove `Vector(768)` column from `SearchIndex`. Embeddings stored in sqlite-vec virtual table. |
| FR-06 | Remove `TSVECTOR` column from `SearchIndex`. Full-text search via FTS5 virtual table. |
| FR-07 | Replace PostgreSQL partial index (`postgresql_where=`) with SQLite equivalent (`sqlite_where=`) on `EvalTrace.is_stale` |
| FR-08 | Replace `pg_insert` + `on_conflict_do_update` in `reading_state_repo.py` with `sqlite_insert` from `sqlalchemy.dialects.sqlite` |
| FR-09 | Delete all 7 existing Alembic migration files. Create a single fresh baseline migration for SQLite schema. |
| FR-10 | Configure Alembic `env.py` with `render_as_batch=True` for SQLite compatibility |
| FR-11 | Data directory: `~/.local/share/bookcompanion/` on Linux, `~/Library/Application Support/bookcompanion/` on macOS, `%LOCALAPPDATA%/bookcompanion/` on Windows. Overridable via `BOOKCOMPANION_DATA_DIR` env var. Use `platformdirs` library for cross-platform resolution. |
| FR-12 | Database file path: `{data_dir}/library.db` |

### 6.2 Search (FTS5 + sqlite-vec)

| ID | Requirement |
|----|-------------|
| FR-13 | Create FTS5 virtual table `search_fts(rowid, content)` that mirrors `SearchIndex` text content |
| FR-14 | Create sqlite-vec virtual table `search_vec(rowid, embedding float[384])` that stores embeddings keyed by SearchIndex rowid |
| FR-15 | BM25 search: query `search_fts` using `MATCH` operator with `bm25()` ranking function |
| FR-16 | Semantic search: query `search_vec` using `vec_distance_cosine()` with the query embedding |
| FR-17 | RRF fusion: merge BM25 and semantic rankings using existing RRF algorithm (no change) |
| FR-18 | On `index_section/annotation/concept/image_caption`: insert into `SearchIndex` (ORM) — FTS5 syncs automatically via database triggers — then insert into `search_vec` (raw SQL) with matching rowid |
| FR-19 | On delete: remove from `SearchIndex` (ORM) — FTS5 syncs via trigger — then delete from `search_vec` by rowid (raw SQL) |
| FR-20 | sqlite-vec extension must be loaded on every connection via `connection.enable_load_extension(True); connection.load_extension("vec0"); connection.enable_load_extension(False)` — disable extension loading after vec0 is loaded for security |

### 6.3 Embedding (fastembed)

| ID | Requirement |
|----|-------------|
| FR-21 | Replace `EmbeddingService.embed_text()`: use `fastembed.TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")`. Verify exact model identifier at implementation time. |
| FR-22 | fastembed is synchronous — wrap in `asyncio.to_thread()` to maintain async interface |
| FR-23 | Initialize `TextEmbedding` once at service construction, not per-call. Cache in `self._model`. |
| FR-24 | Model weights cached in `{data_dir}/models/` via fastembed's `cache_dir` parameter |
| FR-25 | `bookcompanion init` triggers a warm-up embed call to force model download |
| FR-26 | Remove `ollama_url` from `EmbeddingConfig`. Remove `model` field (hardcoded). Keep `chunk_size` and `chunk_overlap`. |
| FR-27 | Embedding dimension is 384 (hardcoded, matches all-MiniLM-L6-v2) |

### 6.4 Multi-Provider LLM

| ID | Requirement |
|----|-------------|
| FR-28 | Add `LlmConfig` to Settings: `provider` (enum: `claude`, `codex`, `null`), `command` (path override, default `None` = use `$PATH`), `config_dir` (optional override for CLI config directory) |
| FR-29 | On startup, auto-detect providers via `shutil.which("claude")` and `shutil.which("codex")`. Set `provider` to first found. If neither found, set to `null`. |
| FR-30 | Create `CodexCLIProvider` implementing `LLMProvider` ABC, mirroring `ClaudeCodeCLIProvider` with Codex CLI flags |
| FR-31 | Provider factory in `api/deps.py` and `cli/deps.py`: instantiate the correct provider class based on `settings.llm.provider` |
| FR-32 | When `provider` is `null`, `get_summarizer_service()` and `get_eval_service()` return `None`. Callers must handle gracefully. |
| FR-33 | Settings API: `PATCH /api/v1/settings` accepts `llm.provider`, `llm.command`, `llm.config_dir` updates |
| FR-34 | Frontend settings page: new "LLM Provider" section showing detected providers, active selection, command path override, and config directory override |

### 6.5 CORS / LAN Access

| ID | Requirement |
|----|-------------|
| FR-35 | On startup, detect all non-loopback IPv4 addresses via `netifaces` or `socket.getaddrinfo()` |
| FR-36 | Build CORS origin list: `localhost:{port}`, `127.0.0.1:{port}`, plus `http://{ip}:{port}` for each detected interface |
| FR-37 | Pass computed origins to `CORSMiddleware` instead of hardcoded list |
| FR-38 | Add `BOOKCOMPANION_CORS_EXTRA_ORIGINS` env var for manually adding origins (comma-separated) |

### 6.6 Packaging & Init

| ID | Requirement |
|----|-------------|
| FR-39 | `bookcompanion init`: create data directory, initialize SQLite DB (run Alembic migrations), download fastembed model, detect LLM providers |
| FR-40 | `bookcompanion serve`: if no DB exists, auto-run init. Start uvicorn. Print `Serving at http://localhost:{port}` and `Also available at http://{lan_ip}:{port}` |
| FR-41 | Add `bookcompanion serve` CLI command in `app/cli/commands/serve_cmd.py`, wrapping `uvicorn app.api.main:app --host 0.0.0.0 --port {port}`. Register in `app/cli/main.py`. |
| FR-42 | Remove all Docker files: `Dockerfile`, `docker-compose.yml`, `.env.example` |
| FR-43 | Remove Docker-specific code: `check_db_health` Docker message in `deps.py`, `docker compose` commands in `init_cmd.py` |
| FR-44 | Update `pyproject.toml`: add `fastembed`, `aiosqlite`, `sqlite-vec`, `platformdirs` to dependencies. Remove `asyncpg`, `psycopg2-binary`. |

### 6.7 Backup

| ID | Requirement |
|----|-------------|
| FR-45 | Add `BackupConfig` to Settings: `directory` (default: `{data_dir}/backups/`), `frequency` (enum: `hourly`, `daily`, `weekly`, `disabled`; default: `daily`), `max_backups` (default: 5) |
| FR-46 | Rewrite `BackupService`: replace `pg_dump`/`psql` with `shutil.copy2`. Backup file: `{backup_dir}/library-{YYYY-MM-DD-HHMMSS}.db` |
| FR-47 | `list_backups()`: glob `{backup_dir}/library-*.db`, return sorted by timestamp |
| FR-48 | `restore_backup(path)`: copy backup file over `library.db` (with safety check: verify it's a valid SQLite DB first) |
| FR-49 | Prune: after each backup, delete oldest files beyond `max_backups` |
| FR-50 | APScheduler integration: schedule backup job in FastAPI lifespan based on `settings.backup.frequency` |

---

## 7. API Changes

### 7.1 Settings Endpoints (existing, extended)

```
PATCH /api/v1/settings
```

**New fields accepted in body:**

```json
{
  "llm": {
    "provider": "claude | codex | null",
    "command": "/path/to/claude",
    "config_dir": "/path/to/config"
  },
  "backup": {
    "directory": "~/Google Drive/bookcompanion-backups/",
    "frequency": "daily",
    "max_backups": 5
  }
}
```

**Response (200):** Updated settings object with masked sensitive fields.

**Error responses:**
- `422`: Invalid field value (e.g., `provider: "invalid"`, `frequency: "every5min"`)
- `400`: Backup directory path is not writable

### 7.2 Health Endpoint (extended)

```
GET /api/v1/health
```

**Response (200):**
```json
{
  "status": "ok",
  "llm_provider": "claude",
  "llm_available": true,
  "database": "sqlite",
  "embedding_model": "all-MiniLM-L6-v2"
}
```

When no LLM provider detected:
```json
{
  "status": "ok",
  "llm_provider": null,
  "llm_available": false,
  "database": "sqlite",
  "embedding_model": "all-MiniLM-L6-v2"
}
```

### 7.3 Backup Endpoints (existing, adapted)

No API contract changes — `BackupService` method signatures stay the same (`create_backup`, `list_backups`, `restore_backup`). Only the internal implementation changes from `pg_dump` to file copy.

---

## 8. Database Design

### 8.1 Schema Changes

**Remove from `SearchIndex`:**
```sql
-- These columns are removed from the SearchIndex table
-- tsvector TSVECTOR  (was PostgreSQL-specific)
-- embedding VECTOR(768)  (was pgvector-specific)
```

**SearchIndex (simplified ORM table):**
```sql
CREATE TABLE search_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type VARCHAR(50) NOT NULL,  -- 'section', 'annotation', 'concept', 'image_caption'
    content_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL REFERENCES books(id),
    chunk TEXT NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_type, content_id, chunk_index)
);
```

**FTS5 virtual table (shadow):**
```sql
CREATE VIRTUAL TABLE search_fts USING fts5(
    chunk,
    content=search_index,
    content_rowid=id,
    tokenize='porter unicode61'
);

-- Triggers to keep FTS5 in sync with SearchIndex
CREATE TRIGGER search_fts_ai AFTER INSERT ON search_index BEGIN
    INSERT INTO search_fts(rowid, chunk) VALUES (new.id, new.chunk);
END;

CREATE TRIGGER search_fts_ad AFTER DELETE ON search_index BEGIN
    INSERT INTO search_fts(search_fts, rowid, chunk) VALUES ('delete', old.id, old.chunk);
END;

CREATE TRIGGER search_fts_au AFTER UPDATE ON search_index BEGIN
    INSERT INTO search_fts(search_fts, rowid, chunk) VALUES ('delete', old.id, old.chunk);
    INSERT INTO search_fts(rowid, chunk) VALUES (new.id, new.chunk);
END;
```

**sqlite-vec virtual table (shadow):**
```sql
CREATE VIRTUAL TABLE search_vec USING vec0(
    embedding float[384]
);
```

Note: sqlite-vec's `vec0` virtual table uses rowid-based storage. When inserting, the rowid must match `search_index.id` for join queries to work:
```sql
INSERT INTO search_vec(rowid, embedding) VALUES (?, ?);
```

**JSONB → JSON:**
```sql
-- Summary.facets_used: JSONB → JSON (stored as TEXT in SQLite)
-- LibraryView.filters: JSONB → JSON
-- LibraryView.table_columns: JSONB → JSON
```

### 8.2 Migration Notes

- **Fresh baseline:** Delete all 7 existing migration files. Create one new migration (`001_initial_sqlite_schema.py`) with the complete schema.
- **Alembic batch mode:** Configure `env.py` with `render_as_batch=True` and `context.configure(render_as_batch=True)`.
- **Virtual tables in migration:** FTS5 and sqlite-vec virtual tables must be created via `op.execute()` raw SQL in the migration, not via ORM.
- **No rollback from SQLite to PostgreSQL.** This is a one-way migration.

### 8.3 Indexes & Query Patterns

**BM25 search query:**
```sql
SELECT si.*, fts.rank
FROM search_index si
JOIN search_fts fts ON si.id = fts.rowid
WHERE search_fts MATCH :query
ORDER BY fts.rank
LIMIT :limit;
```

**Semantic search query:**
```sql
SELECT si.*, vec.distance
FROM search_index si
JOIN search_vec vec ON si.id = vec.rowid
WHERE vec.embedding MATCH :query_embedding
    AND k = :limit
ORDER BY vec.distance;
```

**Hybrid (RRF) fusion:** Execute both queries in Python, merge using existing RRF algorithm. No SQL-level fusion needed.

---

## 9. Edge Cases

| # | Scenario | Condition | Expected Behavior |
|---|----------|-----------|-------------------|
| E1 | First run without internet | fastembed model not cached, no internet | Init fails with clear error: "Could not download embedding model. Check your internet connection." App starts without embeddings; search falls back to BM25 only. |
| E2 | sqlite-vec extension not available | Platform without prebuilt sqlite-vec wheels | Graceful degradation: semantic search disabled, BM25-only. Warning logged and shown in settings page. |
| E3 | Database file corruption | `library.db` unreadable | Startup fails with error: "Database corrupted. Restore from backup: `bookcompanion restore <backup-path>`" |
| E4 | Concurrent writes (WAL mode) | Multiple browser tabs or background tasks writing simultaneously | WAL mode handles this — writes serialize, reads are concurrent. Acceptable for single-user tool. |
| E5 | Claude CLI requires auth | `claude` binary found but not authenticated | Summarization fails with subprocess error. Surface the CLI's error message to the user: "Claude CLI authentication required. Run `claude auth` in your terminal." |
| E6 | Backup directory doesn't exist | User configures a backup path that doesn't exist | Create the directory on first backup. If creation fails (permissions), show error in settings page. |
| E7 | Backup directory is read-only | Backup to a read-only mount | Backup fails. Log error, show in settings page: "Backup failed: permission denied for {path}" |
| E8 | Large embedding model download on init | Slow network, ~23MB download | Show progress via `fastembed`'s built-in progress bar. If interrupted, next init retries. |
| E9 | MOBI upload without Calibre | User uploads `.mobi` file | Clear error: "MOBI format requires Calibre's ebook-convert. Install Calibre or convert to EPUB first." |
| E10 | LLM provider changed via settings while summarization in progress | User switches from Claude to Codex mid-job | Current job finishes with the old provider. Next job uses the new one. No mid-job switching. |

---

## 10. Testing & Verification Strategy

### 10.0 Existing Test Adaptation

The existing ~78 tests assume PostgreSQL. Tests that directly use the database (integration, e2e) need adaptation:
- **Unit tests:** Most mock the DB and should work with minimal changes (remove pgvector/tsvector-specific mocks).
- **Integration tests:** Replace `clean_db` fixture to use a temporary SQLite file. Remove `BOOKCOMPANION_DATABASE__URL` overrides pointing to PostgreSQL.
- **E2E tests:** Update `config set` tests and CLI output assertions (Docker references removed).
- **Embedding tests:** Replace Ollama HTTP mocks with fastembed mocks.
- `conftest.py` fixtures that create PostgreSQL test databases need full rewrite to create temporary SQLite files.

### 10.1 Unit Tests

- **EmbeddingService:** Mock `fastembed.TextEmbedding`. Verify `embed_text()` returns 384-dim vector. Verify `chunk_and_embed()` splits correctly.
- **BackupService:** Test file copy, prune logic, restore validation (check SQLite header).
- **LLM provider factory:** Verify correct provider instantiated for each config value. Verify `None` returned when provider is `null`.
- **CORS origins builder:** Verify localhost origins always included. Verify LAN IPs detected. Verify extra origins from env var merged.
- **Config:** Verify XDG paths on Linux and macOS. Verify `BOOKCOMPANION_DATA_DIR` override.

### 10.2 Integration Tests

- **Search round-trip:** Index a section (insert into SearchIndex + FTS5 + sqlite-vec), then search by keyword (BM25) and by semantic similarity. Verify results include the indexed section.
- **Backup/restore cycle:** Create DB with data, backup, modify data, restore, verify original data restored.
- **Settings persistence:** Set LLM provider via API, restart, verify provider persists.

### 10.3 End-to-End Tests

- **Full pipeline:** `bookcompanion init` → `bookcompanion serve` → upload EPUB via API → search → verify results.
- **LAN access:** Start server, verify CORS headers include a non-loopback IP.
- **Degradation:** Start with no LLM CLI on PATH. Verify health endpoint reports `llm_available: false`. Verify summarize endpoint returns 503 with helpful message.

### 10.4 Verification Commands

```bash
# Run all tests
cd backend && uv run python -m pytest tests/ -v

# Verify SQLite schema
uv run python -c "
import sqlite3
conn = sqlite3.connect('~/.local/share/bookcompanion/library.db')
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print([t[0] for t in tables])
# Should include: books, book_sections, summaries, search_index, etc.
# Virtual tables: search_fts, search_vec
"

# Verify embedding model works
uv run python -c "
from fastembed import TextEmbedding
model = TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')
result = list(model.embed(['test query']))[0]
print(f'Dimension: {len(result)}')  # Should print 384
"

# Verify FTS5 search
uv run python -c "
import sqlite3
conn = sqlite3.connect('~/.local/share/bookcompanion/library.db')
results = conn.execute(\"SELECT * FROM search_fts WHERE search_fts MATCH 'test'\").fetchall()
print(f'Results: {len(results)}')
"

# Verify LLM detection
uv run python -c "
import shutil
print(f'claude: {shutil.which(\"claude\")}')
print(f'codex: {shutil.which(\"codex\")}')
"

# Verify CORS headers
curl -v -H "Origin: http://192.168.1.100:8000" http://localhost:8000/api/v1/health 2>&1 | grep -i access-control
```

---

## 11. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Verify the exact fastembed model identifier for all-MiniLM-L6-v2 by testing `fastembed.TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")` locally. | Engineer | Before implementation |
| 2 | Does `sqlite-vec` have prebuilt wheels for all target platforms (macOS arm64, Linux x86_64, Windows)? Need to verify compatibility. | Engineer | Before implementation |
