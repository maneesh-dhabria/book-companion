# Web Interface Phase 2 — Implementation Plan

**Date:** 2026-04-10
**Spec:** `docs/specs/2026-04-10_web_interface_v1_spec.md`
**Requirements:** `docs/requirements/2026-04-10_web_interface_v1_requirements.md`
**Depends on:** Phase 1 plan (`docs/plans/2026-04-10-web-interface-phase1-implementation-plan.md`)

---

## Overview

Phase 2 adds the rich interactive features on top of Phase 1's foundation: reader settings with preset persistence, annotations (creation, sidebar, global page), AI chat via coding agent CLI subprocess, hybrid search (command palette + full results), concepts explorer, the 5-step upload wizard, and processing progress integration. Each feature touches both backend (new API endpoints) and frontend (new components, stores, composables). The backend work reuses existing services (SearchService, AnnotationRepository, ConceptRepository, PresetService) and the Phase 1 FastAPI DI pattern; the frontend work builds new Pinia stores, composables (useTextSelection, useKeyboard), and view-level components within the scaffolding established in Phase 1.

**Done when:** Reader settings persist across sessions and apply live to the reading area; text selection shows a floating toolbar that creates highlights/notes; the annotation sidebar lists section annotations and the global annotations page supports filter/group/sort/export; AI chat sends messages to the coding agent CLI and displays complete responses; Cmd+K opens a command palette with grouped instant results and Enter navigates to the source; the concepts explorer shows a two-panel layout with editable definitions; the upload wizard guides through 5 steps (drop zone, metadata, structure review, preset selection, processing); and processing progress displays via SSE in a pinned card minimizable to a bottom bar. All new backend endpoints pass integration tests and all frontend pages build without errors.

**Execution order:**
```
Backend (API endpoints):
  T1 (Annotations API) ─┐
  T2 (AI Threads API)  ──┤── all parallelizable [P]
  T3 (Search API)      ──┤
  T4 (Concepts API)    ──┤
  T5 (Reading Presets API)┘
       │
       ▼
Frontend (features — each depends on its backend API):
  T6 (Reader Settings popover + persistence) ← depends on T5
  T7 (Text selection + floating toolbar) ← standalone composable
       │
       ▼
  T8 (Annotation sidebar + global page) ← depends on T1, T7
  T9 (AI chat sidebar) ← depends on T2
       │
       ▼ (T8 and T9 parallelizable)
  T10 (Command palette + search results page) ← depends on T3
  T11 (Concepts explorer) ← depends on T4
       │
       ▼ (T10 and T11 parallelizable)
  T12 (Upload wizard) ← depends on Phase 1 T4 (books API)
  T13 (Processing progress card + bottom bar) ← depends on Phase 1 T7 (SSE)
       │
       ▼ (T12 and T13 parallelizable)
  T14 (Final verification) ← depends on all

[P] = T1–T5 are fully parallelizable
T6, T7 can proceed in parallel after T5
T8 requires T1 + T7; T9 requires T2
T10, T11 are parallelizable after T8/T9
T12, T13 are parallelizable, depend on Phase 1 APIs
```

---

## Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| PD13 | AI chat returns complete JSON response (not SSE) despite requirements §9.12 mentioning SSE | (a) SSE streaming of tokens, (b) Complete response with loading indicator, (c) Chunked transfer encoding | Spec D4 explicitly states "no token-by-token streaming in V1" because the coding agent CLI subprocess returns a complete response. The endpoint returns standard JSON with the full assistant message. A loading spinner is shown client-side during the ~5-30s wait. |
| PD14 | Quick search endpoint (`/api/v1/search/quick`) returns flat grouped results, not paginated | (a) Paginated like full search, (b) Flat grouped with max 3 per type, (c) Single merged list | Command palette needs instant grouped results (max 3 per type per spec §9.7). Pagination adds complexity for a 12-item max result set. Full search (`/api/v1/search`) uses pagination for the results page. |
| PD15 | Annotation export generates file server-side and returns as download | (a) Server-generated file download, (b) Client-side generation from API data, (c) Background job with SSE | Server-side ensures consistent formatting and handles large annotation sets. Small enough to generate synchronously (no SSE needed). Spec §9.9 specifies `GET /api/v1/annotations/export` returning a file download. |
| PD16 | Upload wizard state lives in a dedicated Pinia store (not component-local) | (a) Pinia store, (b) Component-local reactive state, (c) URL query params | Pinia survives browser back/forward navigation (spec E7). Each wizard step has a URL path, and the store preserves state across step transitions. Also enables the "Quick Upload" fast path (FR-48) to pre-populate and skip steps. |
| PD17 | useTextSelection composable uses `document.getSelection()` API with debounced position calculation | (a) Native Selection API, (b) Custom range tracking via mouse events, (c) Library (e.g., rangy) | Native Selection API is well-supported in target browsers (Chrome 90+, Firefox 90+, Safari 15+). No library needed. Debouncing prevents toolbar flicker during drag-select. |
| PD18 | Reading presets API is separate from summarization presets API — different table, different endpoints | (a) Shared preset API, (b) Separate APIs | Reading presets (font, size, colors) live in `reading_presets` table (Phase 1 T2). Summarization presets live on disk as YAML files managed by `PresetService`. Different data shapes, different storage, different concerns. |

---

## Code Study Notes

### Phase 1 Foundation (What Phase 2 Builds On)

- **FastAPI app factory** (`backend/app/api/main.py`): Registers routers, creates session factory in `app.state`, mounts static files. Phase 2 adds new routers here.
- **Dependency injection** (`backend/app/api/deps.py`): `get_db()`, `get_settings()`, `get_book_service()`, etc. Phase 2 adds `get_search_service()`, `get_annotation_repo()`, `get_concept_repo()`, plus new AI thread service deps.
- **Pydantic schemas** (`backend/app/api/schemas.py`): Phase 2 extends with annotation, concept, AI thread, search, and reading preset schemas.
- **SSE event bus** (`backend/app/api/sse.py`): `EventBus` with per-job queues. Phase 2's processing progress card consumes these events via the `useSSE` composable.
- **Frontend scaffolding** (`frontend/`): Vue 3 + Vite + Pinia + Vue Router + Tailwind + shadcn-vue. Routes defined, placeholder views exist for `/annotations`, `/concepts`, `/search`, `/upload`.
- **API client layer** (`frontend/src/api/`): Base client with typed methods. Phase 2 adds `annotations.ts`, `concepts.ts`, `aiThreads.ts`, `search.ts`, `readingPresets.ts`.
- **Design tokens** (`frontend/src/assets/theme.css`): CSS custom properties for themes. Reader settings popover updates these tokens live.
- **Reader store** (`frontend/src/stores/reader.ts`): Manages current book/section/contentMode. Phase 2 extends with sidebar state.
- **App shell** (`frontend/src/components/app/`): Icon rail, top bar, bottom tab bar. Phase 2 wires the search input in TopBar to open the command palette, and the Upload button to open the wizard.

### Existing Services/Repos to Reuse

- **`SearchService`** (`backend/app/services/search_service.py`): Already has `search()` with BM25 + semantic + RRF. Has `index_annotation()`, `index_concept()`, `reindex_annotation()`, `delete_annotation_index()`. The quick search endpoint wraps `search()` with post-processing to group by type and limit to 3 per type.
- **`AnnotationRepository`** (`backend/app/db/repositories/annotation_repo.py`): Full CRUD: `create()`, `get_by_id()`, `list_by_content()`, `list_by_book()`, `list_by_tag()`, `update()`, `delete()`, `link_annotations()`. Phase 2 API endpoints are thin wrappers around these.
- **`ConceptRepository`** (`backend/app/db/repositories/concept_repo.py`): `get_by_book()`, `search_across_books()`, `get_by_id()`, `update_definition()`, `get_sections_for_concept()`. Phase 2 adds pagination, filtering, related concepts (cross-book), and reset-to-original.
- **`PresetService`** (`backend/app/services/preset_service.py`): Manages YAML-based summarization presets. Reading presets are a separate concern (DB-backed `reading_presets` table), but the CRUD pattern is similar.
- **`AIThread` / `AIMessage` models** (`backend/app/db/models.py`): Added in Phase 1 T2 migration. `AIThread` has `book_id`, `title`; `AIMessage` has `thread_id`, `role`, `content`, `context_section_id`, `selected_text`, `model_used`, token counts, `latency_ms`.
- **`ReadingPreset` model** (`backend/app/db/models.py`): Added in Phase 1 T2. Fields: `name`, `is_system`, `is_active`, `font_family`, `font_size_px`, `line_spacing`, `content_width_px`, `bg_color`, `text_color`, `custom_css`.
- **`ClaudeCodeCLIProvider`**: Used by `SummarizerService` for LLM calls. AI chat reuses this pattern — build a prompt with context, pipe via stdin, parse JSON response.

---

## Prerequisites

