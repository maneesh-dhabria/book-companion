# Changelog

## 2026-04-25 — Summary Markdown Export (v1.6)

- New on the book detail page: **Export summary**, **Copy as Markdown**, and **Customize…** actions next to **Read**. One-click downloads a portable Markdown file (`<slug>-summary-YYYYMMDD.md`); Copy writes the same bytes to the clipboard. Customize opens a modal with toggles for Book summary, Table of contents, Highlights & notes, and per-section selection (tri-state master toggle, "N of M sections summarized" footer, sections without summaries hidden).
- The CLI gains four new flags on `export book`: `--no-book-summary`, `--no-toc`, `--no-annotations`, and `--exclude-section <id>` (repeatable). Combining any of them with `--format json` exits status 2 — JSON exports remain full-fidelity. Invalid `--exclude-section <id>` exits 1 with `Error: section <id> does not belong to book <id>.`
- The Markdown export shape changed: front matter (title, author(s), exported date) → optional anchored Table of Contents → optional book summary → per-section H2 with annotations rendered inline → optional `## Notes` footer for book-scope notes. In-app image URLs (`/api/v1/images/{id}`) are rewritten to `[Image: <alt>]` placeholders so the file renders cleanly in Obsidian, GitHub web preview, and VS Code preview.
- TOC anchors follow GitHub-flavored Markdown rules (Unicode-aware; duplicate slugs disambiguated `bare → -1 → -2`); filenames are ASCII-only with a `book-<id>-summary-<date>.md` fallback for non-ASCII titles.
- **Breaking**: library-level Markdown export is removed. `bookcompanion export library --format markdown` exits status 2; `GET /api/v1/export/library?format=markdown` returns `410 Gone`. Use `--format json` for full-library backups, or `export book` per book.
- **Breaking**: the Settings → Backup & Export library-export dropdown is replaced with a single `Export library (JSON)` button — JSON is now the only supported library export.
- New response headers on `GET /api/v1/export/book/{id}?format=markdown`: `Cache-Control: private, max-age=0` and `X-Empty-Export: true|false` so the UI can pick the right toast variant.
- Toast outlet (`ToastContainer`) now mounts in `AppShell` with `aria-live=polite` and per-toast `role=status`. Every export action confirms with a toast — success ("Summary exported as <filename>"), empty ("Summary exported (empty)"), copy success, network failure, or clipboard permission failure.

**References:** [requirements](requirements/2026-04-25-summary-markdown-export.md), [spec](specs/2026-04-25-summary-markdown-export-spec.md), [plan](plans/2026-04-25-summary-markdown-export-implementation-plan.md)

## 2026-04-25 — V1.5 Reader UX Polish Followups (v1.5.1)

- Settings save now shows a global toast top-right (success or error) instead of leaving you to wonder whether the PATCH landed; the Save button shows an inline spinner while in flight.
- Strict validation on the Settings API: unknown nested keys, type mismatches, or any invalid field rejects the whole PATCH (`HTTP 400` with FastAPI-shape `detail`) and leaves both in-memory state and the on-disk YAML untouched. The same rule applies to `bookcompanion config set <key> <value>` — invalid values exit non-zero with a stderr message and don't write a corrupted YAML.
- The legacy LLM "Config Directory" field has been retired everywhere — `LLMConfig.config_dir` and the `BOOKCOMPANION_LLM__CONFIG_DIR` env var are gone. Existing `settings.yaml` files containing the key are silently ignored on load. **Breaking**: if you depended on `CLAUDE_CONFIG_DIR` injection from this field, point your CLI at the right profile via your shell environment instead.
- Reader theme model is one applied state — either a system preset or one browser-local Custom slot. **Breaking**: user-created server-side presets and the `reading_presets.is_system` / `is_active` columns are removed by the new `v1_5_1_collapse_reading_presets` migration. Any preset that was active at upgrade time is captured into a sidecar file the frontend reads exactly once on first launch so your visual settings survive the migration. POST/PATCH/DELETE/activate routes on `/api/v1/reading-presets` are gone; GET returns `{items: [...]}` (no `default_id`, no per-item `is_system`/`is_active`).
- `+ Add tag` lives behind a tiny text button instead of a persistent input. Click to expand to an underline-only input that supports Enter to commit (clears + stays open), Esc/blur-empty to dismiss, and blur-with-content to commit + dismiss. Tag names exceeding 64 characters are truncated with a one-shot warning toast.
- Quick-search palette (`⌘K`) is mounted once at app boot via `v-show` instead of `v-if`, so the first keystroke after open is never dropped on a not-yet-mounted input. The 200ms hand-rolled debounce is replaced with a `useDebounceFn(300)` composable that auto-cancels on unmount; opening the palette always clears any prior query and re-focuses the input.
- The Summarize / Retry button moved off the reader header onto the book overview page (`/books/:id`), next to the Read CTA. Clicking it disables the button and shows an inline spinner until the POST resolves; failures fire an error toast with the underlying message.

