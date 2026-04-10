# Book Companion Web Interface V1 — Spec

**Date:** 2026-04-10
**Status:** Draft
**Requirements:** `docs/requirements/2026-04-10_web_interface_v1_requirements.md`
**Wireframes:** `docs/wireframes/2026-04-10_v2_web_interface/README.md`

---

## 1. Problem Statement

Book Companion is CLI-only. A web interface adds visual reading, annotation, AI conversation, and library management that are impractical in a terminal. The primary success metric is **full feature parity with the CLI** plus reader-centric capabilities (typography, annotations, AI chat) accessible from desktop and mobile browsers.

---

## 2. Goals

| # | Goal | Success Metric |
|---|------|---------------|
| G1 | Full CLI feature parity via web | Every CLI command (add, summarize, eval, search, export, backup) has a web equivalent |
| G2 | Comfortable long-form reading | Reader with customizable font, size, spacing, width, background; 5 system presets |
| G3 | Real-time processing feedback | SSE streams processing progress; UI updates within 500ms of server event |
| G4 | Mobile-ready | All features accessible on <768px viewports via responsive layouts + touch interactions |
| G5 | Local-first deployment | Single `docker compose up` starts postgres + backend + frontend; no cloud dependency |
| G6 | Annotation & AI conversation | Text selection → highlight/note/AI chat; per-book AI threads with section context |

---

## 3. Non-Goals

- Multi-user authentication — single-user personal tool on trusted local network
- Cloud hosting or SaaS deployment
- Real-time collaboration between users
- Fiction book support
- Token-by-token AI chat streaming in V1 — complete response via coding agent CLI subprocess is acceptable
- Offline editing or background sync — cached pages are read-only when offline
- Focus Mode (V1.1+ nice-to-have)
- Command mode in command palette (V1.1+ nice-to-have)
- Hand-drawn marker stroke highlights (V1.1+ nice-to-have)
- "Surprise me" random section (V1.1+ nice-to-have)
- One-click fix flow for failed eval assertions (V1.1+ nice-to-have)
- Score animation on re-verification (V1.1+ nice-to-have)
- "What changed?" auto-explanation for summary comparison (V1.1+ nice-to-have)
- Export stats card (V1.1+ nice-to-have)
- "Your Notes" UI relabeling (V1.1+ nice-to-have)
- Quick export from reader (V1.1+ nice-to-have)
- Annotation review mode (V1.1+ nice-to-have)

---

## 4. Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | `bookcompanion serve` CLI command starts Uvicorn | (a) CLI command, (b) Separate `uvicorn` entry point | Consistent with CLI-first architecture. All user interactions go through the `bookcompanion` command. |
| D2 | Full docker-compose: postgres + backend container | (a) Full compose (3 services), (b) Separate frontend container with Nginx, (c) Postgres-only Docker | Single `docker compose up` for everything. Backend serves built frontend static files. Simpler for a personal tool. |
| D3 | AI chat uses coding agent CLI subprocess (Claude Code / Codex) | (a) Claude Code CLI subprocess, (b) Direct Anthropic SDK, (c) LLMProvider abstraction | User preference: no direct cloud LLM APIs. Reuses existing `ClaudeCodeCLIProvider` pattern. Environment variables select the provider. |
| D4 | AI chat returns complete response (no streaming) in V1 | (a) Complete response with loading indicator, (b) Parse CLI stdout for partial streaming | CLI subprocess doesn't support token-by-token streaming. Loading indicator is acceptable UX for V1. |
| D5 | Processing jobs run as asyncio background tasks | (a) asyncio.create_task() within FastAPI, (b) Separate subprocess per job | Simpler, shares event loop and DB session factory. SSE integration is straightforward. ProcessingJob table tracks state for crash recovery. |
| D6 | SSE over WebSockets for all streaming | (a) SSE, (b) WebSockets | SSE is simpler (unidirectional, auto-reconnect, works through proxies). All streaming is server→client. |
| D7 | FastAPI serves built Vue SPA from `backend/static/` in production | (a) FastAPI serves static, (b) Nginx in separate container | Eliminates a container. Vite dev server proxies to FastAPI during development. |
| D8 | Shared SQLAlchemy models and service layer between CLI and API | (a) Shared, (b) Separate API models | Avoids duplication. Both CLI and API are thin layers over the same service layer. |
| D9 | Vue 3 + Vite + Tailwind CSS + shadcn-vue | (a) Vue 3 stack, (b) React/Next.js, (c) Svelte | Requirements specify Vue 3. shadcn-vue provides accessible, unstyled components. |
| D10 | Pinia for state management | (a) Pinia, (b) Vuex, (c) Composables only | Pinia is the official Vue 3 state management. Stores for books, reader settings, processing, annotations, AI threads. |
| D11 | No authentication in V1, optional bearer token for LAN | (a) No auth, (b) Basic auth, (c) Token auth | Personal tool. Optional token via `Settings.network.access_token` for LAN exposure. |

---

## 5. User Personas & Journeys

### 5.1 Primary Persona: Knowledge Worker (Solo)

A professional who reads non-fiction for work (product manager, researcher, consultant). Reads 2-5 books/month. Wants to extract, organize, and revisit key ideas efficiently. Uses both desktop (primary) and phone (commute reading).

### 5.2 User Journeys

All 12 user journeys are fully specified in the requirements document (§4.1–4.12). The spec does not duplicate them — implementation should reference the requirements directly. Key flows that drive architectural decisions:

- **Upload → Process → Read** (4.1 + 4.2 + 4.3): Upload triggers parsing, wizard guides metadata/structure/preset, processing uses SSE streaming, completed sections are immediately browsable.
- **Read → Annotate → Ask AI** (4.3 + 4.4 + 4.5): Text selection → floating toolbar → create annotation or start AI thread. AI uses section content + summary as context.
- **Search → Navigate** (4.6): Command palette for quick search, full results page for deep search. Hybrid BM25 + semantic search.
- **Mobile Reading** (4.9): LAN access via QR code, bottom sheet interactions, touch-adapted controls.

---

## 6. System Design