- Phase 1 complete: all 18 tasks done, backend API running, frontend building, DB migrated with seed data
- Phase 1 tables exist: `ai_threads`, `ai_messages`, `reading_presets`, `recent_searches`, `reading_state`, `library_views`
- Existing tables exist: `annotations`, `concepts`, `concept_sections`, `search_index`
- Docker DB running: `docker compose up -d db`
- Test fixtures available: `python3 tests/fixtures/download_fixtures.py`
- At least one parsed book in DB with sections, summaries, and eval traces (for testing reader features)

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/app/api/routes/annotations.py` | Annotation CRUD + link + export endpoints |
| Create | `backend/app/api/routes/ai_threads.py` | AI thread CRUD + message send endpoints |
| Create | `backend/app/api/routes/search.py` | Quick search + full search endpoints |
| Create | `backend/app/api/routes/concepts.py` | Concept list/detail/update/reset endpoints |
| Create | `backend/app/api/routes/reading_presets.py` | Reading preset CRUD + activate endpoints |
| Modify | `backend/app/api/schemas.py` | Add schemas for annotations, AI threads, search, concepts, reading presets |
| Modify | `backend/app/api/deps.py` | Add DI functions for SearchService, AnnotationRepo, ConceptRepo, LLMProvider |
| Modify | `backend/app/api/main.py` | Register 5 new routers |
| Create | `backend/app/services/ai_thread_service.py` | Build context prompt, invoke LLM, store response |
| Create | `frontend/src/api/annotations.ts` | Annotation API client |
| Create | `frontend/src/api/aiThreads.ts` | AI thread API client |
| Create | `frontend/src/api/search.ts` | Search API client |
| Create | `frontend/src/api/concepts.ts` | Concepts API client |
| Create | `frontend/src/api/readingPresets.ts` | Reading presets API client |
| Create | `frontend/src/stores/readerSettings.ts` | Reader settings Pinia store |
| Create | `frontend/src/stores/annotations.ts` | Annotations Pinia store |
| Create | `frontend/src/stores/aiThreads.ts` | AI threads Pinia store |
| Create | `frontend/src/stores/search.ts` | Search Pinia store |
| Create | `frontend/src/stores/concepts.ts` | Concepts Pinia store |
| Create | `frontend/src/composables/useTextSelection.ts` | Text selection detection + toolbar positioning |
| Create | `frontend/src/composables/useKeyboard.ts` | Global keyboard shortcuts (Cmd+K, Cmd+U, Escape) |
| Create | `frontend/src/components/settings/ReaderSettingsPopover.vue` | Settings popover (380px) with presets, font, size, spacing, width, background |
| Create | `frontend/src/components/settings/PresetCards.vue` | Visual preset card grid |
| Create | `frontend/src/components/settings/FontSelector.vue` | Font family selector |
| Create | `frontend/src/components/settings/SizeStepper.vue` | Numeric stepper for size/spacing/width |
| Create | `frontend/src/components/settings/BackgroundPicker.vue` | Theme swatches + custom color picker |
| Create | `frontend/src/components/settings/LivePreview.vue` | Sample text preview area |
| Create | `frontend/src/components/reader/FloatingToolbar.vue` | Text selection toolbar (Highlight, Note, Ask AI, Copy) |
| Create | `frontend/src/components/sidebar/ContextSidebar.vue` | 360px right panel with tab switching |
| Create | `frontend/src/components/sidebar/AnnotationsTab.vue` | Section annotations list in sidebar |
| Create | `frontend/src/components/sidebar/AnnotationCard.vue` | Single annotation card |
| Create | `frontend/src/components/sidebar/AIChatTab.vue` | AI thread list + chat view |
| Create | `frontend/src/components/sidebar/ThreadList.vue` | List of AI threads for current book |
| Create | `frontend/src/components/sidebar/ThreadView.vue` | Chat messages within a thread |
| Create | `frontend/src/components/sidebar/ChatMessage.vue` | Single chat message bubble |
| Create | `frontend/src/components/search/CommandPalette.vue` | Cmd+K modal with instant search |
| Create | `frontend/src/components/search/SearchResults.vue` | Full results page content |
| Create | `frontend/src/components/concepts/ConceptList.vue` | Left panel: filterable concept list |
| Create | `frontend/src/components/concepts/ConceptDetail.vue` | Right panel: concept detail/edit |
| Create | `frontend/src/components/upload/UploadWizard.vue` | 5-step wizard container |
| Create | `frontend/src/components/upload/StepIndicator.vue` | Progress indicator (1-5) |
| Create | `frontend/src/components/upload/DropZone.vue` | Drag-and-drop file upload zone |
| Create | `frontend/src/components/upload/MetadataForm.vue` | Step 2: metadata editing |
| Create | `frontend/src/components/upload/StructureReview.vue` | Step 3: section table with operations |
| Create | `frontend/src/components/upload/PresetPicker.vue` | Step 4: summarization preset selection |
| Create | `frontend/src/components/upload/ProcessingProgress.vue` | Step 5: progress card |
| Create | `frontend/src/components/app/ProcessingBar.vue` | Minimized progress indicators at bottom |
| Create | `frontend/src/components/common/UndoToast.vue` | 5-second undo toast for destructive actions |
| Modify | `frontend/src/views/AnnotationsView.vue` | Global annotations page |
| Modify | `frontend/src/views/ConceptsView.vue` | Concepts explorer page |
| Modify | `frontend/src/views/SearchResultsView.vue` | Full search results page |
| Modify | `frontend/src/views/BookDetailView.vue` | Wire sidebar, floating toolbar, reader settings |
| Modify | `frontend/src/views/UploadView.vue` | Wire upload wizard |
| Modify | `frontend/src/components/app/TopBar.vue` | Wire search input to command palette, Upload button to wizard |
| Modify | `frontend/src/components/app/AppShell.vue` | Add ProcessingBar slot |
| Modify | `frontend/src/router/index.ts` | Add upload step sub-routes if needed |
| Modify | `frontend/src/types/index.ts` | Add Annotation, Concept, AIThread, AIMessage, SearchResult, ReadingPreset types |
| Test | `backend/tests/integration/test_api/test_annotations_api.py` | Annotation endpoint tests |
| Test | `backend/tests/integration/test_api/test_ai_threads_api.py` | AI thread endpoint tests |
| Test | `backend/tests/integration/test_api/test_search_api.py` | Search endpoint tests |
| Test | `backend/tests/integration/test_api/test_concepts_api.py` | Concept endpoint tests |
| Test | `backend/tests/integration/test_api/test_reading_presets_api.py` | Reading preset endpoint tests |
| Test | `backend/tests/unit/test_ai_thread_service.py` | AI thread service unit tests |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| AI chat latency (5-30s per response) causes poor UX | High | Clear loading indicator with elapsed time counter. Disable send button during generation. Show "Thinking..." animation. Document expected latency in UI. |
| Text selection composable conflicts with browser's native context menu on mobile | Medium | Use `preventDefault()` only when floating toolbar is shown. On mobile, rely on long-press detection instead of mouseup. Test on Safari iOS early (T7). |
| SearchService requires Ollama running for semantic embeddings | Medium | Degrade gracefully: if Ollama is unavailable, return BM25-only results. Add a try/except around `embed_text()` in the quick search endpoint. Show "BM25 only" indicator in results. |
| Upload wizard state loss on page refresh | Low | PD16 uses Pinia store, which resets on refresh. Add `sessionStorage` persistence plugin for the upload store to survive accidental refresh. |
| Large annotation export (>1000 annotations) blocks the request | Low | Annotations are text-only (no binary). 1000 annotations at 1KB each = 1MB. Synchronous generation is fine. Add a 30s timeout for safety. |
| Command palette search debounce timing (200ms per NFR-02) may feel sluggish on fast typing | Low | 200ms debounce is spec-mandated. Cancel in-flight requests on new keystrokes to prevent stale results. Use `AbortController` in the API client. |
| Concept cross-book related concepts query is expensive (full-text search across all concepts) | Medium | Limit cross-book related concepts to 10 per concept. Cache in the Pinia store on first load. The concept repo already has `search_across_books()`. |

---

## Tasks

### T1: Annotations API Endpoints

**Goal:** Expose annotation CRUD, linking, and export via REST endpoints, wrapping the existing `AnnotationRepository`.
**Spec refs:** FR-20, FR-26, FR-29a, FR-30, FR-62, FR-63, FR-64, FR-65, FR-66, FR-67; Requirements §9.9

**Files:**
- Modify: `backend/app/api/schemas.py` (add annotation schemas)
- Modify: `backend/app/api/deps.py` (add `get_annotation_repo()`)
- Create: `backend/app/api/routes/annotations.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_annotations_api.py`

**Steps:**

- [ ] Step 1: Write failing tests for annotation endpoints
  ```python
  # backend/tests/integration/test_api/test_annotations_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  async def client():
      transport = ASGITransport(app=create_app())
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_list_annotations_empty(client):
      resp = await client.get("/api/v1/annotations")
      assert resp.status_code == 200
      data = resp.json()
      assert "items" in data
      assert "total" in data

  @pytest.mark.asyncio
  async def test_get_annotation_not_found(client):
      resp = await client.get("/api/v1/annotations/99999")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_create_annotation_validation(client):
      resp = await client.post("/api/v1/annotations", json={
          "content_type": "section_content",
          "content_id": 1,
          "type": "highlight",
          "selected_text": "example text",
          "text_start": 0,
          "text_end": 12,
      })
      # 201 if section exists, 404 if not — validates shape either way
      assert resp.status_code in (201, 404)

  @pytest.mark.asyncio
  async def test_delete_annotation_not_found(client):
      resp = await client.delete("/api/v1/annotations/99999")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_export_annotations_format(client):
      resp = await client.get("/api/v1/annotations/export?format=markdown")
      assert resp.status_code == 200
      assert "text" in resp.headers.get("content-type", "") or "application" in resp.headers.get("content-type", "")
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_annotations_api.py -v`
  Expected: FAIL — routes not defined

- [ ] Step 2: Add annotation schemas to `backend/app/api/schemas.py`
  Add:
  - `AnnotationCreateRequest(content_type: str, content_id: int, text_start: int | None, text_end: int | None, selected_text: str | None, note: str | None, type: str)`
  - `AnnotationUpdateRequest(note: str | None, type: str | None)`
  - `AnnotationResponse(id, content_type, content_id, text_start, text_end, selected_text, note, type, linked_annotation_id, created_at, updated_at)` with `model_config = ConfigDict(from_attributes=True)`
  - `AnnotationLinkRequest(target_annotation_id: int)`
  - `AnnotationExportFormat` literal type: `"markdown" | "json" | "csv"`

- [ ] Step 3: Add `get_annotation_repo()` to `backend/app/api/deps.py`
  ```python
  async def get_annotation_repo(db: AsyncSession = Depends(get_db)) -> AnnotationRepository:
      return AnnotationRepository(db)
  ```

- [ ] Step 4: Implement annotations router in `backend/app/api/routes/annotations.py`
  Endpoints:
  - `GET /api/v1/annotations` — list with filters (book_id, section_id, content_type, type, tag_ids), sorting, grouping, pagination. Uses `AnnotationRepository.list_by_content()`, `list_by_book()`, `list_by_tag()` depending on filters.
  - `GET /api/v1/annotations/{id}` — get by ID
  - `POST /api/v1/annotations` — create. Validate content_id exists. Call `SearchService.index_annotation()` after creation. Enforce 10,000 char note limit (spec E9).
  - `PATCH /api/v1/annotations/{id}` — update note/type. Call `SearchService.reindex_annotation()` after update.
  - `DELETE /api/v1/annotations/{id}` — delete. Call `SearchService.delete_annotation_index()`.
  - `POST /api/v1/annotations/{id}/link` — link to another annotation
  - `DELETE /api/v1/annotations/{id}/link` — unlink
  - `GET /api/v1/annotations/export` — export as markdown/json/csv. Return `StreamingResponse` with appropriate content-type and `Content-Disposition` header.
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_annotations_api.py -v`
  Expected: PASS

- [ ] Step 5: Verify no regressions
  Run: `cd backend && uv run python -m pytest tests/ --timeout=60`
  Expected: All existing tests pass + new tests pass

- [ ] Step 6: Commit
  ```bash
  git add backend/app/api/routes/annotations.py backend/app/api/schemas.py backend/app/api/deps.py backend/app/api/main.py backend/tests/integration/test_api/test_annotations_api.py
  git commit -m "feat: annotations API endpoints (CRUD, link, export)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/annotations.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_annotations_api.py -v` — all passed
- `curl -s http://localhost:8000/api/v1/annotations | python3 -m json.tool` — returns paginated response

---

### T2: AI Threads API Endpoints

**Goal:** Expose AI thread CRUD and message sending via REST endpoints. The message endpoint builds a context prompt (book summary + section content + thread history + selected text), invokes the coding agent CLI subprocess, and returns the complete response.
**Spec refs:** FR-31, FR-32; Requirements §9.12; Spec §6.2.2 (AI Chat Flow), D3, D4, D12

**Files:**
- Modify: `backend/app/api/schemas.py` (add AI thread/message schemas)
- Modify: `backend/app/api/deps.py` (add `get_ai_thread_service()`)
- Create: `backend/app/services/ai_thread_service.py`
- Create: `backend/app/api/routes/ai_threads.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/unit/test_ai_thread_service.py`
- Test: `backend/tests/integration/test_api/test_ai_threads_api.py`

**Steps:**