## 2026-04-19 — Book Reader UX Polish

- Reopening a book lands on the first real chapter instead of the Copyright page, respecting URL → saved position → first summarizable section → section[0] precedence.
- Table of Contents now groups Copyright, Acknowledgments, Dedication, Title Page, Contents, Colophon, Cover, and Part dividers under a collapsed "Front Matter" accordion; real chapters sit at the top level.
- Book header reads "N of M sections summarized" counting only summarizable types, with a *Summarize pending sections* button that fills the remainder over SSE and skips front-matter automatically.
- The Summary tab now renders actual summary markdown when a section has one, and a typed empty-state ("Summary not applicable", "Not yet summarized", "Generating…", or "Failed: …/Retry") for every other case — no more "Generating…" stuck after skipped sections or failed runs.
- Footnote/anchor links render as plain text; external links open in a new tab with `rel="noopener noreferrer"`; `javascript:` and unknown-scheme links never render as clickable anchors.
- Two one-time data migrations run on next startup: legacy `__IMG_PLACEHOLDER__:…__ENDIMG__` tokens are rewritten to `/api/v1/images/{id}` URLs so images render on existing books, and every section is re-classified so pre-existing Copyright-misclassified-as-chapter rows snap into place (with auto-generated front-matter summaries pruned; user-curated summaries preserved).
- New `POST /api/v1/books/{id}/summarize` request fields: `scope` (`"all"` | `"pending"` | `"section"`) and `section_id`. Section responses now include `summary_md` and `is_summarizable`. Book responses now include `summary_progress: {summarized, total}`.
- SSE events (`processing_started`, `section_started`, `section_completed`, `section_failed`, `section_skipped`, `section_retrying`) all carry `section_id` so the UI can update individual sections without a full refetch; a 30-second grace window plus 5-second polling fallback keeps the progress counter honest even when the SSE connection drops mid-job.

## 2026-04-13 — Post-Install Runtime Quality

- Concurrent reads/writes no longer fail with `database is locked` 500s — SQLite now waits up to 5s under write contention (`PRAGMA busy_timeout=5000`), and the pathological case returns a clean 503 "Database busy, please retry" instead of a SQLAlchemy traceback.
- Partial summarize progress is now preserved: each section commits independently, so killing the server mid-run keeps the completed sections and a resumed run skips them (no duplicate LLM calls).
- Cleaner browser console on load — removed the `/reading-presets/active` request that 404'd on first use; the list endpoint now returns `{items, default_id}` in a single fetch.
- Missing images/PDFs/fonts return proper 404s instead of HTML — the SPA-fallback no longer swallows asset requests with known binary extensions.
- Book images now render in the reader: parse-time placeholders are rewritten to `/api/v1/images/{id}` on store, and a new `GET /api/v1/images/{id}` endpoint serves the bytes with `Cache-Control: immutable`.

## 2026-04-12 — Packaging Hardening (sdist + programmatic migrations)

- `uv build` now produces both sdist and wheel in a single invocation. Users installing from sdist (e.g., platforms without a prebuilt wheel) no longer need Node.js — the SPA is built at sdist-creation time and shipped inside the tarball.
- `bookcompanion init` runs migrations programmatically via `alembic.command.upgrade()` — no `uv`, no `alembic` on `$PATH`, no `cd backend` assumption. Migrations, Alembic config, and the CLI all ship inside the installed package under `app/migrations/`.
- Migrations run in a worker thread so `init` (already inside an `asyncio.run` via `@async_command`) doesn't hit "nested `asyncio.run()`" when env.py spins up its own loop.
- `backend/scripts/verify_packaging.sh` + a `@pytest.mark.slow` test now validate the full build → install → run flow locally (twine, wheel-contents lint, fresh-venv install from both wheel and sdist, isolated `uv tool install`, optional Docker clean-room). Run via `bash scripts/verify_packaging.sh` before any release.

## 2026-04-12 — Bundled Web UI in the Wheel

