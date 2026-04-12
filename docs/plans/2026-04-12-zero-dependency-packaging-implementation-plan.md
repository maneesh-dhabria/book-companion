# Zero-Dependency Packaging — Implementation Plan

**Date:** 2026-04-12
**Spec:** `docs/specs/2026-04-12-zero-dependency-packaging-spec.md`
**Requirements:** `docs/requirements/2026-04-11-self-contained-packaging.md`

---

## Overview

Replace PostgreSQL with SQLite (FTS5 + sqlite-vec), Ollama with fastembed, add multi-provider LLM CLI support, and streamline packaging so `pip install bookcompanion && bookcompanion serve` is the entire setup. The plan follows a bottom-up order: config/data dirs → DB engine → models → migration → embedding → search → LLM providers → backup → CORS → init/serve commands → remove Docker → adapt tests → frontend → final verification.

**Done when:** `uv run python -m pytest tests/ -v` passes all tests, `bookcompanion serve` starts on a fresh machine with no Docker, hybrid search returns results for an indexed book, and the health endpoint reports `llm_available: true` when Claude CLI is on `$PATH`.

**Execution order:**
```
T1 (Config + Data Dirs)
  │
  ├─► T2 (DB Engine + Session)
  │     │
  │     ├─► T3 (Models - remove PG types)
  │     │     │
  │     │     └─► T4 (Alembic Migration)
  │     │           │
  │     │           ├─► T5 (Embedding Service) [P]
  │     │           ├─► T6 (Repo Fixes) [P]
  │     │           │
  │     │           └─► T7 (Search Service)
  │     │
  │     └─► T8 (Backup Service) [P]
  │
  ├─► T9 (LLM Multi-Provider) [P]
  │
  ├─► T10 (CORS + LAN) [P]
  │
  └─► T11 (Init + Serve Commands)
        │
        └─► T12 (Remove Docker + Deps)
              │
              └─► T13 (Test Fixture Adaptation)
                    │
                    └─► T14 (Frontend Settings)
                          │
                          └─► T15 (Final Verification)
```

---

## Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| PD1 | Bottom-up task order: config → engine → models → migration → services | (a) Bottom-up, (b) Top-down (CLI first), (c) Feature-slice | Bottom-up ensures each layer is testable before the next builds on it. Config must exist before engine, engine before models, models before migration, migration before services. |
| PD2 | Adapt existing test fixtures in a dedicated task (T13) rather than per-task | (a) Dedicated task, (b) Fix tests in each task | Existing tests will break as soon as T2 changes the engine. Fixing them per-task creates noisy diffs and forces running broken tests mid-plan. Better to adapt all fixtures once after the core infrastructure is stable. |
| PD3 | Use `platformdirs.user_data_dir("bookcompanion")` for data dir resolution | (a) platformdirs, (b) Manual XDG/macOS/Windows detection, (c) Custom env-only | platformdirs is the standard library for this. Already handles Linux XDG, macOS `~/Library/Application Support/`, and Windows `%LOCALAPPDATA%`. One import vs. 20 lines of platform detection. |
| PD4 | FTS5 + sqlite-vec virtual tables created in Alembic migration via `op.execute()` | (a) In migration, (b) In session.py on_connect, (c) In init command | Migrations are the standard place for DDL. Virtual tables are schema, not runtime config. Keeps session.py focused on engine setup. |
| PD5 | sqlite-vec loaded via SQLAlchemy `pool_events.connect` listener | (a) Event listener, (b) Manual load per query, (c) Custom engine wrapper | Event listener fires on every new connection, ensuring vec0 is always available. No per-query boilerplate. Standard SQLAlchemy pattern. |

---

## Code Study Notes

**Key files and patterns discovered:**

- `config.py`: Uses `pydantic_settings.BaseSettings` with `env_prefix="BOOKCOMPANION_"` and `env_nested_delimiter="__"`. YAML config merged in `model_post_init`. Existing `LlmConfig` has `cli_command`, `model`, `timeout_seconds`, `max_budget_usd`, `config_dir` — need to add `provider` field.
- `session.py`: Simple — `create_engine()` + `create_session_factory()`. Uses `pool_size=5, max_overflow=10` which must be removed for SQLite.
- `models.py`: 17+ models. PG-specific: `Vector(768)` and `TSVECTOR` on SearchIndex, `JSONB` on Summary/LibraryView, HNSW/GIN indexes, partial index on EvalTrace. Column names are `source_type`/`source_id`/`chunk_text` (not `content_type`/`content_id`/`chunk` as spec assumed — must use actual names).
- `search_repo.py`: 6 methods. BM25 uses `plainto_tsquery`/`ts_rank`/`@@` operator. Semantic uses `.cosine_distance()`. All must be rewritten to raw SQL.
- `search_service.py`: All 4 `index_*` methods set `tsvector=func.to_tsvector("english", chunk)` on SearchIndex creation. These must be removed (FTS5 triggers handle sync).
- `reading_state_repo.py`: Uses `pg_insert` + `on_conflict_do_update` + `.returning()`.
- `backup_service.py`: Fully pg_dump/psql based. Complete rewrite to `shutil.copy2`.
- `claude_cli.py`: `ClaudeCodeCLIProvider` constructor takes `cli_command`, `default_model`, `default_timeout`, `max_budget_usd`, `config_dir`. Good interface for cloning to `CodexCLIProvider`.
- `deps.py` (CLI): Wires `EmbeddingService` with `ollama_url`, `model`. Wires `ClaudeCodeCLIProvider` directly.
- `deps.py` (API): Hard-instantiates `ClaudeCodeCLIProvider` in `get_summarizer_service` and `get_eval_service`.
- `conftest.py`: `TEST_DB_URL` hardcoded to PostgreSQL. Engine created with `create_async_engine(TEST_DB_URL)`. Tables created via `Base.metadata.create_all`. Teardown uses rollback.
- `api/main.py`: CORS origins hardcoded to 4 localhost URLs. Lifespan already has APScheduler for backups.
- `pyproject.toml`: Has `asyncpg` and `pgvector` to remove. No `aiosqlite`, `fastembed`, `sqlite-vec`, or `platformdirs`.
- No `serve` command exists — must be created from scratch.
- Frontend `AppSettings.llm` type already has `provider` field but it's typed as `string` not an enum.

---