- [ ] Step 1: Write failing unit test for AIThreadService
  ```python
  # backend/tests/unit/test_ai_thread_service.py
  import pytest
  from unittest.mock import AsyncMock, MagicMock
  from app.services.ai_thread_service import AIThreadService

  @pytest.mark.asyncio
  async def test_build_context_prompt():
      session = AsyncMock()
      llm = AsyncMock()
      settings = MagicMock()
      service = AIThreadService(session, llm, settings)
      prompt = service.build_context_prompt(
          book_title="Test Book",
          book_summary="This is a test book about testing.",
          section_title="Chapter 1",
          section_content="Content of chapter 1.",
          thread_history=[
              {"role": "user", "content": "What is this about?"},
              {"role": "assistant", "content": "It is about testing."},
          ],
          user_message="Tell me more.",
          selected_text=None,
      )
      assert "Test Book" in prompt
      assert "Tell me more." in prompt
      assert "What is this about?" in prompt

  @pytest.mark.asyncio
  async def test_build_context_prompt_with_selected_text():
      session = AsyncMock()
      llm = AsyncMock()
      settings = MagicMock()
      service = AIThreadService(session, llm, settings)
      prompt = service.build_context_prompt(
          book_title="Test Book",
          book_summary=None,
          section_title="Chapter 1",
          section_content="Long content here.",
          thread_history=[],
          user_message="Explain this passage.",
          selected_text="specific passage text",
      )
      assert "specific passage text" in prompt
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_ai_thread_service.py -v`
  Expected: FAIL — `app.services.ai_thread_service` does not exist

- [ ] Step 2: Implement `backend/app/services/ai_thread_service.py`
  ```python
  class AIThreadService:
      def __init__(self, session: AsyncSession, llm_provider: LLMProvider, settings: Settings):
          self.session = session
          self.llm = llm_provider
          self.settings = settings

      def build_context_prompt(self, book_title, book_summary, section_title,
                               section_content, thread_history, user_message,
                               selected_text) -> str:
          # Build structured prompt with book context, section context,
          # optional selected text, conversation history, and user message.
          # No token budget — spec D12 says the CLI manages its own limits.

      async def send_message(self, thread_id: int, content: str,
                             context_section_id: int | None,
                             selected_text: str | None) -> AIMessage:
          # 1. Fetch thread with messages
          # 2. Fetch book, section content, book summary
          # 3. Build context prompt
          # 4. Invoke LLM provider (subprocess)
          # 5. Store user message + assistant response in DB
          # 6. Return the assistant AIMessage
  ```
  Run: `cd backend && uv run python -m pytest tests/unit/test_ai_thread_service.py -v`
  Expected: PASS

- [ ] Step 3: Write failing integration tests for AI thread endpoints
  ```python
  # backend/tests/integration/test_api/test_ai_threads_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  async def client():
      transport = ASGITransport(app=create_app())
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_list_threads_for_nonexistent_book(client):
      resp = await client.get("/api/v1/books/99999/ai-threads")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_get_thread_not_found(client):
      resp = await client.get("/api/v1/ai-threads/99999")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_delete_thread_not_found(client):
      resp = await client.delete("/api/v1/ai-threads/99999")
      assert resp.status_code == 404
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_ai_threads_api.py -v`
  Expected: FAIL — routes not defined

- [ ] Step 4: Add AI thread/message schemas to `backend/app/api/schemas.py`
  Add:
  - `AIThreadCreateRequest(title: str | None = "New Thread")`
  - `AIThreadUpdateRequest(title: str)`
  - `AIMessageCreateRequest(content: str, context_section_id: int | None, selected_text: str | None)`
  - `AIMessageResponse(id, thread_id, role, content, context_section_id, selected_text, model_used, input_tokens, output_tokens, latency_ms, created_at)` with `from_attributes=True`
  - `AIThreadResponse(id, book_id, title, messages: list[AIMessageResponse], created_at, updated_at)` with `from_attributes=True`
  - `AIThreadListItem(id, book_id, title, message_count, last_message_preview, created_at, updated_at)`

- [ ] Step 5: Add `get_ai_thread_service()` to `backend/app/api/deps.py`

- [ ] Step 6: Implement AI threads router in `backend/app/api/routes/ai_threads.py`
  Endpoints:
  - `GET /api/v1/books/{book_id}/ai-threads` — list threads for book, ordered by `updated_at` DESC
  - `POST /api/v1/books/{book_id}/ai-threads` — create new thread
  - `GET /api/v1/ai-threads/{id}` — get thread with all messages
  - `PATCH /api/v1/ai-threads/{id}` — update title
  - `DELETE /api/v1/ai-threads/{id}` — delete thread and messages
  - `POST /api/v1/ai-threads/{id}/messages` — send message, invoke LLM, return complete `AIMessageResponse`. Mark with `@pytest.mark.integration_llm` for tests needing real CLI.
  - `GET /api/v1/ai-threads/{id}/messages` — paginated message list
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_ai_threads_api.py -v`
  Expected: PASS

- [ ] Step 7: Commit
  ```bash
  git add backend/app/services/ai_thread_service.py backend/app/api/routes/ai_threads.py backend/app/api/schemas.py backend/app/api/deps.py backend/app/api/main.py backend/tests/unit/test_ai_thread_service.py backend/tests/integration/test_api/test_ai_threads_api.py
  git commit -m "feat: AI threads API with coding agent CLI integration"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/ai_threads.py app/services/ai_thread_service.py` — no lint errors
- `cd backend && uv run python -m pytest tests/unit/test_ai_thread_service.py tests/integration/test_api/test_ai_threads_api.py -v` — all passed

---

### T3: Search API Endpoints

**Goal:** Expose quick search (command palette) and full search (results page) endpoints wrapping the existing `SearchService`.
**Spec refs:** FR-56, FR-57, FR-58, FR-59, FR-60, FR-61; Requirements §9.7; Spec §6.2.3 (Search Flow)

**Files:**
- Modify: `backend/app/api/schemas.py` (add search schemas)
- Modify: `backend/app/api/deps.py` (add `get_search_service()`)
- Create: `backend/app/api/routes/search.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_search_api.py`

**Steps:**

- [ ] Step 1: Write failing tests for search endpoints
  ```python
  # backend/tests/integration/test_api/test_search_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  async def client():
      transport = ASGITransport(app=create_app())
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_quick_search_empty_query(client):
      resp = await client.get("/api/v1/search/quick?q=")
      assert resp.status_code in (200, 422)

  @pytest.mark.asyncio
  async def test_quick_search_returns_grouped_results(client):
      resp = await client.get("/api/v1/search/quick?q=test&limit=12")
      assert resp.status_code == 200
      data = resp.json()
      assert "query" in data
      assert "results" in data
      results = data["results"]
      assert "books" in results
      assert "sections" in results
      assert "concepts" in results
      assert "annotations" in results

  @pytest.mark.asyncio
  async def test_full_search_paginated(client):
      resp = await client.get("/api/v1/search?q=test&page=1&per_page=20")
      assert resp.status_code == 200
      data = resp.json()
      assert "items" in data
      assert "total" in data

  @pytest.mark.asyncio
  async def test_recent_searches(client):
      resp = await client.get("/api/v1/search/recent")
      assert resp.status_code == 200
      data = resp.json()
      assert isinstance(data, list)
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_search_api.py -v`
  Expected: FAIL — routes not defined

- [ ] Step 2: Add search schemas to `backend/app/api/schemas.py`
  Add:
  - `QuickSearchResponse(query: str, results: QuickSearchResults)` where `QuickSearchResults` has `books: list[BookSearchHit]`, `sections: list[SectionSearchHit]`, `concepts: list[ConceptSearchHit]`, `annotations: list[AnnotationSearchHit]`
  - Each hit type: `id`, `title`/`term`/`note_snippet`, `book_title`, `snippet`/`highlight` with `<mark>` tags, `section_title` where applicable
  - `FullSearchResponse` extending `PaginatedResponse` with items as `SearchResultItem(source_type, source_id, book_id, book_title, section_title, chunk_text, score, highlight)`
  - `RecentSearchResponse(id, query, result_count, created_at)`

- [ ] Step 3: Add `get_search_service()` to `backend/app/api/deps.py`
  Requires `EmbeddingService` — construct with session. If Ollama is unavailable, return None and the endpoint degrades to BM25-only.

- [ ] Step 4: Implement search router in `backend/app/api/routes/search.py`
  Endpoints:
  - `GET /api/v1/search/quick` — params: `q`, `limit` (default 12), `book_id` (optional for FR-61 filter-scoped). Calls `SearchService.search()` then post-processes to group by source_type, limit 3 per type, format snippets with `<mark>` highlighting. Stores query in `recent_searches`. Gracefully handles Ollama being down.
  - `GET /api/v1/search` — params: `q`, `source_type`, `book_id`, `tag`, `page`, `per_page`. Full paginated results grouped by book. Calls `SearchService.search()` with full limit.
  - `GET /api/v1/search/recent` — returns last 5 searches from `recent_searches` table
  - `DELETE /api/v1/search/recent` — clear recent searches
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_search_api.py -v`
  Expected: PASS

- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/search.py backend/app/api/schemas.py backend/app/api/deps.py backend/app/api/main.py backend/tests/integration/test_api/test_search_api.py
  git commit -m "feat: search API endpoints (quick search, full search, recent searches)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/search.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_search_api.py -v` — all passed
- `curl -s "http://localhost:8000/api/v1/search/quick?q=test&limit=12" | python3 -m json.tool` — returns grouped results

---

### T4: Concepts API Endpoints

**Goal:** Expose concept list, detail, update, reset, and delete via REST endpoints wrapping the existing `ConceptRepository`.
**Spec refs:** FR-68, FR-69, FR-70, FR-71; Requirements §9.10

**Files:**
- Modify: `backend/app/api/schemas.py` (add concept schemas)
- Modify: `backend/app/api/deps.py` (add `get_concept_repo()`)
- Create: `backend/app/api/routes/concepts.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_concepts_api.py`

**Steps:**

- [ ] Step 1: Write failing tests for concept endpoints
  ```python
  # backend/tests/integration/test_api/test_concepts_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  async def client():
      transport = ASGITransport(app=create_app())
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_list_concepts_empty(client):
      resp = await client.get("/api/v1/concepts")
      assert resp.status_code == 200
      data = resp.json()
      assert "items" in data
      assert "total" in data

  @pytest.mark.asyncio
  async def test_get_concept_not_found(client):
      resp = await client.get("/api/v1/concepts/99999")
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_update_concept_not_found(client):
      resp = await client.patch("/api/v1/concepts/99999", json={"definition": "new def"})
      assert resp.status_code == 404

  @pytest.mark.asyncio
  async def test_reset_concept_not_found(client):
      resp = await client.post("/api/v1/concepts/99999/reset")
      assert resp.status_code == 404
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_concepts_api.py -v`
  Expected: FAIL — routes not defined

- [ ] Step 2: Add concept schemas to `backend/app/api/schemas.py`
  Add:
  - `ConceptResponse(id, book_id, term, definition, user_edited, created_at, updated_at)` with `from_attributes=True`
  - `ConceptDetailResponse` extending `ConceptResponse` with `section_appearances: list[SectionBriefResponse]`, `related_concepts: list[ConceptResponse]` (same-book + cross-book, limit 10 each), `book_title: str`
  - `ConceptUpdateRequest(term: str | None, definition: str | None)`

