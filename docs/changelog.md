# Changelog

## 2026-05-03 — Audiobook Mode (TTS reading + on-device audio generation)

- New **Audio** tab on every book — see at a glance which sections have audio (no-audio / partial / full / generating), and play / download / delete per row. Coverage bar and per-row Play / Download / Delete actions.
- Click **Generate audio** on the Audio tab to queue an MP3 generation job for the whole book. Cost preview shows estimated minutes + disk before you confirm; defaults include section summaries, the book summary, and the annotations playlist.
- **Listen while you read**: the Section Reader now has a Play button in the header. Choose between two engines:
  - **Web Speech** (browser, free, ~50 ms to first audio) — uses your OS voices.
  - **Kokoro** (local, higher quality, requires `ffmpeg` + `espeak-ng`) — pre-generates ID3-tagged MP3s on disk, plays back on click within 2 s.
- Sticky **Playbar** at the bottom of the reader: play/pause, ±10 s seek, prev/next sentence, speed, voice. The current sentence highlights in the body as it plays.
- **Resume affordance**: you'll see "resume from sentence N" when you reopen a section you'd partially listened to (per-browser; cross-browser shows a hint).
- **Annotations playlist**: from the Annotations tab, click "Play as audio" to hear all of a book's highlights + notes back to back. An audible cue (♪) separates highlight from note.
- **Sections tab** gets per-section audio rows with status pills (none / ready / stale / generating) and Play / Regenerate / Delete actions.
- New **Settings → Text-to-Speech** panel — pick engine + voice, sample any voice with one click, see Kokoro's warm/cold/not-downloaded/download-failed status, read your spike findings inline. Default speed and auto-advance toggles included.
- **Library banner** when 2+ books have stale audio after a sanitizer or summary update — one-click "Regenerate all" or 24 h dismiss.
- **Stale detection**: audio is auto-marked stale when the underlying summary changes, the sanitizer is upgraded, or the segmenter drift is detected — with a clear banner + "Regenerate" CTA in the player.
- **Auto-advance**: when a section ends, playback continues into the next section (Web Speech fallback if no MP3 is pre-generated). Toggleable in Settings.
- **Lock-screen integration**: when a Kokoro MP3 is playing, your OS lock screen shows the book/section title, artist, cover art, and play/pause/seek controls. Book-summary playback also exposes a chapter list.
- **Per-AudioFile size cap (50,000 chars post-sanitizer)**: oversized sections are skipped with a `too_large` reason instead of hanging the worker.
- **Mid-listen banners** when a section's summary is regenerated while you're listening, or its source text changes — never silently play stale content.
- New CLI commands:
  - `bookcompanion listen <book_id>` — local-device playback of the book summary.
  - `bookcompanion listen --generate <book_id>` — queues the same audio job as the UI and streams progress.
  - `bookcompanion spike tts --book-id N --section-id M` — generate a Kokoro clip + a findings template for engine comparison.
  - `bookcompanion maintenance audio-positions-sweep` — weekly cleanup for orphaned resume positions.
  - `bookcompanion init --tts-engine kokoro` — eagerly downloads the Kokoro model (~338 MB, one-time, from GitHub Releases) and gates on `ffmpeg` + `espeak-ng`.
- **Optional install extra** for the local engine: `pip install bookcompanion[kokoro]` adds `kokoro-onnx` and `soundfile`. Default install stays lean for Web-Speech-only users.
- Auto-detection: on `bookcompanion serve`, the configured TTS engine warms up at startup; you can swap voices without restart.

**References:**

- [Requirements](requirements/2026-05-02-audiobook-mode-requirements.md)
- [Spec](specs/2026-05-02-audiobook-mode-spec.md)
- [Implementation plan](plans/2026-05-02-audiobook-mode-plan.md)
- [Wireframes](wireframes/2026-05-02-audiobook-mode/)
- [/verify reports](features/2026-05-02-audiobook-mode/verify/)
- [MSF analysis](msf/2026-05-02-audiobook-mode-msf-analysis.md)

## 2026-05-02 — Cross-Surface UX Cohesion Bundle