## Prerequisites

- `uv` installed and working
- Current code on `main` branch, clean working tree
- Internet access (for `fastembed` model download during testing)

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/config.py` | Add `BackupConfig`, `DataConfig`; update `EmbeddingConfig`, `LlmConfig`, `DatabaseConfig` |
| Modify | `backend/app/db/session.py` | Switch to aiosqlite engine, add WAL/FK pragmas, load sqlite-vec |
| Modify | `backend/app/db/models.py` | Remove Vector/TSVECTOR/JSONB, update SearchIndex, fix indexes |
| Delete | `backend/alembic/versions/*.py` (7 files) | Remove PG migrations |
| Create | `backend/alembic/versions/001_initial_sqlite_schema.py` | Fresh SQLite baseline with FTS5 + sqlite-vec virtual tables |
| Modify | `backend/alembic/env.py` | Add `render_as_batch=True` |
| Modify | `backend/app/services/embedding_service.py` | Replace Ollama HTTP with fastembed in-process |
| Modify | `backend/app/db/repositories/search_repo.py` | Rewrite BM25/semantic to raw SQL (FTS5 + sqlite-vec) |
| Modify | `backend/app/db/repositories/reading_state_repo.py` | Switch `pg_insert` to `sqlite_insert` |
| Modify | `backend/app/services/search_service.py` | Remove `tsvector=` from index methods, add sqlite-vec inserts |
| Modify | `backend/app/services/backup_service.py` | Rewrite from pg_dump to shutil.copy2 |
| Create | `backend/app/services/summarizer/codex_cli.py` | CodexCLIProvider implementing LLMProvider |
| Modify | `backend/app/cli/deps.py` | LLM provider factory, update EmbeddingService wiring |
| Modify | `backend/app/api/deps.py` | LLM provider factory |
| Modify | `backend/app/api/main.py` | Dynamic CORS origins |
| Modify | `backend/app/api/routes/health.py` | Extended health response |
| Modify | `backend/app/cli/commands/init_cmd.py` | Remove Docker/Ollama, add fastembed warm-up |
| Create | `backend/app/cli/commands/serve_cmd.py` | `bookcompanion serve` command |
| Modify | `backend/app/cli/main.py` | Register serve command |
| Delete | `Dockerfile`, `docker-compose.yml`, `.env.example` | Remove Docker files |
| Modify | `backend/pyproject.toml` | Swap deps |
| Modify | `backend/tests/conftest.py` | SQLite test fixtures |
| Modify | `frontend/src/api/settings.ts` | Update AppSettings type |
| Modify | `frontend/src/views/SettingsView.vue` | Add LLM section |
| Create | `frontend/src/components/settings/LlmSettings.vue` | LLM provider settings component |
| Test | `backend/tests/unit/test_embedding.py` | fastembed tests |
| Test | `backend/tests/unit/test_backup.py` | File-copy backup tests |
| Test | `backend/tests/unit/test_config.py` | Data dir + new config tests |
| Test | `backend/tests/integration/test_search.py` | FTS5 + sqlite-vec round-trip |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| sqlite-vec missing prebuilt wheels for a platform | Medium | Graceful degradation: catch `ImportError`/`OperationalError` on load, fall back to BM25-only. Test on macOS arm64 + Linux x86_64. |
| fastembed model identifier wrong | Low | Verify with `fastembed.TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")` in T5 before proceeding. |
| FTS5 content sync triggers interfere with ORM flush order | Medium | Test triggers fire correctly with SQLAlchemy ORM inserts in T7 integration test. If triggers fail, switch to manual FTS5 inserts in SearchService. |
| sqlite-vec embedding serialization format | Low (resolved) | Use `sqlite_vec.serialize_float32()` for binary serialization on both insert and query. Verified via sqlite-vec Python docs and examples. |
| Existing tests break in bulk during T13 | High (expected) | Dedicated task with systematic approach: fix conftest first, then unit, then integration. |

---

## Tasks

### T1: Config, Data Dirs, and Dependencies

**Goal:** Update config classes and pyproject.toml for the new stack.
**Spec refs:** FR-11, FR-12, FR-26, FR-28, FR-44, FR-45

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/pyproject.toml`
- Test: `backend/tests/unit/test_config.py`

**Steps:**

- [ ] Step 1: Write tests for new config fields
  ```python
  # tests/unit/test_config.py — add these tests

  def test_data_dir_default(clean_env):
      """Data dir uses platformdirs default."""
      from app.config import Settings
      s = Settings()
      # Should resolve to a platform-specific path containing 'bookcompanion'
      assert "bookcompanion" in str(s.data.directory)

  def test_data_dir_env_override(clean_env, monkeypatch):
      """BOOKCOMPANION_DATA_DIR overrides default."""
      monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", "/tmp/bc-test")
      from app.config import Settings
      s = Settings()
      assert str(s.data.directory) == "/tmp/bc-test"

  def test_database_url_default(clean_env):
      """Database URL defaults to sqlite in data dir."""
      from app.config import Settings
      s = Settings()
      assert "sqlite" in s.database.url
      assert "library.db" in s.database.url

  def test_embedding_config_no_ollama(clean_env):
      """EmbeddingConfig has no ollama_url field."""
      from app.config import Settings
      s = Settings()
      assert not hasattr(s.embedding, "ollama_url")
      assert s.embedding.chunk_size == 512

  def test_llm_provider_field(clean_env):
      """LlmConfig has provider field."""
      from app.config import Settings
      s = Settings()
      assert hasattr(s.llm, "provider")

  def test_backup_config_defaults(clean_env):
      """BackupConfig has directory, frequency, max_backups."""
      from app.config import Settings
      s = Settings()
      assert s.backup.frequency == "daily"
      assert s.backup.max_backups == 5
  ```

- [ ] Step 2: Run tests — expect failures (new fields don't exist yet)
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_config.py -v -k "test_data_dir or test_database_url_default or test_embedding_config_no_ollama or test_llm_provider or test_backup_config"
  ```

- [ ] Step 3: Update `pyproject.toml` dependencies
  Replace `asyncpg>=0.30.0` with `aiosqlite>=0.20.0`. Replace `pgvector>=0.4.0` with `sqlite-vec>=0.1.0`. Add `fastembed>=0.4.0`, `platformdirs>=4.0.0`. Keep all other deps. Run `uv sync --dev`.

- [ ] Step 4: Update `config.py`
  - Add `DataConfig` class: `directory: str` defaulting to `platformdirs.user_data_dir("bookcompanion")`
  - Update `DatabaseConfig.url` default: `f"sqlite+aiosqlite:///{data_dir}/library.db"` (computed in `Settings.model_post_init`)
  - Update `EmbeddingConfig`: remove `ollama_url` and `model` fields, keep `chunk_size` and `chunk_overlap`
  - Add `provider: str = "auto"` to existing `LlmConfig` (alongside existing `cli_command`, `model`, etc.)
  - Add `BackupConfig`: `directory: str = ""` (default computed from data dir), `frequency: str = "daily"`, `max_backups: int = 5`
  - Add `data: DataConfig = DataConfig()` and `backup: BackupConfig = BackupConfig()` to `Settings`

- [ ] Step 5: Run tests — expect passes
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_config.py -v -k "test_data_dir or test_database_url_default or test_embedding_config_no_ollama or test_llm_provider or test_backup_config"
  ```

- [ ] Step 6: Commit
  ```bash
  git add backend/pyproject.toml backend/app/config.py backend/tests/unit/test_config.py
  git commit -m "feat: update config for SQLite, fastembed, and new backup/data settings"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/config.py` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_config.py -v -k "test_data_dir or test_database_url or test_embedding or test_llm_provider or test_backup_config"` — 6 passed

---

### T2: DB Engine and Session

**Goal:** Switch from asyncpg to aiosqlite with WAL mode, foreign keys, and sqlite-vec loading.
**Spec refs:** FR-01, FR-02, FR-03, FR-20, D5

**Files:**
- Modify: `backend/app/db/session.py`
- Test: `backend/tests/unit/test_session.py` (create)

**Steps:**

- [ ] Step 1: Write test for SQLite engine creation
  ```python
  # tests/unit/test_session.py
  import pytest
  from unittest.mock import patch
  from app.config import Settings

  @pytest.fixture
  def sqlite_settings(tmp_path, monkeypatch):
      monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
      monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
      return Settings()

  def test_engine_uses_aiosqlite(sqlite_settings):
      from app.db.session import create_engine
      engine = create_engine(sqlite_settings)
      assert "aiosqlite" in str(engine.url)

  @pytest.mark.asyncio
  async def test_wal_mode_enabled(sqlite_settings):
      from app.db.session import create_session_factory
      factory = create_session_factory(sqlite_settings)
      async with factory() as session:
          result = await session.execute(text("PRAGMA journal_mode"))
          mode = result.scalar()
          assert mode == "wal"

  @pytest.mark.asyncio
  async def test_foreign_keys_enabled(sqlite_settings):
      from app.db.session import create_session_factory
      factory = create_session_factory(sqlite_settings)
      async with factory() as session:
          result = await session.execute(text("PRAGMA foreign_keys"))
          fk = result.scalar()
          assert fk == 1
  ```

- [ ] Step 2: Run tests — expect failures
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_session.py -v
  ```

- [ ] Step 3: Rewrite `session.py`
  - Remove `pool_size` and `max_overflow` args from `create_async_engine`
  - Add `connect_args={"check_same_thread": False}`
  - Add `@event.listens_for(engine.sync_engine, "connect")` handler that runs `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`
  - In the same listener, attempt to load sqlite-vec: `conn.enable_load_extension(True); conn.load_extension("vec0"); conn.enable_load_extension(False)` wrapped in try/except (graceful degradation if vec0 not available)

- [ ] Step 4: Run tests — expect passes
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_session.py -v
  ```

- [ ] Step 5: Commit
  ```bash
  git add backend/app/db/session.py backend/tests/unit/test_session.py
  git commit -m "feat: switch DB engine from asyncpg to aiosqlite with WAL mode"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/db/session.py` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_session.py -v` — 3 passed

---

### T3: Models — Remove PostgreSQL Types

**Goal:** Remove Vector, TSVECTOR, JSONB from models. Update SearchIndex and indexes.
**Spec refs:** FR-04, FR-05, FR-06, FR-07

**Files:**
- Modify: `backend/app/db/models.py`

**Steps:**

- [ ] Step 1: Remove PostgreSQL imports
  - Remove `from pgvector.sqlalchemy import Vector`
  - Remove `JSONB, TSVECTOR` from `sqlalchemy.dialects.postgresql` import
  - Add `from sqlalchemy import JSON` if not already imported

- [ ] Step 2: Update SearchIndex model
  - Remove `embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)`
  - Remove `tsvector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)`
  - Remove the HNSW index on `embedding` and GIN index on `tsvector` from `__table_args__`

- [ ] Step 3: Update JSONB → JSON
  - `Summary.facets_used`: change `JSONB` to `JSON`
  - `LibraryView.filters`: change `JSONB` to `JSON`
  - `LibraryView.table_columns`: change `JSONB` to `JSON`

- [ ] Step 4: Fix EvalTrace partial index
  - Change `postgresql_where="is_stale = FALSE"` to `sqlite_where=text("is_stale = 0")` (SQLite stores booleans as 0/1)

- [ ] Step 5: Verify models import cleanly
  ```bash
  cd backend && uv run python -c "from app.db.models import *; print('Models imported OK')"
  ```

- [ ] Step 6: Commit
  ```bash
  git add backend/app/db/models.py
  git commit -m "feat: remove PostgreSQL-specific types from models (Vector, TSVECTOR, JSONB)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/db/models.py` — no lint errors
- `cd backend && uv run python -c "from app.db.models import SearchIndex, Summary, LibraryView, EvalTrace; print('OK')"` — prints OK

---

### T4: Fresh Alembic Migration

**Goal:** Delete PG migrations, create fresh SQLite baseline with FTS5 + sqlite-vec virtual tables.
**Spec refs:** FR-09, FR-10, FR-13, FR-14, D6

**Files:**
- Delete: `backend/alembic/versions/*.py` (all 7 files)
- Create: `backend/alembic/versions/001_initial_sqlite_schema.py`
- Modify: `backend/alembic/env.py`

**Steps:**

- [ ] Step 1: Delete all existing migration files
  ```bash
  rm backend/alembic/versions/*.py
  ```

- [ ] Step 2: Update `alembic/env.py`
  - Add `render_as_batch=True` to `context.configure()` call in both `run_migrations_offline()` and `do_run_migrations()`

- [ ] Step 3: Create fresh baseline migration
  Generate with: `cd backend && uv run alembic revision --autogenerate -m "initial sqlite schema"`
  Then manually edit the generated file to add virtual tables after the ORM tables:
  ```python
  # At the end of upgrade():
  op.execute("""
      CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
          chunk_text,
          content=search_index,
          content_rowid=id,
          tokenize='porter unicode61'
      )
  """)
  op.execute("""
      CREATE TRIGGER IF NOT EXISTS search_fts_ai AFTER INSERT ON search_index BEGIN
          INSERT INTO search_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
      END
  """)
  op.execute("""
      CREATE TRIGGER IF NOT EXISTS search_fts_ad AFTER DELETE ON search_index BEGIN
          INSERT INTO search_fts(search_fts, rowid, chunk_text) VALUES ('delete', old.id, old.chunk_text);
      END
  """)
  op.execute("""
      CREATE TRIGGER IF NOT EXISTS search_fts_au AFTER UPDATE ON search_index BEGIN
          INSERT INTO search_fts(search_fts, rowid, chunk_text) VALUES ('delete', old.id, old.chunk_text);
          INSERT INTO search_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
      END
  """)
  op.execute("""
      CREATE VIRTUAL TABLE IF NOT EXISTS search_vec USING vec0(
          embedding float[384]
      )
  """)
  ```

- [ ] Step 4: Test migration runs on a fresh SQLite DB
  ```bash
  cd backend && BOOKCOMPANION_DATABASE__URL="sqlite+aiosqlite:///$(mktemp -d)/test.db" uv run alembic upgrade head
  ```

- [ ] Step 5: Verify tables exist
  ```bash
  cd backend && uv run python -c "
  import sqlite3, tempfile, os
  db = os.path.join(tempfile.mkdtemp(), 'verify.db')
  os.environ['BOOKCOMPANION_DATABASE__URL'] = f'sqlite+aiosqlite:///{db}'
  import asyncio
  from app.config import Settings
  from app.db.session import create_session_factory
  from sqlalchemy import text
  async def check():
      s = Settings()
      s.database.url = f'sqlite+aiosqlite:///{db}'
      factory = create_session_factory(s)
      async with factory() as session:
          tables = (await session.execute(text(\"SELECT name FROM sqlite_master WHERE type IN ('table','trigger')\"))).fetchall()
          names = [t[0] for t in tables]
          print(names)
          assert 'search_index' in names
          assert 'search_fts' in names
          assert 'search_fts_ai' in names
          print('All tables and triggers present')
  asyncio.run(check())
  "
  ```

- [ ] Step 6: Commit
  ```bash
  git add backend/alembic/
  git commit -m "feat: fresh Alembic baseline for SQLite with FTS5 + sqlite-vec"
  ```

**Inline verification:**
- Migration runs without errors on fresh SQLite file
- `search_index`, `search_fts`, `search_vec`, and 3 FTS5 triggers all exist

---

### T5: Embedding Service — fastembed

**Goal:** Replace Ollama HTTP calls with in-process fastembed.
**Spec refs:** FR-21, FR-22, FR-23, FR-24, FR-25, FR-26, FR-27

**Files:**
- Modify: `backend/app/services/embedding_service.py`
- Modify: `backend/tests/unit/test_embedding.py`

**Steps:**

- [ ] Step 1: Write tests for fastembed-based embedding service
  ```python
  # tests/unit/test_embedding.py — rewrite

  import pytest
  from unittest.mock import patch, MagicMock
  import numpy as np

  @pytest.fixture
  def mock_fastembed():
      with patch("app.services.embedding_service.TextEmbedding") as mock_cls:
          mock_model = MagicMock()
          mock_model.embed.return_value = iter([np.zeros(384)])
          mock_cls.return_value = mock_model
          yield mock_model

  def test_embed_text_returns_384_dim(mock_fastembed):
      from app.services.embedding_service import EmbeddingService
      svc = EmbeddingService(cache_dir="/tmp/test-models")
      import asyncio
      result = asyncio.run(svc.embed_text("test query"))
      assert len(result) == 384
      mock_fastembed.embed.assert_called_once()

  def test_chunk_splitting():
      from app.services.embedding_service import EmbeddingService
      svc = EmbeddingService.__new__(EmbeddingService)
      svc.chunk_size = 5
      svc.chunk_overlap = 2
      chunks = svc._split_into_chunks("a b c d e f g h i j")
      assert len(chunks) >= 2
      # First chunk should be 5 words
      assert len(chunks[0].split()) == 5

  def test_no_ollama_url_attribute():
      from app.services.embedding_service import EmbeddingService
      svc = EmbeddingService.__new__(EmbeddingService)
      assert not hasattr(svc, "ollama_url")
  ```

- [ ] Step 2: Run tests — expect failures
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_embedding.py -v
  ```

- [ ] Step 3: Rewrite `embedding_service.py`
  - Replace `httpx` import with `from fastembed import TextEmbedding`
  - Constructor: accept `cache_dir: str`, `chunk_size: int = 512`, `chunk_overlap: int = 50`, `max_concurrent: int = 5`. Initialize `self._model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2", cache_dir=cache_dir)`.
  - `embed_text()`: wrap `self._model.embed([text])` in `asyncio.to_thread()`, return first result as `list[float]`
  - Keep `_split_into_chunks()` and `chunk_and_embed()` unchanged (they're pure Python)
  - Remove `_estimate_tokens()` if unused elsewhere

- [ ] Step 4: Run tests — expect passes
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_embedding.py -v
  ```

- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/embedding_service.py backend/tests/unit/test_embedding.py
  git commit -m "feat: replace Ollama with fastembed for in-process embeddings"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/embedding_service.py` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_embedding.py -v` — 3 passed

---

### T6: Repository Fixes

**Goal:** Fix PostgreSQL-specific code in repos that aren't part of the search rewrite.
**Spec refs:** FR-08

**Files:**
- Modify: `backend/app/db/repositories/reading_state_repo.py`

**Steps:**

- [ ] Step 1: Update `reading_state_repo.py`
  - Change `from sqlalchemy.dialects.postgresql import insert as pg_insert` to `from sqlalchemy.dialects.sqlite import insert as sqlite_insert`
  - Replace `pg_insert(ReadingState)` with `sqlite_insert(ReadingState)`
  - `.on_conflict_do_update(index_elements=["user_agent"], ...)` syntax is the same for SQLite dialect
  - Check if `.returning()` is used — if so, keep it (SQLite 3.35+ supports RETURNING)

- [ ] Step 2: Verify import works
  ```bash
  cd backend && uv run python -c "from app.db.repositories.reading_state_repo import ReadingStateRepo; print('OK')"
  ```

- [ ] Step 3: Commit
  ```bash
  git add backend/app/db/repositories/reading_state_repo.py
  git commit -m "fix: switch reading_state_repo from pg_insert to sqlite_insert"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/db/repositories/reading_state_repo.py` — no lint errors
- Import succeeds without errors

---

### T7: Search Service — FTS5 + sqlite-vec

**Goal:** Rewrite search repo and service for FTS5 BM25 and sqlite-vec semantic search.
**Spec refs:** FR-15, FR-16, FR-17, FR-18, FR-19

**Files:**
- Modify: `backend/app/db/repositories/search_repo.py`
- Modify: `backend/app/services/search_service.py`
- Create: `backend/tests/integration/test_search_sqlite.py`

**Steps:**

- [ ] Step 1: Write integration test for hybrid search round-trip
  ```python
  # tests/integration/test_search_sqlite.py
  import pytest
  from sqlalchemy import text

  @pytest.mark.asyncio
  async def test_bm25_search_finds_indexed_content(db_session):
      """Index a section, search by keyword, verify it's found."""
      from app.db.models import SearchIndex, SourceType
      # Insert a search index entry
      entry = SearchIndex(
          source_type=SourceType.SECTION,
          source_id=1,
          book_id=1,
          chunk_text="Machine learning is a subset of artificial intelligence",
          chunk_index=0,
      )
      db_session.add(entry)
      await db_session.flush()

      # BM25 search via FTS5
      from app.db.repositories.search_repo import SearchRepo
      repo = SearchRepo(db_session)
      results = await repo.bm25_search("machine learning", limit=10)
      assert len(results) >= 1
      assert any("machine learning" in r[0].chunk_text.lower() for r in results)

  @pytest.mark.asyncio
  async def test_semantic_search_finds_indexed_content(db_session):
      """Index a section with embedding, search semantically."""
      from app.db.models import SearchIndex, SourceType
      from sqlalchemy import text

      entry = SearchIndex(
          source_type=SourceType.SECTION,
          source_id=2,
          book_id=1,
          chunk_text="Neural networks process information in layers",
          chunk_index=0,
      )
      db_session.add(entry)
      await db_session.flush()

      # Insert embedding into search_vec
      # sqlite-vec requires binary serialization via serialize_float32()
      from sqlite_vec import serialize_float32
      fake_embedding = [0.1] * 384
      await db_session.execute(
          text("INSERT INTO search_vec(rowid, embedding) VALUES (:id, :emb)"),
          {"id": entry.id, "emb": serialize_float32(fake_embedding)}
      )

      from app.db.repositories.search_repo import SearchRepo
      repo = SearchRepo(db_session)
      results = await repo.semantic_search(fake_embedding, limit=10)
      assert len(results) >= 1
  ```

- [ ] Step 2: Rewrite `search_repo.py`
  - `bm25_search()`: use raw SQL `SELECT si.*, bm25(search_fts) as rank FROM search_index si JOIN search_fts ON si.id = search_fts.rowid WHERE search_fts MATCH :query ORDER BY rank LIMIT :limit`
  - `semantic_search()`: use raw SQL with sqlite-vec. Query embedding must be serialized via `serialize_float32()` before passing as parameter: `SELECT si.*, distance FROM search_index si JOIN (SELECT rowid, distance FROM search_vec WHERE embedding MATCH :query_embedding AND k = :limit) vec ON si.id = vec.rowid ORDER BY vec.distance`
  - `delete_by_book()` and `delete_by_source()`: add raw SQL to delete from `search_vec` by rowid before deleting from `search_index` (FTS5 handles its own deletion via trigger)

- [ ] Step 3: Update `search_service.py` index methods
  - Remove `tsvector=func.to_tsvector("english", chunk)` from all `SearchIndex(...)` constructors in `index_section`, `index_image_captions`, `index_annotation`, `index_concept`
  - After each `session.flush()` that creates SearchIndex entries, add raw SQL to insert embeddings into `search_vec` using `sqlite_vec.serialize_float32()` for binary serialization:
    ```python
    from sqlite_vec import serialize_float32
    await self.session.execute(
        text("INSERT INTO search_vec(rowid, embedding) VALUES (:id, :emb)"),
        {"id": entry.id, "emb": serialize_float32(embedding)}
    )
    ```
  - FTS5 content syncs automatically via triggers (no manual insert needed)

- [ ] Step 4: Run integration tests
  ```bash
  cd backend && uv run python -m pytest tests/integration/test_search_sqlite.py -v
  ```

- [ ] Step 5: Commit
  ```bash
  git add backend/app/db/repositories/search_repo.py backend/app/services/search_service.py backend/tests/integration/test_search_sqlite.py
  git commit -m "feat: rewrite search for FTS5 BM25 + sqlite-vec semantic search"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/db/repositories/search_repo.py app/services/search_service.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_search_sqlite.py -v` — 2 passed

---

### T8: Backup Service — File Copy

**Goal:** Rewrite backup from pg_dump to shutil.copy2 with prune.
**Spec refs:** FR-45, FR-46, FR-47, FR-48, FR-49, FR-50

**Files:**
- Modify: `backend/app/services/backup_service.py`
- Create: `backend/tests/unit/test_backup.py`

**Steps:**

- [ ] Step 1: Write tests
  ```python
  # tests/unit/test_backup.py
  import pytest
  import sqlite3
  from pathlib import Path

  @pytest.fixture
  def backup_env(tmp_path):
      db_path = tmp_path / "library.db"
      conn = sqlite3.connect(str(db_path))
      conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
      conn.execute("INSERT INTO test VALUES (1)")
      conn.commit()
      conn.close()
      backup_dir = tmp_path / "backups"
      backup_dir.mkdir()
      return db_path, backup_dir

  @pytest.mark.asyncio
  async def test_create_backup_copies_db(backup_env):
      db_path, backup_dir = backup_env
      from app.services.backup_service import BackupService
      svc = BackupService(db_path=db_path, backup_dir=backup_dir, max_backups=5)
      result = await svc.create_backup()
      assert result.exists()
      assert result.suffix == ".db"
      # Verify backup is a valid SQLite DB with our test data
      conn = sqlite3.connect(str(result))
      rows = conn.execute("SELECT * FROM test").fetchall()
      assert rows == [(1,)]

  @pytest.mark.asyncio
  async def test_prune_keeps_max_backups(backup_env):
      db_path, backup_dir = backup_env
      from app.services.backup_service import BackupService
      svc = BackupService(db_path=db_path, backup_dir=backup_dir, max_backups=2)
      await svc.create_backup()
      await svc.create_backup()
      await svc.create_backup()
      backups = svc.list_backups()
      assert len(backups) == 2

  @pytest.mark.asyncio
  async def test_restore_backup_overwrites_db(backup_env):
      db_path, backup_dir = backup_env
      from app.services.backup_service import BackupService
      svc = BackupService(db_path=db_path, backup_dir=backup_dir, max_backups=5)
      backup_path = await svc.create_backup()
      # Modify the original DB
      conn = sqlite3.connect(str(db_path))
      conn.execute("INSERT INTO test VALUES (2)")
      conn.commit()
      conn.close()
      # Restore
      await svc.restore_backup(str(backup_path))
      conn = sqlite3.connect(str(db_path))
      rows = conn.execute("SELECT * FROM test").fetchall()
      assert rows == [(1,)]  # Only original data
  ```

- [ ] Step 2: Run tests — expect failures
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_backup.py -v
  ```

- [ ] Step 3: Rewrite `backup_service.py`
  - Constructor: accept `db_path: Path`, `backup_dir: Path`, `max_backups: int = 5`
  - Remove `_parse_db_url()` entirely
  - `create_backup()`: `shutil.copy2(self.db_path, backup_path)` where `backup_path = self.backup_dir / f"library-{timestamp}.db"`. Call `self._prune()` after.
  - `list_backups()`: glob `library-*.db`, sort by mtime, return list of dicts with `path`, `filename`, `size_bytes`, `created`.
  - `restore_backup(path)`: validate SQLite header (first 16 bytes = `"SQLite format 3\000"`), then `shutil.copy2(path, self.db_path)`.
  - `_prune()`: sort backups by mtime, delete oldest beyond `max_backups`.

- [ ] Step 4: Run tests — expect passes
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_backup.py -v
  ```

- [ ] Step 5: Update APScheduler wiring in `api/main.py`
  - In `lifespan()`, update BackupService instantiation to use new constructor: `BackupService(db_path=Path(settings.data.directory) / "library.db", backup_dir=Path(settings.backup.directory), max_backups=settings.backup.max_backups)`
  - Update APScheduler trigger to use `settings.backup.frequency` instead of `settings.backup.schedule_hours`

- [ ] Step 6: Commit
  ```bash
  git add backend/app/services/backup_service.py backend/app/api/main.py backend/tests/unit/test_backup.py
  git commit -m "feat: rewrite backup service from pg_dump to file copy with prune"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/backup_service.py app/api/main.py` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_backup.py -v` — 3 passed

---

### T9: Multi-Provider LLM

**Goal:** Create CodexCLIProvider, add provider factory, auto-detection.
**Spec refs:** FR-28, FR-29, FR-30, FR-31, FR-32, FR-33

**Files:**
- Create: `backend/app/services/summarizer/codex_cli.py`
- Modify: `backend/app/cli/deps.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/api/routes/health.py`
- Test: `backend/tests/unit/test_llm_provider.py` (create)

**Steps:**

- [ ] Step 1: Write tests for provider factory and auto-detection
  ```python
  # tests/unit/test_llm_provider.py
  import pytest
  from unittest.mock import patch

  def test_detect_claude_only():
      from app.services.summarizer import detect_llm_provider
      with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/claude" if cmd == "claude" else None):
          provider = detect_llm_provider()
          assert provider == "claude"

  def test_detect_codex_only():
      from app.services.summarizer import detect_llm_provider
      with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/codex" if cmd == "codex" else None):
          provider = detect_llm_provider()
          assert provider == "codex"

  def test_detect_none():
      from app.services.summarizer import detect_llm_provider
      with patch("shutil.which", return_value=None):
          provider = detect_llm_provider()
          assert provider is None

  def test_create_provider_claude():
      from app.services.summarizer import create_llm_provider
      with patch("shutil.which", return_value="/usr/bin/claude"):
          provider = create_llm_provider("claude")
          assert provider is not None
          assert "claude" in type(provider).__name__.lower() or hasattr(provider, 'generate')

  def test_create_provider_null():
      from app.services.summarizer import create_llm_provider
      provider = create_llm_provider(None)
      assert provider is None
  ```

- [ ] Step 2: Run tests — expect failures
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_llm_provider.py -v
  ```

- [ ] Step 3: Create `codex_cli.py`
  - Clone `claude_cli.py` structure
  - Constructor: accept same params but `cli_command="codex"` default
  - `generate()`: build Codex CLI command (adapt flags as needed for Codex CLI syntax)
  - `generate_with_image()`: adapt for Codex CLI

- [ ] Step 4: Create `backend/app/services/summarizer/__init__.py` with factory functions
  ```python
  def detect_llm_provider() -> str | None:
      """Auto-detect available CLI providers."""
      import shutil
      if shutil.which("claude"):
          return "claude"
      if shutil.which("codex"):
          return "codex"
      return None

  def create_llm_provider(provider: str | None, **kwargs) -> LLMProvider | None:
      if provider == "claude":
          return ClaudeCodeCLIProvider(**kwargs)
      elif provider == "codex":
          return CodexCLIProvider(**kwargs)
      return None
  ```

- [ ] Step 5: Update `cli/deps.py` and `api/deps.py`
  - In both files, replace hard `ClaudeCodeCLIProvider(...)` with `create_llm_provider(settings.llm.provider, ...)`.
  - When provider is `None` or `"auto"`, call `detect_llm_provider()` first.
  - When result is `None`, set `services["llm"] = None` and skip summarizer/eval service creation.

- [ ] Step 6: Update `health.py`
  - Extend response to include `llm_provider`, `llm_available`, `database`, `embedding_model`

- [ ] Step 7: Run tests — expect passes
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_llm_provider.py -v
  ```

- [ ] Step 8: Commit
  ```bash
  git add backend/app/services/summarizer/ backend/app/cli/deps.py backend/app/api/deps.py backend/app/api/routes/health.py backend/tests/unit/test_llm_provider.py
  git commit -m "feat: multi-provider LLM support with auto-detection (Claude + Codex)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/summarizer/ app/cli/deps.py app/api/deps.py app/api/routes/health.py` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_llm_provider.py -v` — 5 passed

---

### T10: CORS + LAN Access

**Goal:** Auto-detect LAN IPs and build dynamic CORS origin list.
**Spec refs:** FR-35, FR-36, FR-37, FR-38

**Files:**
- Modify: `backend/app/api/main.py`
- Test: `backend/tests/unit/test_cors.py` (create)

**Steps:**

- [ ] Step 1: Write tests
  ```python
  # tests/unit/test_cors.py
  import pytest
  from unittest.mock import patch

  def test_cors_includes_localhost():
      from app.api.main import build_cors_origins
      origins = build_cors_origins(port=8000)
      assert "http://localhost:8000" in origins
      assert "http://127.0.0.1:8000" in origins

  def test_cors_includes_lan_ip():
      from app.api.main import build_cors_origins
      with patch("socket.getaddrinfo", return_value=[
          (2, 1, 6, '', ('192.168.1.50', 0)),
      ]):
          origins = build_cors_origins(port=8000)
          assert "http://192.168.1.50:8000" in origins

  def test_cors_extra_origins_env(monkeypatch):
      from app.api.main import build_cors_origins
      monkeypatch.setenv("BOOKCOMPANION_CORS_EXTRA_ORIGINS", "http://myhost:3000,http://other:9000")
      origins = build_cors_origins(port=8000)
      assert "http://myhost:3000" in origins
      assert "http://other:9000" in origins
  ```

- [ ] Step 2: Run tests — expect failures
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_cors.py -v
  ```

- [ ] Step 3: Implement `build_cors_origins()` in `api/main.py`
  - Use `socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)` to get local IPs
  - Filter out `127.x.x.x` loopback
  - Build list: localhost variants + LAN IPs, all with `http://` and port
  - Read `BOOKCOMPANION_CORS_EXTRA_ORIGINS` env var, split by comma, merge
  - Replace hardcoded CORS origins with call to `build_cors_origins(settings.network.port)`

- [ ] Step 4: Run tests — expect passes
  ```bash
  cd backend && uv run python -m pytest tests/unit/test_cors.py -v
  ```

- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/main.py backend/tests/unit/test_cors.py
  git commit -m "feat: auto-detect LAN IPs for dynamic CORS origins"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/main.py` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_cors.py -v` — 3 passed

---

### T11: Init + Serve Commands

**Goal:** Rewrite init for SQLite/fastembed, create serve command.
**Spec refs:** FR-39, FR-40, FR-41, FR-25, FR-43

**Files:**
- Modify: `backend/app/cli/commands/init_cmd.py`
- Create: `backend/app/cli/commands/serve_cmd.py`
- Modify: `backend/app/cli/main.py`

**Steps:**

- [ ] Step 1: Rewrite `init_cmd.py`
  - Remove Docker check and `docker compose up -d`
  - Remove Ollama check and `ollama pull`
  - Keep Calibre check (optional)
  - Add: create data directory via `platformdirs`
  - Add: run Alembic migrations on the SQLite DB
  - Add: warm-up fastembed model download: `from fastembed import TextEmbedding; TextEmbedding("sentence-transformers/all-MiniLM-L6-v2", cache_dir=...)`
  - Add: detect and report LLM providers via `detect_llm_provider()`

- [ ] Step 2: Create `serve_cmd.py`
  ```python
  import typer
  import uvicorn
  from app.config import Settings

  def serve(
      port: int = typer.Option(8000, "--port", "-p"),
      host: str = typer.Option("0.0.0.0", "--host"),
  ):
      """Start the Book Companion web server."""
      settings = Settings()
      db_path = Path(settings.data.directory) / "library.db"
      if not db_path.exists():
          from app.cli.commands.init_cmd import init
          init()  # auto-init on first run
      typer.echo(f"Serving at http://localhost:{port}")
      # Print LAN IP if available
      uvicorn.run("app.api.main:app", host=host, port=port)
  ```

- [ ] Step 3: Register in `main.py`
  - `app.command("serve")(serve_cmd.serve)`

- [ ] Step 4: Verify commands work
  ```bash
  cd backend && uv run bookcompanion init --help
  cd backend && uv run bookcompanion serve --help
  ```

- [ ] Step 5: Commit
  ```bash
  git add backend/app/cli/commands/init_cmd.py backend/app/cli/commands/serve_cmd.py backend/app/cli/main.py
  git commit -m "feat: rewrite init for SQLite/fastembed, add serve command"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/cli/commands/init_cmd.py app/cli/commands/serve_cmd.py` — no lint errors
- `cd backend && uv run bookcompanion serve --help` — shows help with --port and --host options

---

### T12: Remove Docker + Update Deps

**Goal:** Delete Docker files and Docker-specific code.
**Spec refs:** FR-42, FR-43

**Files:**
- Delete: `Dockerfile`, `docker-compose.yml`, `.env.example`
- Modify: `backend/app/cli/deps.py` (remove Docker health check message)

**Steps:**

- [ ] Step 1: Delete Docker files
  ```bash
  rm -f Dockerfile docker-compose.yml .env.example
  ```

- [ ] Step 2: Update `cli/deps.py`
  - In `check_db_health()`: remove any Docker-specific messaging (e.g., "Check: docker compose ps")
  - Update to check SQLite file existence instead

- [ ] Step 3: Clean up any remaining Docker references
  ```bash
  cd backend && grep -r "docker" app/ --include="*.py" -l
  ```
  Fix any remaining references found.

- [ ] Step 4: Commit
  ```bash
  git add -A
  git commit -m "chore: remove Docker files and Docker-specific code paths"
  ```

**Inline verification:**
- `ls Dockerfile docker-compose.yml .env.example 2>/dev/null` — no files found
- `cd backend && grep -r "docker" app/ --include="*.py" | wc -l` — 0

---

### T13: Test Fixture Adaptation

**Goal:** Fix conftest.py and existing tests to work with SQLite.
**Spec refs:** Spec section 10.0

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: various test files as needed

**Steps:**

- [ ] Step 1: Rewrite `conftest.py`
  - Remove `TEST_DB_URL` constant (was hardcoded PostgreSQL)
  - Create `test_db_path` fixture (session-scoped) that returns `tmp_path_factory.mktemp("db") / "test.db"`
  - Update `test_settings` fixture: set `BOOKCOMPANION_DATABASE__URL` to `sqlite+aiosqlite:///{test_db_path}`
  - Update `engine` fixture:
    ```python
    @pytest.fixture(scope="session")
    async def engine(test_db_path):
        url = f"sqlite+aiosqlite:///{test_db_path}"
        eng = create_async_engine(url, connect_args={"check_same_thread": False})
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Create FTS5 + sqlite-vec virtual tables
            await conn.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                    chunk_text, content=search_index, content_rowid=id,
                    tokenize='porter unicode61'
                )
            """))
            # ... FTS5 triggers (same as in T4 migration) ...
            await conn.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_vec USING vec0(
                    embedding float[384]
                )
            """))
        yield eng
        await eng.dispose()
    ```
  - Keep `db_session` fixture using rollback isolation (same pattern as before)

- [ ] Step 2: Run unit tests and fix failures
  ```bash
  cd backend && uv run python -m pytest tests/unit/ -v --tb=short 2>&1 | head -100
  ```
  Fix each failure category:
  - Import errors from pgvector/postgresql → already fixed in T3
  - Ollama HTTP mocks → already fixed in T5
  - Config test env vars → may need updates for new defaults

- [ ] Step 3: Run integration tests and fix failures
  ```bash
  cd backend && uv run python -m pytest tests/integration/ -v --tb=short 2>&1 | head -100
  ```

- [ ] Step 4: Run e2e tests and fix failures
  ```bash
  cd backend && uv run python -m pytest tests/e2e/ -v --tb=short 2>&1 | head -100
  ```

- [ ] Step 5: Run full test suite
  ```bash
  cd backend && uv run python -m pytest tests/ -v
  ```

- [ ] Step 6: Commit
  ```bash
  git add backend/tests/
  git commit -m "fix: adapt test fixtures and tests for SQLite backend"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/ -v` — all tests pass, 0 failures

---

### T14: Frontend Settings — LLM Provider

**Goal:** Add LLM Provider section to the settings page.
**Spec refs:** FR-34

**Files:**
- Modify: `frontend/src/api/settings.ts`
- Create: `frontend/src/components/settings/LlmSettings.vue`
- Modify: `frontend/src/views/SettingsView.vue`

**Steps:**

- [ ] Step 1: Update `AppSettings` type in `settings.ts`
  - Add `provider: string` to the `llm` interface (if not already there — verify current shape)
  - Ensure `command` and `config_dir` fields exist in `llm`

- [ ] Step 2: Create `LlmSettings.vue`
  - Show detected LLM provider(s)
  - Dropdown to select active provider: Claude, Codex, or None
  - Text input for command path override
  - Text input for config directory override
  - Save button that calls `settingsStore.saveSettings({ llm: { ... } })`

- [ ] Step 3: Register in `SettingsView.vue`
  - Add `'llm'` to sidebar sections
  - Add `v-else-if="section === 'llm'"` block with `<LlmSettings />`

- [ ] Step 4: Build and type-check
  ```bash
  cd frontend && npm run type-check && npm run build
  ```

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/
  git commit -m "feat: add LLM Provider section to settings page"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no type errors
- `cd frontend && npm run build` — build succeeds

---

### T15: Final Verification

**Goal:** Verify the entire implementation works end-to-end.

- [ ] **Lint & format:** `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] **Full test suite:** `cd backend && uv run python -m pytest tests/ -v` — expect all tests pass, 0 failures
- [ ] **Fresh init:** `rm -rf ~/.local/share/bookcompanion && cd backend && uv run bookcompanion init` — creates data dir, SQLite DB, downloads embedding model
- [ ] **Serve:** `cd backend && uv run bookcompanion serve --port 8001 &` — starts without errors, prints URL
- [ ] **Health check:** `curl -s http://localhost:8001/api/v1/health | python3 -m json.tool` — returns `{"status": "ok", "llm_provider": "claude", "llm_available": true, "database": "sqlite", "embedding_model": "all-MiniLM-L6-v2"}`
- [ ] **CORS headers:** `curl -v -H "Origin: http://192.168.1.100:8001" http://localhost:8001/api/v1/health 2>&1 | grep -i access-control` — returns CORS headers
- [ ] **No Docker files:** `ls Dockerfile docker-compose.yml .env.example 2>/dev/null` — no files found
- [ ] **Frontend builds:** `cd frontend && npm run build` — succeeds
- [ ] **Manual spot check:** Open `http://localhost:8001` in browser. Verify settings page has LLM Provider section. Verify library page loads.

**Cleanup:**
- [ ] Kill background serve process
- [ ] Remove test data: `rm -rf ~/.local/share/bookcompanion`
- [ ] Update `CLAUDE.md` to reflect SQLite/fastembed stack, remove Docker references, add serve command docs

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1    | FR-50 APScheduler wiring missing; sqlite-vec embedding format unclear; T13 conftest underspecified | Added APScheduler update step to T8; added JSON serialization note for sqlite-vec in T7; fleshed out conftest.py rewrite in T13 with code example |
| 2    | Cosmetic only — task sizing acceptable, dependency ordering correct, type consistency confirmed | No changes needed |
| 3 (execution) | **sqlite-vec blocked**: macOS system Python compiled without `enable_load_extension`. pysqlite3-binary has no macOS arm64 wheels. | **Pivoted to in-Python cosine similarity**: embeddings stored as BLOB (struct.pack float32) in SearchIndex.embedding column. Semantic search loads embeddings and computes cosine sim via numpy. Removed sqlite-vec and pysqlite3-binary deps, added numpy. FTS5 for BM25 unchanged. This eliminates T2 extension loading and simplifies T7 search queries. |