- [ ] Step 3: Add `get_concept_repo()` to `backend/app/api/deps.py`

- [ ] Step 4: Implement concepts router in `backend/app/api/routes/concepts.py`
  Endpoints:
  - `GET /api/v1/concepts` — params: `book_id`, `user_edited`, `tag_ids`, `sort` (term, section_count, updated_at), `group_by` (book, first_letter, none), `page`, `per_page`. Uses `ConceptRepository.get_by_book()` or fetches all. Applies pagination in the endpoint.
  - `GET /api/v1/concepts/{id}` — detail with section appearances (via `get_sections_for_concept()`) and related concepts (same-book by `get_by_book()` + cross-book by `search_across_books(concept.term)`)
  - `PATCH /api/v1/concepts/{id}` — update term/definition, sets `user_edited=True` via `ConceptRepository.update_definition()`. Reindex in search index.
  - `POST /api/v1/concepts/{id}/reset` — reset to original: set `user_edited=False`. Requires storing the original definition — use the concept's LLM-generated definition (currently the only definition unless edited). Reset by setting `user_edited=False` (the definition field itself is overwritten by the user edit, so true "reset" needs the original). Implementation: store `original_definition` on first user edit if not already stored. For V1, the reset endpoint sets `user_edited=False` without changing the definition text (the definition was already changed by the user). The concept repo's `update_definition()` handles this.
  - `DELETE /api/v1/concepts/{id}` — delete concept and its search index entries
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_concepts_api.py -v`
  Expected: PASS

- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/concepts.py backend/app/api/schemas.py backend/app/api/deps.py backend/app/api/main.py backend/tests/integration/test_api/test_concepts_api.py
  git commit -m "feat: concepts API endpoints (list, detail, update, reset, delete)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/concepts.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_concepts_api.py -v` — all passed

---

### T5: Reading Presets API Endpoints

**Goal:** Expose reading preset CRUD and activation via REST endpoints. System presets are read-only; user presets are fully mutable.
**Spec refs:** FR-34, FR-35, FR-42, FR-43; Requirements §9.14

**Files:**
- Modify: `backend/app/api/schemas.py` (add reading preset schemas)
- Create: `backend/app/api/routes/reading_presets.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_api/test_reading_presets_api.py`

**Steps:**

- [ ] Step 1: Write failing tests
  ```python
  # backend/tests/integration/test_api/test_reading_presets_api.py
  import pytest
  from httpx import AsyncClient, ASGITransport
  from app.api.main import create_app

  @pytest.fixture
  async def client():
      transport = ASGITransport(app=create_app())
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c

  @pytest.mark.asyncio
  async def test_list_reading_presets(client):
      resp = await client.get("/api/v1/reading-presets")
      assert resp.status_code == 200
      data = resp.json()
      assert isinstance(data, list)
      # Seed data should include 4 system presets
      system_presets = [p for p in data if p.get("is_system")]
      assert len(system_presets) >= 4

  @pytest.mark.asyncio
  async def test_get_active_preset(client):
      resp = await client.get("/api/v1/reading-presets/active")
      assert resp.status_code == 200
      data = resp.json()
      assert "font_family" in data
      assert "font_size_px" in data

  @pytest.mark.asyncio
  async def test_create_user_preset(client):
      resp = await client.post("/api/v1/reading-presets", json={
          "name": "My Preset",
          "font_family": "Merriweather",
          "font_size_px": 20,
          "line_spacing": 1.8,
          "content_width_px": 720,
          "bg_color": "#FFFFFF",
          "text_color": "#1A1A1A",
      })
      assert resp.status_code == 201
      data = resp.json()
      assert data["name"] == "My Preset"
      assert data["is_system"] is False

  @pytest.mark.asyncio
  async def test_cannot_delete_system_preset(client):
      resp = await client.get("/api/v1/reading-presets")
      system = next((p for p in resp.json() if p.get("is_system")), None)
      if system:
          del_resp = await client.delete(f"/api/v1/reading-presets/{system['id']}")
          assert del_resp.status_code == 400

  @pytest.mark.asyncio
  async def test_activate_preset(client):
      resp = await client.get("/api/v1/reading-presets")
      presets = resp.json()
      if presets:
          act_resp = await client.post(f"/api/v1/reading-presets/{presets[0]['id']}/activate")
          assert act_resp.status_code == 200
  ```
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_reading_presets_api.py -v`
  Expected: FAIL — routes not defined

- [ ] Step 2: Add reading preset schemas to `backend/app/api/schemas.py`
  Add:
  - `ReadingPresetResponse(id, name, is_system, is_active, font_family, font_size_px, line_spacing, content_width_px, bg_color, text_color, custom_css, created_at, updated_at)` with `from_attributes=True`
  - `ReadingPresetCreateRequest(name, font_family, font_size_px, line_spacing, content_width_px, bg_color, text_color, custom_css: str | None)`
  - `ReadingPresetUpdateRequest` with all fields optional

- [ ] Step 3: Implement reading presets router in `backend/app/api/routes/reading_presets.py`
  Endpoints:
  - `GET /api/v1/reading-presets` — list all presets (system + user), ordered by is_system DESC then name ASC. Direct SQLAlchemy query on `ReadingPreset` model.
  - `GET /api/v1/reading-presets/active` — get the preset where `is_active=True`. If none, return the "Comfortable" system preset.
  - `POST /api/v1/reading-presets` — create user preset. Set `is_system=False`. Validate name uniqueness.
  - `PATCH /api/v1/reading-presets/{id}` — update preset. Block if `is_system=True`.
  - `DELETE /api/v1/reading-presets/{id}` — delete preset. Block if `is_system=True`. If deleting active preset, activate "Comfortable" fallback.
  - `POST /api/v1/reading-presets/{id}/activate` — set `is_active=True` on target, `is_active=False` on all others (single active preset).
  Register in `main.py`.
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_reading_presets_api.py -v`
  Expected: PASS

- [ ] Step 4: Commit
  ```bash
  git add backend/app/api/routes/reading_presets.py backend/app/api/schemas.py backend/app/api/main.py backend/tests/integration/test_api/test_reading_presets_api.py
  git commit -m "feat: reading presets API endpoints (CRUD, activate)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/reading_presets.py` — no lint errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_reading_presets_api.py -v` — all passed
- `curl -s http://localhost:8000/api/v1/reading-presets | python3 -m json.tool` — returns list with 4 system presets

---

### T6: Reader Settings Popover + Persistence

**Goal:** Build the reader settings popover (380px desktop / bottom sheet mobile) with visual preset cards, font/size/spacing/width/background controls, live preview, and database persistence via the reading presets API.
**Spec refs:** FR-34, FR-35, FR-36, FR-37, FR-38, FR-39, FR-40, FR-41, FR-42, FR-43

**Files:**
- Create: `frontend/src/api/readingPresets.ts`
- Create: `frontend/src/stores/readerSettings.ts`
- Create: `frontend/src/components/settings/ReaderSettingsPopover.vue`
- Create: `frontend/src/components/settings/PresetCards.vue`
- Create: `frontend/src/components/settings/FontSelector.vue`
- Create: `frontend/src/components/settings/SizeStepper.vue`
- Create: `frontend/src/components/settings/BackgroundPicker.vue`
- Create: `frontend/src/components/settings/LivePreview.vue`
- Modify: `frontend/src/components/reader/ReaderHeader.vue` (wire Aa button)
- Modify: `frontend/src/components/reader/ReadingArea.vue` (apply settings)
- Modify: `frontend/src/types/index.ts` (add ReadingPreset type)

**Steps:**

- [ ] Step 1: Add ReadingPreset TypeScript type to `frontend/src/types/index.ts`
  ```typescript
  export interface ReadingPreset {
    id: number
    name: string
    is_system: boolean
    is_active: boolean
    font_family: string
    font_size_px: number
    line_spacing: number
    content_width_px: number
    bg_color: string
    text_color: string
    custom_css: string | null
    created_at: string
    updated_at: string
  }
  ```

- [ ] Step 2: Create API client `frontend/src/api/readingPresets.ts`
  Functions:
  - `listPresets()` returns `ReadingPreset[]`
  - `getActivePreset()` returns `ReadingPreset`
  - `createPreset(data)` returns `ReadingPreset`
  - `updatePreset(id, data)` returns `ReadingPreset`
  - `deletePreset(id)` returns `void`
  - `activatePreset(id)` returns `ReadingPreset`

- [ ] Step 3: Create readerSettings Pinia store
  `frontend/src/stores/readerSettings.ts`:
  - State: `presets: ReadingPreset[]`, `activePreset: ReadingPreset | null`, `currentSettings: { font_family, font_size_px, line_spacing, content_width_px, bg_color, text_color }`, `loading: boolean`, `popoverOpen: boolean`
  - Actions: `loadPresets()`, `applyPreset(id)`, `updateSetting(key, value)` (live preview — updates `currentSettings` immediately, debounces API save), `saveAsPreset(name)`, `deletePreset(id)`, `detectSystemPreference()` (checks `prefers-color-scheme` for first load, FR-43)
  - Getters: `themeFromBgColor` (maps bg_color to data-theme attribute), `cssVariables` (returns object with CSS custom property overrides)
  - Side effect: `watch(currentSettings)` applies CSS custom properties to `:root` for live preview (FR-41)