- Book Detail now has a proper tab strip — Overview / Summary / Sections — with `?tab=` deep-links. The legacy `/books/:id/summary` route redirects to `?tab=summary` automatically.
- The Book Detail toolbar is reshaped to a single primary **Read** CTA plus a `⋯` overflow menu (Generate book summary, Customize reader…, Edit structure, Re-import, Export Markdown, Delete). Dead "Read Summary" and floating "Customize text" controls are gone.
- New **Summary** tab on Book Detail with empty / in-progress / failed / populated states. The Generate CTA enables as soon as ≥1 section summary exists, shows live progress with Cancel, surfaces the last error with a Retry CTA, and refreshes automatically when a regeneration completes in another tab.
- The Section Reader's summary tab now renders Markdown legibly: bullet markers (`disc` / `circle`), numbered list markers, and tables with borders, padded cells, and a distinct header row.
- Inline **Previous / Next** footer nav at the end of every section's content (both Summary and Original tabs), with first/last sections rendering only the available side and the active `?tab=` preserved across navigation.
- The TOC dropdown now shows real per-section character counts that match the Book Detail Sections table — no more "0 chars" placeholders.
- Annotations and AI Chat side panels now follow the active reader theme. Switching to Dark, Sepia, Night, etc. no longer leaves the side panel as a white island next to the themed reading area.
- Highlights you create on the Summary tab now persist with `content_type=section_summary` and re-render the next time you visit that tab. Original-tab highlights continue to work unchanged.
- The app-bar title and the BC logo in the side rail are both clickable and route to `/` with proper hover, focus, and cursor states.
- Database settings: migration status now shows real revision IDs (or `Unknown` with the underlying error in a tooltip) instead of leaking the literal string `"FAILED:"`. The stats table no longer has alternating row stripes.
- New **Preset management UI** under Settings → Presets: create, edit, and delete user presets (name, label, description, four facet card grids with plain-language subheads). Selecting any preset shows the raw Jinja prompt template — base file plus each fragment block — so you can see exactly what the LLM receives. System presets are read-only. Malformed user-preset YAML files are skipped with a structured warning instead of breaking the whole list.
- Reading Settings preset cards now use the same shared component as the reader settings popover — proper bordered cards with each theme's actual bg/fg colors and font preview, instead of plain text labels.
- LLM Settings page restyled to match the rest of the settings pages — no more divergent Tailwind `dark:` utility classes.
- Compression in the Sections table now reads `~15%`, `~25%` etc. (rounded to the nearest 5) instead of `15.5%` — same number, less false precision.

**References:**
- [Requirements](requirements/2026-05-01-cross-surface-ux-cohesion-bundle.md)
- [Spec](specs/2026-05-01-cross-surface-ux-cohesion-bundle-spec.md)
- [Plan](plans/2026-05-01-cross-surface-ux-cohesion-bundle-implementation-plan.md)
- [Verify report](audits/2026-05-02-cross-surface-ux-cohesion-bundle-review.md)
- [Verify-skill feedback](audits/2026-05-02-verify-skill-feedback.md)

## 2026-05-01 — Reader + Book Detail UX Fixes Bundle