- `pip install bookcompanion` now ships with the Vue web UI included — `bookcompanion serve` immediately serves the UI at `http://localhost:8000/` with no extra build step
- The Vue SPA is compiled and bundled during wheel creation by a custom Hatchling build hook (`npm ci && npm run build`, copied into `app/static/`)
- Static assets are served with cache-friendly headers: `no-cache` on `index.html`, `public, max-age=31536000, immutable` on hashed files under `/assets/`
- SPA deep links (e.g., `/library/<id>`) now fall back to `index.html` so direct-load and refresh work
- New `bookcompanion serve --api-only` flag (also `BOOKCOMPANION_API_ONLY=1`) starts the JSON API without mounting the SPA — useful for local dev against the Vite dev server
- Running `serve` from a source checkout without a built frontend now prints a clear, actionable error with two valid workflows instead of silently 404-ing the UI

## 2026-04-12 — Zero-Dependency Install: SQLite, in-process embeddings, multi-provider LLM

**Install & Run**
- New `bookcompanion serve` command starts the web UI with one command — no Docker, no separate database, no background services
- First run auto-initializes the data directory, runs migrations, and downloads the embedding model (~23MB, one-time)
- Data lives in a standard OS location (`~/.local/share/bookcompanion/` on Linux, `~/Library/Application Support/bookcompanion/` on macOS, `%LOCALAPPDATA%/bookcompanion/` on Windows); override with `BOOKCOMPANION_DATA__DIRECTORY`
- Removed Docker entirely — `Dockerfile`, `docker-compose.yml`, and `.env.example` are gone

**Embedded Database**
- Replaced PostgreSQL + pgvector (Docker) with embedded SQLite — your whole library is now a single `library.db` file
- Full-text search via SQLite FTS5 (BM25 ranking, same quality as before)
- Semantic search via in-process cosine similarity (no external vector DB required)

**In-Process Embeddings**
- Replaced Ollama with `fastembed` running in the Python process — embedding generation no longer needs a separate server
- Default model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, ~23MB, ~2ms per query on CPU)

**Multi-Provider LLM Support**
- Auto-detects Claude Code CLI or Codex CLI on `$PATH` — whichever is installed becomes the default
- Configure provider from the web UI Settings → LLM Provider section (or via `config.yaml`)
- When no LLM CLI is installed, library/search/reading/annotations still work; summarization is disabled with a clear UI banner
- Summarization and evaluation are fully wired in the web API — click "Summarize" in the UI and it runs end-to-end with eval and auto-retry on failure

**LAN Access**
- Web UI is now accessible from other devices on your network without configuration — visit `http://<your-desktop-ip>:8000` from your tablet or phone
- CORS auto-detects all non-loopback IPv4 addresses at startup
- `BOOKCOMPANION_CORS_EXTRA_ORIGINS` env var lets you add extra origins if needed

**Backups**
- Backups are now plain SQLite file copies to a configurable directory (default `{data_dir}/backups/`)
- Point the backup directory at your Google Drive / Dropbox / iCloud sync folder for free cloud backups — no OAuth or API keys needed
- Configure frequency (hourly/daily/weekly) and retention (`max_backups`) from Settings

**Fixed**
- Web UI "Summarize" button now actually runs — was crashing silently since the web interface shipped (wrong kwargs between API route and summarizer service)
- Summarization no longer crashes with `MissingGreenlet` on books with images (deferred `Image.data` column now loaded eagerly)
- Invalid preset names return a clear 400 error before queuing a background job (was silently failing mid-job)
- Job status correctly reports `FAILED` instead of silent `COMPLETED` when all sections fail
- Backup download/delete endpoints now find backup files (was looking for `.sql`, files are `.db`)

**References**
- [Requirements](requirements/2026-04-11-self-contained-packaging.md)
- [Spec](specs/2026-04-12-zero-dependency-packaging-spec.md)
- [Implementation plan](plans/2026-04-12-zero-dependency-packaging-implementation-plan.md)

## 2026-04-11 — Web Interface: Full-stack Vue.js UI for reading, summarization, and library management

**Library & Navigation**
- Browse your book library in grid, list, or table view with cover images, author names, status badges, and section counts
- Filter by status (parsed, summarizing, completed) and format (EPUB, PDF, MOBI); sort by recent, title, or date added
- Save custom filtered views with the View Tabs system (e.g. "Strategy Books", "To Summarize")
- Command palette (Cmd+K) provides instant search across books, sections, and concepts with grouped results
- Icon rail navigation on desktop; bottom tab bar on mobile with 5 tabs (Library, Concepts, Search, Notes, Settings)