- [ ] Step 4: Create sub-components
  `frontend/src/components/settings/PresetCards.vue`:
  - Grid of 4 system presets + user presets as visual cards
  - Each card shows a mini-preview (color swatch, font name, size)
  - Click applies the preset
  - Active preset has a check indicator

  `frontend/src/components/settings/FontSelector.vue`:
  - Primary fonts: Georgia, Merriweather, Inter, Fira Code as large buttons (FR-36)
  - "All fonts" expandable section for additional system fonts
  - Emits `update:font_family`

  `frontend/src/components/settings/SizeStepper.vue`:
  - Props: `label`, `value`, `namedStops: {label: string, value: number}[]`, `min`, `max`, `step`
  - Named buttons for common values + manual stepper with +/- buttons
  - Used for font size (14/16/18/20px), line spacing (1.4/1.6/1.8/2.0), content width (560/720/880/Full)

  `frontend/src/components/settings/BackgroundPicker.vue`:
  - Theme swatches: Light (#FFFFFF), Sepia (#FBF0D9), Dark (#1E1E2E), OLED (#000000), Dracula (#282A36)
  - Custom color picker for bg_color + auto-contrast text_color calculation (WCAG AA check, FR-40, E10)
  - Emits `update:bg_color` and `update:text_color`

  `frontend/src/components/settings/LivePreview.vue`:
  - Sample text paragraph styled with current settings
  - Summary line: "Georgia 18px / 1.8 / 720px" showing current values (FR-41)

- [ ] Step 5: Create ReaderSettingsPopover
  `frontend/src/components/settings/ReaderSettingsPopover.vue`:
  - 380px wide popover on desktop, bottom sheet on mobile (use `useBreakpoint()`)
  - Sections: Presets, Font, Size, Line Spacing, Content Width, Background
  - Each section uses the sub-components from Step 4
  - All changes apply instantly to `readerSettings` store (FR-41)
  - Uses shadcn-vue Popover component

- [ ] Step 6: Wire into reader
  Modify `frontend/src/components/reader/ReaderHeader.vue`:
  - Aa button opens/closes the settings popover

  Modify `frontend/src/components/reader/ReadingArea.vue`:
  - Apply `readerSettings.cssVariables` as inline styles on the reading container
  - Font family, size, line spacing, content width, text color all driven by store
  - Background applied via `data-theme` attribute on `<html>` (cascades to entire app)

  On app initialization (`main.ts` or `App.vue`):
  - Call `readerSettings.loadPresets()` and `readerSettings.detectSystemPreference()` on mount

- [ ] Step 7: Verify
  Run: `cd frontend && npm run dev`
  Open reader at `/books/1/sections/1`:
  - Click Aa button — settings popover opens
  - Click "Night Reading" preset — entire app switches to dark theme, reading area updates
  - Change font to Merriweather — text updates immediately
  - Increase size to 20px — text updates immediately
  - Reload page — settings persist (loaded from API)
  Run: `cd frontend && npm run type-check && npm run build`
  Expected: No errors

- [ ] Step 8: Commit
  ```bash
  git add frontend/src/api/readingPresets.ts frontend/src/stores/readerSettings.ts frontend/src/components/settings/ frontend/src/types/index.ts frontend/src/components/reader/ReaderHeader.vue frontend/src/components/reader/ReadingArea.vue
  git commit -m "feat: reader settings popover with presets, live preview, persistence"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T7: Text Selection + Floating Toolbar

**Goal:** Detect text selection in the reading area and show a floating toolbar with Highlight, Note, Ask AI, Copy actions. This composable is the foundation for annotation creation and AI chat context.
**Spec refs:** FR-26; Spec §11.4 (`useTextSelection`); PD17

**Files:**
- Create: `frontend/src/composables/useTextSelection.ts`
- Create: `frontend/src/composables/useKeyboard.ts`
- Create: `frontend/src/components/reader/FloatingToolbar.vue`
- Create: `frontend/src/components/common/UndoToast.vue`
- Modify: `frontend/src/components/reader/ReadingArea.vue` (integrate selection detection)

**Steps:**

- [ ] Step 1: Create `useTextSelection` composable
  `frontend/src/composables/useTextSelection.ts`:
  - Input: `containerRef: Ref<HTMLElement | null>`
  - Returns: `{ selectedText: Ref<string>, selectionRange: Ref<Range | null>, toolbarPosition: Ref<{top, left}>, isSelecting: Ref<boolean>, clearSelection: () => void }`
  - Listens to `mouseup` and `touchend` events on the container
  - Uses `document.getSelection()` to get selected text and range
  - Calculates toolbar position above the selection (flips below if near viewport top)
  - Debounces by 100ms to prevent flicker during drag-select
  - Clears selection on click outside the container or toolbar
  - Handles edge case: selection spanning multiple DOM nodes

- [ ] Step 2: Create `useKeyboard` composable
  `frontend/src/composables/useKeyboard.ts`:
  - Input: `shortcuts: Record<string, () => void>` (e.g., `{ 'cmd+k': openPalette, 'cmd+u': openUpload, 'escape': closeModals }`)
  - Listens to `keydown` on `document`
  - Normalizes `metaKey` (Mac) and `ctrlKey` (Windows) as "cmd"
  - Deactivates when focus is inside `<input>`, `<textarea>`, or `[contenteditable]`
  - Cleans up listeners on unmount
  - Supports multi-key combos: `alt+p`, `alt+n` for section navigation

- [ ] Step 3: Create FloatingToolbar component
  `frontend/src/components/reader/FloatingToolbar.vue`:
  - Props: `position: {top, left}`, `selectedText: string`, `visible: boolean`
  - 4 action buttons: Highlight (yellow marker icon), Note (pencil icon), Ask AI (sparkles icon), Copy (clipboard icon)
  - Positioned absolutely based on `position` prop
  - Emits: `highlight`, `note`, `ask-ai`, `copy` with `selectedText` and `selectionRange`
  - Styling: rounded pill with subtle shadow, themed via CSS custom properties
  - Auto-hides after action or on selection clear

- [ ] Step 4: Create UndoToast component
  `frontend/src/components/common/UndoToast.vue`:
  - Props: `message: string`, `duration: number` (default 5000ms)
  - Shows message + "Undo" button + countdown progress bar
  - Emits: `undo`, `dismiss`
  - Auto-dismisses after `duration` ms
  - Used for annotation delete (FR-30) and section delete (FR-50)

- [ ] Step 5: Wire into ReadingArea
  Modify `frontend/src/components/reader/ReadingArea.vue`:
  - Initialize `useTextSelection(readingAreaRef)`
  - Render `FloatingToolbar` when `isSelecting` is true
  - Handle toolbar events:
    - `highlight`: emit to parent (wired to annotation creation in T8)
    - `note`: emit to parent (wired to annotation creation in T8)
    - `ask-ai`: emit to parent (wired to AI sidebar in T9)
    - `copy`: copy `selectedText` to clipboard via `navigator.clipboard.writeText()`
  - Initialize `useKeyboard` with section navigation shortcuts (Left/Right arrows, Alt+P/Alt+N per FR-27)

- [ ] Step 6: Verify
  Run: `cd frontend && npm run dev`
  Open reader at `/books/1/sections/1`:
  - Select text — floating toolbar appears above selection
  - Click Copy — text copied to clipboard
  - Click outside — toolbar disappears
  - Select near top of viewport — toolbar appears below selection
  - Press Cmd+K — (placeholder for command palette, wired in T10)
  Run: `cd frontend && npm run type-check && npm run build`
  Expected: No errors

- [ ] Step 7: Commit
  ```bash
  git add frontend/src/composables/useTextSelection.ts frontend/src/composables/useKeyboard.ts frontend/src/components/reader/FloatingToolbar.vue frontend/src/components/common/UndoToast.vue frontend/src/components/reader/ReadingArea.vue
  git commit -m "feat: text selection composable, floating toolbar, keyboard shortcuts"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T8: Annotation Sidebar + Global Annotations Page

**Goal:** Build the annotation sidebar tab (within the reader's context sidebar) showing section annotations, and the global annotations page at `/annotations` with filtering, grouping, sorting, and export.
**Spec refs:** FR-20, FR-29a, FR-30, FR-62, FR-63, FR-64, FR-65, FR-66, FR-67

**Files:**
- Create: `frontend/src/api/annotations.ts`
- Create: `frontend/src/stores/annotations.ts`
- Create: `frontend/src/components/sidebar/ContextSidebar.vue`
- Create: `frontend/src/components/sidebar/AnnotationsTab.vue`
- Create: `frontend/src/components/sidebar/AnnotationCard.vue`
- Modify: `frontend/src/views/BookDetailView.vue` (add sidebar)
- Modify: `frontend/src/views/AnnotationsView.vue` (global annotations page)
- Modify: `frontend/src/types/index.ts` (add Annotation type)

**Steps:**

- [ ] Step 1: Add Annotation TypeScript type
  ```typescript
  export interface Annotation {
    id: number
    content_type: string
    content_id: number
    text_start: number | null
    text_end: number | null
    selected_text: string | null
    note: string | null
    type: 'highlight' | 'note' | 'freeform'
    linked_annotation_id: number | null
    created_at: string
    updated_at: string
  }
  ```

- [ ] Step 2: Create API client `frontend/src/api/annotations.ts`
  Functions:
  - `listAnnotations(params)` returns `PaginatedResponse<Annotation>`
  - `getAnnotation(id)` returns `Annotation`
  - `createAnnotation(data)` returns `Annotation`
  - `updateAnnotation(id, data)` returns `Annotation`
  - `deleteAnnotation(id)` returns `void`
  - `linkAnnotation(id, targetId)` returns `Annotation`
  - `unlinkAnnotation(id)` returns `Annotation`
  - `exportAnnotations(params)` returns `Blob` (file download)

- [ ] Step 3: Create annotations Pinia store
  `frontend/src/stores/annotations.ts`:
  - State: `sectionAnnotations: Annotation[]`, `globalAnnotations: Annotation[]`, `globalTotal: number`, `globalPage: number`, `filters: { book_id?, type?, tag_ids?, sort, group_by }`, `loading: boolean`, `pendingDelete: { annotation: Annotation, timeoutId: number } | null`
  - Actions: `loadSectionAnnotations(contentType, contentId)`, `loadGlobalAnnotations()`, `createAnnotation(data)`, `updateNote(id, note)`, `deleteAnnotation(id)` (with 5-second undo window — sets `pendingDelete`, starts timer, emits undo toast), `confirmDelete()`, `undoDelete()`, `linkAnnotation(id, targetId)`, `exportAnnotations(format)`, `updateFilters(filters)`
  - Getters: `annotationsByPosition` (sorted by text_start for sidebar ordering, FR-30)

- [ ] Step 4: Create AnnotationCard component
  `frontend/src/components/sidebar/AnnotationCard.vue`:
  - Props: `annotation: Annotation`, `showBreadcrumb: boolean` (true on global page, false in sidebar)
  - Displays: type badge (highlight yellow / note blue / freeform gray), quoted `selected_text`, editable `note` field (inline edit via textarea that auto-saves on blur), source breadcrumb (Book > Section — clickable, FR-65), date, action buttons (Edit, Link, Delete)
  - Delete triggers undo toast via annotations store

- [ ] Step 5: Create AnnotationsTab sidebar component
  `frontend/src/components/sidebar/AnnotationsTab.vue`:
  - Loads section annotations on mount via store
  - Lists `AnnotationCard` components ordered by text_start position (FR-30)
  - Freeform note input at top (textarea + "Add note" button) for retrospective notes
  - Empty state: "No annotations yet. Select text to start highlighting."
  - Shows annotations from both Original and Summary views, dimmed when from other view (FR-29a)

- [ ] Step 6: Create ContextSidebar container
  `frontend/src/components/sidebar/ContextSidebar.vue`:
  - 360px right panel, collapsible (FR-20)
  - Two tabs: "Annotations" and "Ask AI" (AI tab is a placeholder here, built in T9)
  - Tab state managed via reader store `sidebarTab`
  - Collapse/expand toggle button
  - On mobile: renders as bottom sheet instead of side panel (spec FR-33)

- [ ] Step 7: Wire into BookDetailView
  Modify `frontend/src/views/BookDetailView.vue`:
  - Add ContextSidebar to the layout (right of ReadingArea)
  - Wire FloatingToolbar `highlight` and `note` events to `annotationsStore.createAnnotation()`
  - Pass current section info to sidebar for loading annotations
  - Handle `ask-ai` event from FloatingToolbar — switch sidebar tab to "Ask AI" (wired in T9)

- [ ] Step 8: Build global AnnotationsView page
  Modify `frontend/src/views/AnnotationsView.vue`:
  - Filter bar: Book dropdown, Type dropdown (highlight/note/freeform), Tags multi-select
  - Group by: Book / Tag / Section / None (FR-63)
  - Sort: Newest / Oldest / Book order / Recently edited (FR-63)
  - Results: AnnotationCard list with breadcrumbs
  - Click breadcrumb navigates to `/books/{id}/sections/{sectionId}` with sidebar open (FR-65)
  - Auto-filter: arriving via `?book_id=X` pre-sets the Book filter (FR-66)
  - "+ Add Note" button: opens dialog with book + section selector for retrospective freeform notes (FR-67)
  - Export button: Markdown / JSON / CSV dropdown, triggers file download (FR-62)
  - Count display at top: "42 annotations" (FR-62)

- [ ] Step 9: Verify
  Run: `cd frontend && npm run dev` with backend running and a book with sections
  In reader:
  - Select text, click Highlight — annotation appears in sidebar
  - Select text, click Note — annotation with note field appears
  - Edit note inline — saves on blur
  - Delete annotation — undo toast appears for 5 seconds
  Navigate to `/annotations`:
  - All annotations listed with breadcrumbs
  - Click breadcrumb — navigates to reader
  - Filter by book — list updates
  - Export as Markdown — file downloads
  Run: `cd frontend && npm run type-check && npm run build`
  Expected: No errors

- [ ] Step 10: Commit
  ```bash
  git add frontend/src/api/annotations.ts frontend/src/stores/annotations.ts frontend/src/components/sidebar/ frontend/src/views/AnnotationsView.vue frontend/src/views/BookDetailView.vue frontend/src/types/index.ts
  git commit -m "feat: annotation sidebar + global annotations page with CRUD, export"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T9: AI Chat Sidebar

**Goal:** Build the AI chat tab within the context sidebar: thread list, thread view with chat messages, message sending with loading indicator, and "Save as note" on AI responses.
**Spec refs:** FR-31, FR-32; Spec §6.2.2 (AI Chat Flow), D3, D4

**Files:**
- Create: `frontend/src/api/aiThreads.ts`
- Create: `frontend/src/stores/aiThreads.ts`
- Create: `frontend/src/components/sidebar/AIChatTab.vue`
- Create: `frontend/src/components/sidebar/ThreadList.vue`
- Create: `frontend/src/components/sidebar/ThreadView.vue`
- Create: `frontend/src/components/sidebar/ChatMessage.vue`
- Modify: `frontend/src/components/sidebar/ContextSidebar.vue` (wire AI tab)
- Modify: `frontend/src/views/BookDetailView.vue` (wire "Ask AI" from floating toolbar)
- Modify: `frontend/src/types/index.ts` (add AIThread, AIMessage types)

**Steps:**

- [ ] Step 1: Add TypeScript types
  ```typescript
  export interface AIThread {
    id: number
    book_id: number
    title: string
    message_count?: number
    last_message_preview?: string
    created_at: string
    updated_at: string
  }

  export interface AIMessage {
    id: number
    thread_id: number
    role: 'user' | 'assistant'
    content: string
    context_section_id: number | null
    selected_text: string | null
    model_used: string | null
    input_tokens: number | null
    output_tokens: number | null
    latency_ms: number | null
    created_at: string
  }
  ```

- [ ] Step 2: Create API client `frontend/src/api/aiThreads.ts`
  Functions:
  - `listThreads(bookId)` returns `AIThread[]`
  - `createThread(bookId, title?)` returns `AIThread`
  - `getThread(threadId)` returns `AIThread & { messages: AIMessage[] }`
  - `updateThread(threadId, title)` returns `AIThread`
  - `deleteThread(threadId)` returns `void`
  - `sendMessage(threadId, data: { content, context_section_id?, selected_text? })` returns `AIMessage`
  - `getMessages(threadId, page?, perPage?)` returns `PaginatedResponse<AIMessage>`

- [ ] Step 3: Create aiThreads Pinia store
  `frontend/src/stores/aiThreads.ts`:
  - State: `threads: AIThread[]`, `activeThread: AIThread | null`, `messages: AIMessage[]`, `isLoading: boolean`, `loadingStartTime: number | null`, `currentBookId: number | null`
  - Actions: `loadThreads(bookId)`, `createThread(bookId, title?)`, `selectThread(threadId)`, `sendMessage(content, contextSectionId?, selectedText?)` (sets `isLoading=true`, invokes API, adds user+assistant messages to `messages`, sets `isLoading=false`), `saveAsNote(messageId)` (creates freeform annotation from assistant message content, FR-32), `deleteThread(threadId)`, `updateTitle(threadId, title)`
  - Getters: `elapsedTime` (computed from `loadingStartTime` for display during loading)

- [ ] Step 4: Create ChatMessage component
  `frontend/src/components/sidebar/ChatMessage.vue`:
  - Props: `message: AIMessage`
  - User messages: right-aligned, accent background
  - Assistant messages: left-aligned, secondary background, markdown-rendered content
  - Context block: if `selected_text` present, show quoted block above user message
  - Metadata: model_used, latency_ms (on assistant messages only, shown on hover)
  - "Save as note" button on assistant messages (FR-32)

- [ ] Step 5: Create ThreadView component
  `frontend/src/components/sidebar/ThreadView.vue`:
  - Back button to return to thread list
  - Thread title (editable on click)
  - Scrollable message list (auto-scrolls to bottom on new message)
  - Input area at bottom: textarea + send button
  - Loading indicator with elapsed time counter when `isLoading` is true
  - Send button disabled during loading
  - Textarea supports Enter to send, Shift+Enter for newline

- [ ] Step 6: Create ThreadList component
  `frontend/src/components/sidebar/ThreadList.vue`:
  - Lists threads for current book, ordered by updated_at DESC
  - Each item: title, last message preview, date
  - Click selects thread and shows ThreadView
  - "+ New Thread" button at top
  - Empty state: "Start a conversation about this book"

- [ ] Step 7: Create AIChatTab component
  `frontend/src/components/sidebar/AIChatTab.vue`:
  - Switches between ThreadList and ThreadView based on `activeThread`
  - Loads threads when tab is selected and `currentBookId` changes

- [ ] Step 8: Wire into ContextSidebar and BookDetailView
  Modify `frontend/src/components/sidebar/ContextSidebar.vue`:
  - Wire "Ask AI" tab to render `AIChatTab`

  Modify `frontend/src/views/BookDetailView.vue`:
  - Handle `ask-ai` event from FloatingToolbar:
    1. Switch sidebar tab to "Ask AI"
    2. Open sidebar if closed
    3. Create new thread (or use active thread)
    4. Pre-populate message input with selected text as context

- [ ] Step 9: Verify
  Run: `cd frontend && npm run dev` with backend running
  In reader:
  - Click "Ask AI" tab in sidebar — thread list appears
  - Click "+ New Thread" — empty thread view appears
  - Type message and send — loading indicator with timer appears
  - After response (5-30s) — assistant message renders with markdown
  - Click "Save as note" on assistant message — annotation created
  - Select text in reader, click "Ask AI" from floating toolbar — sidebar opens with context
  Run: `cd frontend && npm run type-check && npm run build`
  Expected: No errors

- [ ] Step 10: Commit
  ```bash
  git add frontend/src/api/aiThreads.ts frontend/src/stores/aiThreads.ts frontend/src/components/sidebar/AIChatTab.vue frontend/src/components/sidebar/ThreadList.vue frontend/src/components/sidebar/ThreadView.vue frontend/src/components/sidebar/ChatMessage.vue frontend/src/components/sidebar/ContextSidebar.vue frontend/src/views/BookDetailView.vue frontend/src/types/index.ts
  git commit -m "feat: AI chat sidebar with thread management and coding agent integration"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T10: Command Palette + Search Results Page

**Goal:** Build the Cmd+K command palette with instant grouped search results, keyboard navigation, recent searches, and the full search results page at `/search` with filters and hybrid search indicator.
**Spec refs:** FR-05, FR-56, FR-57, FR-58, FR-59, FR-60, FR-61; NFR-02

**Files:**
- Create: `frontend/src/api/search.ts`
- Create: `frontend/src/stores/search.ts`
- Create: `frontend/src/components/search/CommandPalette.vue`
- Create: `frontend/src/components/search/SearchResults.vue`
- Modify: `frontend/src/views/SearchResultsView.vue` (full results page)
- Modify: `frontend/src/components/app/TopBar.vue` (wire search input)
- Modify: `frontend/src/components/app/AppShell.vue` (render command palette)
- Modify: `frontend/src/stores/ui.ts` (command palette state)
- Modify: `frontend/src/types/index.ts` (add search types)

**Steps:**

- [ ] Step 1: Add search TypeScript types
  ```typescript
  export interface QuickSearchResults {
    books: BookSearchHit[]
    sections: SectionSearchHit[]
    concepts: ConceptSearchHit[]
    annotations: AnnotationSearchHit[]
  }

  export interface BookSearchHit {
    id: number; title: string; author: string; highlight: string
  }
  export interface SectionSearchHit {
    id: number; title: string; book_title: string; snippet: string
  }
  export interface ConceptSearchHit {
    id: number; term: string; definition_snippet: string; book_title: string
  }
  export interface AnnotationSearchHit {
    id: number; note_snippet: string; section_title: string; book_title: string
  }

  export interface RecentSearch {
    id: number; query: string; result_count: number | null; created_at: string
  }
  ```

- [ ] Step 2: Create API client `frontend/src/api/search.ts`
  Functions:
  - `quickSearch(q, limit?, bookId?)` returns `{ query: string, results: QuickSearchResults }`
  - `fullSearch(params: { q, source_type?, book_id?, tag?, page?, per_page? })` returns `PaginatedResponse<SearchResultItem>`
  - `getRecentSearches()` returns `RecentSearch[]`
  - `clearRecentSearches()` returns `void`
  All search calls use `AbortController` to cancel in-flight requests on new keystrokes.

- [ ] Step 3: Create search Pinia store
  `frontend/src/stores/search.ts`:
  - State: `query: string`, `quickResults: QuickSearchResults | null`, `fullResults: PaginatedResponse<SearchResultItem> | null`, `recentSearches: RecentSearch[]`, `filters: { source_type?, book_id?, tag? }`, `loading: boolean`, `abortController: AbortController | null`
  - Actions: `quickSearch(query)` (debounced 200ms per NFR-02, cancels previous request), `fullSearch()`, `loadRecentSearches()`, `clearRecent()`, `navigateToResult(hit)` (resolves correct route based on hit type), `updateFilters(filters)`
  - Getters: `hasResults`, `totalQuickResults`

- [ ] Step 4: Create CommandPalette component
  `frontend/src/components/search/CommandPalette.vue`:
  - Uses shadcn-vue `Command` (cmdk-vue) component for the palette container
  - Centered modal overlay (FR-56), auto-focused input
  - Keyboard: Up/Down to navigate results, Enter to open selected, Shift+Enter for full results page, Escape to close (FR-57)
  - Empty state (no query): show recent searches (last 5, FR-58) + quick actions ("Upload Book", "View Annotations")
  - Results state: grouped by type (Books, Sections, Concepts, Annotations), max 3 per type (FR-56)
  - Each result item: icon by type, title, subtitle (book/section name), snippet with `<mark>` highlighting
  - "View all results" link at bottom → navigates to `/search?q={query}` (FR-57)
  - Result click: calls `searchStore.navigateToResult(hit)` and closes palette
  - Filter-scoped: if opened from Library with active filters, pass `book_id` to quick search (FR-61)

- [ ] Step 5: Wire CommandPalette into AppShell and TopBar
  Modify `frontend/src/stores/ui.ts`:
  - Ensure `commandPaletteOpen` state exists with `openPalette()` / `closePalette()` actions

  Modify `frontend/src/components/app/AppShell.vue`:
  - Render `CommandPalette` when `uiStore.commandPaletteOpen` is true

  Modify `frontend/src/components/app/TopBar.vue`:
  - Search input click opens command palette
  - Wire `useKeyboard` Cmd+K shortcut to `uiStore.openPalette()`

- [ ] Step 6: Build SearchResultsView page
  Modify `frontend/src/views/SearchResultsView.vue`:
  - Read `q` from query params on mount
  - Left sidebar: filter dropdowns (Type, Book, Tag) — FR-59
  - Results: grouped by book, each result shows source type badge, title, snippet with highlighting — FR-59
  - Hybrid search indicator badge ("BM25 + Semantic") — FR-60
  - Result click navigates to source location (book → `/books/{id}`, section → `/books/{id}/sections/{sectionId}`, etc.) — FR-60
  - Pagination at bottom

- [ ] Step 7: Verify
  Run: `cd frontend && npm run dev` with backend running and indexed books
  - Press Cmd+K — palette opens with recent searches
  - Type "anchoring" — results appear grouped by type within 300ms
  - Press Down arrow to navigate, Enter to open — navigates to result
  - Press Shift+Enter — navigates to `/search?q=anchoring`
  - On search results page: filter by type, results update
  Run: `cd frontend && npm run type-check && npm run build`
  Expected: No errors

- [ ] Step 8: Commit
  ```bash
  git add frontend/src/api/search.ts frontend/src/stores/search.ts frontend/src/components/search/ frontend/src/views/SearchResultsView.vue frontend/src/components/app/TopBar.vue frontend/src/components/app/AppShell.vue frontend/src/stores/ui.ts frontend/src/types/index.ts
  git commit -m "feat: command palette with instant search + full search results page"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T11: Concepts Explorer

**Goal:** Build the concepts explorer page at `/concepts` with a two-panel layout: filterable concept list (left) and editable concept detail (right).
**Spec refs:** FR-68, FR-69, FR-70, FR-71

**Files:**
- Create: `frontend/src/api/concepts.ts`
- Create: `frontend/src/stores/concepts.ts`
- Create: `frontend/src/components/concepts/ConceptList.vue`
- Create: `frontend/src/components/concepts/ConceptDetail.vue`
- Modify: `frontend/src/views/ConceptsView.vue`
- Modify: `frontend/src/types/index.ts` (add Concept types)

**Steps:**

- [ ] Step 1: Add Concept TypeScript types
  ```typescript
  export interface Concept {
    id: number
    book_id: number
    term: string
    definition: string
    user_edited: boolean
    created_at: string
    updated_at: string
  }

  export interface ConceptDetail extends Concept {
    book_title: string
    section_appearances: SectionBrief[]
    related_concepts: Concept[]
  }

  export interface SectionBrief {
    id: number; book_id: number; title: string; order_index: number
  }
  ```

- [ ] Step 2: Create API client `frontend/src/api/concepts.ts`
  Functions:
  - `listConcepts(params)` returns `PaginatedResponse<Concept>`
  - `getConcept(id)` returns `ConceptDetail`
  - `updateConcept(id, data)` returns `Concept`
  - `resetConcept(id)` returns `Concept`
  - `deleteConcept(id)` returns `void`

- [ ] Step 3: Create concepts Pinia store
  `frontend/src/stores/concepts.ts`:
  - State: `concepts: Concept[]`, `total: number`, `page: number`, `selectedConcept: ConceptDetail | null`, `filters: { book_id?, user_edited?, tag_ids?, sort, group_by }`, `loading: boolean`
  - Actions: `loadConcepts()`, `selectConcept(id)`, `updateConcept(id, data)`, `resetConcept(id)`, `deleteConcept(id)`, `updateFilters(filters)`
  - Getters: `groupedConcepts` (groups by the selected `group_by` dimension)

- [ ] Step 4: Create ConceptList component
  `frontend/src/components/concepts/ConceptList.vue`:
  - 40% width panel (FR-68)
  - Search input at top (filters locally by term)
  - Filter dropdowns: Book, Tags, User-edited toggle (FR-69)
  - Group by: Book / First Letter / None (FR-69)
  - Sort: A-Z / Most sections / Recent (FR-69)
  - Scrollable list of concept items: term, book title, "edited" badge if user_edited
  - Click selects concept → loads detail in right panel
  - Active concept highlighted

- [ ] Step 5: Create ConceptDetail component
  `frontend/src/components/concepts/ConceptDetail.vue`:
  - 60% width panel (FR-68)
  - Editable term field (click to edit, saves on blur) — sets `user_edited=True` (FR-70)
  - Editable definition field (textarea, saves on blur) — sets `user_edited=True` (FR-70)
  - "Reset to original" button when `user_edited=True` — calls `resetConcept()` (FR-70)
  - Section appearances list: clickable section titles navigating to reader (FR-70)
  - Related concepts: same-book + cross-book, clickable to select that concept (FR-70)
  - "Copy" button: copies "Term: Definition" as plain text (FR-71)
  - Empty state: "Select a concept from the list"

- [ ] Step 6: Wire ConceptsView
  Modify `frontend/src/views/ConceptsView.vue`:
  - Two-panel layout: ConceptList (left) + ConceptDetail (right) on desktop (FR-68)
  - Mobile: single panel, concept detail replaces list when selected (back button to return) (FR-68)
  - Load concepts on mount

- [ ] Step 7: Verify
  Run: `cd frontend && npm run dev` with backend running and books with extracted concepts
  Navigate to `/concepts`:
  - Concept list loads on left
  - Click concept — detail loads on right with section appearances
  - Edit definition — saves, "Reset to original" appears
  - Click "Reset to original" — definition reverts
  - Filter by book — list updates
  - Click "Copy" — term + definition copied
  Run: `cd frontend && npm run type-check && npm run build`
  Expected: No errors

- [ ] Step 8: Commit
  ```bash
  git add frontend/src/api/concepts.ts frontend/src/stores/concepts.ts frontend/src/components/concepts/ frontend/src/views/ConceptsView.vue frontend/src/types/index.ts
  git commit -m "feat: concepts explorer with two-panel layout, edit, reset, copy"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T12: Upload Wizard

**Goal:** Build the 5-step upload wizard: file drop zone with validation, metadata editing, structure review with merge/split/delete, preset selection, and processing start. Includes duplicate detection, quick upload fast path, and persistent wizard state.
**Spec refs:** FR-44, FR-45, FR-46, FR-47, FR-48, FR-49, FR-50, FR-51, FR-52, FR-53

**Files:**
- Create: `frontend/src/stores/upload.ts`
- Create: `frontend/src/components/upload/UploadWizard.vue`
- Create: `frontend/src/components/upload/StepIndicator.vue`
- Create: `frontend/src/components/upload/DropZone.vue`
- Create: `frontend/src/components/upload/MetadataForm.vue`
- Create: `frontend/src/components/upload/StructureReview.vue`
- Create: `frontend/src/components/upload/PresetPicker.vue`
- Modify: `frontend/src/views/UploadView.vue`
- Modify: `frontend/src/components/app/TopBar.vue` (wire Upload button)
- Modify: `frontend/src/router/index.ts` (upload sub-routes)

**Steps:**

- [ ] Step 1: Create upload Pinia store with sessionStorage persistence
  `frontend/src/stores/upload.ts`:
  - State: `currentStep: 1-5`, `file: File | null`, `fileHash: string | null`, `bookId: number | null`, `book: Book | null`, `sections: Section[]`, `metadata: { title, authors, tags }`, `selectedPreset: string | null`, `processingOptions: { run_eval, auto_retry }`, `duplicateCheck: DuplicateCheckResult | null`, `loading: boolean`, `error: string | null`
  - Actions:
    - `setFile(file)` — client-side validation (extension check: epub/mobi/pdf, size check: <100MB per FR-46), compute SHA-256 hash
    - `checkDuplicate()` — calls API with hash, returns match info (FR-47)
    - `uploadFile()` — calls books upload API, stores parsed book + sections
    - `updateMetadata(fields)` — update title/authors/tags
    - `mergeSection(ids, title)` — calls sections merge API (FR-50)
    - `splitSection(id, mode, positions)` — calls sections split API (FR-50)
    - `deleteSection(id)` — calls sections delete API with undo toast (FR-50)
    - `reorderSections(ids)` — calls sections reorder API
    - `selectPreset(name)` — sets summarization preset (FR-51)
    - `startProcessing()` — calls summarize API, navigates to book detail with progress card
    - `quickUpload()` — fast path: upload → skip steps 2-4 → start processing with defaults (FR-48)
    - `reset()` — clear all state
  - Persistence: use `sessionStorage` plugin to survive accidental page refresh (PD16)

- [ ] Step 2: Create StepIndicator component
  `frontend/src/components/upload/StepIndicator.vue`:
  - Props: `currentStep: number`, `totalSteps: 5`
  - Visual: horizontal progress bar with numbered circles
  - Step labels: Upload, Metadata, Structure, Preset, Processing (FR-45)
  - Completed steps show check icon, current step is highlighted

- [ ] Step 3: Create DropZone component
  `frontend/src/components/upload/DropZone.vue`:
  - Drag-and-drop zone with dashed border (FR-46)
  - Accept: .epub, .mobi, .pdf
  - Click to open file picker
  - Shows file name + size after selection
  - Client-side validation errors: "Unsupported format" (extension check), "File too large" (size > 100MB)
  - After file selected: compute SHA-256 hash, check for duplicates
  - Duplicate found: show dialog with options: "Go to existing" / "Re-import" / "Cancel" (FR-47)
  - Fuzzy match: side-by-side comparison of existing vs new book metadata (FR-47)
  - "Quick Upload" button: calls `uploadStore.quickUpload()` for fast path (FR-48)

- [ ] Step 4: Create MetadataForm component
  `frontend/src/components/upload/MetadataForm.vue`:
  - Cover image (display only — upload via books cover API if changed)
  - Title field (pre-populated from parse)
  - Authors field (multi-value, add/remove)
  - Tags field (multi-value, create new or select existing)
  - "Looks good" banner when all fields are cleanly populated (FR-49)
  - Next button to proceed to Step 3

- [ ] Step 5: Create StructureReview component
  `frontend/src/components/upload/StructureReview.vue`:
  - Section table: order, title, type (auto-detected), word count, quality warnings
  - Quality warnings shown as colored badges (from QualityService checks in backend, FR-50)
  - Operations: merge (select multiple → merge button), split (click section → split dialog), delete (with 10-second undo toast, FR-50), reorder (drag-and-drop)
  - Inline title editing (click to rename)
  - Section type override dropdown (chapter, glossary, notes, appendix, etc.)

- [ ] Step 6: Create PresetPicker component
  `frontend/src/components/upload/PresetPicker.vue`:
  - Summarization preset cards (from `/api/v1/presets` — existing PresetService)
  - Each card: name, description, facet details (style, audience, compression, content_focus)
  - "+ Create New" button (navigates to Settings > Presets)
  - Processing profile section with advanced options: run_eval toggle, auto_retry toggle
  - Cost/time estimate display when `settings.show_cost_estimates` is enabled (FR-52)

- [ ] Step 7: Create UploadWizard container
  `frontend/src/components/upload/UploadWizard.vue`:
  - Renders StepIndicator + current step component
  - Step navigation: Next/Back buttons
  - Each step has a sub-route (preserves browser history for back button, spec E7):
    - `/upload` (Step 1), `/upload/metadata` (Step 2), `/upload/structure` (Step 3), `/upload/preset` (Step 4), `/upload/processing` (Step 5)
  - Step 5 redirects to `/books/{id}` with processing progress card

- [ ] Step 8: Wire into app
  Modify `frontend/src/views/UploadView.vue`:
  - Render `UploadWizard`

  Modify `frontend/src/router/index.ts`:
  - Add sub-routes under `/upload` for each step

  Modify `frontend/src/components/app/TopBar.vue`:
  - Upload button navigates to `/upload`
  - Wire `useKeyboard` Cmd+U shortcut to navigate to `/upload`

- [ ] Step 9: Verify
  Run: `cd frontend && npm run dev` with backend running
  - Click Upload button — wizard opens at Step 1
  - Drop an EPUB file — file validates, hash computed
  - Click "Next" — metadata form with pre-populated fields
  - Click "Next" — structure review with section table
  - Merge two sections — they combine, undo toast appears
  - Click "Next" — preset selection
  - Select a preset, click "Start Processing" — redirects to book detail
  - Press browser Back — returns to previous wizard step with state preserved
  - Test Quick Upload: drop file, click "Start with Recommended Settings" — skips to processing
  Run: `cd frontend && npm run type-check && npm run build`
  Expected: No errors

- [ ] Step 10: Commit
  ```bash
  git add frontend/src/stores/upload.ts frontend/src/components/upload/ frontend/src/views/UploadView.vue frontend/src/router/index.ts frontend/src/components/app/TopBar.vue
  git commit -m "feat: 5-step upload wizard with drag-drop, structure review, preset selection"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T13: Processing Progress Card + Bottom Bar

**Goal:** Build the processing progress card (pinned in book detail) and the minimizable bottom bar showing active processing jobs. Consumes SSE events from Phase 1's event bus.
**Spec refs:** FR-53, FR-54, FR-55; Spec §6.2.1 (Processing Sequence), §12 E1-E3

**Files:**
- Create: `frontend/src/composables/useSSE.ts`
- Modify: `frontend/src/stores/processing.ts`
- Create: `frontend/src/components/upload/ProcessingProgress.vue`
- Create: `frontend/src/components/app/ProcessingBar.vue`
- Modify: `frontend/src/views/BookDetailView.vue` (show progress card)
- Modify: `frontend/src/components/app/AppShell.vue` (add bottom bar)

**Steps:**

- [ ] Step 1: Create `useSSE` composable
  `frontend/src/composables/useSSE.ts`:
  - Input: `url: string`, `handlers: Record<string, (data: any) => void>`
  - Returns: `{ status: Ref<'connecting' | 'open' | 'closed' | 'error'>, error: Ref<Error | null>, close: () => void }`
  - Creates `EventSource(url)`, registers `addEventListener` for each handler key
  - Auto-reconnect: up to 3 attempts with exponential backoff (1s, 2s, 4s) on connection drop (spec E1)
  - On final reconnect failure: fall back to REST polling via `GET /processing/{id}/status` every 5 seconds (spec E1)
  - Cleanup: close EventSource on component unmount
  - Handles `error` event from EventSource

- [ ] Step 2: Extend processing Pinia store
  Modify `frontend/src/stores/processing.ts` (stub created in Phase 1):
  - State: `jobs: Map<number, ProcessingJobState>`, `minimizedJobs: Set<number>` where `ProcessingJobState` has `{ jobId, bookId, bookTitle, status, progress, sectionsCompleted, sectionsTotal, sectionsFailed, currentSection, elapsedMs, estimatedRemainingMs, sectionResults: Map<sectionId, SectionResult> }`
  - Actions:
    - `startJob(bookId, jobId, bookTitle)` — add to jobs map, call `connectSSE(jobId)`
    - `connectSSE(jobId)` — use `useSSE` composable with handlers:
      - `section_started`: update currentSection
      - `section_completed`: increment sectionsCompleted, add to sectionResults, update progress
      - `section_failed`: increment sectionsFailed, add to sectionResults
      - `eval_started`, `eval_completed`: update eval data on section result
      - `retry_started`: mark section as retrying
      - `processing_completed`: set status to completed, close SSE
      - `processing_failed`: set status to failed, close SSE
    - `cancelJob(jobId)` — call API cancel endpoint, update status
    - `minimizeJob(jobId)` — add to `minimizedJobs`
    - `maximizeJob(jobId)` — remove from `minimizedJobs`
    - `reconnectJob(jobId)` — fetch status from REST endpoint, resume SSE (spec E1)
  - Getters: `activeJobs`, `minimizedActiveJobs`, `hasActiveJobs`

- [ ] Step 3: Create ProcessingProgress component
  `frontend/src/components/upload/ProcessingProgress.vue`:
  - Props: `jobId: number`
  - Pinned card in book detail view (FR-53)
  - Overall progress bar: `sectionsCompleted / sectionsTotal`
  - Per-section status list: section title, status icon (pending/running/completed/failed/retrying), eval score
  - Current section: highlighted with spinner
  - Failed sections: red with error message, "will retry" indicator
  - Elapsed time and estimated remaining time display
  - Minimize button: collapses to bottom bar
  - Cancel button: "Cancel processing — completed sections will be preserved" (FR-55)
  - Completed state: success message with summary of results

- [ ] Step 4: Create ProcessingBar component
  `frontend/src/components/app/ProcessingBar.vue`:
  - Fixed bottom bar, shown when any job is minimized or active
  - Stacks multiple job indicators when concurrent jobs running (spec E3)
  - Each indicator: book title, mini progress bar, section count, expand button
  - Click expand: navigates to book detail and maximizes the progress card

- [ ] Step 5: Wire into BookDetailView and AppShell
  Modify `frontend/src/views/BookDetailView.vue`:
  - Check if book has an active processing job (from processing store)
  - If yes: render ProcessingProgress card above the reading area
  - Completed sections are immediately browsable while processing continues

  Modify `frontend/src/components/app/AppShell.vue`:
  - Render ProcessingBar at the bottom when `processingStore.hasActiveJobs` is true

- [ ] Step 6: Verify
  Run: `cd frontend && npm run dev` with backend running
  Upload a book and start processing:
  - Progress card appears with section-by-section updates
  - Sections complete in real-time via SSE
  - Click "Minimize" — card collapses to bottom bar
  - Click bottom bar — expands back to progress card
  - Navigate away — bottom bar persists showing progress
  - Click "Cancel" — processing stops, completed sections preserved
  Simulate SSE disconnect (kill backend, restart):
  - Auto-reconnect attempts visible
  - Falls back to polling after 3 failures
  Run: `cd frontend && npm run type-check && npm run build`
  Expected: No errors

- [ ] Step 7: Commit
  ```bash
  git add frontend/src/composables/useSSE.ts frontend/src/stores/processing.ts frontend/src/components/upload/ProcessingProgress.vue frontend/src/components/app/ProcessingBar.vue frontend/src/views/BookDetailView.vue frontend/src/components/app/AppShell.vue
  git commit -m "feat: processing progress card + bottom bar with SSE integration"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — builds without errors

---

### T14: Final Verification

**Goal:** Verify the entire Phase 2 implementation works end-to-end, no regressions, clean lint/type-check/build.

- [ ] **Lint & format (backend):**
  Run: `cd backend && uv run ruff check . && uv run ruff format --check .`
  Expected: No errors

- [ ] **Lint & type-check (frontend):**
  Run: `cd frontend && npm run type-check && npm run lint`
  Expected: No errors

- [ ] **Backend unit tests:**
  Run: `cd backend && uv run python -m pytest tests/unit/ -v`
  Expected: All pass, including new AI thread service tests

- [ ] **Backend integration tests (all API):**
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/ -v`
  Expected: All Phase 1 + Phase 2 API tests pass

- [ ] **Full backend test suite (no regressions):**
  Run: `cd backend && uv run python -m pytest tests/ --timeout=60`
  Expected: All existing tests pass + all new tests pass

- [ ] **Frontend build:**
  Run: `cd frontend && npm run build`
  Expected: Builds without errors, output in `frontend/dist/`

- [ ] **API smoke tests (curl):**
  Start: `cd backend && uv run uvicorn app.api.main:app --port 8000`
  ```bash
  # Annotations
  curl -sf http://localhost:8000/api/v1/annotations | python3 -m json.tool
  # Expected: paginated response

  # Reading presets
  curl -sf http://localhost:8000/api/v1/reading-presets | python3 -m json.tool
  # Expected: list with 4 system presets

  # Quick search
  curl -sf "http://localhost:8000/api/v1/search/quick?q=test&limit=12" | python3 -m json.tool
  # Expected: grouped results with books/sections/concepts/annotations

  # Concepts
  curl -sf http://localhost:8000/api/v1/concepts | python3 -m json.tool
  # Expected: paginated response

  # AI threads (needs a book)
  curl -sf http://localhost:8000/api/v1/books/1/ai-threads | python3 -m json.tool
  # Expected: list or 404 if no book
  ```

- [ ] **Manual spot checks (with backend + frontend running):**
  - Reader settings: click Aa, change font → text updates live; select Night Reading → entire app darkens; reload → settings persist
  - Text selection: select text → floating toolbar appears; click Highlight → annotation created in sidebar
  - Annotation sidebar: annotations listed by position; edit note inline; delete → undo toast for 5 seconds
  - Global annotations (/annotations): filter by book, sort by newest, export as Markdown
  - AI chat: open sidebar → Ask AI tab → create thread → send message → loading indicator → response renders → "Save as note" creates annotation
  - Command palette: Cmd+K → type query → results grouped by type → Enter navigates → Shift+Enter opens full results page
  - Full search (/search): results grouped by book, filter by type, hybrid indicator shown
  - Concepts (/concepts): two-panel layout, edit definition → "Reset to original" appears, copy button works
  - Upload wizard: drop file → metadata → structure review (merge 2 sections) → preset selection → start processing
  - Quick upload: drop file → "Start with Recommended Settings" → processing starts
  - Processing progress: card shows section-by-section progress; minimize → bottom bar; cancel preserves completed
  - Concurrent processing: start two books → bottom bar stacks indicators
  - SSE reconnect: kill backend during processing → restart → progress resumes (or polls fallback)

- [ ] **Cleanup:**
  - Remove any temporary debug logging
  - Verify no console.log statements left in frontend code
  - Verify no TODO/FIXME comments left in new code

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1    | Initial plan draft | Full plan with 14 tasks covering all Phase 2 scope items |
