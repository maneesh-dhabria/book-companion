# Book Companion Web Interface - V1 Requirements

**Version:** 1.2
**Date:** 2026-04-10
**Status:** Draft
**MSF Analysis:** [Web Interface MSF Analysis](../msf/2026-04-10_web_interface_msf_analysis.md)
**Creativity Analysis:** [Web Interface Creativity Analysis](../creativity/2026-04-10_web_interface_creativity_analysis.md)
**Predecessor:** [V1 CLI Requirements](2026-04-01_book_companion_v1_requirements.md)
**Wireframes:** [V2 Web Interface Wireframes](../wireframes/2026-04-10_v2_web_interface/README.md)

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [Tech Stack & Architecture](#2-tech-stack--architecture)
3. [Screen-by-Screen Requirements](#3-screen-by-screen-requirements)
   - 3.1 [App Shell & Navigation](#31-app-shell--navigation)
   - 3.2 [Library Page](#32-library-page)
   - 3.3 [Book Detail / Reader](#33-book-detail--reader)
   - 3.4 [Reader Settings](#34-reader-settings)
   - 3.5 [Upload & Processing](#35-upload--processing)
   - 3.6 [Search](#36-search)
   - 3.7 [Annotations Page](#37-annotations-page)
   - 3.8 [Concepts Explorer](#38-concepts-explorer)
   - 3.9 [Settings Page](#39-settings-page)
   - 3.10 [Multi-Device / Mobile](#310-multi-device--mobile)
4. [User Journeys](#4-user-journeys)
5. [Edge Cases & Error Handling](#5-edge-cases--error-handling)
6. [Test Scenarios](#6-test-scenarios)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Data Model](#8-data-model)
9. [API Design Overview](#9-api-design-overview)

---

## 1. Overview & Goals

### 1.1 Purpose

Build a web interface for Book Companion that provides full feature parity with the existing CLI tool. The web interface adds visual reading, annotation, AI conversation, and library management capabilities that are impractical in a terminal.

### 1.2 Goals

- **Full feature parity**: Every CLI operation (add, summarize, evaluate, search, export, backup) is accessible from the web UI.
- **Reader-centric design**: Books are the center of gravity. Every feature flows from or back to a book.
- **Reading-first experience**: Comfortable long-form reading with customizable typography, background, and spacing.
- **Real-time feedback**: Long-running operations (summarization, evaluation, embedding) stream progress via SSE.
- **Mobile-ready**: Full feature parity on mobile devices via responsive layouts and touch-adapted interactions.
- **Local-first**: No cloud dependency. Runs on localhost with optional LAN access for mobile devices.

### 1.3 Non-Goals

- Multi-user authentication (single user, personal tool)
- Cloud hosting or SaaS deployment
- Real-time collaboration
- Fiction book support
- Social/sharing features

### 1.4 Glossary

Inherits all terms from V1 CLI requirements. Additional web-specific terms:

| Term | Definition |
|------|-----------|
| **Library View** | A saved combination of filters, sort order, and display mode. Persisted to database. |
| **Reading Preset** | A saved combination of font, size, spacing, width, and background for the reader. |
| **AI Thread** | A per-book conversation with the LLM, stored as a sequence of messages. |
| **Command Palette** | A centered modal triggered by Cmd+K for quick search and navigation. |
| **Context Sidebar** | Collapsible right panel in the reader showing Annotations or AI Chat. |
| **Bottom Sheet** | Mobile-adapted modal that slides up from the bottom of the screen. |
| **SSE** | Server-Sent Events, used for streaming progress of long-running operations. |
| **Icon Rail** | A narrow (56px) sidebar showing only icons for primary navigation. |
| **Verify / Verification** | User-facing term for the eval assertion system. Internal code uses "eval" — the UI always says "Verify." *(Creativity: M8)* |

---

## 2. Tech Stack & Architecture

### 2.1 Frontend

| Component | Technology |
|-----------|-----------|
| Framework | Vue 3 (Composition API, `<script setup>`) |
| Build tool | Vite |
| Routing | Vue Router 4 |
| State management | Pinia |
| CSS | Tailwind CSS 3 |
| Component library | shadcn-vue |
| HTTP client | Fetch API (native, for SSE support) |
| Markdown rendering | markdown-it or remark |
| Code highlighting | Shiki (for code blocks in technical books) |

### 2.2 Backend (FastAPI Layer)

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI |
| ASGI server | Uvicorn |
| Serialization | Pydantic v2 (response/request models) |
| Database | Shared SQLAlchemy 2.0 async models (same as CLI) |
| Services | Shared service layer (same as CLI) |
| File uploads | `python-multipart` |
| SSE | `sse-starlette` |
| CORS | `fastapi.middleware.cors` (for dev, localhost only) |

### 2.3 Architecture Diagram

```
Vue 3 SPA (Vite)
  │  Fetch API / SSE
  ▼
FastAPI (same repo: backend/app/api/)
  │  Depends() injection
  ▼
Shared Service Layer (BookService, SummarizerService, EvalService, etc.)
  │
  ▼
SQLAlchemy 2.0 async → asyncpg → PostgreSQL 16 + pgvector
```

### 2.4 Key Architectural Decisions

- **Same repository**: FastAPI routes live alongside CLI commands in `backend/app/api/`. Both share models, services, repositories.
- **Shared session management**: FastAPI dependency injection provides `AsyncSession` per request, mirroring `cli/deps.py:get_services()`.
- **No BFF pattern**: The FastAPI backend serves the Vue SPA directly. No intermediate API gateway.
- **SSE over WebSockets**: For streaming progress, SSE is simpler (unidirectional, auto-reconnect, works through proxies). WebSockets are not needed since all streaming is server-to-client.
- **Static file serving**: In production, FastAPI serves the built Vue SPA from `backend/static/`. During development, Vite dev server proxies API calls to FastAPI.
- **No auth**: Single-user personal tool running on a trusted local network. No authentication layer.

### 2.5 Project Structure

```
backend/
  app/
    api/                    # NEW: FastAPI layer
      __init__.py
      main.py               # FastAPI app factory, CORS, static files
      deps.py               # Depends() for session, services, settings
      middleware.py          # Optional auth token middleware
      routes/
        books.py             # /api/books/*
        sections.py          # /api/books/{id}/sections/*
        summaries.py         # /api/summaries/*
        search.py            # /api/search/*
        presets.py           # /api/presets/*
        eval.py              # /api/eval/*
        annotations.py       # /api/annotations/*
        concepts.py          # /api/concepts/*
        tags.py              # /api/tags/*
        settings.py          # /api/settings/*
        upload.py            # /api/upload/*
        export.py            # /api/export/*
        views.py             # /api/views/*
        reading_prefs.py     # /api/reading-preferences/*
        ai_threads.py        # /api/ai-threads/*
        processing.py        # /api/processing/* (SSE streams)
      schemas/               # Pydantic request/response models
        book.py
        section.py
        summary.py
        ...
    cli/                    # Existing CLI (unchanged)
    db/
      models.py             # Existing + new web tables
    services/               # Existing services (shared)
frontend/
  src/
    components/
    views/
    stores/
    composables/
    router/
    assets/
  vite.config.ts
  tailwind.config.ts
```

---

## 3. Screen-by-Screen Requirements

### 3.1 App Shell & Navigation

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/app_shell/app-shell-final.html` (desktop)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/app_shell/app-shell-mobile.html` (mobile)

#### 3.1.1 Desktop Layout (>= 1024px)

- **Icon Rail Sidebar** (56px wide, fixed left):
  - 4 navigation items, each as a 40x40px icon button with tooltip on hover:
    1. Library (book icon) - route: `/`
    2. Concepts (lightbulb icon) - route: `/concepts`
    3. Annotations (pencil icon) - route: `/annotations`
    4. Settings (gear icon) - route: `/settings`
  - Active item: accent-colored background + icon fill
  - Subtle separator above Settings (pushed to bottom)
  - Background: neutral gray, slightly darker than content area

- **Top Bar** (full width minus sidebar, 48px height):
  - Left: Page title (e.g., "Library", "Settings") in semibold text
  - Center-right: Search input field (240px min-width, expandable). Placeholder: "Search books, concepts... (Cmd+K)". Click or Cmd+K opens command palette.
  - Right: "Upload" button (primary accent, icon + text). Always visible as the primary action.

- **Content Area**: Fills remaining space. Scrollable. Max-width varies by page.

#### 3.1.2 Tablet Layout (768-1023px)

- Sidebar collapses to icon-only (same 56px rail, no change needed since it is already icon-only)
- Top bar search input shrinks; may collapse to icon-only with click to expand
- Content area gets full remaining width

#### 3.1.3 Mobile Layout (< 768px)

- Sidebar is removed entirely
- **Bottom Tab Bar** (56px, fixed bottom, 5 tabs):
  1. Library (book icon + "Library" label)
  2. Search (magnifying glass + "Search")
  3. Concepts (lightbulb + "Concepts")
  4. Annotations (pencil + "Annotations")
  5. Settings (gear + "Settings")
- Active tab: accent-colored icon + label
- Top bar simplified: Page title left, Upload button right (icon only on narrow screens)
- Content area: full width, bottom padding for tab bar

#### 3.1.4 Global Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+K` / `Ctrl+K` | Open command palette |
| `Cmd+U` / `Ctrl+U` | Open upload dialog |
| `Escape` | Close any modal/palette/popover |
| `Cmd+/` / `Ctrl+/` | Toggle keyboard shortcuts help |
| `f` | Toggle Focus Mode in reader *(Nice-to-have — V1.1+)* *(Creativity: N5)* |

---

### 3.2 Library Page

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/library/library-final.html` (desktop)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/library/library-mobile.html` (mobile)

#### 3.2.1 Custom Views (Notion-style)

- **View tabs**: Horizontal row below the top bar. Each tab shows the view name. Active tab is underlined with accent color.
- **Default view**: "All Books" (built-in, cannot be deleted, can be customized).
- **"+ New View" button**: Appears as last tab. Creates a new view either:
  - From current filter state (pre-populates with active filters)
  - From scratch (empty filters)
- **View tab actions** (right-click or click "..." on tab):
  - Rename
  - Duplicate
  - Set as default (shown on app load)
  - Reorder (drag tabs)
  - Delete (with confirmation; cannot delete last view)
- **Unsaved changes indicator**: When filters/sort differ from saved state, a subtle dot appears on the tab. Tooltip: "Unsaved changes. Click to save or reset."
- **View persistence**: Each view saves:
  - Filter selections (all dimensions)
  - Sort field and direction
  - Display mode (grid/list/table)
  - Table column visibility and order (when in table mode)

#### 3.2.2 Filter Row

Single horizontal row of uniform multi-select dropdown buttons:

| Filter | Options | Behavior |
|--------|---------|----------|
| Tags | All user-created tags | Multi-select, OR within |
| Status | uploading, parsing, parsed, summarizing, completed, parse_failed | Multi-select, OR within |
| Author | All authors in library | Multi-select, OR within |
| Eval | Passed, Failed, Partial, Not evaluated | Multi-select, OR within |
| Format | EPUB, MOBI, PDF | Multi-select, OR within |

- **Between dimensions**: AND logic (e.g., Tag="ML" AND Status="completed" AND Author="Kahneman")
- **Within dimension**: OR logic (e.g., Status="completed" OR Status="summarizing")
- **Active filter display**: Selected values shown as pills inside the dropdown button. "x" to remove individual values.
- **Clear all**: "Clear filters" link appears when any filter is active.
- **Filter counts**: Each dropdown option shows count of matching books (e.g., "completed (12)"). Counts update dynamically as other filters change (cross-filter counts), so users always see how many books will match before applying. *(Creativity: M5)*

#### 3.2.3 Sort Control

Dropdown to the right of filters:

| Sort Option | Description |
|-------------|-------------|
| Recent (default) | `updated_at` descending |
| Title A-Z | Alphabetical by title |
| Author A-Z | Alphabetical by first author name |
| Most sections | `section_count` descending |
| Eval score | Percentage of passing assertions descending |
| Date added | `created_at` descending |

#### 3.2.4 Display Modes

Toggle group (3 icon buttons) to the right of sort:

**Grid Mode:**
- Responsive grid: 4 columns (desktop), 3 (tablet), 2 (mobile)
- **Book card contents**:
  - Cover thumbnail (160x240px placeholder if no cover). Hover: subtle scale-up.
  - Title (truncated at 2 lines)
  - Author(s) (truncated at 1 line)
  - Tag pills (max 3 shown, "+N" for overflow)
  - Status badge (color-coded: green=completed, blue=summarizing, yellow=parsed, red=failed, gray=uploading/parsing)
  - Eval score (if available): green/yellow/red ring with "14/16" text
  - Section count: "24 sections" in muted text
- **Card click**: Navigate to Book Detail (`/books/{id}`)
- **Card right-click / long-press**: Context menu with: Open, Summarize, Verify, Edit metadata, Export, Delete *(Creativity: M8)*

**List Mode:**
- Compact rows, one book per row
- Columns: Cover thumbnail (40x60px), Title, Author, Tags (pills), Status badge, Eval, Sections, Updated
- Row click: Navigate to Book Detail
- Row hover: Subtle background highlight

**Table Mode:**
- Full data table with configurable columns
- Default columns: Title, Author, Status, Tags, Format, Sections, Eval Score, Date Added, Last Updated
- **Column layout**: Title (min 200px, sticky left), Author (150px), Status (100px badge), Tags (150px pills), Format (80px badge), Sections (80px number), Eval Score (100px with mini ring), Date Added (120px relative), Last Updated (120px relative)
- Column visibility toggle (gear icon on table header): Checklist of all columns, "Reset to defaults" at bottom
- Column drag-to-reorder: Visual drag handle on column header, drop indicator line between columns
- Column sort by clicking header: Toggle asc/desc, sort indicator arrow on active column
- Row click: Navigate to Book Detail
- Row hover: Subtle background highlight + action icons appear (Summarize, Export, Delete)
- **Checkbox column** (fixed first column): For multi-select bulk operations (see 3.2.6)
- Horizontal scroll when columns exceed viewport width; Title column stays fixed

#### 3.2.5 Empty States

- **No books at all** (first-time user experience):
  - Centered welcome illustration
  - Heading: "Welcome to Book Companion"
  - Subheading: "Upload a non-fiction book and get AI-powered summaries, concepts, and a searchable knowledge base"
  - 3-step "how it works" visual: (1) Upload book icon + "Upload an EPUB, MOBI, or PDF", (2) AI processing icon + "AI summarizes each section and extracts key concepts", (3) Library icon + "Browse, annotate, search, and ask AI questions"
  - Primary CTA: "Upload Your First Book" button (accent, large)
  - Supported formats note: "Supports EPUB, MOBI, and PDF files up to 100MB"
  - Optional: "Typical processing time: ~8 min for a 300-page book"
- **No books match filters**: "No books match your filters" + "Clear filters" button + "or try a different view"
- **View has no books**: Same as above, specific to the active view

#### 3.2.6 Bulk Book Operations

- **Multi-select mode**: Checkboxes on book cards (grid/list mode: visible on hover; table mode: always-visible first column)
- **Activation**: Click any checkbox, or "Select" toggle button in filter row
- **Floating toolbar** (appears when 1+ books selected): "N books selected" + action buttons:
  - "Tag" — Opens tag picker to apply tags to all selected books
  - "Summarize" — Opens preset picker, applies to all selected books (queued processing)
  - "Export" — Opens export dialog with scope pre-set to selected books
  - "Delete" — Confirmation dialog listing all selected books by title
  - "Deselect All" — Clears selection
- **Select all**: Checkbox in table header selects all visible books (respects current filters)

---

### 3.3 Book Detail / Reader

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/book_detail/book-detail-final.html` (desktop)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/book_detail/book-detail-mobile.html` (mobile)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/ai_chat/ai-chat-final.html` (AI chat — desktop)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/ai_chat/ai-chat-mobile.html` (AI chat — mobile)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/images/image-handling-final.html` (image display in reader)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/editing/editing-final.html` (all editing interfaces)

#### 3.3.1 Layout Structure

- **Header bar** (sticky top, within content area):
  - Left: Breadcrumb navigation: `Library` > `Book Title` > `Chapter Name (dropdown)`
  - Center: Original/Summary segmented control toggle
  - Right: Action buttons (left to right):
    - `Aa` (reader settings popover)
    - `AI` (opens context sidebar on AI tab, always visible including in focus mode)
    - `Annotations` (opens context sidebar on Annotations tab, badge shows count when closed)
    - `Prev/Next` section arrows

- **Reading Area** (center):
  - Max-width: 720px, centered
  - Renders markdown content (original `content_md` or summary `summary_md`)
  - Applies reader settings (font, size, spacing, width, background)
  - Text selection triggers floating toolbar

- **Context Sidebar** (right, collapsible):
  - Default: collapsed (hidden)
  - Width: 360px (desktop), full-screen bottom sheet (mobile)
  - Two tabs: Annotations | Ask AI
  - Close via X button or clicking the active sidebar toggle button again

#### 3.3.2 Breadcrumb Navigation

- **Library segment**: Always links to `/` (Library page)
- **Book Title segment**: Links to book's first section (or book summary if available). Click opens dropdown with:
  - Book actions: Summarize, Verify, Edit metadata, Edit sections, Export, Delete, Re-import *(Creativity: M8)*
  - "Quick export" -- copies the current section's default summary as plain text to clipboard and optionally saves as `.txt` in Downloads. No dialog, no checkboxes -- a one-tap share path. *(Nice-to-have — V1.1+)* *(Creativity: N6)*
  - Book summary link (if default summary exists)
- **Chapter Name segment**: Click opens full Table of Contents dropdown:
  - Search input at top for filtering sections
  - Sections listed with: title, section type badge (chapter/appendix/glossary/etc.), eval status dot (green=passed, yellow=partial, red=failed, gray=not evaluated)
  - Grouped by section type: Chapters first, then other types
  - Current section highlighted
  - Click navigates to that section

#### 3.3.3 Original/Summary Toggle

- **Segmented control** (not tabs): Two options, "Original" and "Summary". When the book has summaries, the toggle defaults to "Summary" on first load. Users switch to "Original" on demand. *(Creativity: M1)*
- When "Summary" is active:
  - If no summary exists: Show "No summary yet" message + "Summarize" button
  - If summary exists: Render default summary markdown
  - **Summary version**: The default summary (`default_summary_id`) is always shown automatically — no version picker is displayed unless multiple versions exist. When multiple versions exist, a "History (N versions)" link appears below the eval badge. Clicking it opens the comparison view. This avoids the "which version am I reading?" decision during normal reading. Users who want to switch versions do so intentionally via History.
  - **Edit preserves original**: When a user edits a summary (via inline editing), the edit is saved as a **new summary version** (with `user_edited=True`) rather than overwriting the AI-generated version. Both "AI version" and "My edit" appear in the version selector. The user-edited version becomes the new default.
  - **Eval trust badge**: Single compact badge within summary view (not an expandable accordion):
    - Green badge: "This summary is solid" with checkmark (16/16 or 15/16 passed) *(Creativity: M3)*
    - Yellow badge: "Worth a quick review" with warning icon (12-14/16 passed) *(Creativity: M3)*
    - Red badge: "Some issues found" with alert icon (< 12/16 passed) *(Creativity: M3)*
    - Gray badge: "Not verified" with "Verify" link *(Creativity: M3, M8)*
    - Score shown as "14/16" next to the badge label
    - **"View details" link** navigates to a dedicated eval detail view (route: `/books/{id}/sections/{section_id}/eval`) rather than expanding inline. This keeps the reading experience clean and avoids QA-dashboard friction during study.
    - The eval detail view shows the full grouped accordion (Faithfulness, Completeness, Coherence, Specificity, Format) with assertion names, pass/fail, reasoning, and Re-verify button. Each assertion name includes a plain-language tooltip explaining what it checks (e.g., `no_hallucinated_facts` → "Checks that the summary doesn't include facts not present in the source text"). *(Creativity: M3, M8)*
- When "Original" is active:
  - Render `content_md` from `BookSection`
  - No eval banner, no version selector

#### 3.3.4 Concepts in Content

- Concept terms appearing in summary content are rendered as **clickable chips** (subtle background, rounded).
- Click on concept chip opens tooltip/popover:
  - Term name (bold)
  - Definition
  - "Appears in N sections" with clickable list
  - Related concepts as clickable pills
  - "Edit" link (opens concept editing inline)
  - **"Ask AI about this" button** -- opens the AI sidebar tab and creates a new thread seeded with: "Explain [concept term] as discussed in [section title]". The concept definition and section context are included in the AI prompt. *(Creativity: S1)*
- Concept detection: Match `Concept.term` values against rendered summary text. Case-insensitive, word-boundary matching.

#### 3.3.5 Text Selection Floating Toolbar

When user selects text in the reading area, a floating toolbar appears above the selection:

| Button | Icon | Action |
|--------|------|--------|
| Highlight | Highlight icon | Creates a `highlight` annotation for selected text |
| Note | Pencil icon | Opens note input inline, creates `note` annotation |
| Ask AI | Sparkle icon | Opens AI sidebar with selected text as context block |
| Link | Link icon | Opens annotation linking dialog |
| Copy | Copy icon | Copies selected text to clipboard |

- Toolbar positioning: Centered above selection, flips below if near top of viewport
- Disappears when selection is cleared or user clicks elsewhere
- **Highlight style**: Text highlights use a hand-drawn marker stroke aesthetic (CSS with SVG clip-path for slightly irregular edges) rather than flat rectangular backgrounds. This references the physical act of highlighting in a book and gives the reader a distinctive, warm visual identity. *(Nice-to-have — V1.1+)* *(Creativity: N7)*
- **Annotation visibility across views**: Annotations created in either Original or Summary view are **visible in both views**. When viewing the alternate content type, annotations from the other view appear as subtle indicators (dimmed highlight, dashed border) with a label showing their source: "Highlighted in Summary" or "Highlighted in Original". Clicking the indicator scrolls to the approximate location in the other view. The `content_type` field still tracks where the annotation was created, but it does not restrict display.

#### 3.3.6 Section Navigation

- **Prev/Next arrows** in header: Navigate to adjacent sections (by `order_index`)
- **Keyboard shortcuts**:
  - `Left arrow` or `Alt+P`: Previous section
  - `Right arrow` or `Alt+N`: Next section
- At first section: Prev is disabled. At last section: Next is disabled.
- Navigation preserves toggle state (original/summary) and sidebar state
- **Reading re-entry**: When a user navigates to a section they previously visited (detected by `last_opened_at` timestamp with >24h gap), a subtle re-entry card appears above the content: "Last time here, you highlighted: '[quoted text]...'" with a link to scroll to that annotation. Dismissed on scroll or close. Uses the most recent annotation on that section. *(Creativity: S3)*

#### 3.3.7 Book-Level Summary View

- Accessed from breadcrumb Book Title dropdown or directly via URL `/books/{id}/summary`
- Shows the book's `default_summary_id` summary
- Same eval banner, version selector, and concept chip behavior as section summaries
- **Consistency indicator**: In addition to the book-level eval badge, show a consistency metric: the variance (or range) of eval scores across all sections. Example: "Sections range from 12/16 to 16/16 -- 3 sections need attention." Sections below the book average are listed as clickable links. This surfaces uneven quality that per-section scores alone do not reveal. *(Creativity: S9)*
- Actions available: Summarize (opens preset picker), Verify, Export *(Creativity: M8)*

#### 3.3.8 Context Sidebar - Annotations Tab

- Shows annotations for the current section, ordered by text position (`text_start`)
- Each annotation card:
  - Type badge (color-coded: yellow=highlight, blue=note, green=freeform)
  - Quoted selected text (if highlight/note) with left-border accent
  - Note body (editable on click)
  - Linked annotations: "Linked to: [Section X annotation]" (clickable)
  - Date (relative: "2 hours ago")
  - Actions: Edit, Link, "..." menu (Delete with 5-second undo toast, Copy text, Move to section)
  - **Inline quick-link** (opened via Link action): A compact popover (not a full modal) attached to the annotation card:
    - Search input: "Find annotation to link..." with instant results
    - Results show: annotation type badge, quoted text preview (truncated), source breadcrumb (Book > Section)
    - **Recent annotations** shown first when no search query is entered (last 5)
    - Click a result to link immediately (no preview pane, no confirmation step — keeps the interaction lightweight during reading)
    - The **full link dialog** (with book filter, preview pane, and advanced search) is accessible from the global Annotations page where cross-book linking is a deliberate activity, not an interruption to reading flow
- **Margin alignment**: When scrolling through content, annotations visually align with their corresponding highlighted text spans
- **Freeform note input** at bottom: Text area for section-level notes not tied to specific text selections. "Add note" button.

#### 3.3.9 Context Sidebar - Ask AI Tab

- **Thread list** (default view when no thread is active):
  - Each thread: Title (auto-generated or user-set), message count, last activity date, preview of last message (truncated)
  - "New Thread" button at top (for creating additional threads)
  - Click thread to open it
  - When no threads exist for this book, opening the AI tab auto-creates a new thread seeded with the current section as context. The input area is immediately focused — no "New Thread" click needed. *(Creativity: M4)*

- **Thread view** (active conversation):
  - Back arrow to return to thread list
  - Thread title (editable via click)
  - Chat-style messages:
    - User messages: Right-aligned, accent background
    - AI responses: Left-aligned, neutral background, rendered markdown
  - **Context blocks**: When text was selected before asking, it appears as a quoted block above the user message. Shows section source.
  - **Multi-section context**: AI can reference and quote from multiple sections. Section references appear as clickable links.
  - **Input area** at bottom:
    - Text input with "Ask about this book..." placeholder
    - Send button (Cmd+Enter)
    - If text is selected in the reader: Context preview chip showing "Using selected text from [Section]" with X to remove
    - **"+ Add context" button**: Opens a section picker (TOC checkbox list) to include additional sections in the AI context. Selected sections appear as stacked context chips: "Using Chapter 3, Chapter 5, Chapter 8". Each chip has X to remove. This enables cross-chapter questions like "Compare the arguments in chapters 3 and 8."
  - **Save as annotation**: Each AI response has a "Save as note" action that creates a freeform annotation on the relevant section. Shows a confirmation toast: "Saved as annotation on [Section Name]" with an "Open" link to the Annotations sidebar.

- **AI behavior**:
  - Context includes: current section content, current section summary (if exists), book title, author
  - Multi-section queries: AI can be asked about the entire book. Context window includes book summary + relevant section summaries. When additional sections are selected via "+ Add context", their content/summaries are included in the prompt.
  - Streaming: AI responses stream token-by-token via SSE. During generation, a thin progress bar animates below the AI message bubble (indeterminate style) to provide visual feedback beyond the typing indicator dots.

#### 3.3.10 Focus Mode

- **Focus Mode**: Keyboard shortcut `f` (or toggle button in header) collapses the header bar, hides the sidebar, removes the eval banner, and leaves only the centered reading area with arrow-key section navigation. Press `f` or `Escape` to exit. *(Nice-to-have — V1.1+)* *(Creativity: N5)*

---

### 3.4 Reader Settings

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/reader_settings/reader-settings-final.html` (desktop)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/reader_settings/reader-settings-mobile.html` (mobile)

#### 3.4.1 Popover Trigger

- Triggered by clicking "Aa" button in the Book Detail header
- Popover appears below the button, right-aligned
- Width: 380px (desktop), full-width bottom sheet (mobile)

#### 3.4.2 Presets Section (top of popover)

- **Visual preset cards**: Horizontal scrollable row of square cards (80x80px each):
  - Each card shows:
    - Background color fill
    - "Aa" rendered in the preset's chosen font
    - Font name below
    - Spacing value in muted text
  - Active preset: Accent border + checkmark overlay
  - User presets show pencil (edit) icon on hover
- **System presets** (read-only): Comfortable, Night Reading, Study Mode, Compact
- **User presets**: Created via "+ Save Current" button
- **"+ Save Current"**: Saves current settings as a named user preset. Opens name input inline.

#### 3.4.3 Font Selection

- **Named font buttons**: Horizontal wrap of pill buttons, each showing the font name rendered in that font. **Primary fonts** (shown by default):
  - Georgia (serif), Merriweather (serif), Inter (sans-serif), Fira Code (monospace)
- **"All fonts" expansion link**: Reveals additional options: Literata, Lora, Open Sans, JetBrains Mono. Collapsed by default to reduce choice overload.
- Active font: Accent background + border
- Fonts are loaded on demand (Google Fonts or self-hosted)

#### 3.4.4 Size

- **Named buttons**: Small (14px), Medium (16px), Large (18px), XL (20px)
- **Manual stepper**: Minus/Plus buttons with current px value displayed between them
- Named buttons are shortcuts that set the stepper value

#### 3.4.5 Line Spacing

- **Named buttons**: Tight (1.4), Normal (1.6), Relaxed (1.8), Spacious (2.0)
- **Manual stepper**: Minus/Plus with current multiplier value

#### 3.4.6 Content Width

- **Named buttons**: Narrow (560px), Medium (720px), Wide (880px), Full (100%)
- **Manual stepper**: Minus/Plus with current px value
- Only applies to reading area max-width

#### 3.4.7 Background & Colors

- **Preset swatches**: Circular color buttons with labels:
  - Light: white background (#FFFFFF), dark text
  - Sepia: warm cream (#FBF0D9), dark brown text
  - Dark: dark gray (#1E1E2E), light gray text
  - OLED: pure black (#000000), white text
  - Dracula: Dracula theme (#282A36), Dracula foreground
- **Custom button** (palette icon): Opens expanded color picker:
  - Gradient area (saturation/brightness) + hue slider
  - Hex input field
  - Text color auto-adjusts: Calculates contrast ratio, switches to light or dark text for WCAG AA compliance
- Active swatch: Checkmark overlay + accent ring

#### 3.4.8 Live Preview

- **Sample text area** at bottom of popover: 3-4 lines of sample text that updates in real-time as settings change
- **Summary line**: "16px Merriweather, 1.6 spacing, 720px, Sepia" in muted text

#### 3.4.9 Persistence

- Reader settings are saved to database (per-user, since single user: global)
- Applied immediately on load across all book pages
- Persisted across sessions (not just localStorage -- survives browser clearing)
- **System preference detection**: On first load (no saved reading preferences), the app detects the system color scheme (`prefers-color-scheme` media query). If dark mode is detected, the "Dark" background swatch is pre-selected. If light, "Light" is pre-selected. Users can change at any time. *(Creativity: S10)*

---

### 3.5 Upload & Processing

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/upload_processing/upload-step1-final.html` (Step 1 drag-drop)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/upload_processing/upload-flow-final.html` (Steps 2-5)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/upload_processing/upload-edge-cases.html` (Edge cases + presets)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/upload_processing/upload-mobile.html` (mobile)

#### 3.5.1 Entry Points

- "Upload" button in top bar (always visible)
- Drag-and-drop anywhere on the Library page
- Command palette: Type "upload" to see Upload action

#### 3.5.1a Wizard Step Indicator

The upload wizard uses a **3-step visual indicator** to reduce perceived complexity:

| Visible Step | Label | Internal Sub-steps |
|-------------|-------|-------------------|
| 1 | **Upload** | File selection, parsing, Quick Upload fork |
| 2 | **Configure** | Metadata review, Structure review, Preset selection |
| 3 | **Process** | Summarization progress (in Book Detail) |

The indicator shows 3 numbered circles connected by lines. Step 2 ("Configure") encompasses the Metadata, Structure Review, and Preset Selection screens as sub-steps — these advance within the same visual step. This reduces the perceived effort from 5 steps to 3 without removing any functionality.

#### 3.5.2 Step 1: Upload

- **Drag-and-drop zone**: Large dashed-border area with icon + "Drop your book here or click to browse"
- **Accepted formats**: .epub, .mobi, .pdf
- **Max file size**: 100MB (configurable via `storage.max_file_size_mb`)
- **Cost hint** (shown when `settings.show_cost_estimates` is enabled): Muted text below the format note: "AI processing typically costs ~$1-2 per book." Appears before file selection to set expectations early, preventing surprise cost discovery at later steps.
- **Progress**: Upload progress bar during file transfer to server
- **Validation**:
  - File extension check (client-side, immediate)
  - File size check (client-side, immediate)
  - MIME type validation (server-side, after upload)
  - File integrity check (server-side, after upload)
- **Duplicate detection** (server-side, by SHA-256 hash):
  - **Same file (exact hash match)**: Warning dialog with options:
    1. "Go to existing" -- Navigate to the existing book's detail page
    2. "Re-import" -- Re-process the file. Marks existing eval traces as `is_stale=True`. Updates sections in-place by `order_index`.
    3. "Cancel" -- Return to upload
  - **Different format, same title+author** (fuzzy match): Side-by-side comparison dialog:
    - Left: Existing book (format, sections, date added, summary status)
    - Right: New upload (format, estimated sections)
    - Options:
      1. "Add as separate book" -- Adds as a distinct book entry
      2. "Replace existing" -- Deletes old book, adds new one. Warning: "This will delete all summaries, annotations, and eval data for the existing book."
      3. "Cancel"
- On success: Auto-advance to Step 2
- **Quick Upload fast path**: After successful upload and parsing, show a prominent split CTA:
  - Primary button: **"Start with Recommended Settings"** — skips Steps 2-4, uses auto-extracted metadata, default preset (marked "Recommended"), runs eval and auto-retry. Advances directly to Book Detail with processing.
  - Secondary link: "Customize metadata, structure & preset →" — enters the full Step 2-4 wizard.
  - The fast path is designed for first-time users who want to see value quickly. Power users use the full wizard.

#### 3.5.3 Step 2: Metadata

- **Cover image**: Auto-extracted thumbnail (from EPUB metadata). Click to change (file picker). If no cover found: placeholder graphic.
- **Title**: Text input, pre-filled from book metadata. Editable.
- **Author(s)**: Text input(s), pre-filled from metadata. Multiple author support with add/remove. Editable.
- **Tags**: Tag chips with "+ Add tag" button. Autocomplete from existing tags. Create new tags inline.
- **Format**: Read-only badge (EPUB/MOBI/PDF)
- **File size**: Read-only display
- All fields are pre-populated from book metadata. If metadata extraction is complete and no quality issues are detected, a "Looks good" confirmation banner appears with a prominent "Next" button — the default path is a single tap to advance without editing. *(Creativity: M2)*
- **Navigation**: Back to Step 1, Next to Step 3

#### 3.5.4 Step 3: Structure Review

- **Section list** as a table:

  | Column | Description |
  |--------|-------------|
  | Drag handle | For reordering via drag-and-drop |
  | Checkbox | For multi-select operations |
  | Title | Section title (editable inline) |
  | Type | Section type badge (chapter, glossary, etc.) with dropdown to change |
  | Characters | Character count |
  | Quality | Quality indicator (green/yellow/red) |

- **Quality warnings** shown inline per section:
  - Short section (< 200 chars): Yellow warning "Very short section" + suggestion "Merge with adjacent?"
  - Empty section (0 chars): Red warning "Empty section" + suggestion "Delete?"
  - Stub section (< 50 chars, e.g., just a title): Red warning "Stub section" + suggestion "Merge with next section or delete"
  - Very long section (> 50,000 chars): Yellow warning "Very long section" + suggestion "Consider splitting"
  - Detected duplicate title: Yellow warning "Possible duplicate of Section N"

- **Multi-select operations**:
  - Select sections via checkboxes
  - Floating toolbar appears: "N sections selected" + "Merge Selected" + "Delete Selected" + "Change Type" + "Deselect All"
  - **Merge flow**:
    1. Select 2+ adjacent sections via checkboxes
    2. Click "Merge Selected"
    3. Preview dialog: Shows combined content preview, editable merged title (defaults to first section's title), total character count
    4. Confirm: Sections merged, original sections removed, `derived_from` field tracks source section IDs
    5. Non-adjacent selection: Error "Can only merge adjacent sections"

- **Split flow** (via section "..." menu):
  1. Select section > "..." > "Split"
  2. Split mode toggle: "At heading" (auto-detected) vs "Manual position"
  3. **At heading**: Shows list of detected headings within the section. Select split point(s). Preview shows resulting Part A and Part B with titles + character counts.
  4. **Manual position**: Show content with line numbers. Click to place split marker. Preview as above.
  5. Confirm: Section split, new sections created with appropriate `order_index` values

- **Section type detection**: Auto-detected on upload (existing `SectionType` enum logic). Changeable via dropdown in the Type column.

- **Undo for destructive operations**: After confirming a merge, split, or delete operation, show a **10-second undo toast** at the bottom of the screen: "Sections merged. [Undo]". During the undo window, original sections are preserved in a soft-delete state. After the window closes, the operation is finalized. Multiple consecutive operations queue their undo toasts.

- **Auto-advance when clean**: If the quality service detects **zero quality warnings** (no stubs, empties, duplicates, or very long sections), this step shows a dismissible **"Everything looks good"** banner: "All N sections look well-structured. You can review details below or continue." with a prominent "Next" button. The section table is still visible below for users who want to review, but the path of least resistance is to click Next.

- **Exit paths**:
  - "Save without processing" button: Saves book with status `parsed`. User can return later to summarize.
  - "Next" to Step 4

#### 3.5.5 Step 4: Preset Selection

- **Preset cards**: Grid of available presets (system + user). Each card:
  - Preset name (bold)
  - Brief description
  - Expandable section showing:
    - 4 facets: Style, Audience, Compression, Content Focus (with selected value for each)
    - Eval assertions grouped by category (Faithfulness, Completeness, Coherence, Specificity, Format) with active/skipped badges and brief explanations
    - Prompt template preview (collapsed, expandable)
  - Radio selection (one preset at a time)
  - **Recommended badge**: The `balanced` preset (or whichever is set as default in Settings) shows a star icon and "Recommended" label on its card. Pre-selected by default so first-time users can click "Start Summarizing" without making a choice.

- **"+ Create New" button**: Opens custom preset creation modal:
  - Name field
  - 2x2 grid of 4 facet dimensions, each as card-style selector:
    - **Style** (6 options): Academic, Bullets, Narrative, Technical, Executive, Conversational -- each with name + 1-line description
    - **Audience** (3 options): Expert, Practitioner, Beginner
    - **Compression** (3 options): Brief (10%), Standard (20%), Detailed (30%)
    - **Content Focus** (3 options): Concepts, Actionable, Comprehensive
  - "Save as reusable preset" checkbox (if unchecked, one-time use)
  - Confirm: Creates preset, selects it

- **"Manage Presets" link**: Navigates to Settings > Summarization Presets

- **Processing Profile**: The primary view shows preset selection and a single "Start Processing" button. The preset card, verification toggle, and auto-retry toggle are bundled into a named **Processing Profile** -- one choice instead of three. Default profile: preset=balanced, verify=on, auto-retry=on (labeled "Recommended"). Users can save custom profiles for reuse across books. *(Creativity: S2)*
  - An **"Advanced options"** disclosure link expands to show individual control over:
    - "Run verification after summarization" checkbox (default: checked) *(Creativity: M8)*
    - "Auto-retry on verification failure" checkbox (default: checked, disabled if verification unchecked) *(Creativity: M8)*
  - First-time users see only the profile selection and Start button. Power users expand Advanced for granular verification/retry control.

- **Cost & time estimate** (shown when `settings.show_cost_estimates` is enabled):
  - Displayed below processing options as an informational card
  - "Estimated processing: ~N minutes, ~$X.XX API cost (N sections, ~N tokens)"
  - Cost calculated from: section count x average tokens per section x model pricing
  - Time calculated from: section count x average latency per section (from past processing history, or default estimate)
  - Toggle in Settings > General: "Show cost estimates" (default: off)

- **Navigation**: Back to Step 3, "Start Summarizing" button (primary action)

#### 3.5.6 Step 5: Processing (In Book Detail)

After clicking "Start Summarizing," user is redirected to the Book Detail page. Processing is shown as a **pinned progress card** at the top of the content area:

- **Progress bar**: Overall percentage (sections completed / total)
- **Section-by-section status list**:
  - `check` = completed successfully
  - `spinner` = currently processing
  - `circle` = pending
  - `x` = failed (with error message on hover)
  - Each completed section shows: eval score (if eval enabled), latency
- **Timing**: Elapsed time, estimated remaining (based on average section time)
- **Completed sections are immediately browsable**: User can navigate to a completed section while others are still processing
- **Cancel button**: "Stop Processing" -- cancels remaining sections, keeps completed ones

- **Minimizable progress**:
  - "Minimize" button collapses progress card to a **bottom bar**
  - Bottom bar shows: Mini progress bar + book name + "Section 5/24" + "Expand" link
  - Multiple concurrent jobs stack in the bottom bar
  - Bottom bar persists across page navigation (app-level component)

- **SSE stream**: Processing updates delivered via SSE. Events:
  - `section_started`: `{section_id, section_title, index}`
  - `section_completed`: `{section_id, summary_id, eval_score, latency_ms}`
  - `section_failed`: `{section_id, error, will_retry}`
  - `eval_started`: `{section_id}`
  - `eval_completed`: `{section_id, passed, total, assertions}`
  - `retry_started`: `{section_id, attempt, reason}`
  - `processing_completed`: `{book_id, total_sections, passed, failed, total_time_ms}`
  - `processing_failed`: `{book_id, error}`

---

### 3.6 Search

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/search/search-final.html` (desktop)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/search/search-mobile.html` (mobile)

#### 3.6.1 Command Palette (Cmd+K)

- **Trigger**: Cmd+K (Mac) / Ctrl+K (Windows/Linux), or clicking the search input in the top bar
- **Appearance**: Centered modal with backdrop blur. Width: 600px. Search input at top, results below.
- **Input**: Auto-focused text input. Placeholder: "Search books, sections, concepts..."
- **Instant results** (debounced 200ms) grouped by type:
  - **Books**: Title + author. Max 3 shown.
  - **Sections**: Section title + book name + snippet. Max 3 shown.
  - **Concepts**: Term + definition snippet + book name. Max 3 shown.
  - **Annotations**: Note text snippet + source section + book name. Max 3 shown.
- **Keyboard navigation**:
  - `Up/Down arrows`: Move between results
  - `Enter`: Open selected result
  - `Shift+Enter` or `Cmd+Enter`: Open full search results page
  - `Escape`: Close palette
- **Match highlighting**: Search terms highlighted in yellow in result text
- **Empty state** (no query entered): Show recent searches (last 5) + quick actions:
  - "Upload a book" (opens upload flow)
  - "Go to Library" (navigates to library)
  - "Browse Concepts" (navigates to concepts)
  - "Surprise me" — returns a random high-verification-score section the user hasn't visited recently. Designed for serendipitous rediscovery in growing libraries. *(Nice-to-have — V1.1+)* *(Creativity: N10)*
- **No results state**: "No results for [query]" + suggestion "Try different keywords or check spelling"
- **Filter-scoped search**: When the command palette is opened from the Library page with active filters, search results are automatically scoped to the filtered book set. A "Searching within: [filter summary]" indicator appears below the input. Users can click "Search all books" to remove the scope. *(Creativity: S5)*
- **Command mode**: In addition to search, the palette accepts commands prefixed with `>` (e.g., `> Night Reading`, `> set font Serif`, `> Focus Mode`). Commands are auto-completed from available actions: reading preset names, font names, display modes. This unifies search and settings into one keyboard-driven surface. *(Nice-to-have — V1.1+)* *(Creativity: N1)*

#### 3.6.2 Full Search Results Page

Route: `/search?q={query}`

- **Left sidebar** (collapsible on tablet/mobile, **auto-collapsed when total results < 20** to reduce decision cost for quick searches):
  - **Source Type filter** with counts:
    - Sections (N)
    - Summaries (N)
    - Concepts (N)
    - Annotations (N)
  - **Book filter**: Multi-select dropdown of books that have matching results
  - **Tag filter**: Multi-select dropdown of tags

- **Results area** (main content):
  - **Results header**: "N results for [query]" + sort dropdown (Relevance / Date / Book order)
  - **Hybrid search indicator**: Subtle badge "BM25 + Semantic" showing search type
  - **Results grouped by book**: Each book group:
    - Book header: Cover thumbnail + title + author + total match count for this book
    - Result items (max 3 shown per book initially):
      - Color-coded type badge: Section (blue), Summary (green), Concept (purple), Annotation (orange)
      - Title or term
      - Snippet with highlighted matches (max 200 chars)
      - Relevance score (0-1, shown as percentage or bar)
      - Section breadcrumb (for sections/summaries)
    - "Show N more from this book" link to expand all results from that book
  - **Result click**: Navigate to the source location:
    - Section: Opens Book Detail at that section, Original view
    - Summary: Opens Book Detail at that section, Summary view
    - Concept: Opens Concepts Explorer with that concept selected
    - Annotation: Opens Book Detail at the annotation's section, scrolled to annotation

---

### 3.7 Annotations Page

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/annotations/annotations-final.html` (desktop)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/annotations/annotations-mobile.html` (mobile)

Route: `/annotations`

#### 3.7.1 Header

> **UI label**: The user-facing label for annotations is "Your Notes" (navigation, page title, sidebar tab). Internal code and API endpoints continue to use "annotations". The term "Your Notes" signals personal knowledge capture rather than document markup. *(Nice-to-have — V1.1+)* *(Creativity: N11)*

- Page title: "Your Notes" *(see N11 above — user-facing label)*
- Count: "(N total)"
- **"+ Add Note" button**: Opens an inline form at the top of the page for creating a freeform annotation. Form fields: Book selector (dropdown), Section selector (dropdown, populated after book selection), Note text area, Tags. Creates a freeform annotation attached to the selected section. Allows retrospective note-taking without navigating to the reader.
- Search input: Filter annotations by text content
- Export button: "Export" dropdown (Markdown, JSON, CSV)

#### 3.7.2 Filter Bar

| Filter | Options | Type |
|--------|---------|------|
| Book | All books with annotations | Multi-select dropdown |
| Type | Highlight, Note, Freeform | Multi-select dropdown |
| Tags | All tags | Multi-select dropdown |

| Control | Options |
|---------|---------|
| Group by | Book (default), Tag, Section, None |
| Sort | Newest first, Oldest first, Book order, Recently edited |

#### 3.7.3 Annotation Cards

Grouped by selected grouping (default: by book). Each group is a collapsible accordion:

- **Group header**: Book title (or tag name, or section title) + count + expand/collapse toggle

- **Annotation card**:
  - Type badge (color-coded: yellow=highlight, blue=note, green=freeform)
  - Source breadcrumb: "Book Title > Section Name" (clickable, navigates to reader)
  - Quoted selected text (for highlight/note types): Left-bordered block, italic
  - Note body: Regular text. Editable on click (inline editing).
  - Tags: Chip pills. "+ Add tag" to tag individual annotations.
  - Linked annotations: "Linked to: [description]" -- clickable
  - Date: Relative time ("3 hours ago"), absolute on hover
  - Actions row: Edit | Link | "..." menu (Delete, Copy, Move to section)

- **"Show N more from this book"**: When a book group has > 5 annotations, shows first 5 + expand link

- **Click behavior**: Clicking the source breadcrumb navigates to the book reader at the annotation's section, scrolled to the annotation position, with the Annotations sidebar open.

#### 3.7.4 Auto-filtering

When navigating to Annotations from within a book's reader (via sidebar), the page opens with the Book filter pre-set to that book.

#### 3.7.5 Empty State

- "No annotations yet. Start highlighting and taking notes while reading."
- "Go to Library" button

#### 3.7.6 Browse vs Review Modes

**Two modes**: The Annotations page has a mode toggle (Browse | Review): *(Creativity: S7)*

- **Browse** (default): Full filter, grouping, sort, and export -- the current layout described above.
- **Review**: A sequential flashcard-style view. Shows one annotation at a time: quoted text, note, source breadcrumb. Navigation: "Previous" / "Next" buttons + swipe on mobile. Optionally prompts "Still relevant?" (Yes / Archive). Designed for periodic annotation review sessions, especially on mobile.

---

### 3.8 Concepts Explorer

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/concepts_explorer/concepts-explorer-final.html` (desktop)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/concepts_explorer/concepts-mobile.html` (mobile)

Route: `/concepts`

#### 3.8.1 Two-Panel Layout

- **Left panel** (40% width): Concept list
- **Right panel** (60% width): Concept detail
- **Mobile**: Single panel with back navigation

#### 3.8.2 Concept List (Left Panel)

- **Search input** at top: Filter concepts by term name
- **Filters**:
  - Book: Multi-select dropdown
  - Tags: Multi-select dropdown
  - "User-edited only" checkbox
- **Grouping**: Dropdown (Book / First Letter / None)
- **Sort**: Dropdown (A-Z / Most sections / Recently added)
- **Concept items**:
  - Term name
  - "edited" badge (if `user_edited=True`)
  - Section count ("Appears in 5 sections")
  - Book name (muted, when not grouped by book)
- Grouped by book (default): Collapsible accordion per book
- Selected concept: Highlighted background, detail shown in right panel

#### 3.8.3 Concept Detail (Right Panel)

- **Term**: Large text, editable inline (click to edit). Editing sets `user_edited=True`.
- **Definition**: Paragraph text, editable inline. Editing sets `user_edited=True`. **"Copy" button** (clipboard icon) next to the definition copies the term + definition as plain text for pasting into notes, presentations, or emails.
- **Section appearances**: List of sections where this concept appears:
  - Section title + book name (clickable, navigates to reader)
  - "First mentioned" badge on the earliest section
  - Sorted by `order_index`
- **Related concepts**: Chip pills:
  - Same-book concepts: Default color
  - Cross-book concepts: Purple with external link icon
  - Click navigates to that concept in the list
- **Related annotations**: List of annotations that reference or are near this concept
- **Actions**: "Reset to original" (if user-edited, reverts to LLM-generated definition), "Delete"

#### 3.8.4 Auto-filtering

When navigating to Concepts from within a book's reader, the page opens with the Book filter pre-set to that book.

#### 3.8.5 Empty State

- "No concepts extracted yet. Concepts are generated during summarization."
- "Go to Library" button

---

### 3.9 Settings Page

Route: `/settings`

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/upload_processing/upload-edge-cases.html` (preset management section)

#### 3.9.1 Settings Sidebar

Left sidebar with sections:
1. General
2. Database
3. Summarization Presets
4. Reading Preferences
5. Backup & Export

#### 3.9.2 General Settings

- **Network**:
  - `Read on your phone` toggle (internally: `allow_lan`): When enabled, binds to 0.0.0.0 instead of 127.0.0.1. Friendly copy: "Your library will be readable from any device on your home network." *(Creativity: M7)*
  - **LAN Info**: When LAN is enabled, displays the access URL (`http://<ip>:<port>`) prominently.
  - **QR Code**: When LAN is enabled, shows a QR code encoding the access URL for easy phone pairing.
  - **Mobile Setup Kit**: A single "Set up mobile reading" action that enables LAN access, generates the QR code, and pre-caches the 5 most recently opened books for faster mobile loading. *(Creativity: M7)*
- **Default preset**: Dropdown of all presets (used when no preset specified)
- **Show cost estimates** toggle (default: off): When enabled, the upload wizard Step 4 and processing progress card show estimated API cost and processing time based on section count and average token usage.
- **LLM Settings** (read-only display from config):
  - Provider, model, timeout, max retries, budget

#### 3.9.3 Database Settings

- **Connection info**: Database URL (masked password), connection status indicator (green/red)
- **Migration status**: Current revision, latest available revision, "Run migrations" button if behind
- **Stats**: Total books, sections, summaries, annotations, concepts, search index entries

#### 3.9.4 Summarization Presets

- **List/detail layout** (similar to Concepts Explorer):
  - Left: Preset list with system (5) and user presets
  - Right: Preset detail

- **System presets** (read-only): `balanced`, `practitioner_bullets`, `academic`, `executive_brief`, `deep_study`
  - Cannot edit or delete
  - "Duplicate as User Preset" button creates an editable copy

- **User presets** (full CRUD):
  - Create: "New Preset" button opens creation form
  - Edit: All fields editable
  - Delete: With confirmation dialog

- **Preset detail view**:
  - Name (editable for user presets)
  - 4 facets displayed as 2x2 grid, each showing selected option:
    - Style: selected value + description
    - Audience: selected value + description
    - Compression: selected value + target percentage
    - Content Focus: selected value + description
  - Eval assertions grouped by category:
    - **Faithfulness** (4 assertions): `no_hallucinated_facts`, `accurate_statistics`, `faithful_tone`, `quotes_preserved`
    - **Completeness** (3): `covers_main_arguments`, `no_missing_sections`, `has_key_concepts`
    - **Coherence** (3): `logical_flow`, `consistent_terminology`, `self_contained`
    - **Specificity** (3): `includes_examples`, `avoids_generics`, `preserves_nuance`
    - **Format** (3): `reasonable_length`, `follows_structure_request`, `image_refs_preserved`
    - Each assertion: Name, active/skipped badge (green/gray), brief explanation
  - Rendered prompt template preview (monospace, scrollable, collapsed by default)

#### 3.9.5 Reading Preferences

- Default reading preset selection (dropdown of system + user presets)
- Font loading preference: "Load all fonts on startup" vs "Load on demand"
- Custom CSS injection (advanced): Textarea for additional CSS applied to the reader

#### 3.9.6 Backup & Export

- **Create backup**: Button triggers `pg_dump`. Shows progress. Download link when complete.
- **Backup history**: List of previous backups with date, size, download link, delete button
- **Restore from backup**: File upload for `.sql` backup file. Warning: "This will replace all current data."
- **Scheduled backups**: Configurable automatic backup (daily or weekly) to a local directory. Silent background `pg_dump` runs at the configured interval. Backup history page shows both manual and scheduled backups. A "Last backup: N days ago" indicator appears in the Settings sidebar navigation. *(Creativity: M6)*
- **Export library**:
  - Format: Markdown or JSON
  - Scope: All books or selected books (multi-select)
  - Include: Checkboxes for Summaries, Annotations, Concepts, Eval results
  - "Export" button, download link when complete

---

### 3.10 Multi-Device / Mobile

> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/multi_device/multi-device-final.html` (LAN access + responsive patterns)
> See wireframe: `docs/wireframes/2026-04-10_v2_web_interface/multi_device/mobile-views-final.html` (consolidated mobile overview)

#### 3.10.1 Network Configuration

- Default: Binds to `127.0.0.1` (localhost only)
- `network.allow_lan: true` in config (or Settings `Read on your phone` toggle): Binds to `0.0.0.0` *(Creativity: M7)*
- QR code in Settings: Encodes `http://<lan-ip>:<port>` for easy phone setup

#### 3.10.2 Responsive Breakpoints

| Breakpoint | Width | Label | Key Adaptations |
|------------|-------|-------|-----------------|
| Desktop | >= 1024px | `lg` | Full layout: icon rail + content + context sidebar |
| Tablet | 768-1023px | `md` | Icon rail (same), reduced content width, sidebar as overlay |
| Mobile | < 768px | `sm` | Bottom tab bar, single column, bottom sheets |

#### 3.10.3 Mobile-Specific Adaptations

**Navigation:**
- Bottom tab bar replaces sidebar (5 tabs: Library, Search, Concepts, Annotations, Settings)
- No persistent search input in header (Search tab instead)

**Library:**
- **Custom views sync across devices**: Mobile shows the same saved view tabs as desktop, rendered as horizontally scrollable pills. Users can switch between views but cannot create or edit views on mobile (desktop only).
- Defaults to List view (grid view available but defaults to 2 columns)
- Filter dropdowns open as full-screen modals with done/apply button
- Sort is in the full-screen filter modal

**Reader (Book Detail):**
- Single column layout, no persistent context sidebar
- **Bottom action bar** (fixed, above tab bar, each button has icon + text label): `Aa Settings` | `AI Chat` | `Annotations` | `More`
- Context sidebar becomes **bottom sheets**:
  - Draggable: Swipe up from handle to expand, swipe down to collapse
  - Three snap points: Peek (30% height), Half (50%), Full (90%)
  - Dismissible by swiping down past peek
  - **Minimum text size in bottom sheets: 14px** (applies to AI chat messages, annotation cards, and thread lists). Touch targets within bottom sheets: 44px minimum height.
- Floating text selection toolbar: Same actions but larger touch targets (44px min)
- Text selection: via long-press (standard mobile behavior)
- Chapter navigation: TOC opens as full-screen bottom sheet
- Original/Summary toggle: Full-width segmented control below header

**Upload:**
- Drag-and-drop zone replaced by "Choose File" button (uses native file picker)
- **3-step wizard indicator** matching desktop: Upload / Configure / Process. The step indicator shows 3 steps visually (Metadata + Structure Review are sub-steps within "Configure"; Preset Selection leads into "Process"). Steps are full-screen, one at a time. Step indicator uses compact numbered dots connected by lines.
- Quick Upload fast path available on mobile too: "Start with Recommended Settings" after upload.
- Structure review table: Card layout per section (one card per row, horizontally scrollable for wide tables)

**Search:**
- Command palette: Full-screen modal (no backdrop, takes over)
- Full results: Single column, no left sidebar. Filters in collapsible header area.

**Settings:**
- Settings sidebar becomes top-level navigation within the settings page (accordion or tab bar)

#### 3.10.4 Touch Interactions

| Desktop Action | Mobile Equivalent |
|----------------|-------------------|
| Hover to preview | Long-press for preview |
| Right-click context menu | Long-press context menu |
| Drag to reorder | Long-press + drag |
| Mouse text selection | Long-press + drag handles |
| Cmd+K | Search tab in bottom nav |
| Keyboard shortcuts | Not available (touch gestures instead) |

#### 3.10.5 Performance Considerations for Mobile

- Images lazy-loaded, thumbnails at reduced resolution
- Infinite scroll instead of pagination for long lists
- Skeleton loaders for perceived performance
- Service worker for caching static assets (PWA potential)
- Reduced animation on `prefers-reduced-motion`

#### 3.10.6 Reading Position Sync

- **Reading position sync**: The server tracks the last-viewed book and section per session (`last_book_id`, `last_section_id`, `last_viewed_at` on a new `reading_state` table). When a user opens the app on a different device (detected by different user-agent), a "Continue where you left off" banner appears: "You were reading [Book Title], [Section Name]" with a "Continue" button that navigates directly. *(Creativity: S4)*

---

## 4. User Journeys

### 4.1 Upload a Book

**Happy Path:**

1. User clicks "Upload" button in top bar (or drags file onto Library page)
2. Upload wizard opens at Step 1 (Upload)
3. User drops an .epub file onto the drag zone
4. Client validates: file extension is .epub, file size is 42MB (under 100MB limit)
5. Upload progress bar shows transfer progress
6. Server receives file, computes SHA-256 hash, checks for duplicates -- none found
7. Server parses EPUB: extracts metadata (title, author, cover), identifies sections
8. Wizard auto-advances to Step 2 (Metadata)
9. User sees auto-extracted title "Thinking, Fast and Slow", author "Daniel Kahneman", cover image
10. User adds tags: "Psychology", "Decision Making"
11. User clicks Next
12. Step 3 (Structure Review): 38 sections displayed. 2 quality warnings:
    - Section 3 "Also by Daniel Kahneman" -- 45 chars, flagged as stub
    - Section 37 "Index" -- detected as index type
13. User checks Section 3 and clicks "Delete Selected" from toolbar. Confirms deletion.
14. User clicks Next
15. Step 4 (Preset Selection): User selects "practitioner_bullets" preset. Both eval and auto-retry checkboxes are checked.
16. User clicks "Start Summarizing"
17. Wizard closes. User lands on Book Detail page for the new book.
18. Pinned progress card shows: "Summarizing... Section 1/37" with progress bar
19. As sections complete, they become browsable. User navigates to Section 2 while Section 5 is processing.
20. After all sections complete, book-level summary is generated.
21. Processing card shows: "Complete! 37/37 sections. Eval: 35/37 sections passed. Time: 12m 34s."
22. Progress card auto-dismisses after 10 seconds (or user clicks Dismiss).

**Edge Case: Duplicate File (Same Hash)**

1. Steps 1-5 as above
2. Server computes SHA-256 hash and finds an existing book with the same hash
3. Duplicate detection dialog appears: "This book already exists in your library"
   - Shows existing book: "Thinking, Fast and Slow" added on April 2, 37 sections, 35 summaries
4. User chooses one of:
   - a) "Go to existing" -- Navigates to existing book's detail page. Upload wizard closes.
   - b) "Re-import" -- Server marks existing eval traces as `is_stale=True`. Re-parses and updates sections in-place by `order_index`. Existing summaries are preserved but eval data is stale. Wizard advances to Step 2.
   - c) "Cancel" -- Returns to upload wizard Step 1 with zone cleared.

**Edge Case: Different Format, Same Book**

1. User uploads a .pdf version of a book that exists as .epub
2. Server matches title+author fuzzy (Levenshtein distance < threshold)
3. Side-by-side comparison dialog:
   - Left: "Thinking, Fast and Slow (EPUB)" -- 37 sections, 35 summaries, 142 annotations
   - Right: "Thinking, Fast and Slow (PDF)" -- estimated 42 sections
4. User chooses:
   - a) "Add as separate book" -- Both exist independently. Wizard continues to Step 2.
   - b) "Replace existing" -- Warning: "This will permanently delete all summaries, annotations, and evaluation data for the EPUB version." User confirms. Old book deleted, new one added. Wizard continues to Step 2.
   - c) "Cancel"

**Edge Case: Quality Warnings in Structure Review**

1. At Step 3, quality service detects issues:
   - 3 sections under 200 chars (stub threshold)
   - 1 section with 0 chars (empty)
   - 1 section over 50,000 chars (very long)
2. Each issue shows inline:
   - Stub sections: Yellow warning with "Merge with adjacent?" suggestion
   - Empty section: Red warning with "Delete?" suggestion
   - Long section: Yellow warning with "Consider splitting" suggestion
3. User clicks "Merge with adjacent?" on a stub -- this checks the stub and its next section, opens merge preview
4. User clicks "Delete?" on the empty section -- immediate deletion with undo toast (5 second window)
5. User manually selects the long section > "..." > "Split" > "At heading" > selects a detected heading > confirms split

**Edge Case: Corrupt File Upload**

1. User uploads a file named "book.epub" that is actually a renamed .zip
2. Client-side: Extension check passes (.epub is valid)
3. Server-side: EPUB parser fails (invalid structure)
4. Error displayed in wizard Step 1: "Unable to parse this file. The file appears to be corrupt or in an unsupported format."
5. User remains on Step 1, can try a different file

**Edge Case: File Too Large**

1. User drags a 150MB PDF onto the upload zone
2. Client-side validation: Immediately shows error "File size (150MB) exceeds the 100MB limit"
3. File is not uploaded. User can try a smaller file.

**Edge Case: Save Without Processing**

1. User completes Steps 1-3 (upload, metadata, structure review)
2. At Step 3, user clicks "Save without processing" instead of Next
3. Book is saved with status `parsed` and appears in Library with "Parsed" status badge
4. User can later open the book, click "Summarize" from book actions, and be taken to preset selection (equivalent to Step 4)

---

### 4.2 Summarize a Book

**Happy Path:**

1. User navigates to Library, clicks on an existing book (status: "parsed")
2. Book Detail opens. Content shows original text. No summaries exist yet.
3. User clicks book title in breadcrumb, selects "Summarize" from dropdown actions
4. Preset picker modal opens (same as Step 4 of upload wizard)
5. User selects "academic" preset, keeps eval and auto-retry checked
6. Clicks "Start Summarizing"
7. Progress card appears at top of Book Detail
8. Sections process one by one:
   - Section 1: Summarized (1.2s) > Verified (2.1s) > 16/16 passed
   - Section 2: Summarized (0.9s) > Verified (1.8s) > 15/16 passed (auto-retry not triggered, 15/16 is acceptable)
   - Section 5: Summarized (1.1s) > Verified (2.3s) > 12/16 passed > Auto-retry triggered > Re-summarized (1.3s) > Re-verified (2.0s) > 15/16 passed
9. After all sections: Book-level summary generated from section summaries
10. Book status changes to "completed"
11. User can now toggle to "Summary" view and read summaries

**Edge Case: Custom Preset**

1. At preset picker, user clicks "+ Create New"
2. Modal opens with facet selection:
   - Style: Selects "Bullets"
   - Audience: Selects "Practitioner"
   - Compression: Selects "Detailed (30%)"
   - Content Focus: Selects "Actionable"
3. Names it "my-custom-preset"
4. Checks "Save as reusable preset"
5. Clicks Create. Modal closes. New preset appears selected in the picker grid.
6. Clicks "Start Summarizing"

**Edge Case: Processing Failure**

1. During summarization, LLM times out on Section 12
2. SSE event: `section_failed: {section_id: 12, error: "LLM timeout after 300s", will_retry: true}`
3. Auto-retry triggers (up to `max_retries` from config)
4. If retry succeeds: Processing continues normally
5. If retry fails again: Section marked as failed. Processing continues with remaining sections.
6. Final progress: "Complete! 36/37 sections. 1 failed. Eval: 34/36 passed."
7. Failed section shows red X in progress list. Click to see error details.

**Edge Case: Cancel During Processing**

1. User clicks "Stop Processing" while Section 8/37 is running
2. Confirmation: "Stop processing? Sections 1-7 are complete and will be preserved."
3. User confirms
4. Current section (8) is abandoned. Sections 9-37 are not processed.
5. Book status remains "summarizing" until explicitly re-triggered or stays as-is
6. Completed sections (1-7) have their summaries preserved and are browsable

---

### 4.3 Read a Book Section

**Happy Path:**

1. User navigates to Library, clicks on a completed book
2. Book Detail opens at the first section, "Summary" view active (default when summaries exist) *(Creativity: M1)*
3. User reads the summary content
4. User clicks "Original" in the segmented control to see the source text
5. Summary view shows: summary markdown rendered with concept chips, eval banner ("16/16 passed"), version selector showing "practitioner_bullets - Apr 10"
6. User clicks a concept chip ("Anchoring Effect")
7. Tooltip shows: definition, "Appears in 8 sections", related concepts (Availability Heuristic, Priming)
8. User clicks "Availability Heuristic" in related concepts
9. Tooltip updates to show that concept's detail
10. User clicks the chapter name in breadcrumb to open TOC
11. TOC dropdown shows all 37 sections with eval status dots
12. User clicks "Chapter 5: Cognitive Ease"
13. Reader navigates to Chapter 5, maintaining "Summary" view

**Edge Case: No Summary Exists**

1. User navigates to a section that has not been summarized
2. Toggles to "Summary" view
3. Content area shows: "No summary available for this section."
4. "Summarize this book" button below (starts summarization for the entire book, not just this section)

**Edge Case: Multiple Summary Versions**

1. User is reading a section with 3 summary versions
2. Version selector shows: "practitioner_bullets - Apr 10" (default), "academic - Apr 8", "executive_brief - Apr 5"
3. User selects "academic - Apr 8"
4. Summary content updates to show the academic version
5. Eval banner updates to show that version's eval results
6. "History (3 versions)" link opens summary comparison (see Journey 4.10)

---

### 4.4 Annotate Text

**Happy Path: Highlight**

1. User is reading a section in the Book Detail reader (original or summary view)
2. User selects a passage of text: "System 1 operates automatically and quickly, with little or no effort"
3. Floating toolbar appears above the selection
4. User clicks "Highlight" button
5. Selected text is immediately highlighted (yellow background in content)
6. Annotation appears in the Annotations sidebar (if open)
7. Toast: "Highlight created"

**Happy Path: Note**

1. User selects text and clicks "Note" in the floating toolbar
2. A note input field appears inline below the highlight
3. User types: "Key distinction between System 1 and System 2"
4. Presses Enter or clicks Save
5. Annotation created with type=note, including both the selected text and the note body
6. Highlight appears in content, note appears in sidebar

**Happy Path: Freeform Note**

1. User opens the Annotations sidebar tab
2. Scrolls to the bottom where the freeform input area is
3. Types a section-level note: "This chapter's argument about cognitive ease connects to Chapter 12's discussion of WYSIATI"
4. Clicks "Add note"
5. Freeform annotation created (no `text_start`/`text_end`, no selected text)
6. Appears at the bottom of the annotation list for this section

**Edge Case: Cross-Book Link**

1. User creates a highlight annotation
2. Clicks "Link" in the annotation's action row
3. Link dialog opens with search input: "Find annotation to link..."
4. User types "anchoring" and sees annotations from other books mentioning anchoring
5. Selects an annotation from "Nudge" book
6. Link created: Both annotations now show "Linked to: [other annotation]" with clickable cross-references
7. `linked_annotation_id` FK set on the source annotation

**Edge Case: Annotation on Summary Content**

1. User is in Summary view and selects text from the summary
2. Creates a highlight annotation
3. Annotation's `content_type` = `section_summary`, `content_id` = section's ID
4. Annotation is associated with the summary content, not the original content
5. When viewing the same section in Original view, this annotation is not visible (it belongs to the summary)

---

### 4.5 Ask AI About Content

**Happy Path: New Thread with Selected Text**

1. User is reading Chapter 3 and selects a passage about "loss aversion"
2. Clicks "Ask AI" in the floating toolbar
3. Context sidebar opens on the AI tab
4. A new thread is automatically created
5. Input area shows context chip: "Using selected text from Chapter 3"
6. User types: "How does loss aversion differ from risk aversion in practice?"
7. Presses Cmd+Enter (or clicks Send)
8. User message appears with the selected text as a quoted context block above it
9. AI response streams token-by-token, referencing the passage and providing explanation
10. Response rendered as markdown with section references as clickable links

**Happy Path: Continue Existing Thread**

1. User opens AI sidebar, sees thread list with 2 existing threads
2. Clicks "Loss Aversion Discussion" thread
3. Previous messages displayed
4. User types a follow-up question: "Can you give me examples from other chapters?"
5. AI responds, referencing Chapters 5 and 8 with clickable section links
6. Multi-section context: AI has access to the book's overall summary and relevant section summaries

**Happy Path: Save AI Response as Annotation**

1. AI provides a helpful explanation about a concept
2. User clicks "Save as note" action on the AI response message
3. A freeform annotation is created on the current section
4. Annotation body contains the AI response text
5. Toast: "Saved as annotation on Chapter 3"

**Edge Case: No Book Context Available**

1. Book is in "parsed" state (no summaries)
2. User opens AI tab and starts a thread
3. AI context includes: section original content, book title, author
4. AI can still answer questions using the original content but cannot reference summaries

**Edge Case: Multi-Section Question**

1. User asks: "What are the main themes across the first half of this book?"
2. AI receives context: book summary (if exists) + summaries of relevant sections
3. AI responds with a synthesis spanning multiple chapters, each referenced
4. User can click any chapter reference to navigate there

---

### 4.6 Search Across Library

**Happy Path: Quick Search (Command Palette)**

1. User presses Cmd+K
2. Command palette opens with empty input, showing recent searches: "loss aversion", "cognitive bias"
3. User types "anchoring"
4. After 200ms debounce, results appear:
   - Books (1): "Thinking, Fast and Slow"
   - Sections (3): "Chapter 11: Anchors", "Chapter 14: ...", "Chapter 26: ..."
   - Concepts (2): "Anchoring Effect (Thinking, Fast and Slow)", "Anchoring Heuristic (Nudge)"
   - Annotations (1): Note: "Important anchoring example..." in Chapter 11
5. User presses Down arrow twice to select "Chapter 11: Anchors"
6. Presses Enter
7. Palette closes. Book Detail opens at Chapter 11.

**Happy Path: Full Results Page**

1. User types "decision making" in command palette and presses Shift+Enter (or clicks "See all results")
2. Full search results page opens at `/search?q=decision%20making`
3. Left sidebar: Source Type (Sections: 12, Summaries: 8, Concepts: 5, Annotations: 3), Book filter, Tag filter
4. Results grouped by book:
   - "Thinking, Fast and Slow" (15 matches): 3 section results shown + "Show 12 more"
   - "Nudge" (8 matches): 3 section results shown + "Show 5 more"
   - "Predictably Irrational" (5 matches): 3 results shown + "Show 2 more"
5. User clicks "Concepts" in Source Type filter to show only concept results
6. Results update to show 5 concept results across 3 books
7. User clicks on "Decision Fatigue" concept result
8. Navigates to Concepts Explorer with "Decision Fatigue" selected

**Edge Case: No Results**

1. User searches for "xyzzy123"
2. Command palette: "No results for 'xyzzy123'. Try different keywords."
3. Full results page: Same message + "Suggestions: Check spelling, try broader terms, or search for related concepts"

**Edge Case: Special Characters in Query**

1. User searches for "80/20 rule" or "Pareto's principle"
2. Search handles special characters (slashes, apostrophes) correctly
3. Both BM25 (keyword) and semantic search return relevant results

---

### 4.7 Manage Library Views

**Happy Path: Create a View**

1. User is on Library page, "All Books" view active
2. Sets filters: Status = "completed", Tags = "Psychology"
3. Sets sort: "Eval score" descending
4. Sets display: Grid mode
5. Clicks "+ New View" tab
6. Dialog: "Create view" with name input. Pre-filled: "completed + Psychology" (auto-generated from filters)
7. User renames to "Psychology Reading"
8. Clicks Create
9. New tab appears: "Psychology Reading" (active, with current filters)
10. "All Books" tab returns to unfiltered state

**Happy Path: Edit a View**

1. User right-clicks "Psychology Reading" tab (or clicks "..." on the tab)
2. Context menu: Rename, Duplicate, Set as default, Reorder, Delete
3. Clicks "Rename"
4. Inline edit: Changes to "Psych Books"
5. Tab updates immediately

**Happy Path: Ad-Hoc Refinement**

1. User is on "Psych Books" view (saved: Status=completed, Tags=Psychology)
2. Adds another filter: Author = "Daniel Kahneman"
3. Unsaved changes dot appears on the tab
4. Tooltip on dot: "Unsaved changes"
5. User can either:
   - Click the dot > "Save" to persist the additional filter
   - Click the dot > "Reset" to revert to saved state
   - Navigate away and come back -- reverts to saved state (ad-hoc changes are transient)

**Edge Case: Delete Last Custom View**

1. User has "All Books" (built-in) + "Psych Books" (custom)
2. User deletes "Psych Books"
3. Confirmation: "Delete view 'Psych Books'?"
4. Deleted. Only "All Books" remains.
5. "All Books" cannot be deleted (built-in).

**Edge Case: Reorder Views**

1. User has 4 view tabs: All Books, Psych, Business, Technical
2. User drags "Technical" tab to second position
3. Tab order updates: All Books, Technical, Psych, Business
4. Order is persisted

---

### 4.8 Configure Reader Settings

**Happy Path: Use a Preset**

1. User is reading a book, clicks "Aa" button
2. Reader settings popover opens
3. Presets section shows 4 system presets: Comfortable (active), Night Reading, Study Mode, Compact
4. User clicks "Night Reading" card
5. All settings immediately update: Font changes to Georgia, Size to 18px, Spacing to 1.8, Background to Dark (#1E1E2E)
6. Live preview at bottom shows updated sample text
7. Reading area behind the popover updates in real-time
8. User closes popover. Settings persist.

**Happy Path: Custom Tweaks**

1. User is using "Comfortable" preset
2. Opens reader settings
3. Changes font to "Merriweather" (clicks the pill button)
4. Increases size to 20px (clicks XL or uses stepper)
5. Unsaved preset state: User's settings no longer match any preset. No preset card is highlighted.
6. Summary line shows: "20px Merriweather, 1.6 spacing, 720px, Light"
7. User clicks "+ Save Current"
8. Name input appears: Types "My Reading Setup"
9. Clicks Save. New preset card appears with user's customization.

**Happy Path: Custom Background Color**

1. User clicks the palette icon (Custom) next to the background swatches
2. Full color picker opens: Gradient area + hue slider + hex input
3. User picks a warm olive green (#2D3436)
4. Text color auto-adjusts to light (#ECEFF1) for WCAG AA contrast
5. Preview updates. Reading area updates.
6. Hex input shows "#2D3436"

**Edge Case: Invalid Contrast**

1. User picks a medium-gray background (#808080) using the color picker
2. System calculates contrast ratio for both black and white text
3. Selects whichever meets WCAG AA (4.5:1 ratio minimum)
4. If neither meets AA: Warning text appears "Low contrast - text may be hard to read" but does not block the user

---

### 4.9 Access from Mobile

**Happy Path: LAN Setup**

1. User opens Settings > General on desktop
2. Enables "Allow LAN Access" toggle
3. Warning displayed and acknowledged
4. QR code appears encoding: `http://192.168.1.42:8000` (actual LAN IP)
5. Access URL displayed prominently below QR code
6. User scans QR code with phone's camera or types the URL
8. Phone browser opens Book Companion at the Library page
9. Bottom tab bar visible. Library shows in list view.

**Happy Path: Mobile Reading**

1. User opens a book from the Library on phone
2. Book Detail loads with mobile layout: Full-width content, bottom action bar
3. User taps a section to read it
4. Long-presses a sentence to select text
5. Floating toolbar appears (larger touch targets)
6. Taps "Note" -- note input opens inline
7. Types note, taps Save
8. Taps "AI" in bottom action bar
9. AI bottom sheet slides up from bottom (peek state: 30%)
10. User swipes up to expand to half (50%)
11. Types question in AI input, taps Send
12. AI response streams in the bottom sheet
13. User swipes down past peek to dismiss

**Edge Case: Offline Behavior**

1. User opened a book while on LAN
2. Loses network connection (moves out of WiFi range)
3. Cached pages (service worker) still show previously loaded content
4. Attempting to navigate to a new section: Error message "Unable to connect to Book Companion server. Check your network connection."
5. No background sync or offline editing (V1 non-goal)

---

### 4.10 Compare Summaries

**Happy Path:**

1. User is reading a section with multiple summary versions
2. Clicks "History (3 versions)" link in the version selector
3. Summary comparison view opens:
   - Two-column layout
   - Left dropdown: Select summary A (e.g., "practitioner_bullets - Apr 10")
   - Right dropdown: Select summary B (e.g., "academic - Apr 8")
   - **Auto-selection**: The two most recent summary versions are auto-selected in the dropdowns -- no manual selection needed for the most common comparison. Dropdowns remain available to change selections. *(Creativity: S8)*
4. Side-by-side rendering of both summaries
5. **Diff highlighting**: Sections unique to A highlighted in red, unique to B in green, shared in neutral
6. **Concept diff**: Below the summaries, a section shows:
   - Concepts only in A
   - Concepts only in B
   - Concepts in both
7. **Metadata comparison**: Compression ratio, token counts, eval scores for each
8. User can click "Set as default" on either summary to make it the active one
9. **"What changed?" auto-explanation**: When the divergence between two summaries exceeds 60% (measured by concept diff and text overlap), an auto-generated one-sentence explanation appears above the columns: e.g., "Version 2 emphasizes implementation steps; Version 1 focuses on theory." Generated from concept diff data. *(Nice-to-have — V1.1+)* *(Creativity: N2)*

**Edge Case: Only One Summary**

1. Section has only one summary version
2. "History (1 version)" link is shown but clicking it shows: "Only one summary version exists. Summarize again with a different preset to compare."

---

### 4.11 Verify Summaries *(Creativity: M8)*

**Happy Path: View Verification Results**

1. User navigates to a completed book
2. Switches to Summary view on a section
3. Verification banner shows: "Verified: 14/16 passed" (yellow) *(Creativity: M8)*
4. Clicks "View details"
5. Inline expansion shows assertions grouped by category:
   - **Faithfulness** (4/4): All green checks
   - **Completeness** (3/3): All green checks
   - **Coherence** (2/3): 2 green, 1 red (logical_flow failed)
     - `logical_flow`: FAILED -- Reasoning: "The summary jumps from the introduction directly to conclusions without covering the experimental evidence presented in the middle of the section."
   - **Specificity** (2/3): 2 green, 1 red (avoids_generics failed)
     - `avoids_generics`: FAILED -- Reasoning: "The summary uses phrases like 'research shows' without specifying which studies."
   - **Format** (3/3): All green checks
6. User reads the reasoning to understand why assertions failed

**Happy Path: Force Re-verification** *(Creativity: M8)*

1. User views verification results, sees 2 failures
2. Clicks "Re-verify" button (or navigates to book actions > "Verify") *(Creativity: M8)*
3. Verification runs again on the current default summary
4. SSE events stream verification progress (assertion by assertion)
5. New eval traces created (old traces still exist but new `eval_run_id`)
6. Results update in real-time
7. **Score animation on re-verification**: When a re-verification improves the score, the trust badge animates: the score counter ticks up, the badge color transitions with a brief glow effect, and a one-liner appears: "Improved from 'Worth a quick review' to 'This summary is solid.'" *(Nice-to-have — V1.1+)* *(Creativity: N8)*

**Edge Case: Stale Verification Data** *(Creativity: M8)*

1. User re-imports a book (updates sections)
2. Existing eval traces marked `is_stale=True`
3. Verification banner shows: "Verification data is stale (book was re-imported). Re-verify?" *(Creativity: M8)*
4. "Re-verify" button triggers new verification run
5. New traces with `is_stale=False` replace the display

**Edge Case: Book-Level Verification** *(Creativity: M8)*

1. User navigates to the book's overall summary (book-level, not section-level)
2. Verification banner shows results for the book-level summary
3. "View details" shows the same grouped assertion view
4. Book-level eval may have different assertions applicable vs. section-level

**One-click fix flow** *(Nice-to-have — V1.1+)* *(Creativity: N12)*: On a failed assertion card, a "Fix & Re-verify" button opens the summary editor pre-scrolled to the likely problem span (identified from the assertion's reasoning text). After the user saves the edit (creating a new summary version), re-verification triggers automatically via SSE. Closes the find-fix-verify loop in one action.

---

### 4.12 Export & Backup

**Happy Path: Export Single Book**

1. User opens a book > book title breadcrumb > "Export"
2. Export dialog:
   - Format: Markdown / JSON radio buttons
   - Include: Checkboxes for Summaries (checked), Annotations (checked), Concepts (checked), Eval results (unchecked)
3. User selects Markdown, checks all boxes
4. Clicks "Export"
5. Server generates markdown file. Download starts automatically.
6. Toast: "Exported Thinking, Fast and Slow.md"
7. **Export stats card**: After export completes, show an "Export complete" card with library stats: "Exported N books, N summaries, N concepts — that's N years of reading." Reinforces the value of the user's knowledge base. *(Nice-to-have — V1.1+)* *(Creativity: N9)*

**Happy Path: Full Library Export**

1. User navigates to Settings > Backup & Export
2. Under "Export Library":
   - Selects "All books"
   - Format: JSON
   - Includes: All checked
3. Clicks "Export"
4. Progress indicator (for large libraries)
5. Download: `book_companion_library_2026-04-10.json`

**Happy Path: Database Backup**

1. User navigates to Settings > Backup & Export
2. Clicks "Create Backup"
3. Progress: "Running pg_dump..."
4. Complete: Backup listed in history: `backup_2026-04-10_14-30.sql` (245MB)
5. Download link available

**Happy Path: Restore from Backup**

1. User clicks "Restore from Backup"
2. Warning: "This will replace ALL current data with the backup contents. This action cannot be undone."
3. User uploads `.sql` file
4. Confirmation: "Restore from backup_2026-04-10_14-30.sql? Current data will be permanently replaced."
5. User confirms
6. Restore runs. Progress indicator.
7. Complete: "Database restored. Page will reload."
8. Page reloads. All data from backup is now live.

**Edge Case: Export with No Data**

1. User exports a book with no summaries, no annotations, no concepts
2. Export still succeeds -- contains book metadata, sections (original content), and empty arrays for other fields
3. No error, but exported file is smaller than expected

---

## 5. Edge Cases & Error Handling

### 5.1 Network Failures During Processing

| Scenario | Behavior |
|----------|----------|
| Browser loses connection during summarization | SSE connection drops. On reconnect, client fetches current processing state via REST endpoint. Progress UI resumes from server state. |
| Server crashes during processing | `ProcessingJob` has `pid` field for orphan detection. On next page load, orphan check runs. Shows "Processing was interrupted. Resume?" prompt. |
| SSE connection timeout (no events for 60s) | Client reconnects SSE automatically. If 3 reconnect failures: "Connection lost. Processing may still be running on the server." + "Refresh" button. |
| Upload network error mid-transfer | Upload progress bar shows error. "Upload failed. Please try again." File must be re-uploaded from scratch. |

### 5.2 Upload Failures

| Scenario | Error Message | Recovery |
|----------|--------------|----------|
| Corrupt EPUB file | "Unable to parse this file. The file may be corrupt." | Stay on Step 1, try different file |
| Unsupported format (.doc, .txt) | "Unsupported format. Please upload EPUB, MOBI, or PDF files." | Client-side validation, immediate |
| File exceeds 100MB | "File too large (SIZE). Maximum is 100MB." | Client-side validation, immediate |
| MOBI conversion fails (Calibre not available) | "MOBI conversion requires Calibre. Install Calibre or convert to EPUB first." | Show link to Calibre installation |
| PDF with no extractable text (scanned) | "This PDF contains no extractable text. OCR PDFs are not supported." | Stay on Step 1 |
| Server disk full during upload | "Server storage error. Please free disk space and try again." | 500 error with user-friendly message |

### 5.3 Processing Failures

| Scenario | Behavior |
|----------|----------|
| LLM timeout (300s) | Auto-retry up to `max_retries`. If all retries fail: section marked failed, processing continues. |
| LLM returns malformed JSON | Parse error caught. Auto-retry. |
| Section content too short (< 200 chars) | Skipped with note: "Section too short to summarize." Not counted as failure. |
| LLM budget exceeded | Processing stops. Warning: "LLM budget limit reached ($5.00). Processing paused." Resume option after config change. |
| Embedding service (Ollama) down | Embedding step fails silently. Search index not updated. Warning in processing results. |
| Eval assertion error (LLM returns unparseable eval) | Eval trace saved with `passed=False`, error noted. Does not block processing. |

### 5.4 Empty States

| Page / Component | Empty State |
|------------------|-------------|
| Library (no books) | Illustration + "Your library is empty" + Upload button + format info |
| Library (no filter matches) | "No books match your filters" + Clear filters button |
| Search results (no matches) | "No results for '[query]'" + spelling/broadening suggestions |
| Annotations page (no annotations) | "No annotations yet. Start highlighting while reading." + Library link |
| Concepts page (no concepts) | "No concepts yet. Concepts are generated during summarization." + Library link |
| Annotations sidebar (no annotations for section) | "No annotations for this section. Select text to highlight or add a note." |
| AI sidebar (no threads) | "Ask AI about this book. Select text for context or start a new conversation." |
| Verification banner (not verified) | "Not verified" + "Verify" link *(Creativity: M8)* |
| Summary view (no summary) | "No summary available." + "Summarize" button |
| Search results sidebar filters (empty category) | Category hidden (don't show "Concepts (0)") |

### 5.5 Concurrent Operations

| Scenario | Behavior |
|----------|----------|
| Multiple books summarizing simultaneously | Each has its own SSE stream. Bottom bar shows stacked progress indicators. |
| Upload while processing | Upload proceeds independently. New book appears in Library immediately (status: parsed). |
| Two tabs open on same book | Both receive SSE updates. No conflicts since both are read-only views of server state. |
| Evaluating while summarization is running | Eval waits for section's summary to be committed before evaluating. Queue-based ordering. |
| Editing sections while processing | Should be blocked. "Cannot edit sections while processing is active." |

### 5.6 Stale Data

| Scenario | Behavior |
|----------|----------|
| Re-import marks eval traces stale | Verification banner: "Verification data is stale. Re-verify?" *(Creativity: M8)* All queries filter `is_stale=FALSE`. |
| Summary exists but section content changed (re-import) | Summary still displayed but with warning: "Section content has changed since this summary was generated." |
| Concept definition outdated after re-summarization | Concepts are regenerated during summarization. Old user edits are preserved (`user_edited=True`). |

### 5.7 Browser/Client Edge Cases

| Scenario | Behavior |
|----------|----------|
| Browser back/forward during wizard | Vue Router history management. Each step has a URL. Back returns to previous step with state preserved. |
| Page refresh during processing | SSE reconnects. Client fetches current state. Progress resumes. |
| Multiple browser tabs | Independent state. Each tab has its own SSE connection. |
| Very large section content (> 100KB markdown) | Virtualized rendering if needed. Progressive loading. |
| Paste very long text in annotation note | Max length enforcement (10,000 chars). "Note is too long. Maximum 10,000 characters." |

---

## 6. Test Scenarios

### 6.1 Library Tests

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| LIB-01 | Display books in grid view | Navigate to Library with 5+ books, select Grid | All books visible as cards with cover, title, author, tags, status, eval |
| LIB-02 | Switch display modes | Toggle Grid > List > Table | Layout changes, same books shown, no data loss |
| LIB-03 | Filter by status | Select Status = "completed" | Only completed books shown. Count updates. |
| LIB-04 | Filter by multiple tags (OR) | Select Tags = "Psychology" + "Business" | Books with either tag shown |
| LIB-05 | Filter across dimensions (AND) | Status = "completed" + Tags = "Psychology" | Only completed psychology books shown |
| LIB-06 | Sort by eval score | Sort = "Eval score" | Books ordered by percentage descending. Unevaluated at bottom. |
| LIB-07 | Create a view | Set filters, click "+ New View", name it | View tab created with current filters |
| LIB-08 | Delete a view | Right-click view tab > Delete > Confirm | View removed. Falls back to All Books. |
| LIB-09 | View remembers display mode | Create view in Table mode, switch to another view, come back | Table mode restored |
| LIB-10 | Unsaved changes indicator | In a saved view, change a filter | Dot appears on tab |
| LIB-11 | Empty library state | No books in database | Empty state illustration + upload CTA |
| LIB-12 | Table column visibility | In Table mode, toggle off "Tags" column | Tags column hidden. Persistence on reload. |
| LIB-13 | Book card context menu | Right-click book card | Menu: Open, Summarize, Verify, Edit metadata, Export, Delete |
| LIB-14 | Mobile list view | View on 375px viewport | List view default, 2-col grid available, bottom tab nav |

### 6.2 Upload Tests

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| UPL-01 | Upload EPUB happy path | Drop .epub file on zone | Upload completes, advances to Step 2 with extracted metadata |
| UPL-02 | Upload PDF | Drop .pdf file | Upload, parse with pymupdf4llm, advance to Step 2 |
| UPL-03 | Upload MOBI | Drop .mobi file | Calibre conversion to EPUB, then normal parsing |
| UPL-04 | Reject unsupported format | Drop .doc file | "Unsupported format" error, stays on Step 1 |
| UPL-05 | Reject oversized file | Drop 150MB file | "File too large" error, stays on Step 1 |
| UPL-06 | Duplicate detection (same hash) | Upload exact same file twice | Duplicate dialog with Go to existing / Re-import / Cancel |
| UPL-07 | Different format detection | Upload PDF of existing EPUB book | Side-by-side comparison dialog |
| UPL-08 | Edit metadata | Change title and author in Step 2 | Changes persisted when advancing to Step 3 |
| UPL-09 | Add tags during upload | Add 2 tags in Step 2 | Tags appear on book in Library after save |
| UPL-10 | Delete stub section | In Step 3, delete a stub section | Section removed from list, count updates |
| UPL-11 | Merge adjacent sections | Select 2 adjacent sections, merge | Preview shows combined content, confirm creates merged section |
| UPL-12 | Merge non-adjacent sections | Select 2 non-adjacent sections, merge | Error: "Can only merge adjacent sections" |
| UPL-13 | Split at heading | Select section > Split > At heading | Detected headings shown, preview of parts, confirm splits |
| UPL-14 | Save without processing | Click "Save without processing" at Step 3 | Book saved with status "parsed", no summarization |
| UPL-15 | Corrupt file upload | Upload a renamed .zip as .epub | Server-side parse error, user-friendly error message |
| UPL-16 | Upload progress | Upload a 50MB file | Progress bar shows real-time transfer percentage |
| UPL-17 | Preset selection | At Step 4, select a preset | Preset details visible (facets, assertions, prompt preview) |
| UPL-18 | Create custom preset during upload | Click "+ Create New" at Step 4 | Modal with facet selectors, save and select |
| UPL-19 | Re-import existing book | Choose "Re-import" on duplicate dialog | Eval traces marked stale, sections updated in-place |

### 6.3 Reader Tests

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| RDR-01 | View original content | Open book, select "Original" | Section content_md rendered as markdown |
| RDR-02 | View summary content | Toggle to "Summary" | Default summary rendered with eval banner |
| RDR-03 | Navigate via TOC | Click chapter breadcrumb > select Chapter 5 | Reader navigates to Chapter 5 |
| RDR-04 | Navigate with arrows | Click Next arrow | Advances to next section by order_index |
| RDR-05 | Keyboard navigation | Press Right arrow | Same as Next arrow |
| RDR-06 | Concept chip click | Click a concept chip in summary | Tooltip with definition, section count, related concepts |
| RDR-07 | Text selection toolbar | Select text in content area | Floating toolbar appears: Highlight, Note, Ask AI, Link, Copy |
| RDR-08 | Summary version selector | Click version dropdown | Shows all summary versions with preset + date |
| RDR-09 | No summary state | Toggle to Summary on un-summarized section | "No summary available" + Summarize button |
| RDR-10 | Eval banner display | View summary with eval results | Correct pass/fail count, color-coded banner |
| RDR-11 | Eval details expansion | Click "View eval details" | Grouped assertions with pass/fail, reasoning |
| RDR-12 | Max-width content | Desktop viewport > 1024px | Content area maxes out at 720px, centered |
| RDR-13 | Mobile reader layout | 375px viewport | Single column, bottom action bar, no sidebar |
| RDR-14 | Context sidebar toggle | Click Annotations button | Sidebar opens on Annotations tab. Click again closes. |
| RDR-15 | Focus mode AI access | In focus mode, click AI button | AI sidebar opens (AI is always accessible) |

### 6.4 Annotation Tests

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| ANN-01 | Create highlight | Select text > Highlight | Yellow highlight on text, annotation in sidebar |
| ANN-02 | Create note | Select text > Note > type > Save | Highlight + note body saved |
| ANN-03 | Create freeform note | Sidebar > bottom input > type > Add note | Freeform annotation created (no text selection) |
| ANN-04 | Edit annotation | Sidebar > click note text > edit | Inline editing, saves on blur/Enter |
| ANN-05 | Delete annotation | Sidebar > annotation > ... > Delete | Annotation removed, highlight removed from content |
| ANN-06 | Link annotations | Annotation > Link > search > select target | Both annotations show linked reference |
| ANN-07 | Annotation on summary | In Summary view, highlight text | Annotation has content_type=section_summary |
| ANN-08 | Navigate from global page | Annotations page > click source breadcrumb | Opens book reader at annotation location |
| ANN-09 | Filter annotations by book | Annotations page > Book filter = specific book | Only that book's annotations shown |
| ANN-10 | Group by tag | Annotations page > Group by = Tag | Annotations grouped by tag in accordion |
| ANN-11 | Margin alignment | Scroll through section with annotations | Sidebar annotations align with content highlights |
| ANN-12 | Export annotations | Annotations page > Export > Markdown | Downloads file with all visible annotations |
| ANN-13 | Annotation count badge | Close Annotations sidebar | Badge on Annotations button shows count |

### 6.5 AI Chat Tests

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| AI-01 | New thread from text selection | Select text > Ask AI > type question > Send | New thread created, context block shown, response streams |
| AI-02 | Continue existing thread | Open thread > type follow-up > Send | Message appended to thread, AI responds in context |
| AI-03 | Thread list display | Open AI tab with 3 threads | All threads shown with title, count, date, preview |
| AI-04 | Rename thread | Click thread title > edit | Title updates |
| AI-05 | Save response as note | AI response > "Save as note" | Freeform annotation created on current section |
| AI-06 | Multi-section reference | Ask about "themes across chapters" | AI references multiple sections with clickable links |
| AI-07 | Streaming response | Send message | Response appears token-by-token via SSE |
| AI-08 | Context from selected text | Select text then open AI | Context chip shows "Using selected text from [Section]" |
| AI-09 | Remove context | Click X on context chip | Context removed, question asked without specific passage context |
| AI-10 | Mobile AI bottom sheet | On mobile, tap AI in bottom bar | Bottom sheet slides up at 30%, swipeable to 50%, 90% |

### 6.6 Search Tests

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| SRC-01 | Command palette open | Press Cmd+K | Palette opens with recent searches |
| SRC-02 | Instant search results | Type "cognitive" in palette | Grouped results appear within 300ms |
| SRC-03 | Keyboard navigation | Arrow down through results, Enter | Selected result opens |
| SRC-04 | Full results page | Shift+Enter from palette | Full results page at /search?q=... |
| SRC-05 | Filter by source type | Full results > click "Concepts" filter | Only concept results shown |
| SRC-06 | Group by book | Full results page | Results grouped under book headers |
| SRC-07 | Expand book group | Click "Show N more" | All results for that book visible |
| SRC-08 | No results | Search "xyzzy123" | Empty state with suggestions |
| SRC-09 | Highlight matches | Search "anchoring" | Term highlighted in yellow in snippets |
| SRC-10 | Mobile search | Tap Search tab on mobile | Full-screen search modal |

### 6.7 Settings Tests

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| SET-01 | View system preset | Settings > Presets > select "balanced" | Read-only detail with facets, assertions, prompt preview |
| SET-02 | Duplicate system preset | Settings > Presets > "balanced" > Duplicate | Editable copy created as user preset |
| SET-03 | Create user preset | Settings > Presets > New Preset | Form with 4 facet selectors, save |
| SET-04 | Delete user preset | Settings > Presets > user preset > Delete | Confirmation > deleted |
| SET-05 | Enable LAN access | Settings > General > toggle Allow LAN | Warning shown, QR code appears |
| SET-06 | Generate access token | Settings > General > Generate token | Random token generated, copyable |
| SET-07 | Create database backup | Settings > Backup > Create Backup | pg_dump runs, download link appears |
| SET-08 | Restore from backup | Settings > Backup > Restore > upload .sql | Data replaced, page reloads |
| SET-09 | Export library as JSON | Settings > Backup > Export > JSON > All books | JSON file downloads with all data |
| SET-10 | View database stats | Settings > Database | Shows counts for all entity types |

### 6.8 Reader Settings Tests

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| RST-01 | Apply preset | Open Aa > click "Night Reading" | Font, size, spacing, background all update |
| RST-02 | Change font | Click "Merriweather" button | Reader font changes immediately |
| RST-03 | Adjust size via stepper | Click + button 3 times from 16px | Size is 19px, reader updates |
| RST-04 | Custom background color | Click palette icon > pick color | Background changes, text auto-contrasts |
| RST-05 | Save custom preset | Configure settings > "+ Save Current" > name | New preset card appears |
| RST-06 | Persistence across sessions | Set preferences, close browser, reopen | Same settings applied |
| RST-07 | Live preview | Change font with popover open | Sample text at bottom updates in real-time |
| RST-08 | Mobile bottom sheet | On mobile, tap Aa | Settings appear as bottom sheet, not popover |

### 6.9 Processing & SSE Tests

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| PRC-01 | Full processing flow | Start summarization on a 10-section book | All 10 sections processed, progress tracked |
| PRC-02 | SSE events received | Monitor network tab during processing | SSE events for each section start/complete/fail |
| PRC-03 | Minimize progress | Click Minimize during processing | Bottom bar shows mini progress |
| PRC-04 | Multiple concurrent jobs | Start 2 books processing | Both appear in bottom bar stack |
| PRC-05 | Cancel processing | Click Stop during Section 5/10 | Sections 1-4 preserved, 5+ cancelled |
| PRC-06 | Browse during processing | Click completed Section 2 while Section 5 processes | Section 2 readable with summary |
| PRC-07 | Auto-retry on eval fail | Section fails critical eval assertion | Re-summarization triggered, new eval run |
| PRC-08 | SSE reconnect | Simulate brief network drop | SSE reconnects, progress state recovered |
| PRC-09 | Page reload during processing | Refresh browser | Processing state recovered from server |

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Metric | Target |
|--------|--------|
| Library page load (< 100 books) | < 500ms |
| Library page load (100-500 books) | < 1.5s |
| Search (command palette) results | < 300ms after debounce |
| Search (full results) page load | < 1s |
| Section content rendering | < 200ms |
| Reader settings change | < 50ms (real-time feel) |
| File upload start (client-side validation) | < 100ms |
| SSE event delivery latency | < 500ms from server event to UI update |
| API response (simple CRUD) | < 200ms |

**Loading & Skeleton States:**

Every page and async-loaded component must show a loading state while data is fetched:

| Component | Loading State |
|-----------|--------------|
| Library book grid/list/table | Skeleton cards/rows matching the layout shape (cover placeholder, text bars) |
| Book Detail content area | Skeleton paragraph blocks matching reader width |
| Annotations sidebar | Skeleton annotation cards (type badge placeholder, text bars) |
| AI chat messages | Typing indicator (three animated dots) for AI responses |
| Search results | Skeleton result cards grouped by book headers |
| Concepts Explorer detail panel | Skeleton definition block, section list placeholders |
| Processing progress | Spinner with "Loading processing status..." text |
| Settings pages | Skeleton form fields |

- Skeleton animations: Subtle shimmer/pulse effect (CSS `@keyframes`), not spinners
- Target: All skeleton states render within 50ms of navigation, replaced by real content when data arrives
- Error fallback: If data fails to load after 10 seconds, show error message with "Retry" button

### 7.2 Accessibility

- **WCAG 2.1 AA** compliance target
- Semantic HTML elements (nav, main, article, aside, section)
- ARIA labels on all interactive elements
- Keyboard navigation: All features accessible without mouse
- Focus management: Logical tab order, visible focus indicators
- Screen reader support: Meaningful alt text, live regions for updates
- Color contrast: 4.5:1 minimum for text, 3:1 for large text/UI elements
- Reduced motion: Respect `prefers-reduced-motion` media query
- Font sizing: Uses rem units, respects user's browser font size setting

### 7.3 Browser Support

| Browser | Minimum Version |
|---------|----------------|
| Chrome | 90+ |
| Firefox | 90+ |
| Safari | 15+ |
| Edge | 90+ |
| Mobile Safari (iOS) | 15+ |
| Chrome (Android) | 90+ |

### 7.4 Responsive Design

| Breakpoint | Width Range | Tailwind Prefix |
|------------|-------------|-----------------|
| Mobile | < 768px | `sm:` (default) |
| Tablet | 768-1023px | `md:` |
| Desktop | >= 1024px | `lg:` |
| Wide | >= 1280px | `xl:` |

### 7.5 Security

- **No authentication** — personal tool on trusted local network
- CORS restricted to localhost and LAN origins
- File upload validation: Size limit, format whitelist, server-side MIME check
- No user-supplied HTML rendering (markdown only, sanitized)
- SQL injection prevention via SQLAlchemy ORM (parameterized queries)
- XSS prevention via Vue's default text interpolation (no `v-html` with user content)

### 7.6 Internationalization

- V1: English only
- All user-facing strings centralized in locale files (preparation for future i18n)
- Date formatting: Use `Intl.DateTimeFormat` for locale-aware dates
- Number formatting: Use `Intl.NumberFormat`

---

## 8. Data Model

### 8.1 Existing Models (Unchanged)

The web interface reuses all existing models from `backend/app/db/models.py`:

- `Book` (id, title, file_data, file_hash, file_format, file_size_bytes, cover_image, default_summary_id, status, quick_summary, metadata_, created_at, updated_at)
- `Author` (id, name, metadata_, created_at)
- `BookAuthor` (book_id, author_id, role)
- `BookSection` (id, book_id, parent_id, title, order_index, depth, content_md, content_token_count, default_summary_id, section_type, derived_from, created_at)
- `Image` (id, section_id, data, mime_type, filename, width, height, caption, caption_model, relevance, alt_text, content_hash, created_at)
- `Summary` (id, content_type, content_id, book_id, preset_name, facets_used, prompt_text_sent, model_used, input_tokens, output_tokens, input_char_count, summary_char_count, summary_md, eval_json, quality_warnings, retry_of_id, latency_ms, created_at)
- `EvalTrace` (id, section_id, summary_id, assertion_name, assertion_category, passed, prompt_sent, prompt_version, llm_response, reasoning, model_used, input_tokens, output_tokens, latency_ms, is_stale, eval_run_id, likely_cause, suggestion, created_at)
- `SearchIndex` (id, source_type, source_id, book_id, chunk_text, chunk_index, embedding, tsvector, created_at)
- `ProcessingJob` (id, book_id, step, status, progress, error_message, started_at, completed_at, pid)
- `Tag` (id, name, color, created_at)
- `Taggable` (tag_id, taggable_type, taggable_id)
- `Annotation` (id, content_type, content_id, text_start, text_end, selected_text, note, type, linked_annotation_id, created_at, updated_at)
- `Concept` (id, book_id, first_section_id, term, definition, related_concepts, user_edited, created_at, updated_at)
- `ConceptSection` (concept_id, section_id)
- `ExternalReference` (id, book_id, url, title, source_name, snippet, quality_notes, discovered_at)

### 8.2 New Models (Web Interface)

#### 8.2.1 LibraryView

Persists saved library views (filter + sort + display combinations).

```
Table: library_views
  id              BIGINT PRIMARY KEY
  name            VARCHAR(200) NOT NULL
  is_default      BOOLEAN DEFAULT FALSE
  display_mode    VARCHAR(20) NOT NULL DEFAULT 'grid'  -- grid | list | table
  sort_field      VARCHAR(50) NOT NULL DEFAULT 'updated_at'
  sort_direction  VARCHAR(4) NOT NULL DEFAULT 'desc'  -- asc | desc
  filters         JSONB NOT NULL DEFAULT '{}'
    -- Example: {"status": ["completed"], "tags": [1, 3], "authors": [2], "eval": ["passed"], "format": ["epub"]}
  table_columns   JSONB  -- Column visibility/order for table mode
    -- Example: {"visible": ["title", "author", "status", "tags", "eval"], "order": ["title", "author", "status"]}
  position        INTEGER NOT NULL DEFAULT 0  -- Tab ordering
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()
```

#### 8.2.2 ReadingPreset

Persists reading display preferences (font, size, spacing, colors).

```
Table: reading_presets
  id              BIGINT PRIMARY KEY
  name            VARCHAR(200) NOT NULL
  is_system       BOOLEAN DEFAULT FALSE  -- System presets are read-only
  is_active       BOOLEAN DEFAULT FALSE  -- Currently selected preset
  font_family     VARCHAR(100) NOT NULL DEFAULT 'Georgia'
  font_size_px    INTEGER NOT NULL DEFAULT 16
  line_spacing    DECIMAL(3,1) NOT NULL DEFAULT 1.6
  content_width_px INTEGER NOT NULL DEFAULT 720
  bg_color        VARCHAR(7) NOT NULL DEFAULT '#FFFFFF'  -- Hex color
  text_color      VARCHAR(7) NOT NULL DEFAULT '#1A1A1A'  -- Hex color (auto-calculated or user-set)
  custom_css      TEXT  -- Advanced: user-injected CSS
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE(name)
```

#### 8.2.3 AIThread

Per-book conversation threads with the LLM.

```
Table: ai_threads
  id              BIGINT PRIMARY KEY
  book_id         BIGINT NOT NULL REFERENCES books(id) ON DELETE CASCADE
  title           VARCHAR(500) NOT NULL DEFAULT 'New Thread'
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  INDEX ix_ai_threads_book_id (book_id)
```

#### 8.2.4 AIMessage

Individual messages within a conversation thread.

```
Table: ai_messages
  id              BIGINT PRIMARY KEY
  thread_id       BIGINT NOT NULL REFERENCES ai_threads(id) ON DELETE CASCADE
  role            VARCHAR(20) NOT NULL  -- 'user' | 'assistant'
  content         TEXT NOT NULL
  context_section_id  BIGINT REFERENCES book_sections(id) ON DELETE SET NULL  -- Section that was being read
  selected_text   TEXT  -- Text that was selected as context (if any)
  model_used      VARCHAR(100)  -- Only for assistant messages
  input_tokens    INTEGER  -- Only for assistant messages
  output_tokens   INTEGER  -- Only for assistant messages
  latency_ms      INTEGER  -- Only for assistant messages
  created_at      TIMESTAMPTZ DEFAULT now()

  INDEX ix_ai_messages_thread_id (thread_id)
```

#### 8.2.5 RecentSearch

Stores recent search queries for command palette empty state.

```
Table: recent_searches
  id              BIGINT PRIMARY KEY
  query           VARCHAR(500) NOT NULL
  result_count    INTEGER
  created_at      TIMESTAMPTZ DEFAULT now()

  INDEX ix_recent_searches_created_at (created_at DESC)
```

#### 8.2.6 ReadingState

Tracks reading position for cross-device sync. *(Creativity: S4)*

```
Table: reading_state
  id                BIGINT PRIMARY KEY
  user_agent        VARCHAR(500) NOT NULL
  last_book_id      BIGINT REFERENCES books(id) ON DELETE CASCADE
  last_section_id   BIGINT REFERENCES book_sections(id) ON DELETE SET NULL
  last_viewed_at    TIMESTAMPTZ DEFAULT now()
  created_at        TIMESTAMPTZ DEFAULT now()
  updated_at        TIMESTAMPTZ DEFAULT now()

  UNIQUE ix_reading_state_user_agent (user_agent)
```

### 8.3 Model Relationships

```
Book  1──N  AIThread  1──N  AIMessage
                              └──?  BookSection (context)

ReadingState   ──?  Book, BookSection
ReadingPreset  (standalone, no FKs)
LibraryView    (standalone, no FKs)
RecentSearch   (standalone, no FKs)
```

### 8.4 Migration Notes

- New tables require an Alembic migration: `alembic revision --autogenerate -m "add web interface tables"`
- No changes to existing tables
- System reading presets should be seeded via a data migration (Comfortable, Night Reading, Study Mode, Compact)
- Default "All Books" library view should be seeded as well
- `ai_messages.context_section_id` FK uses `ON DELETE SET NULL` to handle section deletion gracefully

---

## 9. API Design Overview

### 9.1 General Conventions

- Base path: `/api/v1/`
- Content type: `application/json` (except file uploads: `multipart/form-data`)
- Pagination: `?page=1&per_page=20` (defaults: page=1, per_page=20, max per_page=100)
- Sorting: `?sort=created_at&order=desc`
- Error responses: `{"detail": "Human-readable error message", "code": "ERROR_CODE"}`
- SSE streams: `text/event-stream` content type, events as `data: {json}\n\n`
- Auth (when enabled): `Authorization: Bearer <token>` header. 401 if missing/invalid when token is configured.

### 9.2 Books

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/books` | List books. Query: `?status=completed&tag_ids=1,3&author_ids=2&format=epub&sort=updated_at&order=desc&page=1&per_page=20` |
| `GET` | `/api/v1/books/{id}` | Get book detail. Includes authors, section count, default summary info, tag IDs, eval summary. |
| `POST` | `/api/v1/books/upload` | Upload a book file. Multipart form: `file` (required), `title` (optional override), `author` (optional override). Returns parsed book with sections. |
| `POST` | `/api/v1/books/{id}/check-duplicate` | Check SHA-256 hash for duplicate. Body: `{file_hash}`. Returns: `{duplicate: bool, existing_book_id?, match_type: "exact"|"similar"}` |
| `PATCH` | `/api/v1/books/{id}` | Update book metadata. Body: `{title?, authors?: [{name, role}], tag_ids?}` |
| `DELETE` | `/api/v1/books/{id}` | Delete a book and all associated data. |
| `POST` | `/api/v1/books/{id}/reimport` | Re-import book. Marks eval traces stale, re-parses file, updates sections in-place. |
| `GET` | `/api/v1/books/{id}/cover` | Get book cover image. Returns image binary with appropriate content type. |
| `PUT` | `/api/v1/books/{id}/cover` | Update book cover image. Multipart form: `file`. |

### 9.3 Sections

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/books/{book_id}/sections` | List sections for a book. Ordered by `order_index`. Includes: id, title, order_index, section_type, content_token_count, has_summary, eval_summary. |
| `GET` | `/api/v1/books/{book_id}/sections/{id}` | Get section detail. Includes content_md, default summary, annotations count. |
| `GET` | `/api/v1/books/{book_id}/sections/{id}/content` | Get section original content (markdown). Separate endpoint to avoid loading content in list views. |
| `PATCH` | `/api/v1/books/{book_id}/sections/{id}` | Update section. Body: `{title?, section_type?, order_index?}` |
| `DELETE` | `/api/v1/books/{book_id}/sections/{id}` | Delete section. |
| `POST` | `/api/v1/books/{book_id}/sections/merge` | Merge sections. Body: `{section_ids: [1, 2, 3], title: "Merged"}` |
| `POST` | `/api/v1/books/{book_id}/sections/{id}/split` | Split section. Body: `{mode: "heading"|"manual", positions: [500]}` Returns new sections. |
| `POST` | `/api/v1/books/{book_id}/sections/reorder` | Reorder sections. Body: `{section_ids: [3, 1, 2]}` (new order) |
| `GET` | `/api/v1/books/{book_id}/sections/{id}/headings` | Detect headings within a section (for split UI). Returns: `[{position, level, text}]` |

### 9.4 Summaries

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/summaries` | List summaries. Query: `?book_id=1&content_type=section&content_id=5&sort=created_at` |
| `GET` | `/api/v1/summaries/{id}` | Get summary detail. Includes: summary_md, eval_json, facets_used, quality_warnings. |
| `POST` | `/api/v1/summaries/{id}/set-default` | Set as default summary for its content (section or book). |
| `GET` | `/api/v1/summaries/compare` | Compare two summaries. Query: `?id1=5&id2=8`. Returns both summaries + concept diff. |
| `DELETE` | `/api/v1/summaries/{id}` | Delete a summary. If it was default, clears `default_summary_id`. |

### 9.5 Processing & Summarization

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/books/{id}/summarize` | Start summarization. Body: `{preset_name?, facets?, run_eval: bool, auto_retry: bool}`. Returns `{job_id}`. |
| `GET` | `/api/v1/processing/{job_id}/stream` | SSE stream for processing progress. Content-Type: `text/event-stream`. |
| `GET` | `/api/v1/processing/{job_id}/status` | Get current processing status (for reconnection). Returns: `{status, progress, sections_completed, sections_total, current_section}`. |
| `POST` | `/api/v1/processing/{job_id}/cancel` | Cancel a running processing job. |
| `GET` | `/api/v1/books/{id}/processing-jobs` | List processing jobs for a book. |

### 9.6 Evaluation

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/eval/book/{book_id}` | Get eval results for a book. Aggregated across all sections. Query: `?summary_id=5&book_only=true` |
| `GET` | `/api/v1/eval/section/{section_id}` | Get eval results for a section. Query: `?summary_id=5` |
| `GET` | `/api/v1/eval/traces` | List eval traces. Query: `?section_id=5&summary_id=8&assertion_name=no_hallucinated_facts&include_stale=false` |
| `POST` | `/api/v1/books/{id}/evaluate` | Trigger evaluation. Body: `{section_id?, summary_id?, force: bool}`. Returns `{job_id}` for SSE tracking. |

### 9.7 Search

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/search` | Full search. Query: `?q=anchoring&source_types=section,concept&book_ids=1,2&tag_ids=3&sort=relevance&page=1&per_page=20`. Returns grouped results with highlights. |
| `GET` | `/api/v1/search/quick` | Quick search (command palette). Query: `?q=anchoring&limit=12`. Returns max 3 per type, lighter response. |

### 9.8 Presets

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/presets` | List all presets (system + user). |
| `GET` | `/api/v1/presets/{name}` | Get preset detail. Includes facets, assertion config, rendered prompt template. |
| `POST` | `/api/v1/presets` | Create user preset. Body: `{name, style, audience, compression, content_focus}` |
| `PUT` | `/api/v1/presets/{name}` | Update user preset. |
| `DELETE` | `/api/v1/presets/{name}` | Delete user preset. |
| `POST` | `/api/v1/presets/{name}/duplicate` | Duplicate a preset (system or user) as a new user preset. Body: `{new_name}` |

### 9.9 Annotations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/annotations` | List annotations. Query: `?book_id=1&section_id=5&content_type=section_content&type=highlight&tag_ids=1&sort=created_at&group_by=book&page=1&per_page=50` |
| `GET` | `/api/v1/annotations/{id}` | Get annotation detail. |
| `POST` | `/api/v1/annotations` | Create annotation. Body: `{content_type, content_id, text_start?, text_end?, selected_text?, note?, type}` |
| `PATCH` | `/api/v1/annotations/{id}` | Update annotation. Body: `{note?, type?}` |
| `DELETE` | `/api/v1/annotations/{id}` | Delete annotation. |
| `POST` | `/api/v1/annotations/{id}/link` | Link to another annotation. Body: `{target_annotation_id}` |
| `DELETE` | `/api/v1/annotations/{id}/link` | Remove annotation link. |
| `GET` | `/api/v1/annotations/export` | Export annotations. Query: `?book_id=1&format=markdown|json|csv`. Returns file download. |

### 9.10 Concepts

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/concepts` | List concepts. Query: `?book_id=1&user_edited=true&tag_ids=1&sort=term&group_by=book&page=1&per_page=50` |
| `GET` | `/api/v1/concepts/{id}` | Get concept detail. Includes section appearances, related concepts, related annotations. |
| `PATCH` | `/api/v1/concepts/{id}` | Update concept. Body: `{term?, definition?}`. Sets `user_edited=True`. |
| `POST` | `/api/v1/concepts/{id}/reset` | Reset to LLM-generated definition. Sets `user_edited=False`. |
| `DELETE` | `/api/v1/concepts/{id}` | Delete concept. |

### 9.11 Tags

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/tags` | List all tags with usage counts. |
| `POST` | `/api/v1/tags` | Create tag. Body: `{name, color?}` |
| `PATCH` | `/api/v1/tags/{id}` | Update tag. Body: `{name?, color?}` |
| `DELETE` | `/api/v1/tags/{id}` | Delete tag. Removes all taggable associations. |
| `POST` | `/api/v1/tags/{id}/assign` | Assign tag to entity. Body: `{taggable_type, taggable_id}` |
| `DELETE` | `/api/v1/tags/{id}/assign` | Remove tag from entity. Body: `{taggable_type, taggable_id}` |

### 9.12 AI Threads

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/books/{book_id}/ai-threads` | List AI threads for a book. Ordered by `updated_at` descending. |
| `POST` | `/api/v1/books/{book_id}/ai-threads` | Create new thread. Body: `{title?}` |
| `GET` | `/api/v1/ai-threads/{id}` | Get thread with all messages. |
| `PATCH` | `/api/v1/ai-threads/{id}` | Update thread. Body: `{title}` |
| `DELETE` | `/api/v1/ai-threads/{id}` | Delete thread and all messages. |
| `POST` | `/api/v1/ai-threads/{id}/messages` | Send a message. Body: `{content, context_section_id?, selected_text?}`. Returns SSE stream of AI response tokens. |
| `GET` | `/api/v1/ai-threads/{id}/messages` | Get messages for a thread. Paginated. |

### 9.13 Library Views

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/views` | List all library views. Ordered by `position`. |
| `POST` | `/api/v1/views` | Create view. Body: `{name, display_mode?, sort_field?, sort_direction?, filters?, table_columns?}` |
| `PATCH` | `/api/v1/views/{id}` | Update view. Body: any field subset. |
| `DELETE` | `/api/v1/views/{id}` | Delete view. Cannot delete last view. |
| `POST` | `/api/v1/views/reorder` | Reorder view tabs. Body: `{view_ids: [3, 1, 2]}` |
| `POST` | `/api/v1/views/{id}/set-default` | Set as default view (loaded on app start). |

### 9.14 Reading Preferences

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/reading-presets` | List all reading presets (system + user). |
| `GET` | `/api/v1/reading-presets/active` | Get the currently active reading preset. |
| `POST` | `/api/v1/reading-presets` | Create user preset. Body: `{name, font_family, font_size_px, line_spacing, content_width_px, bg_color, text_color?}` |
| `PATCH` | `/api/v1/reading-presets/{id}` | Update preset (user only). |
| `DELETE` | `/api/v1/reading-presets/{id}` | Delete preset (user only). |
| `POST` | `/api/v1/reading-presets/{id}/activate` | Set as active preset. |

### 9.15 Settings & System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/settings` | Get current application settings (safe subset, no secrets). |
| `PATCH` | `/api/v1/settings` | Update settings. Body: Partial settings object. Writes to YAML config. |
| `GET` | `/api/v1/settings/database-stats` | Database statistics: row counts for all tables. |
| `GET` | `/api/v1/settings/migration-status` | Alembic migration status: current, latest, is_behind. |
| `POST` | `/api/v1/settings/run-migrations` | Run pending Alembic migrations. |

### 9.16 Export & Backup

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/export/book/{id}` | Export single book. Query: `?format=markdown|json&include_summaries=true&include_annotations=true&include_concepts=true&include_eval=false` |
| `GET` | `/api/v1/export/library` | Export library. Query: `?format=json&book_ids=1,2,3` (omit book_ids for all). |
| `POST` | `/api/v1/backup/create` | Create database backup. Returns `{backup_id}`. Progress via SSE. |
| `GET` | `/api/v1/backup/list` | List backups. Returns: `[{id, filename, size_bytes, created_at}]` |
| `GET` | `/api/v1/backup/{id}/download` | Download a backup file. |
| `POST` | `/api/v1/backup/restore` | Restore from uploaded backup. Multipart form: `file`. |
| `DELETE` | `/api/v1/backup/{id}` | Delete a backup file. |

### 9.17 Images

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/images/{id}` | Get image binary. Returns image with correct MIME type. Used by `<img>` tags in rendered markdown. |
| `GET` | `/api/v1/images/{id}/thumbnail` | Get image thumbnail (resized). Query: `?width=200&height=300` |

---

*End of requirements document. This document is the source of truth for building the Book Companion web interface. All implementation plans, wireframes, and technical decisions should reference this document.*