**Book Reader**
- Read original book content with markdown rendering, section-by-section navigation via arrows or table-of-contents dropdown
- Toggle between Original and Summary views when summaries are available
- Reader settings popover: font family, font size, line spacing, content width, and theme (Light, Sepia, Dark, OLED, Dracula)
- Reading presets (Comfortable, Compact, Night Reading, Study Mode) for quick configuration
- Cross-device reading position sync — open on your phone and see a "Continue where you left off" banner showing the last section you read on desktop

**Annotations & AI Chat**
- Highlight text in the reader to create annotations with a floating toolbar — supports highlight, note, bookmark, and question types
- Context sidebar (toggle with ☰) shows annotations for the current section and an AI Chat panel
- AI Chat: create conversation threads about the book, ask questions, and get AI-powered answers using your configured Claude instance
- Annotations page: browse all annotations across all books, filter by type

**Upload & Processing**
- 5-step upload wizard: drag-and-drop file selection, metadata confirmation, structure review (section table with types), preset picker (Balanced, Brief, Detailed, Practitioner), and processing kickoff
- Background summarization with processing progress tracking via server-sent events (SSE)
- Supports EPUB, PDF, and MOBI uploads

**Concepts & Search**
- Concepts explorer: browse key concepts extracted from summarized books with definitions, source sections, and edit/reset controls
- Full search results page with keyword highlighting and relevance scoring
- Recent search history

**Settings**
- 5-section settings page with sidebar navigation (horizontal tabs on mobile):
  - **General**: "Read on your phone" LAN toggle with QR code, cost estimates toggle, read-only LLM config display
  - **Database**: connection info with masked password, migration status with "Run Migrations" button, table row counts
  - **Presets**: browse system summarization presets with detail view
  - **Reading**: default preset selector, reading preset chips, custom CSS textarea
  - **Backup & Export**: create/download/delete database backups, export library as JSON or Markdown
- Scheduled backups via APScheduler (configurable interval via settings API)
- Settings persist to YAML config file with atomic write (temp file + rename)

**Mobile**
- Responsive layout: icon rail sidebar on desktop (>=1024px), bottom tab bar on mobile (<768px)
- Bottom sheet component with 3 snap points (30%/50%/90%), drag gestures on handle, backdrop click and Escape to dismiss
- Touch interaction composable with 500ms long-press detection

**Accessibility & Polish**
- Keyboard focus indicators (`:focus-visible` outlines), `prefers-reduced-motion` disables all animations
- ARIA roles and labels on navigation components
- Skeleton loaders for all data-loading states (grid, list, table, reader, settings, sidebar variants)
- Empty states with illustrations and CTAs for library, search, annotations, and concepts
- Error boundary component catches render errors with "Connection lost" / "Try again" UI

**Docker & Deployment**
- Multi-stage Dockerfile: Node.js frontend build + Python runtime with pg_dump, non-root user, and HEALTHCHECK
- Docker Compose with health checks, restart policies, log rotation (10MB/3 files), 1GB memory limit
- Data stored in local bind mounts (`./data/postgres`, `./data/backups`, `./data/config`) — visible on host, survives container recreation
- Production override file (`docker-compose.prod.yml`) for WARNING-level logging

**LLM Configuration**
- Claude CLI provider now supports `config_dir` setting — set `CLAUDE_CONFIG_DIR` via config instead of requiring shell functions or wrapper scripts. Just set `cli_command: claude` and `config_dir: ~/.claude-personal`

**References:**
- [Requirements](docs/requirements/2026-04-10_web_interface_v1_requirements.md)
- [Spec](docs/specs/2026-04-10_web_interface_v1_spec.md)
- [Phase 1 plan](docs/plans/2026-04-10-web-interface-phase1-implementation-plan.md)
- [Phase 2 plan](docs/plans/2026-04-10-web-interface-phase2-implementation-plan.md)
- [Phase 3 plan](docs/plans/2026-04-10-web-interface-phase3-implementation-plan.md)

## 2026-04-10 — V1.3: Eval system overhaul — fewer false positives, auto-retry, diagnostics