- The book-detail page's section list is now a sortable 6-column table (#, Title, Type, Chars, Summary, Compression). Each summarised section shows its real compression ratio (e.g., 18.2%) instead of a placeholder dash, and the same component renders in compact form inside the reader's TOC dropdown.
- Action row above the section table is reorganised: **Read** and **Read Summary** lead, **Export Markdown** is a split-button (default click downloads, chevron opens a Copy-to-Clipboard menu), with secondary actions ("Edit Structure", "Customize Reader") moved into a `⋯` overflow menu. Export shows a 250 ms loader floor so a fast download doesn't flicker, and the clipboard fallback drops to a plain-text format when rich copy isn't available.
- Six themes now actually theme. **Night**, **Paper**, and **High Contrast** previously left the page identical to Light; each one now has a distinct, fully-populated palette (Night `#0a0e1a`, Paper warm cream `#f7f1e3`, Contrast pure-black/white). Theme tiles in the gear popover render an `Aa` preview in each theme's actual font.
- Font picker is keyboard-accessible: an ARIA listbox replaces the native `<select>`, with arrow-key navigation, per-option live previews, and bundled webfonts (Inter, Merriweather, Lora, Fira Code, Source Serif Pro) shipped via `@fontsource` so reader fonts work offline.
- The reader's content tab choice is now reflected in the URL — `?tab=summary` or `?tab=original`. Refreshing, deep-linking, and the browser back button all preserve the tab. Inactive tabs are styled muted-but-clickable instead of disabled-looking.
- New `/jobs/:id` deep-link view shows live progress for any summarisation job (PENDING / RUNNING / COMPLETED / FAILED), or a "Job not found" card on 404. The persistent processing indicator's running-job row links straight to it.
- Stale summarisation jobs no longer block retries. If a previous server crash or kill left a `RUNNING` row behind, the next `POST /summarize` detects it (dead PID or older than 24h), marks it FAILED, and proceeds — no more `bookcompanion init` workaround. When a job *is* genuinely active, the 409 response now carries the active job's id, scope, and progress so the UI can deep-link to it.
- Summary markdown no longer breaks images. The legacy `![alt](image:N)` scheme that older prompts emitted is now rewritten on-write to absolute `/api/v1/images/N` URLs, the prompt template instructs new generations to emit absolute URLs directly, and a one-shot data migration cleans up every existing summary in the library.
- Section briefs now expose `content_char_count` and a small `default_summary` block so the table can compute compression without extra round-trips.

### Fixed

- Bug 1 — stale-job retry deadlock
- Bug 5 — content tab styled as disabled
- Bug 6 — broken images in summaries
- Bug 7 — tab choice not surviving reload
- Bug 8 — accidental button hierarchy in the action row
- Bug 9 — copy-to-clipboard failure
- Bug 10 — Night/Paper/Contrast themes were no-ops
- Bug 11 — duplicate progress counter on book-detail

### References

- `docs/requirements/2026-04-30-reader-and-book-detail-ux-fixes.md`
- `docs/specs/2026-04-30-reader-and-book-detail-ux-fixes-spec.md`
- `docs/plans/2026-04-30-reader-and-book-detail-ux-fixes-implementation-plan.md`
- `docs/simulations/2026-04-30-reader-and-book-detail-ux-fixes-trace.md`
- `docs/2026-04-30-reader-and-book-detail-ux-fixes/verify/2026-05-01-review.md`

## 2026-04-30 — Reader Settings Popover Consolidation

- The reader's gear popover is now a single, compact picker. Opens to seven theme cards (Light, Dark, Sepia, Night, Paper, High Contrast, Custom) plus the existing highlights / annotations-scope toggles — no more duplicate theme grids and no font/size/spacing controls cluttering the default view.
- Customising a theme is opt-in: click the **Custom** card and the editor expands inline with background/foreground swatches, accent picker, font, size, line spacing, content width, contrast badge, live preview, and Save/Revert. Picking any preset card collapses the editor and applies the bundle as-is.
- The sticky save bar is gone. Save/Revert sit inside the Custom editor where the dirty state lives, and never overlap content during scroll.
- One active-state visual rule across every card (2px primary outline + corner ✓), so colour-blind users still get a non-colour cue.
- Press **Esc** or click outside the popover to close it; focus returns to the gear button. Pending Custom edits are preserved across close/reopen.
- Keyboard nav: tab into the grid, arrow keys (with wrap) move between cards, Home/End jump to first/last, Enter or Space activates. The grid exposes proper ARIA radiogroup semantics.
- If `/api/v1/reading-presets` fails, the popover shows a one-line "Couldn't load themes." notice and renders only the Custom card so users can still customise locally.

**References:** [requirements](requirements/2026-04-30-reader-settings-popover-consolidation.md), [spec](specs/2026-04-30-reader-settings-popover-consolidation-spec.md), [plan](plans/2026-04-30-reader-settings-popover-consolidation-implementation-plan.md)

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