### 6.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Docker Compose                                         │
│                                                         │
│  ┌──────────────────────────────────────────────┐       │
│  │  backend (Python 3.12 + FastAPI)             │       │
│  │                                               │       │
│  │  ┌─────────────┐   ┌──────────────────────┐  │       │
│  │  │ Vue 3 SPA   │   │ FastAPI Router Layer │  │       │
│  │  │ (static/)   │   │ /api/v1/*            │  │       │
│  │  └──────┬──────┘   └──────────┬───────────┘  │       │
│  │         │  Fetch/SSE          │ Depends()    │       │
│  │         └──────────┬──────────┘              │       │
│  │                    ▼                          │       │
│  │  ┌────────────────────────────────────────┐  │       │
│  │  │         Shared Service Layer           │  │       │
│  │  │  BookService, SummarizerService,       │  │       │
│  │  │  EvalService, SearchService,           │  │       │
│  │  │  AnnotationService, AIThreadService,   │  │       │
│  │  │  etc.                                  │  │       │
│  │  └───────────────────┬────────────────────┘  │       │
│  │                      ▼                        │       │
│  │  ┌────────────────────────────────────────┐  │       │
│  │  │  SQLAlchemy 2.0 async + Repositories   │  │       │
│  │  └───────────────────┬────────────────────┘  │       │
│  │                      │ asyncpg                │       │
│  └──────────────────────┼───────────────────────┘       │
│                         ▼                                │
│  ┌──────────────────────────────────────────────┐       │
│  │  postgres (pgvector/pgvector:pg16)           │       │
│  │  Port 5438                                    │       │
│  └──────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘

Development mode:
  Vite dev server (port 5173) → proxy /api/* → FastAPI (port 8000)

Production mode:
  FastAPI serves built SPA from backend/static/
  Uvicorn on port 8000
```

### 6.2 Sequence Diagrams

#### 6.2.1 Upload & Processing Flow

```mermaid
sequenceDiagram
    participant Browser
    participant FastAPI
    participant BookService
    participant SummarizerService
    participant EvalService
    participant DB

    Browser->>FastAPI: POST /api/v1/books/upload (multipart)
    FastAPI->>BookService: add_book(file)
    BookService->>DB: INSERT book, sections
    BookService-->>FastAPI: Book (parsed)
    FastAPI-->>Browser: 201 {book_id, sections}

    Browser->>FastAPI: POST /api/v1/books/{id}/summarize
    FastAPI->>DB: INSERT processing_job
    FastAPI-->>Browser: 200 {job_id}
    FastAPI->>FastAPI: asyncio.create_task(run_processing)

    Browser->>FastAPI: GET /api/v1/processing/{job_id}/stream (SSE)

    loop For each section
        FastAPI->>SummarizerService: summarize_section()
        SummarizerService->>DB: INSERT summary
        FastAPI-->>Browser: SSE: section_completed
        alt run_eval=true
            FastAPI->>EvalService: evaluate_summary()
            EvalService->>DB: INSERT eval_traces
            FastAPI-->>Browser: SSE: eval_completed
            alt auto_retry and critical failure
                FastAPI->>SummarizerService: summarize_section(fix_instructions)
                FastAPI-->>Browser: SSE: retry_started
            end
        end
    end

    FastAPI->>SummarizerService: summarize_book()
    FastAPI-->>Browser: SSE: processing_completed
```

#### 6.2.2 AI Chat Flow

```mermaid
sequenceDiagram
    participant Browser
    participant FastAPI
    participant AIThreadService
    participant LLMProvider
    participant DB

    Browser->>FastAPI: POST /api/v1/ai-threads/{id}/messages
    Note right of Browser: {content, context_section_id, selected_text}
    FastAPI->>DB: INSERT ai_message (role=user)
    FastAPI->>AIThreadService: generate_response(thread, message)
    AIThreadService->>DB: SELECT section content, summary, book info
    AIThreadService->>AIThreadService: Build prompt with context
    AIThreadService->>LLMProvider: prompt(full_context) [subprocess]
    Note right of LLMProvider: Blocks until complete response
    LLMProvider-->>AIThreadService: response text
    AIThreadService->>DB: INSERT ai_message (role=assistant)
    FastAPI-->>Browser: 200 {message_id, content, model_used}
```

#### 6.2.3 Search Flow (Command Palette)

```mermaid
sequenceDiagram
    participant Browser
    participant FastAPI
    participant SearchService
    participant DB

    Browser->>FastAPI: GET /api/v1/search/quick?q=anchoring&limit=12
    FastAPI->>SearchService: quick_search(query, limit)
    SearchService->>DB: BM25 tsvector query
    SearchService->>DB: Semantic embedding cosine similarity
    SearchService->>SearchService: RRF fusion merge
    SearchService-->>FastAPI: Grouped results (max 3 per type)
    FastAPI-->>Browser: 200 {books: [], sections: [], concepts: [], annotations: []}
```

#### 6.2.4 Annotation Creation Flow

```mermaid
sequenceDiagram
    participant Browser
    participant FastAPI
    participant AnnotationService
    participant DB

    Browser->>FastAPI: POST /api/v1/annotations
    Note right of Browser: {content_type, content_id, text_start, text_end, selected_text, type}
    FastAPI->>AnnotationService: create_annotation(data)
    AnnotationService->>DB: INSERT annotation
    AnnotationService-->>FastAPI: Annotation
    FastAPI-->>Browser: 201 {id, ...annotation}
```

---

## 7. Functional Requirements

Requirements are organized by feature area. Detailed screen-by-screen behavior is in the requirements doc (§3). This spec captures the testable requirements with FR IDs for the implementation plan.

### 7.1 App Shell & Navigation

| ID | Requirement |
|----|-------------|
| FR-01 | Desktop layout: 56px icon rail sidebar (Library, Concepts, Annotations, Settings) + 48px top bar + content area |
| FR-02 | Mobile layout (<768px): Bottom tab bar (5 tabs) replaces sidebar; top bar simplified |
| FR-03 | Tablet layout (768-1023px): Same icon rail, content gets full remaining width |
| FR-04 | Top bar: page title (left), search input (center-right), Upload button (right) |
| FR-05 | `Cmd+K` / `Ctrl+K` opens command palette; `Cmd+U` / `Ctrl+U` opens upload; `Escape` closes modals |
| FR-06 | Active nav item shows accent-colored background + icon fill |

### 7.2 Library Page

| ID | Requirement |
|----|-------------|
| FR-07 | Custom views as horizontal tabs; "All Books" built-in default view; "+ New View" creates view from current filters |
| FR-08 | View persistence: saves filters, sort, display mode, table column config to `library_views` table |
| FR-09 | Unsaved changes dot on tab when filters differ from saved state |
| FR-10 | Filter row: Tags, Status, Author, Eval, Format — multi-select dropdowns, OR within dimension, AND across |
| FR-11 | Cross-filter counts: each dropdown option shows count of matching books, updating dynamically |
| FR-12 | Sort: Recent, Title A-Z, Author A-Z, Most sections, Eval score, Date added |
| FR-13 | Display modes: Grid (responsive columns), List (compact rows), Table (configurable columns, drag-to-reorder, column visibility toggle) |
| FR-14 | Table mode: checkbox column for multi-select, sticky Title column, horizontal scroll |
| FR-15 | Empty states: first-time welcome with 3-step how-it-works + Upload CTA; no-match with clear filters button |
| FR-16 | Bulk operations: floating toolbar with Tag, Summarize, Export, Delete actions when books selected |
| FR-17 | Book card context menu (right-click/long-press): Open, Summarize, Verify, Edit metadata, Export, Delete |

### 7.3 Book Detail / Reader

| ID | Requirement |
|----|-------------|
| FR-18 | Header: breadcrumb (Library > Book > Chapter dropdown), Original/Summary segmented control, action buttons (Aa, AI, Annotations, Prev/Next) |
| FR-19 | Reading area: max-width 720px centered, renders markdown, applies reader settings |
| FR-20 | Context sidebar: 360px right panel, collapsible, two tabs (Annotations, Ask AI) |
| FR-21 | Original/Summary toggle: defaults to Summary when summaries exist; shows "No summary" + Summarize button otherwise |
| FR-22 | Summary version: shows default summary automatically; "History (N versions)" link when multiple exist |
| FR-23 | User edits to summaries saved as new version with `user_edited=True`, becomes new default |
| FR-24 | Eval trust badge: green/yellow/red/gray with score; "View details" links to eval detail route |
| FR-25 | Concept chips: clickable terms in summary with tooltip (definition, section count, related concepts, "Ask AI about this") |
| FR-26 | Text selection floating toolbar: Highlight, Note, Ask AI, Link, Copy |
| FR-27 | Section navigation: Prev/Next arrows + keyboard shortcuts (Left/Right, Alt+P/Alt+N) |
| FR-27a | Reading re-entry card: when revisiting a section (>24h gap), show card with most recent annotation quote and scroll link |
| FR-28 | TOC dropdown: searchable, sections grouped by type, eval status dots |
| FR-29 | Book-level summary view at `/books/{id}/summary` with consistency indicator (section score variance) |
| FR-29a | Annotations visible across views: annotations from Original appear as dimmed indicators in Summary view and vice versa, with "Highlighted in [view]" label |
| FR-30 | Annotation sidebar: section annotations ordered by text position, freeform note input, inline edit, 5-second undo on delete |
| FR-31 | AI sidebar: thread list, thread view with chat messages, context blocks from selected text, "+ Add context" for multi-section queries |
| FR-32 | "Save as note" on AI responses creates freeform annotation |
| FR-33 | Mobile reader: bottom action bar, bottom sheets for sidebar content (3 snap points: 30%, 50%, 90%), 44px touch targets |

### 7.4 Reader Settings

| ID | Requirement |
|----|-------------|
| FR-34 | Settings popover (380px desktop, bottom sheet mobile) triggered by Aa button |
| FR-35 | Visual preset cards: 4 system presets (Comfortable, Night Reading, Study Mode, Compact) + user presets |
| FR-36 | Font selection: Georgia, Merriweather, Inter, Fira Code primary; "All fonts" expansion for additional |
| FR-37 | Size: named buttons (14/16/18/20px) + manual stepper |
| FR-38 | Line spacing: named buttons (1.4/1.6/1.8/2.0) + manual stepper |
| FR-39 | Content width: named buttons (560/720/880/Full) + manual stepper |
| FR-40 | Background: Light, Sepia, Dark, OLED, Dracula swatches + custom color picker with WCAG AA auto-contrast |
| FR-41 | Live preview: sample text area updates in real-time; summary line shows current values |
| FR-42 | Settings persisted to database (`reading_presets` table), applied across sessions |
| FR-43 | System preference detection: first load uses `prefers-color-scheme` to pre-select Light or Dark |

### 7.5 Upload & Processing

| ID | Requirement |
|----|-------------|
| FR-44 | Entry points: Upload button, drag-and-drop on Library, command palette |
| FR-45 | 3-step wizard indicator: Upload / Configure / Process |
| FR-46 | Step 1: Drag-and-drop zone, client-side validation (extension, size), server-side validation (MIME, integrity), SHA-256 duplicate detection |
| FR-47 | Duplicate detection: same hash → Go to existing / Re-import / Cancel; fuzzy title+author match → side-by-side comparison |
| FR-48 | Quick Upload fast path: "Start with Recommended Settings" skips wizard steps 2-4 |
| FR-49 | Step 2 (Metadata): cover, title, authors, tags — pre-populated, "Looks good" banner when clean |
| FR-50 | Step 3 (Structure Review): section table with quality warnings, merge/split/delete/reorder operations, 10-second undo toasts |
| FR-51 | Step 4 (Preset Selection): preset cards with facet details, "+ Create New", processing profile with advanced options |
| FR-52 | Cost & time estimate display when `settings.show_cost_estimates` is enabled |
| FR-53 | Step 5 (Processing): pinned progress card in Book Detail, section-by-section SSE status, minimizable to bottom bar |
| FR-54 | Processing SSE events: section_started, section_completed, section_failed, eval_started, eval_completed, retry_started, processing_completed, processing_failed |
| FR-55 | Cancel processing preserves completed sections |

### 7.6 Search

| ID | Requirement |
|----|-------------|
| FR-56 | Command palette (Cmd+K): centered modal, auto-focused input, instant results grouped by type (Books, Sections, Concepts, Annotations), max 3 per type |
| FR-57 | Keyboard navigation in palette: Up/Down, Enter to open, Shift+Enter for full results |
| FR-58 | Empty palette state: recent searches (last 5) + quick actions |
| FR-59 | Full search results page at `/search?q={query}`: left sidebar with type/book/tag filters, results grouped by book |
| FR-60 | Hybrid search indicator badge; result click navigates to source location |
| FR-61 | Filter-scoped search: palette opened from Library inherits active filters |

### 7.7 Annotations Page

| ID | Requirement |
|----|-------------|
| FR-62 | Global annotations page at `/annotations` with count, search, export (Markdown/JSON/CSV) |
| FR-63 | Filter bar: Book, Type, Tags filters; Group by (Book/Tag/Section/None); Sort (Newest/Oldest/Book order/Recently edited) |
| FR-64 | Annotation cards: type badge, source breadcrumb, quoted text, note body (inline edit), tags, linked annotations, date, actions |
| FR-65 | Click source breadcrumb → opens reader at annotation location with sidebar open |
| FR-66 | Auto-filtering: arriving from reader pre-sets Book filter |
| FR-67 | "+ Add Note" button for retrospective freeform notes (book + section selector) |

### 7.8 Concepts Explorer

| ID | Requirement |
|----|-------------|
| FR-68 | Two-panel layout at `/concepts`: concept list (40%) + concept detail (60%); mobile: single panel |
| FR-69 | Concept list: search, filters (Book, Tags, User-edited), grouping (Book/First Letter/None), sort (A-Z/Most sections/Recent) |
| FR-70 | Concept detail: editable term + definition (sets `user_edited=True`), section appearances, related concepts (same-book + cross-book), "Reset to original" |
| FR-71 | "Copy" button on definition copies term + definition as plain text |

### 7.9 Settings Page

| ID | Requirement |
|----|-------------|
| FR-72 | Settings at `/settings` with sidebar: General, Database, Summarization Presets, Reading Preferences, Backup & Export |
| FR-73 | General: "Read on your phone" toggle (allow_lan), LAN info + QR code, default preset, show cost estimates toggle, LLM settings (read-only) |
| FR-74 | Database: connection info, migration status + "Run migrations" button, table stats |
| FR-75 | Summarization Presets: list/detail layout, system presets (read-only, duplicable), user presets (full CRUD), facet grid, assertion config |
| FR-76 | Reading Preferences: default preset, font loading preference, custom CSS textarea |
| FR-77 | Backup & Export: create/restore/list backups (pg_dump), scheduled backups, export library (Markdown/JSON, scope + include options) |

### 7.10 Multi-Device & Mobile

| ID | Requirement |
|----|-------------|
| FR-78 | Responsive breakpoints: Desktop >=1024px, Tablet 768-1023px, Mobile <768px |
| FR-79 | Mobile: bottom tab bar, filter dropdowns as full-screen modals, bottom sheets for sidebar content |
| FR-80 | Touch interactions: long-press for preview/context menu, long-press+drag for reorder |
| FR-81 | Reading position sync: `reading_state` table tracks last book/section per user-agent; "Continue where you left off" banner on different device |
| FR-82 | Custom views sync across devices (read-only on mobile) |
| FR-83 | Performance: lazy-loaded images, skeleton loaders, reduced animation on `prefers-reduced-motion` |

---

## 8. Non-Functional Requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-01 | Performance | Library page load <500ms (<100 books), <1.5s (100-500 books) |
| NFR-02 | Performance | Command palette results <300ms after 200ms debounce |
| NFR-03 | Performance | Section content rendering <200ms |
| NFR-04 | Performance | Reader settings change <50ms (real-time feel) |
| NFR-05 | Performance | SSE event delivery <500ms from server event to UI update |
| NFR-06 | Performance | API response (simple CRUD) <200ms |
| NFR-07 | Performance | Skeleton states render within 50ms of navigation |
| NFR-08 | Accessibility | WCAG 2.1 AA compliance; semantic HTML; ARIA labels; keyboard navigation; focus management |
| NFR-09 | Accessibility | Color contrast >=4.5:1 for text, >=3:1 for large text/UI; `prefers-reduced-motion` respected |
| NFR-10 | Accessibility | rem-based font sizing; visible focus indicators |
| NFR-11 | Browser | Chrome 90+, Firefox 90+, Safari 15+, Edge 90+, Mobile Safari 15+, Chrome Android 90+ |
| NFR-12 | Security | CORS restricted to localhost + LAN origins; file upload validation; no v-html with user content; parameterized queries via SQLAlchemy |
| NFR-13 | i18n | English only; all strings in locale files (prep for future i18n); `Intl.DateTimeFormat` / `Intl.NumberFormat` |

---

## 9. API Contracts

### 9.1 General Conventions

- **Base path:** `/api/v1/`
- **Content type:** `application/json` (except file uploads: `multipart/form-data`)
- **Pagination:** `?page=1&per_page=20` (max: 100). Response includes `{"items": [...], "total": N, "page": N, "per_page": N, "pages": N}`
- **Sorting:** `?sort=field&order=asc|desc`
- **Error shape:** `{"detail": "message", "code": "ERROR_CODE"}`
- **SSE:** `text/event-stream`, events as `event: type\ndata: {json}\n\n`
- **Auth:** Optional `Authorization: Bearer <token>` when `network.access_token` is configured

### 9.2 Books

#### `POST /api/v1/books/upload`

Uploads and parses a book file.

**Request:** `multipart/form-data`
- `file` (required): Book file (.epub, .mobi, .pdf)
- `title` (optional): Override extracted title
- `author` (optional): Override extracted author

**Response (201):**
```json
{
  "id": 1,
  "title": "Thinking, Fast and Slow",
  "status": "parsed",
  "file_format": "epub",
  "file_size_bytes": 4200000,
  "file_hash": "sha256:abc123...",
  "authors": [{"id": 1, "name": "Daniel Kahneman", "role": "author"}],
  "sections": [
    {"id": 1, "title": "Introduction", "order_index": 0, "section_type": "chapter", "content_token_count": 3200}
  ],
  "section_count": 37,
  "cover_url": "/api/v1/books/1/cover",
  "created_at": "2026-04-10T14:30:00Z"
}
```

**Error responses:**
- `400`: `{"detail": "Unsupported file format. Accepts: epub, mobi, pdf", "code": "UNSUPPORTED_FORMAT"}`
- `400`: `{"detail": "File too large (150MB). Maximum is 100MB", "code": "FILE_TOO_LARGE"}`
- `422`: `{"detail": "Unable to parse file. The file may be corrupt.", "code": "PARSE_FAILED"}`

#### `POST /api/v1/books/{id}/check-duplicate`

**Request:**
```json
{"file_hash": "sha256:abc123..."}
```

**Response (200):**
```json
{
  "duplicate": true,
  "match_type": "exact",
  "existing_book": {"id": 5, "title": "...", "status": "completed", "section_count": 37, "created_at": "..."}
}
```

#### `GET /api/v1/books`

**Query:** `?status=completed&tag_ids=1,3&author_ids=2&format=epub&sort=updated_at&order=desc&page=1&per_page=20`

**Response (200):**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Thinking, Fast and Slow",
      "status": "completed",
      "file_format": "epub",
      "file_size_bytes": 4200000,
      "authors": [{"id": 1, "name": "Daniel Kahneman"}],
      "tags": [{"id": 1, "name": "Psychology", "color": "#4A90D9"}],
      "section_count": 37,
      "cover_url": "/api/v1/books/1/cover",
      "eval_summary": {"passed": 35, "total": 37},
      "default_summary_id": 42,
      "created_at": "2026-04-10T14:30:00Z",
      "updated_at": "2026-04-10T16:00:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "per_page": 20,
  "pages": 1
}
```

#### `GET /api/v1/books/{id}`

**Response (200):** Same as list item + `quick_summary` field.

#### `PATCH /api/v1/books/{id}`

**Request:**
```json
{"title": "New Title", "authors": [{"name": "Author", "role": "author"}], "tag_ids": [1, 3]}
```

**Response (200):** Updated book object.

**Error:** `404` if book not found.

#### `DELETE /api/v1/books/{id}`

**Response:** `204 No Content`

#### `POST /api/v1/books/{id}/reimport`

**Response (200):** Updated book object. Eval traces marked stale.

#### `GET /api/v1/books/{id}/cover` / `PUT /api/v1/books/{id}/cover`

GET returns image binary. PUT accepts `multipart/form-data` with `file`.

### 9.3 Sections

Full contracts specified in requirements §9.3. Key additions:

#### `GET /api/v1/books/{book_id}/sections/{id}`

**Response (200):**
```json
{
  "id": 5,
  "book_id": 1,
  "title": "Chapter 3: The Lazy Controller",
  "order_index": 2,
  "section_type": "chapter",
  "content_token_count": 4500,
  "content_md": "# Chapter 3...",
  "default_summary": {
    "id": 42,
    "summary_md": "## Key Points...",
    "preset_name": "practitioner_bullets",
    "eval_json": {"passed": 16, "total": 16, "eval_run_id": "uuid"},
    "quality_warnings": [],
    "created_at": "2026-04-10T15:00:00Z"
  },
  "summary_count": 2,
  "annotation_count": 5,
  "has_summary": true
}
```

#### `POST /api/v1/books/{book_id}/sections/merge`

**Request:**
```json
{"section_ids": [3, 4, 5], "title": "Merged Chapter"}
```

**Response (200):** New merged section. **Error:** `400` if sections not adjacent.

#### `POST /api/v1/books/{book_id}/sections/{id}/split`

**Request:**
```json
{"mode": "heading", "positions": [1250, 3400]}
```

**Response (200):** Array of new sections created from split.

### 9.4 Summaries

Contracts per requirements §9.4.

#### `GET /api/v1/summaries/compare?id1=5&id2=8`

**Response (200):**
```json
{
  "summary_a": {"id": 5, "summary_md": "...", "preset_name": "...", "eval_json": {...}, "created_at": "..."},
  "summary_b": {"id": 8, "summary_md": "...", "preset_name": "...", "eval_json": {...}, "created_at": "..."},
  "concept_diff": {
    "only_in_a": ["Term1"],
    "only_in_b": ["Term2"],
    "in_both": ["Term3", "Term4"]
  },
  "metadata_comparison": {
    "a": {"compression_ratio": 0.18, "token_count": 450},
    "b": {"compression_ratio": 0.25, "token_count": 620}
  }
}
```

### 9.5 Processing & Summarization

#### `POST /api/v1/books/{id}/summarize`

**Request:**
```json
{
  "preset_name": "practitioner_bullets",
  "run_eval": true,
  "auto_retry": true
}
```

**Response (200):**
```json
{"job_id": 1}
```

Starts an asyncio background task. Client connects to SSE stream.

#### `GET /api/v1/processing/{job_id}/stream`

**Content-Type:** `text/event-stream`

**SSE Events:**
```
event: section_started
data: {"section_id": 5, "section_title": "Chapter 3", "index": 2}

event: section_completed
data: {"section_id": 5, "summary_id": 42, "eval_score": {"passed": 16, "total": 16}, "latency_ms": 3200}

event: section_failed
data: {"section_id": 6, "error": "LLM timeout after 300s", "will_retry": true}

event: eval_started
data: {"section_id": 5}

event: eval_completed
data: {"section_id": 5, "passed": 16, "total": 16, "assertions": {"no_hallucinated_facts": {"passed": true}}}

event: retry_started
data: {"section_id": 6, "attempt": 2, "reason": "critical_eval_failure"}

event: processing_completed
data: {"book_id": 1, "total_sections": 37, "passed": 35, "failed": 2, "total_time_ms": 754000}

event: processing_failed
data: {"book_id": 1, "error": "LLM budget exceeded"}
```

#### `GET /api/v1/processing/{job_id}/status`

REST endpoint for SSE reconnection. Returns current processing state.

**Response (200):**
```json
{
  "job_id": 1,
  "status": "running",
  "progress": 0.35,
  "sections_completed": 13,
  "sections_total": 37,
  "sections_failed": 1,
  "current_section": {"id": 14, "title": "Chapter 14"},
  "elapsed_ms": 280000,
  "estimated_remaining_ms": 520000
}
```

#### `POST /api/v1/processing/{job_id}/cancel`

**Response (200):**
```json
{"status": "cancelled", "sections_completed": 7, "sections_total": 37}
```

### 9.6 Evaluation

Contracts per requirements §9.6.

#### `GET /api/v1/eval/section/{section_id}`

**Response (200):**
```json
{
  "section_id": 5,
  "summary_id": 42,
  "eval_run_id": "uuid",
  "passed": 14,
  "total": 16,
  "is_stale": false,
  "assertions": {
    "faithfulness": [
      {"name": "no_hallucinated_facts", "passed": true, "reasoning": "...", "model_used": "claude-opus-4-6"},
      {"name": "accurate_statistics", "passed": true, "reasoning": "..."}
    ],
    "completeness": [...],
    "coherence": [
      {"name": "logical_flow", "passed": false, "reasoning": "The summary jumps from...", "likely_cause": "...", "suggestion": "..."}
    ],
    "specificity": [...],
    "format": [...]
  }
}
```

### 9.7 Search

Contracts per requirements §9.7.

#### `GET /api/v1/search/quick?q=anchoring&limit=12`

**Response (200):**
```json
{
  "query": "anchoring",
  "results": {
    "books": [{"id": 1, "title": "Thinking...", "author": "Kahneman", "highlight": "..."}],
    "sections": [{"id": 5, "title": "Chapter 11: Anchors", "book_title": "...", "snippet": "The <mark>anchoring</mark> effect..."}],
    "concepts": [{"id": 3, "term": "Anchoring Effect", "definition_snippet": "...", "book_title": "..."}],
    "annotations": [{"id": 7, "note_snippet": "...", "section_title": "...", "book_title": "..."}]
  }
}
```

### 9.8–9.16 Remaining Endpoints

All endpoint contracts are fully specified in the requirements §9.8–9.16. The spec adopts them as-is. Key implementation notes:

- **AI Threads (`POST /api/v1/ai-threads/{id}/messages`):** Returns a standard JSON response (not SSE) since V1 AI chat uses coding agent CLI subprocess and returns a complete response. A loading indicator is shown client-side.
- **Library Views:** The `filters` field is stored as JSONB. View creation pre-populates from current filter state.
- **Reading Presets:** System presets are seeded via Alembic data migration. Only user presets are mutable.
- **Backup (`POST /api/v1/backup/create`):** Returns `{backup_id}` immediately; progress streamed via SSE at `/api/v1/backup/{id}/stream`.
- **Export:** Returns file download directly (no SSE needed for single-book export).

---

## 10. Database Design

### 10.1 Schema Changes

All new tables. No changes to existing tables.

```sql
-- Library views (Notion-style saved filter/sort/display combinations)
CREATE TABLE library_views (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    display_mode    VARCHAR(20) NOT NULL DEFAULT 'grid'
                    CHECK (display_mode IN ('grid', 'list', 'table')),
    sort_field      VARCHAR(50) NOT NULL DEFAULT 'updated_at',
    sort_direction  VARCHAR(4) NOT NULL DEFAULT 'desc'
                    CHECK (sort_direction IN ('asc', 'desc')),
    filters         JSONB NOT NULL DEFAULT '{}',
    table_columns   JSONB,
    position        INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Reading display presets (font, size, spacing, colors)
CREATE TABLE reading_presets (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL UNIQUE,
    is_system       BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    font_family     VARCHAR(100) NOT NULL DEFAULT 'Georgia',
    font_size_px    INTEGER NOT NULL DEFAULT 16,
    line_spacing    DECIMAL(3,1) NOT NULL DEFAULT 1.6,
    content_width_px INTEGER NOT NULL DEFAULT 720,
    bg_color        VARCHAR(7) NOT NULL DEFAULT '#FFFFFF',
    text_color      VARCHAR(7) NOT NULL DEFAULT '#1A1A1A',
    custom_css      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-book AI conversation threads
CREATE TABLE ai_threads (
    id              BIGSERIAL PRIMARY KEY,
    book_id         BIGINT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    title           VARCHAR(500) NOT NULL DEFAULT 'New Thread',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_threads_book_id ON ai_threads(book_id);

-- Messages within AI threads
CREATE TABLE ai_messages (
    id              BIGSERIAL PRIMARY KEY,
    thread_id       BIGINT NOT NULL REFERENCES ai_threads(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    context_section_id BIGINT REFERENCES book_sections(id) ON DELETE SET NULL,
    selected_text   TEXT,
    model_used      VARCHAR(100),
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_messages_thread_id ON ai_messages(thread_id);

-- Recent search queries for command palette
CREATE TABLE recent_searches (
    id              BIGSERIAL PRIMARY KEY,
    query           VARCHAR(500) NOT NULL,
    result_count    INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_recent_searches_created_at ON recent_searches(created_at DESC);

-- Reading position sync across devices
CREATE TABLE reading_state (
    id              BIGSERIAL PRIMARY KEY,
    user_agent      VARCHAR(500) NOT NULL,
    last_book_id    BIGINT REFERENCES books(id) ON DELETE CASCADE,
    last_section_id BIGINT REFERENCES book_sections(id) ON DELETE SET NULL,
    last_viewed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ix_reading_state_user_agent ON reading_state(user_agent);
```

### 10.2 Migration Notes

- Generate migration: `uv run alembic revision --autogenerate -m "add web interface tables"`
- Manual review required: Alembic may not auto-detect CHECK constraints — verify they're in the migration
- Forward-compatible: No changes to existing tables, so rollback = drop new tables
- pgvector import not needed for these tables (no embedding columns)

### 10.3 Data Seeding (via Alembic data migration)

Seed 4 system reading presets and 1 default library view:

```python
# In migration upgrade():
op.bulk_insert(reading_presets_table, [
    {"name": "Comfortable", "is_system": True, "is_active": True,
     "font_family": "Georgia", "font_size_px": 18, "line_spacing": 1.8,
     "content_width_px": 720, "bg_color": "#FFFFFF", "text_color": "#1A1A1A"},
    {"name": "Night Reading", "is_system": True,
     "font_family": "Georgia", "font_size_px": 18, "line_spacing": 1.8,
     "content_width_px": 720, "bg_color": "#1E1E2E", "text_color": "#CDD6F4"},
    {"name": "Study Mode", "is_system": True,
     "font_family": "Inter", "font_size_px": 15, "line_spacing": 1.5,
     "content_width_px": 880, "bg_color": "#FFFFFF", "text_color": "#1A1A1A"},
    {"name": "Compact", "is_system": True,
     "font_family": "Inter", "font_size_px": 14, "line_spacing": 1.4,
     "content_width_px": 880, "bg_color": "#FFFFFF", "text_color": "#1A1A1A"},
])

op.bulk_insert(library_views_table, [
    {"name": "All Books", "is_default": True, "display_mode": "grid",
     "sort_field": "updated_at", "sort_direction": "desc",
     "filters": "{}", "position": 0},
])
```

### 10.4 Indexes & Query Patterns

| Query Pattern | Supporting Index |
|---------------|-----------------|
| AI threads by book | `ix_ai_threads_book_id` on `ai_threads(book_id)` |
| Messages by thread (ordered) | `ix_ai_messages_thread_id` on `ai_messages(thread_id)` — app orders by `created_at` |
| Recent searches | `ix_recent_searches_created_at` DESC — top-5 query |
| Reading state by device | `ix_reading_state_user_agent` UNIQUE — upsert pattern |
| Library views ordering | `position` column — app sorts in-memory (few rows) |
| Active reading preset | `WHERE is_active = TRUE` — few rows, sequential scan is fine |

---

## 11. Frontend Design

### 11.1 Project Structure

```
frontend/
├── src/
│   ├── App.vue                     # Root: AppShell + RouterView
│   ├── main.ts                     # Vue app creation, Pinia, Router
│   ├── router/
│   │   └── index.ts                # Route definitions
│   ├── stores/                     # Pinia stores
│   │   ├── books.ts                # Library state, filters, views
│   │   ├── reader.ts               # Current book/section, toggle state
│   │   ├── readerSettings.ts       # Font, size, spacing, background
│   │   ├── processing.ts           # Active jobs, SSE connections
│   │   ├── annotations.ts          # Section annotations, CRUD
│   │   ├── aiThreads.ts            # Threads, messages, context
│   │   ├── search.ts               # Query, results, recent searches
│   │   ├── concepts.ts             # Concept list, selected detail
│   │   └── ui.ts                   # Sidebar state, modals, toasts
│   ├── composables/                # Reusable logic
│   │   ├── useSSE.ts               # SSE connection management
│   │   ├── useKeyboard.ts          # Global keyboard shortcuts
│   │   ├── useTextSelection.ts     # Text selection detection
│   │   ├── useInfiniteScroll.ts    # List virtualization
│   │   └── useBreakpoint.ts        # Responsive breakpoint detection
│   ├── components/
│   │   ├── app/                    # Shell components
│   │   │   ├── AppShell.vue        # Icon rail + top bar + content
│   │   │   ├── IconRail.vue
│   │   │   ├── TopBar.vue
│   │   │   ├── BottomTabBar.vue    # Mobile nav
│   │   │   └── ProcessingBar.vue   # Minimized progress indicators
│   │   ├── library/                # Library page
│   │   │   ├── ViewTabs.vue
│   │   │   ├── FilterRow.vue
│   │   │   ├── BookGrid.vue
│   │   │   ├── BookList.vue
│   │   │   ├── BookTable.vue
│   │   │   ├── BookCard.vue
│   │   │   └── BulkToolbar.vue
│   │   ├── reader/                 # Book detail / reader
│   │   │   ├── ReaderHeader.vue
│   │   │   ├── Breadcrumb.vue
│   │   │   ├── ContentToggle.vue   # Original/Summary segmented control
│   │   │   ├── ReadingArea.vue
│   │   │   ├── ConceptChip.vue
│   │   │   ├── EvalBadge.vue
│   │   │   ├── FloatingToolbar.vue # Text selection toolbar
│   │   │   ├── TOCDropdown.vue
│   │   │   └── SummaryVersionSelect.vue
│   │   ├── sidebar/                # Context sidebar
│   │   │   ├── ContextSidebar.vue
│   │   │   ├── AnnotationsTab.vue
│   │   │   ├── AnnotationCard.vue
│   │   │   ├── AIChatTab.vue
│   │   │   ├── ThreadList.vue
│   │   │   ├── ThreadView.vue
│   │   │   └── ChatMessage.vue
│   │   ├── settings/               # Reader settings popover
│   │   │   ├── ReaderSettingsPopover.vue
│   │   │   ├── PresetCards.vue
│   │   │   ├── FontSelector.vue
│   │   │   ├── SizeStepper.vue
│   │   │   ├── BackgroundPicker.vue
│   │   │   └── LivePreview.vue
│   │   ├── upload/                 # Upload wizard
│   │   │   ├── UploadWizard.vue
│   │   │   ├── StepIndicator.vue
│   │   │   ├── DropZone.vue
│   │   │   ├── MetadataForm.vue
│   │   │   ├── StructureReview.vue
│   │   │   ├── PresetPicker.vue
│   │   │   └── ProcessingProgress.vue
│   │   ├── search/                 # Search
│   │   │   ├── CommandPalette.vue
│   │   │   └── SearchResults.vue
│   │   ├── annotations/            # Global annotations page
│   │   ├── concepts/               # Concepts explorer
│   │   └── common/                 # Shared components
│   │       ├── SkeletonLoader.vue
│   │       ├── EmptyState.vue
│   │       ├── ConfirmDialog.vue
│   │       ├── UndoToast.vue
│   │       ├── BottomSheet.vue     # Mobile bottom sheet
│   │       └── TagPills.vue
│   ├── views/                      # Route-level components
│   │   ├── LibraryView.vue
│   │   ├── BookDetailView.vue
│   │   ├── BookSummaryView.vue
│   │   ├── EvalDetailView.vue
│   │   ├── SearchResultsView.vue
│   │   ├── AnnotationsView.vue
│   │   ├── ConceptsView.vue
│   │   └── SettingsView.vue
│   ├── api/                        # API client layer
│   │   ├── client.ts               # Base fetch wrapper
│   │   ├── books.ts
│   │   ├── sections.ts
│   │   ├── summaries.ts
│   │   ├── processing.ts
│   │   ├── search.ts
│   │   ├── annotations.ts
│   │   ├── concepts.ts
│   │   ├── aiThreads.ts
│   │   ├── presets.ts
│   │   ├── views.ts
│   │   ├── readingPresets.ts
│   │   └── settings.ts
│   ├── assets/
│   │   └── fonts/                  # Self-hosted web fonts
│   └── types/                      # TypeScript types matching API schemas
│       └── index.ts
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

### 11.2 Routes

```typescript
const routes = [
  { path: '/',                                    component: LibraryView },
  { path: '/books/:id',                           component: BookDetailView },
  { path: '/books/:id/summary',                   component: BookSummaryView },
  { path: '/books/:id/sections/:sectionId',       component: BookDetailView },
  { path: '/books/:id/sections/:sectionId/eval',  component: EvalDetailView },
  { path: '/search',                              component: SearchResultsView },
  { path: '/annotations',                         component: AnnotationsView },
  { path: '/concepts',                            component: ConceptsView },
  { path: '/settings',                            component: SettingsView },
  { path: '/settings/:section',                   component: SettingsView },
  { path: '/upload',                              component: UploadWizard },
]
```

### 11.3 State Management (Pinia Stores)

| Store | State | Key Actions |
|-------|-------|-------------|
| `books` | `books[]`, `currentView`, `views[]`, `filters`, `sort`, `selectedIds[]` | `fetchBooks()`, `createView()`, `updateFilters()`, `bulkAction()` |
| `reader` | `book`, `section`, `contentMode` (original/summary), `sidebarTab`, `sidebarOpen` | `loadSection()`, `navigateSection()`, `toggleContent()` |
| `readerSettings` | `activePreset`, `presets[]`, `currentSettings` | `applyPreset()`, `updateSetting()`, `saveAsPreset()` |
| `processing` | `jobs: Map<jobId, JobState>`, `sseConnections` | `startProcessing()`, `connectSSE()`, `cancelJob()` |
| `annotations` | `sectionAnnotations[]`, `globalAnnotations[]`, `filters` | `createAnnotation()`, `updateNote()`, `deleteAnnotation()`, `linkAnnotation()` |
| `aiThreads` | `threads[]`, `activeThread`, `messages[]`, `isLoading` | `createThread()`, `sendMessage()`, `saveAsNote()` |
| `search` | `query`, `quickResults`, `fullResults`, `recentSearches`, `filters` | `quickSearch()`, `fullSearch()`, `clearRecent()` |
| `concepts` | `concepts[]`, `selectedConcept`, `filters` | `fetchConcepts()`, `updateConcept()`, `resetConcept()` |
| `ui` | `commandPaletteOpen`, `uploadWizardOpen`, `toasts[]`, `activeModals[]` | `showToast()`, `openPalette()`, `closePalette()` |

### 11.4 Key Composables

**`useSSE(url: string)`** — Manages SSE connections with auto-reconnect:
```typescript
// Returns: { data: Ref<T>, error: Ref<Error>, status: Ref<'connecting'|'open'|'closed'> }
// Auto-reconnects up to 3 times on connection drop
// Falls back to REST polling via /processing/{id}/status on failure
```

**`useTextSelection(containerRef)`** — Detects text selection in reading area:
```typescript
// Returns: { selectedText, selectionRange, toolbarPosition, isSelecting }
// Calculates floating toolbar position (above selection, flips below if near top)
// Clears on click outside
```

**`useKeyboard(shortcuts: Record<string, handler>)`** — Global keyboard shortcut registration:
```typescript
// Registers Cmd+K, Cmd+U, Escape, arrow keys, etc.
// Deactivates when input/textarea is focused
```

---

## 12. Edge Cases

All edge cases are comprehensively specified in requirements §5. Key edge cases with architectural implications:

| # | Scenario | Condition | Expected Behavior |
|---|----------|-----------|-------------------|
| E1 | SSE reconnect after network drop | SSE connection drops during processing | Auto-reconnect (3 attempts). On failure, fetch state via `GET /processing/{id}/status`. Resume UI from server state. |
| E2 | Server crash during processing | ProcessingJob has PID, server restarts | Orphan check on next request: if PID dead, mark job failed. UI shows "Processing was interrupted. Resume?" |
| E3 | Concurrent processing jobs | Multiple books summarizing | Each job has its own SSE stream. Bottom bar stacks progress indicators. Jobs run concurrently via separate asyncio tasks. |
| E4 | Section edit during processing | User tries to edit sections | Blocked: "Cannot edit sections while processing is active." Check `ProcessingJob.status == 'running'`. |
| E5 | Stale eval after re-import | Book re-imported, content changed | Eval traces marked `is_stale=True`. Banner: "Verification data is stale. Re-verify?" |
| E6 | Very large section (>100KB markdown) | Long chapter content | Progressive rendering. Consider virtual scrolling for extremely long content. |
| E7 | Browser back during upload wizard | User presses back at Step 3 | Vue Router history: each step has URL path. Back returns to previous step with state preserved in Pinia store. |
| E8 | Multiple browser tabs | Two tabs open on same book | Both receive independent SSE connections. Both are read-only views of server state. No conflicts. |
| E9 | Annotation note too long | User pastes >10,000 chars | Client-side validation: "Note is too long. Maximum 10,000 characters." |
| E10 | Custom color with bad contrast | User picks medium gray background | System calculates contrast ratio for black and white text, picks best. Warning if neither meets WCAG AA. Does not block. |

---

## 13. Configuration & Feature Flags

### 13.1 New Settings (added to `config.py`)

```python
class NetworkConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    allow_lan: bool = False
    access_token: str | None = None  # Optional bearer token for LAN

class WebConfig(BaseModel):
    show_cost_estimates: bool = False
    static_dir: str = "static"  # Path to built frontend assets

# Added to Settings:
class Settings(BaseSettings):
    # ... existing fields ...
    network: NetworkConfig = NetworkConfig()
    web: WebConfig = WebConfig()
```

### 13.2 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `BOOKCOMPANION_NETWORK__HOST` | `127.0.0.1` | Server bind address |
| `BOOKCOMPANION_NETWORK__PORT` | `8000` | Server port |
| `BOOKCOMPANION_NETWORK__ALLOW_LAN` | `false` | Bind to 0.0.0.0 for LAN access |
| `BOOKCOMPANION_NETWORK__ACCESS_TOKEN` | `null` | Optional auth token |
| `BOOKCOMPANION_WEB__SHOW_COST_ESTIMATES` | `false` | Show cost/time estimates in UI |
| `BOOKCOMPANION_WEB__STATIC_DIR` | `static` | Built frontend path |
| `BOOKCOMPANION_LLM__CLI_COMMAND` | `claude` | Coding agent CLI command (claude/codex) |

### 13.3 Docker Compose

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: bookcompanion
      POSTGRES_PASSWORD: bookcompanion
      POSTGRES_DB: bookcompanion
    ports:
      - "5438:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bookcompanion"]
      interval: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      BOOKCOMPANION_DATABASE__URL: "postgresql+asyncpg://bookcompanion:bookcompanion@db:5432/bookcompanion"
      BOOKCOMPANION_NETWORK__HOST: "0.0.0.0"
      BOOKCOMPANION_NETWORK__PORT: "8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - backups:/app/backups

volumes:
  pgdata:
  backups:
```

### 13.4 Dockerfile

```dockerfile
# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim
WORKDIR /app

# Install system deps (Calibre for MOBI, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    calibre \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN pip install uv && cd backend && uv sync --no-dev

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./backend/static/

# Run migrations and start server
WORKDIR /app/backend
CMD ["sh", "-c", "uv run alembic upgrade head && uv run bookcompanion serve --host 0.0.0.0 --port 8000"]
```

---

## 14. Testing & Verification Strategy

### 14.1 Backend Unit Tests

**What to test:**
- All Pydantic request/response schema validation (edge cases, optional fields, type coercion)
- FastAPI dependency injection (session, services, settings)
- New service methods (AIThreadService, LibraryViewService, ReadingPresetService)
- SSE event formatting and serialization

**How:**
```bash
cd backend
uv run python -m pytest tests/unit/test_api_schemas.py -v
uv run python -m pytest tests/unit/test_api_deps.py -v
uv run python -m pytest tests/unit/test_ai_thread_service.py -v
```

### 14.2 Backend Integration Tests

**What to test:**
- Every API endpoint with real database (CRUD operations, pagination, filtering, sorting)
- SSE stream events during processing (mock LLM provider, real DB)
- File upload flow (real file, real parsing, real DB)
- Duplicate detection (hash match, fuzzy title match)
- Section merge/split/reorder operations
- Search (BM25 + semantic with real pgvector)

**How:**
```bash
# Start test DB
BOOKCOMPANION_DATABASE__URL=postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test \
  uv run python -m pytest tests/integration/test_api/ -v

# Test individual endpoint groups
uv run python -m pytest tests/integration/test_api/test_books_api.py -v
uv run python -m pytest tests/integration/test_api/test_processing_api.py -v
uv run python -m pytest tests/integration/test_api/test_search_api.py -v
```

**Test setup:** Use `httpx.AsyncClient` with `app=create_app()` for ASGI testing. Per-test database transaction rollback.

### 14.3 Frontend Unit Tests

**What to test:**
- Pinia store actions and getters
- Composable logic (useSSE reconnect, useTextSelection positioning, useKeyboard)
- Component rendering with props and slots

**How:**
```bash
cd frontend
npm run test:unit  # vitest
```

### 14.4 End-to-End Tests

**What to test:** (Playwright)
- Upload wizard: complete flow from file drop to processing start
- Library: filter, sort, display mode switching, view CRUD
- Reader: section navigation, original/summary toggle, concept chip interaction
- Annotations: create highlight, create note, delete with undo, link annotations
- AI chat: create thread, send message, receive response
- Search: command palette open, type query, navigate to result
- Reader settings: change font, size, background; verify persistence
- Mobile: bottom tab navigation, bottom sheet interactions, touch targets
- Settings: LAN toggle, preset CRUD, backup/restore

**How:**
```bash
cd frontend
npm run test:e2e  # playwright

# Specific test files
npx playwright test tests/e2e/upload.spec.ts
npx playwright test tests/e2e/reader.spec.ts
npx playwright test tests/e2e/search.spec.ts
npx playwright test tests/e2e/mobile.spec.ts --project=mobile-chrome
```

### 14.5 API Verification (CLI scripts before frontend)

Before building the frontend, verify all API endpoints work correctly via curl/httpie:

```bash
# Upload a book
curl -X POST http://localhost:8000/api/v1/books/upload \
  -F "file=@tests/fixtures/test_book.epub"

# List books
curl http://localhost:8000/api/v1/books

# Start processing
curl -X POST http://localhost:8000/api/v1/books/1/summarize \
  -H "Content-Type: application/json" \
  -d '{"preset_name": "balanced", "run_eval": true, "auto_retry": true}'

# Stream processing (SSE)
curl -N http://localhost:8000/api/v1/processing/1/stream

# Quick search
curl "http://localhost:8000/api/v1/search/quick?q=anchoring"

# Create annotation
curl -X POST http://localhost:8000/api/v1/annotations \
  -H "Content-Type: application/json" \
  -d '{"content_type": "section_content", "content_id": 5, "text_start": 100, "text_end": 200, "selected_text": "example text", "type": "highlight"}'
```

### 14.6 Verification Checklist

- [ ] `docker compose up` starts all services; UI accessible at `http://localhost:8000`
- [ ] Upload EPUB → parse → metadata/structure review → preset selection → processing completes
- [ ] SSE streams processing events; progress card updates in real-time
- [ ] Completed sections are browsable while processing continues
- [ ] Reader renders markdown with correct font/size/spacing/background settings
- [ ] Reader settings persist across sessions (page reload)
- [ ] System preference detection pre-selects Dark/Light on first load
- [ ] Original/Summary toggle works; concept chips render in summary view
- [ ] Text selection shows floating toolbar; highlight/note creation works
- [ ] AI chat: create thread, send message, receive complete response with loading indicator
- [ ] Command palette: Cmd+K opens, typing shows grouped results, Enter navigates
- [ ] Full search: hybrid results grouped by book, filter sidebar works
- [ ] Annotations page: filter/group/sort, click navigates to reader, export works
- [ ] Concepts explorer: two-panel layout, edit term/definition, reset to original
- [ ] Library views: create/edit/delete/reorder tabs, filters persist per view
- [ ] Bulk operations: select books → Tag/Summarize/Export/Delete
- [ ] Mobile (375px): bottom tab bar, bottom sheets, 44px touch targets, responsive grid
- [ ] LAN access: enable toggle, QR code shown, accessible from phone
- [ ] Reading position sync: "Continue where you left off" banner on different device
- [ ] Backup: create (pg_dump), list, download, restore, scheduled
- [ ] Export: single book + full library, Markdown/JSON formats
- [ ] Cancel processing: preserves completed sections
- [ ] Duplicate detection: exact hash and fuzzy title+author match
- [ ] All error states render user-friendly messages
- [ ] Skeleton loaders appear during data fetching
- [ ] WCAG AA: keyboard nav, focus indicators, color contrast, screen reader labels

---

## 15. Rollout Strategy

### 15.1 Implementation Phases

**Phase 1: Backend API + Core Pages**
1. FastAPI app factory, dependency injection, CORS, static file serving
2. Database migration (new tables + seed data)
3. Book API endpoints (CRUD, upload, duplicate detection)
4. Section API endpoints (CRUD, merge, split, reorder)
5. Processing API (summarize, SSE stream, status, cancel)
6. Frontend scaffolding (Vite, Vue Router, Pinia, Tailwind, shadcn-vue)
7. App shell (icon rail, top bar, routing)
8. Library page (views, filters, sort, display modes)
9. Book detail / reader (content rendering, navigation, original/summary toggle)

**Phase 2: Rich Features**
10. Reader settings (popover, presets, persistence)
11. Annotations (API + sidebar + global page)
12. AI chat (API + sidebar, coding agent CLI integration)
13. Search (API + command palette + full results page)
14. Concepts explorer (API + two-panel layout)
15. Upload wizard (multi-step flow, quality warnings, preset selection)
16. Processing progress (SSE integration, progress card, bottom bar)

**Phase 3: Settings, Mobile, Polish**
17. Settings page (general, database, presets, reading, backup)
18. Export & backup (API + UI)
19. Mobile responsive layouts (bottom tab, bottom sheets, touch interactions)
20. Reading position sync
21. Skeleton loaders, empty states, error handling
22. Docker compose (multi-stage build, production config)
23. E2E test suite

### 15.2 Rollback Plan

- All new code is additive (new `api/` directory, new `frontend/` directory, new DB tables)
- Existing CLI is unchanged — rollback = stop the web server
- Database rollback: `alembic downgrade -1` drops new tables only
- No feature flags needed — the web interface is either running or not

---

## 16. Research Sources

| Source | Type | Key Takeaway |
|--------|------|-------------|
| `backend/app/cli/deps.py` | Existing code | Service wiring pattern: async context manager yields dict of services with shared session |
| `backend/app/db/models.py` | Existing code | SQLAlchemy 2.0 with `Mapped[T]`, enums as `str, enum.Enum`, JSONB for flexible fields |
| `backend/app/config.py` | Existing code | Pydantic BaseSettings with nested models, YAML + env var loading |
| `backend/app/db/session.py` | Existing code | `create_session_factory()` returns `async_sessionmaker`, `expire_on_commit=False` |
| `backend/app/services/book_service.py` | Existing code | Constructor DI pattern: `__init__(self, db, config)`, creates repos internally |
| `docker-compose.yml` | Existing code | pgvector/pgvector:pg16 on port 5438, health checks |
| `docs/specs/2026-04-01_book_companion_v1_spec.md` | Existing spec | Spec format conventions, architecture decisions, testing strategy |
| `sse-starlette` | External library | FastAPI-compatible SSE via `EventSourceResponse` |
| `shadcn-vue` | External library | Accessible, unstyled Vue 3 components built on Radix Vue |

---

## 17. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Should the `bookcompanion serve` command also run Vite dev server in dev mode, or require a separate terminal? | Maneesh | Before plan |
| 2 | For AI chat context window management: what's the max context size to send (book summary + N section summaries + thread history)? Should there be a token budget? | Maneesh | Before plan |
| 3 | Should LAN access QR code use a JS library (qrcode.js) or server-generated image? | Maneesh | Before plan |
| 4 | Should the coding agent CLI command be configurable per-book or global only? Currently global via `llm.cli_command`. | Maneesh | Before plan |
| 5 | For scheduled backups: should the scheduler run within the FastAPI process (APScheduler) or as a separate cron/systemd timer? | Maneesh | During Phase 3 |

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | Initial draft | Full spec written from requirements + research |
| 2 | Missing: reading re-entry card (§3.3.6), annotation cross-view visibility (§3.3.5), consistency indicator detail (§3.3.7) | Added FR-27a (re-entry), FR-29a (cross-view annotations), clarified FR-29 consistency metric |