- Three eval checks (length, key concepts, image references) now run instantly without LLM calls — faster, cheaper, and 100% reproducible
- Summarization presets can now skip eval checks that don't apply to their format — `practitioner_bullets` no longer fails on "missing Key Concepts heading"
- Eval now receives prior section summaries as context, so cross-chapter references are no longer flagged as hallucinations
- Summaries that fail critical or important eval checks are automatically re-summarized with targeted fix instructions; use `--no-retry` to disable
- Each eval failure now includes a root cause classification and a one-line fix suggestion, visible in `eval <book_id> <section_id>`
- Book-level summaries are now evaluated with the same assertion battery (adapted for book scope); view with `eval <book_id> --book-only`
- Re-importing a book preserves eval history — traces are marked stale rather than deleted; a confirmation prompt shows trace/summary counts before proceeding
- Sections are auto-classified by type (chapter, glossary, appendix, etc.) during parsing; glossary and reference sections get relaxed completeness thresholds
- Section types can be corrected in the editor via `type <index> <type_name>`
- Paraphrased quotes (text in quotation marks that doesn't match the source) are detected and shown as warnings in `summary show`
- Prompt guidance added for quote attribution accuracy and numeric precision (percentages vs multipliers)

**References:**
- [V1.3 spec](docs/specs/2026-04-05_v1_3_eval_improvements_spec.md)
- [V1.3 requirements](docs/requirements/2026-04-05_v1_3_eval_improvements.md)
- [V1.3 implementation plan](docs/plans/2026-04-07_v1_3_eval_improvements_implementation.md)

## 2026-04-04 — V1.2: EPUB parsing fixes, markdown output, eval display

- Fixed: EPUB books that split chapters across multiple files now parse correctly — chapter content is aggregated from all spine items between TOC entries, not just the first file. Books like "Understanding Michael Porter" went from ~100 chars per chapter to 25K-46K chars
- Fixed: Book and section summaries now output clean markdown instead of JSON-wrapped text. Existing JSON-format summaries are still readable (backward compatible)
- Sections with very little real content (< 200 chars after stripping XML/images) are automatically skipped during summarization instead of producing hallucinated summaries. Use `--force` to override
- `summary list` now shows separate "Status" and "Results" columns (e.g., "passed", "3/5") instead of a single "Eval" dash. Distinguishes between "eval not run" and "eval failed"
- After summarizing with `--skip-eval`, a hint reminds you to run `bookcompanion eval <book_id>` separately

**References:**
- Requirements: [`docs/requirements/2026-04-04_v1_2_bugfixes_and_improvements.md`](docs/requirements/2026-04-04_v1_2_bugfixes_and_improvements.md)
- Spec: [`docs/specs/2026-04-04_v1_2_bugfixes_and_improvements_spec.md`](docs/specs/2026-04-04_v1_2_bugfixes_and_improvements_spec.md)
- Plan: [`docs/plans/2026-04-04_v1_2_bugfixes_implementation.md`](docs/plans/2026-04-04_v1_2_bugfixes_implementation.md)

## 2026-04-04 — V1.1: Preset-based summarization, summary log, section editing

- Summarize books using named presets (`--preset practitioner_bullets`, `--preset executive_brief`, etc.) that control style, audience, compression, and content focus — or override individual facets with `--style`, `--audience`, `--compression`, `--content-focus` flags
- 5 built-in presets: Practitioner Bullets, Academic Detailed, Executive Brief, Study Guide, Tweet Thread. Create your own with `bookcompanion preset create`
- Multiple summaries are now saved per section — re-summarize with a different preset and both versions are kept. Switch between them with `summary set-default`
- New `summary` commands: `summary list` shows all summaries for a book, `summary compare` shows two summaries side-by-side with concept diff, `summary show` displays full provenance (preset, model, compression ratio, latency)
- New `read` command: view original section content with `bookcompanion read <book_id> <section_id>`, optionally alongside its summary with `--with-summary`
- Quality validation on book import: 10 automatic checks flag empty, short, duplicate, or non-content sections with suggested fixes. Interactive editing REPL lets you merge, split, reorder, or delete sections before or after saving
- Re-running the same preset skips already-summarized sections automatically. Use `--force` to regenerate everything

**References:**
- Spec: [`docs/specs/2026-04-02_book_companion_v1.1_enhancements_spec.md`](docs/specs/2026-04-02_book_companion_v1.1_enhancements_spec.md)
- Plan: [`docs/plans/2026-04-03_v1_1_enhancements_implementation.md`](docs/plans/2026-04-03_v1_1_enhancements_implementation.md)
- Requirements: [`docs/requirements/2026-04-01_book_companion_v1_requirements.md`](docs/requirements/2026-04-01_book_companion_v1_requirements.md)
