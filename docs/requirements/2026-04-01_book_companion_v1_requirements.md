# Book Companion - V1 Requirements Document

**Version:** 2.0 (post review loops 1-7)
**Date:** 2026-04-01
**Status:** Draft — Reviewed
**Source Document:** [Initial Thoughts](../2026-04-01_initial_thoughts.txt)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [V1 Scope](#3-v1-scope)
4. [Architecture](#4-architecture)
5. [Book Parsing Pipeline](#5-book-parsing-pipeline)
6. [Summarization Pipeline](#6-summarization-pipeline)
7. [Quality Evaluation (Evals)](#7-quality-evaluation-evals)
8. [Data Model](#8-data-model)
9. [Search](#9-search)
10. [CLI Interface](#10-cli-interface)
11. [Web Interface](#11-web-interface)
12. [Configuration Management](#12-configuration-management)
13. [Project Structure](#13-project-structure)
14. [Tech Stack](#14-tech-stack)
15. [Infrastructure & Deployment](#15-infrastructure--deployment)
16. [External Dependencies & Setup](#16-external-dependencies--setup)
17. [Non-Functional Requirements](#17-non-functional-requirements)
18. [V2+ Deferred Features](#18-v2-deferred-features)
19. [Decision Log](#19-decision-log)
20. [Research Sources](#20-research-sources)
21. [Open Questions & Risks](#21-open-questions--risks)

*Note: Sections 17 includes sub-sections for Security, Testing, Logging, Dev Workflow, Data Export, and Prompt Templates added in review loops.*

---

## 1. Project Overview

Book Companion is a personal tool (web + CLI) that takes a book as input, parses its structure, generates section-level and book-level summaries using LLMs, and provides a searchable, annotatable library for efficient knowledge extraction from non-fiction books.

**Inspiration:** [Eugene Yan's AI Reading Club](https://eugeneyan.com/writing/aireadingclub/)

### Core Value Proposition

- Skim through a book quickly to understand core ideas, frameworks, and key arguments
- Search for concepts across multiple books and find relevant advice
- Go deeper on specific sections using LLMs as a reading companion

### Target User

Single user (personal tool). No authentication or multi-tenancy required.

### Book Types

Mixed non-fiction: business, self-help, technical, academic. Fiction is not supported.

---

## 2. Problem Statement

### User Pain Points

1. **Time**: Reading an entire non-fiction book takes 8-15 hours. Users need a way to extract core ideas in minutes.
2. **Recall**: After reading, key frameworks and insights are forgotten. Users need persistent, searchable summaries.
3. **Cross-referencing**: Concepts appear across multiple books. No easy way to search and connect ideas across a personal library.
4. **Resumption**: After a reading gap, it's hard to resume. Users need "summarize up to this point" capability.
5. **Deep understanding**: Some passages need explanation or discussion beyond what the book provides.

### Glossary

| Term | Definition |
|------|-----------|
| **Book** | A collection of Book Sections around a specific topic by one or more authors. Supported formats: EPUB, MOBI, PDF. |
| **Book Section** | An individual high-level logical component within a book, typically referenced in the table of contents (e.g., chapter, part, appendix). Sections can be nested (Part → Chapter → Sub-section). |
| **Library** | The collection of all books managed by Book Companion, with ability to add tags and filter/search. |
| **Concepts Index** | A per-book structured glossary of key terms, frameworks, and models extracted during summarization. Grows as sections are processed. |
| **Summary** | An LLM-generated abstractive summary of a book section or entire book. Evaluated by binary assertions for quality. |
| **Annotation** | A user-created highlight, note, or cross-reference attached to a specific text span in content or summaries. |
| **Eval Assertion** | A binary pass/fail test that evaluates a specific quality dimension of a generated summary. |

---

## 3. V1 Scope

### In Scope (V1)

- Upload and parse books (EPUB, MOBI, PDF)
- Extract structured content (sections, chapters) with images
- Generate section-level summaries with quality evaluation
- Generate book-level summaries from section summaries
- Browse library, book details, and section content/summaries
- Rich annotations (text highlights + notes + tags + cross-book links)
- Concepts index per book (key terms, frameworks, models extracted during summarization)
- Hybrid search (BM25 + semantic) across all books and concepts
- CLI-first development, then Web + REST APIs
- Dual processing mode: step-by-step (default) and fully async

### Explicitly Deferred (V2+)

- Summarize book until a specific point (resume feature)
- Select text and ask LLM to explain/discuss/summarize in context
- Quizzes and simulations per book section
- Summarization modes (N tweets, diagram-only summaries)
- Framework/template/playbook extraction
- Multi-user support / authentication
- Mobile app

### User Journeys

**Journey 1: New Book Upload (Step-by-Step Mode)**

```
User uploads book file
    → System detects format, checks for duplicates (SHA-256)
    → System parses metadata (title, author) and presents for confirmation
    → System detects structure (TOC → heuristics → LLM fallback)
    → User reviews and confirms/edits section structure
    → System segments content, extracts images, stores in DB
    → System generates embeddings for content + metadata
    → User triggers summarization: `bookcompanion summarize <id>`
    → For each section:
        → System generates summary with cumulative context from prior sections
        → System extracts key concepts/frameworks into concepts index
        → System runs binary assertion battery
        → On critical failure: auto-retry (up to 2x)
        → On non-critical failure: flag for review
    → System generates book-level summary from all section summaries
    → System generates embeddings for summaries
    → Book is ready for browsing
```

**Journey 2: Returning User — Browse & Discover**

```
User lands on Library page
    → Sees grid/list of books with covers, titles, tags
    → Can filter by tag, author, or search
    → Selects a book → Book Detail page
        → Sees book metadata, overall summary, section list with 2-3 line descriptions
        → Can read overall book summary
        → Can select a section → Section Reader
            → Views original content OR section summary (tabbed/side-by-side)
            → Can create annotations (highlight text, add notes, tag)
        → Can view all annotations for the book
        → Can search within the book
```

**Journey 3: Cross-Book Search & Discovery**

```
User enters search query (e.g., "mental models for decision making")
    → System runs hybrid search (BM25 + semantic via pgvector)
    → Results ranked by RRF, showing:
        → Source type labels (book title / section content / summary)
        → Snippet with highlighted match
        → Book + section context
    → User clicks result → navigates to relevant section/summary
```

---

## 4. Architecture

### Approach: Layered Monolith

A single Python package with a clean service layer shared by both CLI and API. No microservices, no message queues.

```
┌─────────────────────────────────────────────────┐
│                   Interfaces                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │  Typer   │  │ FastAPI  │  │  Vue 3 SPA    │ │
│  │   CLI    │  │   API    │  │  (Frontend)   │ │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘ │
│       │              │                │         │
│  ─────┴──────────────┴────────────────┘         │
│                      │                           │
│  ┌───────────────────┴───────────────────────┐  │
│  │              Service Layer                 │  │
│  │  book_service | parser | summarizer |      │  │
│  │  search | embedding | annotation          │  │
│  └───────────────────┬───────────────────────┘  │
│                      │                           │
│  ┌───────────────────┴───────────────────────┐  │
│  │           Data Access Layer                │  │
│  │     SQLAlchemy 2.0 + Alembic migrations   │  │
│  └───────────────────┬───────────────────────┘  │
│                      │                           │
│  ┌───────────────────┴───────────────────────┐  │
│  │        PostgreSQL 16 + pgvector           │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘

External:
  ┌──────────────┐    ┌──────────────┐
  │ Claude Code  │    │   Ollama     │
  │ CLI (local)  │    │  (local)     │
  │ subprocess   │    │  embeddings  │
  └──────────────┘    └──────────────┘
```

### Key Architectural Principles

1. **CLI-first development**: Build all functionality via CLI first, then layer Web + REST APIs on top. The service layer is the single source of business logic.
2. **Thin interfaces**: CLI commands and API routes are thin wrappers that delegate to services.
3. **Async via subprocess**: Claude Code CLI calls use Python's `asyncio` + `subprocess` so summarization doesn't block. The "async mode" runs the same pipeline in a background thread/process.
4. **Configurable LLM**: The LLM provider interface is designed so Claude Code CLI can be swapped for direct API calls, Ollama, or other providers in the future.

---

## 5. Book Parsing Pipeline

### Supported Formats & Libraries

| Format | Library | Notes |
|--------|---------|-------|
| EPUB | `ebooklib` + `markdownify` | Extract TOC from toc.ncx/nav.xhtml, content as HTML, convert to Markdown |
| MOBI | `calibre` (ebook-convert) | Convert MOBI to EPUB first, then process as EPUB |
| PDF | `marker-pdf` | ML-based PDF to Markdown converter. Handles complex layouts, tables, images. Fallback to PyMuPDF for simple text-only PDFs |

### Parsing Flow

```
Upload → Format Detection → [MOBI: Convert to EPUB] → Format-Specific Parser
    → Markdown + Images → Structure Detection → User Review → DB Storage
```

1. **Format detection**: File extension + magic bytes validation
2. **MOBI pre-processing**: Convert to EPUB via Calibre's `ebook-convert` CLI tool
3. **Content extraction**: Parse to Markdown + extract images as binary blobs
4. **Structure detection** (3-tier fallback):
   - **Tier 1 - Embedded TOC**: Parse TOC from EPUB `toc.ncx`/`nav.xhtml` or PDF bookmarks
   - **Tier 2 - Heuristic detection**: Heading patterns (H1/H2/H3), font sizes, page breaks, numbering patterns
   - **Tier 3 - LLM-assisted**: Send first N pages to Claude Code CLI, request chapter/section breakdown
5. **User review** (step-by-step mode only): Present detected structure for confirmation or manual editing
6. **Content segmentation**: Split content into sections based on confirmed structure
7. **Storage**: Save structured content to database

### Image Handling

- Images are extracted from books and stored as PostgreSQL BLOBs in an `images` table
- Each image is linked to its book section
- Markdown content references images via UUID: `![caption](blob:{uuid})`
- API/CLI resolves image references when rendering content
- Image metadata (dimensions, format, caption if available) stored alongside

### Image Captioning via Vision Models

Before summarization, images are processed separately to generate text descriptions:

1. **Extract images** during parsing and store as BLOBs
2. **Generate captions** by sending each image to a multimodal LLM (Claude with vision support via CLI) with context from surrounding text
3. **Inject captions** into the Markdown content as `![Generated caption describing the diagram](blob:{uuid})` — replacing any generic alt text
4. **Include in summarization**: The enriched Markdown (with descriptive image captions) is then passed to the summarization pipeline, ensuring visual content is reflected in summaries

This is particularly important for non-fiction books where diagrams, frameworks, and charts carry significant information. Without this step, summaries would miss visual-only content.

### Title & Metadata Extraction

- Parse title from: file metadata, EPUB OPF, PDF metadata, cover page OCR (fallback)
- Parse author(s) from: file metadata, EPUB OPF, PDF metadata
- User can edit/correct parsed metadata

### Duplicate Detection & Re-upload

- On upload, compute a SHA-256 hash of the file content
- If a book with the same hash already exists, warn the user: "This book already exists (ID: X). Re-import? [y/N]"
- Re-import replaces the parsed content and sections but preserves: annotations, tags, and manual metadata edits
- Summaries are marked as `stale` after re-import and must be regenerated
- Embeddings for re-imported sections are automatically re-generated

### Metadata Editing

Users can edit book metadata and section structure after import:

```bash
bookcompanion edit <book_id> --title "New Title" --author "Name"
bookcompanion edit <book_id> sections   # Interactive section structure editor
```

Cascading effects:
- **Title/author change**: Updates search index entries for book_title
- **Section structure change** (merge/split/reorder): Affected sections' summaries are marked `stale`, annotations are preserved via text anchoring fallback

---

## 6. Summarization Pipeline

### Approach: Hierarchical Map-Reduce

Books are too long for a single LLM context window. Summarization follows a two-phase approach:

```
Phase 1 (Map): Book Sections → Individual Section Summaries
Phase 2 (Reduce): All Section Summaries → Book-Level Summary
```

### Handling Long Sections

Some book sections can exceed the LLM context window (e.g., 50+ page chapters). Strategy:

1. **Estimate token count** for each section (rough: 1 token ≈ 4 characters)
2. **If under context limit** (~150K tokens for Claude Sonnet): summarize directly
3. **If over context limit**: Split into sub-chunks at natural paragraph boundaries, summarize each sub-chunk, then merge sub-chunk summaries into the section summary (recursive map-reduce within a single section)
4. This is transparent to the user — the final output is still one section summary

### Phase 1: Section Summarization

For each book section, invoke Claude Code CLI with a structured prompt requesting:

- **Key concepts** (3-5 bullet points)
- **Detailed summary** (proportional to source, ~20% compression default)
- **Frameworks/models mentioned** (if any)
- **Key quotes** (verbatim notable passages)
- **Image references** (what images depict and their significance in context)

**Cumulative context** (inspired by AI Reading Club's progressive summarization): When summarizing section N, the prompt includes a brief cumulative context from sections 1 to N-1:
- List of key themes identified so far
- Running concepts index (terms and frameworks encountered)
- Brief reference to how the current section connects to prior content

This produces more coherent summaries that reflect the book's narrative arc rather than treating each section in isolation.

### Concepts Index Extraction

During section summarization, the LLM also extracts structured entries for the **concepts index**:

```json
{
  "concepts": [
    {
      "term": "System 1 / System 2",
      "definition": "Two modes of thinking: fast/intuitive (System 1) vs slow/deliberate (System 2)",
      "first_mentioned_section": 3,
      "related_concepts": ["cognitive bias", "heuristics"]
    }
  ]
}
```

The concepts index:
- Grows as each section is processed
- Is stored in a `concepts` table linked to the book
- Supports search and cross-book concept discovery
- Is included in the cumulative context for subsequent section summarization
- Is displayed on the Book Detail page as a "Key Concepts" tab

### Phase 2: Book Summary

Concatenate all section summaries and invoke Claude Code CLI requesting:

- **Book thesis / main argument**
- **Chapter-by-chapter overview** (2-3 lines each)
- **Key frameworks and models** (aggregated from concepts index)
- **Cross-cutting themes**

### Compression Ratios

Based on research (OpenAI's "Recursively Summarizing Books with Human Feedback", Wu et al. 2021; BookSum, Kryscinski et al. 2022):

| Level | Default Ratio | Rationale |
|-------|--------------|-----------|
| Section summary | ~20% of source | Good balance of detail and conciseness for non-fiction |
| Book summary | ~30% of combined section summaries (~5-6% of original) | Comparable to Shortform's depth |

Compression ratios are **configurable per book** via a "detail level" setting:

| Detail Level | Section Ratio | Book Ratio |
|-------------|---------------|------------|
| Brief | ~10% | ~20% |
| Standard (default) | ~20% | ~30% |
| Detailed | ~30% | ~40% |

If a summary fails quality assertions at the current ratio, the system automatically retries with a higher ratio.

### Claude Code CLI Integration

Summaries are generated by invoking Claude Code CLI as a subprocess:

```bash
<cli_alias> -p "<prompt>" --output-format json --model sonnet --json-schema '<schema>'
```

Configuration:
```yaml
llm:
  cli_command: "claude-personal"   # Alias from ~/.zshrc
  model: "sonnet"                   # Default model for summarization
  max_budget_usd: 5.0              # Per-book budget cap
  output_format: "json"
  timeout_seconds: 300             # Per-section timeout
```

The CLI alias is configurable to support multiple Claude Code profiles.

### Prompt Management

- Prompts are stored as versioned template files in `backend/app/services/summarizer/prompts/`
- Each prompt has a version identifier (e.g., `summarize_section_v1.txt`)
- The prompt version used is recorded with each generated summary for traceability
- Enables A/B testing different prompt strategies

---

## 7. Quality Evaluation (Evals)

### Approach: Binary Pass/Fail Assertion Battery

Following best practices from Hamel Husain's evaluation methodology: use **binary pass/fail assertions** rather than rubric-based scoring (1-5 scales). Binary tests are clearer, more actionable, and easier to aggregate.

Each summary is evaluated by a battery of independent assertions, each producing a pass or fail result.

### Assertion Categories

**Faithfulness (Critical — auto-regenerate on failure):**

| Assertion | Description |
|-----------|-------------|
| `no_hallucinated_facts` | Summary does not contain claims absent from source |
| `no_contradictions` | Summary does not contradict any source statements |
| `accurate_quotes` | Any quotes in summary match source verbatim |
| `cross_summary_consistency` | Generate a second summary variant; flag significant divergences between the two as potential hallucination signals (sample-and-compare technique) |

**Completeness (Important — flag for user review on failure):**

| Assertion | Description |
|-----------|-------------|
| `covers_main_argument` | Summary captures the section's primary thesis |
| `covers_key_concepts` | All major concepts from source appear in summary |
| `covers_frameworks` | Any frameworks/models mentioned in source are reflected |
| `covers_examples` | Key supporting examples are referenced |

**Coherence (Advisory — log but don't block):**

| Assertion | Description |
|-----------|-------------|
| `standalone_readable` | Summary makes sense without reading the source |
| `logical_flow` | Ideas follow a logical progression |
| `no_dangling_references` | No references to "above" or "below" that don't resolve |

**Specificity (Important — flag for user review on failure):**

| Assertion | Description |
|-----------|-------------|
| `not_generic` | Summary contains claims and details specific to THIS book/section — not generic enough to apply to any book on the topic |
| `preserves_author_terminology` | Summary uses the author's key terms and vocabulary rather than generic paraphrasing |

**Format (Advisory):**

| Assertion | Description |
|-----------|-------------|
| `has_key_concepts` | Contains a key concepts section |
| `reasonable_length` | Length is within target compression ratio (configurable tolerance) |
| `image_refs_preserved` | Referenced images from source are noted in summary |

### Evaluation Flow

```
Summary Generated
    ├── Run all assertions in parallel (each is a separate LLM call)
    ├── Store results as JSON in summary_eval field
    │
    ├── Any Critical assertion failed?
    │   └── Yes → Auto-regenerate summary (up to 2 retries with adjusted prompt)
    │
    ├── Any Important assertion failed?
    │   └── Yes → Flag for user review (show in CLI/web with failure details)
    │
    └── Advisory failures → Log, display as quality indicators
```

### Eval Development Harness

A CLI command for comparing summarization approaches during development:

```bash
bookcompanion eval compare --book <id> --section <id> --ratios 10,20,30
```

Generates summaries at multiple compression ratios for the same section and displays assertion results side-by-side. This is an on-demand development/tuning tool, not part of the default pipeline.

### Human Evaluation Baseline (Bootstrapping Step)

Per Hamel Husain's methodology, **automated evals must be bootstrapped with human evaluation**:

1. **Before automating anything**: Read 20-30 generated summaries manually and annotate what's good/bad
2. **Build a golden test set**: Curate 10-15 chapters of varying difficulty (short/long, technical/narrative, with/without frameworks) as a fixed eval corpus
3. **Calibrate the LLM judge**: Run automated assertions on the golden set, verify that the judge agrees with your human annotations at >80% agreement rate
4. **Periodic re-validation**: Every 5-10 prompt iterations, manually review a sample to catch judge drift

This is a non-negotiable bootstrapping step — you cannot automate what you haven't defined through human judgment first.

### Pairwise Comparison for Prompt Iteration

When A/B testing different summarization prompts, use **pairwise LLM-judge comparison** rather than scoring each independently:

```bash
bookcompanion eval compare-prompts --book <id> --section <id> --prompt-a v1 --prompt-b v2
```

The judge is asked: "Given the source text, which summary (A or B) is more faithful/complete/specific?" This is more reliable and sensitive than absolute scoring because:
- It eliminates score calibration issues
- Relative judgments are easier than absolute ones
- Smaller quality differences are detectable

### Why Not ROUGE/BERTScore?

Traditional metrics (ROUGE, BERTScore, BLEU) correlate poorly with human judgment for abstractive summaries (see Eugene Yan's analysis). LLM-as-judge with binary assertions is the current best practice for evaluating LLM-generated content.

---

## 8. Data Model

### Entity Relationship Diagram

```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│    authors     │     │  book_authors  │     │     books      │
│                │     │                │     │                │
│ id (PK)       │──M:N│ book_id (FK)   │N:1──│ id (PK)       │
│ name          │     │ author_id (FK) │     │ title          │
│ metadata      │     │ role           │     │ file_data (BLOB)│
│ created_at    │     └────────────────┘     │ file_format    │
└────────────────┘                           │ cover_image    │
                                             │ status         │
                                             │ overall_summary│
                                             │ metadata (JSON)│
                                             │ created_at     │
                                             │ updated_at     │
                                             └────────┬───────┘
                                                      │ 1:N
┌────────────────┐     ┌────────────────┐     ┌───────┴────────┐
│     tags       │     │   taggables    │     │ book_sections  │
│                │     │                │     │                │
│ id (PK)       │──M:N│ tag_id (FK)    │     │ id (PK)       │
│ name (unique) │     │ taggable_type  │     │ book_id (FK)   │
│ color         │     │ taggable_id    │     │ parent_id (FK) │ ← self-referential
│ created_at    │     └────────────────┘     │ title          │
└────────────────┘                           │ order_index    │
                                             │ depth          │
  taggable_type enum:                        │ content_md     │
  - book                                     │ summary_md     │
  - book_section                             │ summary_status │
  - annotation                               │ summary_version│
                                             │ summary_eval   │ ← JSON: assertion results
                                             │ created_at     │
                                             └───────┬────────┘
                                                     │ 1:N
                           ┌─────────────────────────┼─────────────────┐
                           │                         │                 │
                    ┌──────┴───────┐          ┌──────┴──────┐   ┌─────┴──────┐
                    │ annotations  │          │   images    │   │ search_    │
                    │              │          │             │   │ index      │
                    │ id (PK)     │          │ id (PK)    │   │            │
                    │ content_type│          │ section_id  │   │ id (PK)   │
                    │ content_id  │          │ data (BLOB) │   │ source_type│
                    │ text_start  │          │ mime_type   │   │ source_id │
                    │ text_end    │          │ caption     │   │ chunk_text│
                    │ selected_   │          │ created_at  │   │ chunk_idx │
                    │   text      │          └─────────────┘   │ embedding │ ← pgvector
                    │ note        │                             │ tsvector  │ ← BM25
                    │ type        │                             │ created_at│
                    │ linked_     │                             └───────────┘
                    │  anno_id(FK)│ ← cross-book linking
                    │ created_at  │
                    └─────────────┘

  content_type enum:            source_type enum:
  - section_content             - book_title
  - section_summary             - book_summary
  - book_summary                - section_title
                                - section_content
                                - section_summary
                                - concept

┌────────────────────┐     ┌────────────────────┐     ┌─────────────────────┐
│  processing_jobs   │     │     concepts       │     │  concept_sections   │
│                    │     │                    │     │                     │
│ id (PK)           │     │ id (PK)           │──M:N│ concept_id (FK)     │
│ book_id (FK)      │     │ book_id (FK)      │     │ section_id (FK)     │
│ step              │     │ first_section_id   │     └─────────────────────┘
│ status            │     │ term              │
│ progress (JSON)   │     │ definition        │ A concept can appear in multiple
│ error_message     │     │ related_concepts  │ sections. first_section_id tracks
│ started_at        │     │ created_at        │ where it was first introduced.
│ completed_at      │     │ updated_at        │ concept_sections tracks all mentions.
└────────────────────┘     └────────────────────┘
```

### Key Design Decisions

1. **`book_sections.parent_id`**: Self-referential FK enables nested structure (Part → Chapter → Sub-section). `depth` tracks nesting level, `order_index` preserves original book ordering.

2. **Polymorphic annotations**: `content_type` + `content_id` allows annotations on section content, section summaries, or book-level summaries.

3. **Polymorphic tags**: `taggables` junction table with `taggable_type` supports tagging books, sections, and annotations. Extensible without schema changes.

4. **Unified search index**: `search_index` table indexes all searchable content types with both vector embeddings and tsvector for hybrid search.

5. **File storage**: Book files, cover images, and extracted images stored as PostgreSQL BLOBs. Simplifies backup/restore for single-user deployment.

6. **Summary versioning**: `summary_version` tracks which prompt version generated the summary. `summary_eval` stores assertion results as JSON.

7. **Annotation text anchoring**: Character offsets alone are fragile — they break if content is re-parsed or updated. The annotation model uses a **dual anchoring strategy**:
   - **Primary**: `text_start` + `text_end` (character offsets within the content)
   - **Fallback**: `selected_text` (the actual highlighted text, stored verbatim)
   - **Resolution**: On display, first try offsets. If the text at those offsets doesn't match `selected_text`, fall back to fuzzy text search within the section to relocate the annotation. This handles re-parsing scenarios gracefully.

---

## 9. Search

### Hybrid Search: BM25 + Semantic with Reciprocal Rank Fusion

All searchable content is indexed in the `search_index` table with both:
- **`embedding`** (pgvector): Vector for semantic similarity search
- **`tsvector`**: PostgreSQL full-text search (BM25-equivalent keyword matching)

### Indexed Content Types

| Source Type | Content Indexed |
|-------------|----------------|
| `book_title` | Book title + author names |
| `book_summary` | Book-level summary (chunked if long) |
| `section_title` | Section titles |
| `section_content` | Original section content (chunked into ~512-token overlapping segments) |
| `section_summary` | Section summaries (chunked if needed) |
| `concept` | Concept term + definition from concepts index |

### Search Query Flow

```
User Query
    ├── Generate query embedding via Ollama (nomic-embed-text or similar)
    ├── BM25 search: tsvector @@ plainto_tsquery(query) → ranked results
    ├── Semantic search: embedding <=> query_embedding → ranked by cosine similarity
    └── Reciprocal Rank Fusion (RRF): merge and re-rank
         └── Return top-K results with source labels
```

**RRF formula:**
```
RRF_score(doc) = 1/(k + rank_bm25) + 1/(k + rank_semantic)
```
where `k=60` (standard constant).

### Embedding Model

- **Provider**: Ollama (local)
- **Model**: `nomic-embed-text` (768-dim, good quality/performance balance)
- **Chunking**: Overlapping windows of ~512 tokens with 50-token overlap
- **Index**: pgvector HNSW index for approximate nearest neighbor search

### Embedding Index Lifecycle

Embeddings are created and updated at specific trigger points:

| Event | Action |
|-------|--------|
| Book parsed (sections created) | Embed section titles + section content chunks |
| Summary generated | Embed summary chunks, add to search index |
| Summary regenerated | Delete old summary embeddings, create new ones |
| Book re-imported | Delete all embeddings for book, re-embed all content |
| Book deleted | Delete all embeddings for book |
| Book metadata edited (title/author) | Re-embed book_title entry |

Embedding generation is the final step in both the parse and summarize pipelines. The `processing_jobs` table tracks embedding as a distinct step (`step: embed`).

### Search Features

- Global search across all books
- Scoped search within a specific book
- Filter results by source type (title, content, summary)
- Filter by tags or authors

---

## 10. CLI Interface

### Command Structure

Development follows CLI-first approach. All functionality is available via CLI before web.

```bash
# Book management
bookcompanion add <file_path>              # Upload + parse (step-by-step mode)
bookcompanion add <file_path> --async      # Upload + parse + summarize (async)
bookcompanion list                          # List all books
bookcompanion list --tag <tag>              # Filter by tag
bookcompanion list --author <name>          # Filter by author
bookcompanion show <book_id>                # Book details + section list
bookcompanion delete <book_id>              # Remove a book

# Reading & summaries
bookcompanion read <book_id> [section_id]   # Read original content
bookcompanion summary <book_id>             # Book-level summary
bookcompanion summary <book_id> <section_id> # Section summary
bookcompanion summarize <book_id>           # Trigger summarization
bookcompanion summarize <book_id> <section_id> # Re-summarize a section

# Annotations
bookcompanion annotate <book_id> <section_id> --text "..." --note "..."
bookcompanion annotations <book_id>         # List annotations for a book
bookcompanion annotations --tag <tag>       # List by tag

# Search
bookcompanion search "query"                # Hybrid search across all books
bookcompanion search "query" --book <id>    # Search within a book

# Tags & authors
bookcompanion tag <book_id> <tag_name>      # Add tag to book
bookcompanion tags                          # List all tags
bookcompanion authors                       # List all authors

# Concepts index
bookcompanion concepts <book_id>            # Show concepts index for a book
bookcompanion concepts search "term"        # Search concepts across all books

# Processing & evaluation
bookcompanion status <book_id>              # Processing status
bookcompanion eval <book_id> [section_id]   # Show eval results
bookcompanion eval compare --book <id> --section <id> --ratios 10,20,30

# Configuration
bookcompanion config                        # Show current config
bookcompanion config set llm.cli_command "claude-personal"
bookcompanion config set llm.model "sonnet"

# Setup & maintenance
bookcompanion init                          # First-time setup (DB, migrations, dependency check)
bookcompanion backup [--output path]        # Full database backup (pg_dump)
bookcompanion restore <backup_file>         # Restore from backup
bookcompanion backup list                   # List available backups

# Export
bookcompanion export [--format json|markdown] [--output /path/to/dir]
bookcompanion export <book_id> [--format json|markdown]
```

### Step-by-Step Flow Example

```
$ bookcompanion add ~/books/thinking-fast-slow.epub

Parsing "thinking-fast-slow.epub"...
Title: "Thinking, Fast and Slow"
Author(s): Daniel Kahneman
Format: EPUB

Detected structure (12 sections):
  1. Introduction
  2. Part I: Two Systems
    2.1 Chapter 1: The Characters of the Story
    2.2 Chapter 2: Attention and Effort
    ...

Accept this structure? [Y/n/edit]: y

Book saved (ID: 7). 12 sections parsed and stored.
Run `bookcompanion summarize 7` to generate summaries.

$ bookcompanion summarize 7

Summarizing section 1/12: Introduction... done (eval: 13/13 passed)
Summarizing section 2/12: Part I: Two Systems... done (eval: 12/13 passed)
  ⚠ covers_examples: FAIL - consider reviewing
...
Generating book-level summary... done (eval: 13/13 passed)

Summarization complete. Run `bookcompanion summary 7` to read.
```

### CLI Output Formatting

- **Long content** (read, summary commands): Pipe through system pager (`less` or `$PAGER`) with Markdown rendering via `rich` library
- **Tables** (list, search, annotations): Formatted tables via `rich.table`
- **Progress** (summarize, add --async): Rich progress bars with section-level granularity
- **Markdown rendering**: Use `rich.markdown` for terminal Markdown rendering with syntax highlighting for code blocks
- **Output redirection**: All commands support `--format json` for piping to other tools and `--no-pager` to disable paging

---

## 11. Web Interface

### Pages (V1)

| Page | Purpose |
|------|---------|
| Library | Grid/list view of all books with search, tag filters, author filters |
| Book Detail | Book metadata, section list with 2-3 line descriptions, overall summary |
| Section Reader | View original content and/or section summary |
| Annotations | List/filter annotations by tag, book, type |
| Search Results | Unified results showing source type labels |
| Processing Status | Progress of parsing and summarization jobs |

### Design Approach

- Custom design system built with Vue 3 + Tailwind CSS (no component library)
- Full UI/UX design brainstorm with multiple layout approaches will be conducted before implementation
- Responsive design for desktop and tablet (mobile deferred)

### Frontend Architecture

- Vue 3 with Composition API and TypeScript
- Pinia for client-side state management (UI state, user preferences)
- TanStack Query (Vue Query) for server state management (API data caching, deduplication, background refetching)
- Vue Router for navigation
- Axios/fetch for API communication
- Vite for build tooling

**Pinia vs Vue Query split**: Pinia manages client-only state (UI toggles, selected filters, theme). Vue Query manages server-sourced data (book lists, summaries, search results) with automatic caching, staleness tracking, and background refetching. This reduces boilerplate and prevents stale data bugs.

---

## 12. Configuration Management

### Config File Location

Configuration follows the XDG Base Directory Specification:

- **Primary**: `~/.config/bookcompanion/config.yaml`
- **Fallback**: `~/.bookcompanion/config.yaml`
- **Override**: `BOOKCOMPANION_CONFIG` environment variable

### Configuration Schema

```yaml
# ~/.config/bookcompanion/config.yaml

database:
  url: "postgresql://bookcompanion:bookcompanion@localhost:5438/bookcompanion"

llm:
  cli_command: "claude-personal"       # Claude Code CLI alias from ~/.zshrc
  model: "sonnet"                       # Default model for summarization
  max_budget_usd: 5.0                  # Per-book budget cap
  timeout_seconds: 300                 # Per-section timeout
  eval_enabled: true                   # Run binary assertions on summaries
  max_retries: 2                       # Auto-retry on critical eval failures

summarization:
  default_detail_level: "standard"     # brief | standard | detailed
  prompt_version: "v1"                 # Active prompt version
  eval_prompt_version: "v1"            # Active eval prompt version

embedding:
  ollama_url: "http://localhost:11434"
  model: "nomic-embed-text"
  chunk_size: 512                      # Tokens per embedding chunk
  chunk_overlap: 50                    # Token overlap between chunks

search:
  rrf_k: 60                           # RRF constant
  default_limit: 20                   # Default results per query

storage:
  max_file_size_mb: 200               # Maximum book file size
```

### Configuration Loading

1. Load defaults from code (hardcoded sensible defaults)
2. Override with config file values
3. Override with environment variables (prefixed `BOOKCOMPANION_`, e.g., `BOOKCOMPANION_DATABASE__URL`)
4. Override with CLI flags (highest priority)

This is implemented via `pydantic-settings` which supports this cascade natively.

### Database Initialization

First-time setup via CLI:

```bash
# Auto-creates database, runs migrations, pulls embedding model
bookcompanion init

# Or with custom database URL
bookcompanion init --database-url "postgresql://..."
```

The `init` command:
1. Checks if config file exists, creates with defaults if not
2. Connects to Postgres, creates the database if needed
3. Runs all Alembic migrations
4. Verifies Ollama is running and pulls the embedding model if needed
5. Runs a health check

Subsequent runs: `bookcompanion` commands auto-check if migrations are pending and prompt the user.

### Backup & Restore

```bash
# Create a full backup (pg_dump of entire database including BLOBs)
bookcompanion backup [--output /path/to/backup.sql.gz]
# Default: ~/.config/bookcompanion/backups/bookcompanion_YYYY-MM-DD_HHMMSS.sql.gz

# Restore from backup
bookcompanion restore /path/to/backup.sql.gz

# List available backups
bookcompanion backup list
```

---

## 13. Project Structure

```
book-companion/
├── backend/
│   ├── pyproject.toml                  # Python project config (uv)
│   ├── alembic/                        # DB migrations
│   │   ├── alembic.ini
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                   # Settings (pydantic-settings)
│   │   ├── db/
│   │   │   ├── models.py              # SQLAlchemy ORM models
│   │   │   ├── session.py             # DB session management
│   │   │   └── repositories/          # Data access layer
│   │   ├── services/                   # Business logic (shared)
│   │   │   ├── book_service.py
│   │   │   ├── parser/
│   │   │   │   ├── base.py            # Parser interface
│   │   │   │   ├── epub_parser.py
│   │   │   │   ├── pdf_parser.py
│   │   │   │   └── mobi_parser.py
│   │   │   ├── summarizer/
│   │   │   │   ├── base.py            # LLM provider interface
│   │   │   │   ├── claude_cli.py      # Claude Code CLI subprocess
│   │   │   │   ├── prompts/           # Versioned prompt templates
│   │   │   │   └── evaluator.py       # Binary assertion evaluator
│   │   │   ├── search_service.py
│   │   │   ├── embedding_service.py
│   │   │   └── annotation_service.py
│   │   ├── api/                        # FastAPI (thin layer)
│   │   │   ├── main.py
│   │   │   └── routes/
│   │   └── cli/                        # Typer CLI (thin layer)
│   │       ├── main.py
│   │       └── commands/
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── components/                 # Design system components
│   │   ├── composables/               # Vue composables
│   │   ├── stores/                    # Pinia stores
│   │   ├── views/                     # Page-level components
│   │   ├── router/
│   │   └── api/                       # API client layer
│   └── index.html
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── docs/
│   ├── 2026-04-01_initial_thoughts.txt
│   └── requirements/
│       └── v1-requirements.md
├── .gitignore
└── CLAUDE.md
```

---

## 13. Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Backend language** | Python 3.12+ | As specified. Strong ecosystem for NLP/parsing |
| **API framework** | FastAPI | As specified. Async, auto-docs, pydantic integration |
| **CLI framework** | Typer | Type-hint driven CLI built on Click. Auto-generated help, great DX |
| **ORM** | SQLAlchemy 2.0 | Industry standard, async support, mature migration tooling |
| **Migrations** | Alembic | Standard companion to SQLAlchemy |
| **Settings** | pydantic-settings | Env var loading, validation, type safety |
| **Package manager** | uv | Fast, modern Python package manager. Replaces pip+virtualenv |
| **Database** | PostgreSQL 16 | As specified. With pgvector extension for embeddings |
| **Vector search** | pgvector | In-Postgres vector similarity search. No separate vector DB needed |
| **Full-text search** | PostgreSQL tsvector | Built-in BM25-equivalent. No Elasticsearch needed |
| **Embedding model** | Ollama (nomic-embed-text) | Local embeddings via existing Ollama installation |
| **LLM (summarization)** | Claude Code CLI | Subprocess invocation with configurable profile alias |
| **EPUB parsing** | ebooklib + markdownify | Mature EPUB parser + HTML-to-Markdown conversion |
| **PDF parsing** | marker-pdf | ML-based PDF to Markdown. Best quality for complex layouts |
| **MOBI parsing** | Calibre (ebook-convert) | Convert MOBI to EPUB, then process as EPUB |
| **Frontend framework** | Vue 3 (Composition API) | As specified. TypeScript, Pinia, Vue Router |
| **Server state** | TanStack Query (Vue Query) | API data caching, deduplication, background refetching. Reduces Pinia boilerplate for server data. |
| **CSS** | Tailwind CSS | As specified. Utility-first, custom design system |
| **Build tool** | Vite | Fast HMR, Vue 3 native support |
| **CLI output** | rich | Terminal Markdown rendering, tables, progress bars, pager integration |
| **Logging** | structlog | Structured JSON logging with daily rotation |
| **Prompt templates** | Jinja2 | Versioned prompt templates with defined variable contracts |
| **Containerization** | Docker Compose | As specified. Local dev and deployment |

---

## 15. Infrastructure & Deployment

### Docker Compose Configuration

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    ports:
      - "5438:5432"               # Avoid conflict with host Postgres (5432) and other projects
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: bookcompanion
      POSTGRES_USER: bookcompanion
      POSTGRES_PASSWORD: bookcompanion

  backend:
    build: ./backend
    depends_on: [db]
    ports:
      - "8002:8000"               # Avoid conflict with port 8000 (in use)
    volumes:
      - ./backend:/app
    environment:
      DATABASE_URL: postgresql://bookcompanion:bookcompanion@db:5432/bookcompanion
      OLLAMA_URL: http://host.docker.internal:11434   # Use host Ollama

  frontend:
    build: ./frontend
    depends_on: [backend]
    ports:
      - "3010:3000"               # Avoid conflict with ports 3000-3007 (in use)
    volumes:
      - ./frontend:/app
```

**Note:** Ollama runs on the host machine (already installed at port 11434). No separate container needed. Backend connects via `host.docker.internal`.

### Port Assignments

| Service | Host Port | Container Port | Rationale |
|---------|-----------|----------------|-----------|
| PostgreSQL | 5438 | 5432 | 5432 (host PG), 55432 (other project), 5437 (porter) taken |
| Backend API | 8002 | 8000 | 8000 (other project), 8003 (porter) taken |
| Frontend | 3010 | 3000 | 3000-3007 all taken by other projects |
| Ollama | N/A | N/A | Uses host Ollama at 11434 |

### Deployment Modes

- **Local (primary)**: `docker-compose up` — everything runs locally
- **Cloud-ready**: Docker Compose structure is compatible with deployment to any VPS or cloud provider. Environment variables externalized for easy configuration.

---

## 16. External Dependencies & Setup

### System Dependencies

| Dependency | Required For | Installation | Notes |
|-----------|-------------|-------------|-------|
| **Docker + Docker Compose** | Running the full stack | [docs.docker.com](https://docs.docker.com) | Required for all users |
| **Ollama** | Local embeddings | [ollama.com](https://ollama.com) | Already running on host. Only the CLI/server is needed, not a GUI. |
| **Calibre (ebook-convert)** | MOBI format support | `brew install calibre` or install CLI tools only | Only the `ebook-convert` CLI tool is needed, not the full Calibre GUI. On macOS: `brew install --cask calibre` installs both. On Linux: `apt install calibre` or download CLI-only from calibre website. |
| **Claude Code CLI** | LLM summarization | [claude.ai/code](https://claude.ai/code) | Must be configured with a valid profile. The alias (e.g., `claude-personal`) must be resolvable from the shell. |

### Dependency Verification

The `bookcompanion init` command verifies all dependencies:

```bash
$ bookcompanion init

Checking dependencies...
  ✓ Docker: v27.1.0
  ✓ Docker Compose: v2.29.0
  ✓ Ollama: running at http://localhost:11434
  ✓ ebook-convert: Calibre 7.x
  ✓ Claude Code CLI: claude-personal → Claude Code v2.1.x
  ✓ PostgreSQL: pgvector/pgvector:pg16 image available

All dependencies satisfied. Setting up database...
```

### LLM Provider Interface

The summarizer uses an abstract provider interface to support future extensibility:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str | None = None,
                       json_schema: dict | None = None) -> str:
        """Generate a completion from the LLM."""
        ...

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: type[BaseModel],
                                  system_prompt: str | None = None) -> BaseModel:
        """Generate a structured (validated) completion."""
        ...

class ClaudeCodeCLIProvider(LLMProvider):
    """Invokes Claude Code CLI as a subprocess."""
    def __init__(self, cli_command: str, model: str, timeout: int): ...

# Future providers:
# class OllamaProvider(LLMProvider): ...
# class AnthropicAPIProvider(LLMProvider): ...
```

The active provider is selected via configuration. Swapping providers requires only a config change, no code changes.

### Async Processing & Progress Tracking

For the **fully async** processing mode:

- **CLI**: The `bookcompanion add --async` command starts processing in a background thread and returns immediately. Progress is polled via `bookcompanion status <book_id>`.
- **Web UI**: Processing status is tracked in the `processing_jobs` table. The frontend polls the status endpoint at regular intervals (e.g., every 5 seconds) to update the progress UI. WebSocket support can be added in V2 for real-time updates.
- **Progress granularity**: The `processing_jobs.progress` JSON field stores `{current: N, total: M, current_step: "Summarizing Chapter 3"}` for detailed progress display.

---

## 17. Non-Functional Requirements

### Performance

- Book parsing: Should complete within 2 minutes for a typical 300-page book
- Section summarization: ~30-60 seconds per section (dependent on Claude Code CLI response time)
- Search: < 500ms for hybrid search results
- Web UI: First contentful paint < 2 seconds

### Data Integrity

- All processing is idempotent — re-running summarization replaces existing summaries
- Processing jobs track state to enable retry on failure
- Database backups via standard `pg_dump` (single Postgres instance with all data including BLOBs)

### Storage Estimates (per book)

| Content | Size Estimate |
|---------|--------------|
| Original file (BLOB) | 1-50 MB |
| Extracted images | 5-100 MB |
| Markdown content | 200 KB - 2 MB |
| Summaries | 50-500 KB |
| Embeddings | ~50 KB (768-dim vectors) |
| **Total per book** | **~10-150 MB** |

For a personal library of ~100 books: **1-15 GB total** — well within single Postgres capacity.

### Error Handling & Recovery

- Failed parsing: Log error, mark book as `parse_failed`, allow retry via `bookcompanion add <file> --force`
- Failed summarization: Log error, mark section as `summary_failed`, allow retry per-section
- Failed eval assertions: Auto-retry for critical failures (max 2 retries), flag for user review otherwise
- Claude Code CLI timeout: Configurable timeout (default 300s), fail gracefully with error message

### Partial Processing Recovery

Summarization processes sections sequentially. If it fails midway (e.g., on section 7 of 12):

1. Sections 1-6 retain their completed summaries
2. Section 7 is marked as `summary_failed` with the error message
3. Sections 8-12 remain as `summary_pending`
4. The user can resume with: `bookcompanion summarize <book_id>` — this skips already-completed sections and starts from the first `pending` or `failed` section
5. To force re-summarization of all sections: `bookcompanion summarize <book_id> --force`
6. The book-level summary is only generated after all sections are successfully summarized

This is tracked via `book_sections.summary_status` enum: `pending | running | completed | failed | stale`

### Security Considerations

Even as a single-user local tool, the app processes untrusted files and runs shell subprocesses:

| Concern | Mitigation |
|---------|-----------|
| **File upload validation** | Verify magic bytes match claimed format. Enforce configurable max file size (default 200MB). Reject files that fail format detection. |
| **CLI command injection** | The Claude Code CLI alias is read from config, not from user input. The subprocess call uses Python's `subprocess.run()` with list arguments (not shell=True), preventing injection. Prompt content is passed via stdin or `--system-prompt`, not interpolated into the command string. |
| **SQL injection** | Mitigated by SQLAlchemy ORM (parameterized queries). No raw SQL string interpolation. |
| **Path traversal** | File paths from uploads are sanitized. Backup/restore paths are validated. |
| **Denial of service** | Budget caps on LLM usage. Configurable timeouts on all external calls. |

### Testing Strategy

| Test Type | Scope | Tools |
|-----------|-------|-------|
| **Unit tests** | Service layer functions, parsers, evaluator assertions | `pytest`, `pytest-asyncio` |
| **Integration tests** | Database operations, full parsing pipeline, search queries | `pytest` + test Postgres (Docker) |
| **E2E tests (CLI)** | Full CLI command flows | `pytest` + `typer.testing.CliRunner` |
| **Eval tests** | Summarization quality regression | Custom eval harness against golden test books |

**Test infrastructure:**
- Test database: Separate Postgres instance in Docker (or testcontainers)
- Fixtures: Small test EPUB/PDF files included in `tests/fixtures/`
- CI: GitHub Actions running unit + integration tests on push

**What to test first (priority order):**
1. Parser correctness (does EPUB/PDF parsing produce expected Markdown?)
2. Data model integrity (do cascading operations work correctly?)
3. Search accuracy (do hybrid search results rank correctly?)
4. CLI command flows (do commands produce expected output?)
5. Eval assertion accuracy (do binary assertions catch known-bad summaries?)

### Logging & Observability

- **Structured logging** via Python's `logging` module with `structlog` for JSON-formatted output
- **Log levels**: DEBUG (parser details), INFO (processing milestones), WARNING (eval failures), ERROR (crashes)
- **Per-book processing log**: Each processing run creates a structured log entry in `processing_jobs` with timing, step details, and error traces
- **CLI verbosity**: `--verbose` flag increases log output. Default shows progress only.
- **Log location**: `~/.config/bookcompanion/logs/` with daily rotation

### Development Workflow

**Local development (outside Docker):**

```bash
# Setup
uv sync                                    # Install Python dependencies
cd frontend && npm install                 # Install frontend dependencies

# Backend
uv run bookcompanion init                  # Setup DB
uv run bookcompanion <command>             # Run CLI commands
uv run uvicorn app.api.main:app --reload   # Run API server

# Frontend
cd frontend && npm run dev                 # Vite dev server

# Testing
uv run pytest                              # Run all tests
uv run pytest tests/unit                   # Run unit tests only
```

**Code quality tools:**
- **Formatter**: `ruff format` (fast, opinionated)
- **Linter**: `ruff check` (replaces flake8, isort, etc.)
- **Type checking**: `mypy` (strict mode)
- **Frontend**: `eslint` + `prettier` for Vue/TypeScript

### Data Export

Users can export their library data for portability:

```bash
# Export all data as JSON
bookcompanion export [--format json|markdown] [--output /path/to/dir]

# Export a specific book with all its data
bookcompanion export <book_id> [--format json|markdown]
```

**JSON export** includes: book metadata, section content, summaries, annotations, tags, eval results.

**Markdown export** produces a directory structure:
```
export/
├── Thinking Fast and Slow/
│   ├── metadata.json
│   ├── summary.md                 # Book-level summary
│   ├── sections/
│   │   ├── 01_introduction.md     # Original content
│   │   ├── 01_introduction_summary.md
│   │   └── ...
│   └── annotations.md             # All annotations formatted
└── ...
```

### Prompt Template Structure

Prompts are stored as Jinja2 templates with defined variable contracts:

```
backend/app/services/summarizer/prompts/
├── summarize_section_v1.txt
├── summarize_book_v1.txt
├── eval_faithfulness_v1.txt
├── eval_completeness_v1.txt
├── eval_coherence_v1.txt
├── eval_format_v1.txt
└── detect_structure_v1.txt
```

**Template variables available:**

| Variable | Available In | Description |
|----------|-------------|-------------|
| `{{ section_title }}` | Section prompts | Title of the current section |
| `{{ section_content }}` | Section prompts | Full Markdown content of the section |
| `{{ book_title }}` | All prompts | Book title |
| `{{ book_author }}` | All prompts | Book author(s) |
| `{{ compression_target }}` | Summarization prompts | Target compression percentage |
| `{{ detail_level }}` | Summarization prompts | brief/standard/detailed |
| `{{ all_section_summaries }}` | Book summary prompt | Concatenated section summaries |
| `{{ source_text }}` | Eval prompts | Original content being evaluated |
| `{{ summary_text }}` | Eval prompts | Summary being evaluated |

**Version convention**: `{purpose}_v{N}.txt` — increment N when making changes. Old versions are kept for reproducibility.

---

## 18. V2+ Deferred Features

These features are explicitly out of scope for V1 but inform the architecture to ensure extensibility:

| Feature | V2 Priority | Architecture Impact |
|---------|-------------|-------------------|
| Resume summarization (up to a point) | High | Sections already ordered — filter by order_index |
| Select text + ask LLM | High | Annotation infrastructure already supports text selection |
| Framework/template extraction | Medium | New prompt template + storage field on sections |
| Quizzes per section | Medium | New `quizzes` table linked to sections |
| Summarization modes (tweets, diagrams) | Low | New prompt templates, additional summary fields |
| Global semantic search improvements | Medium | Already have pgvector foundation |
| Multi-user / auth | Low | Add users table, FK to all entities |
| Mobile app | Low | API already built for web frontend |

---

## 19. Decision Log

| # | Decision | Options Considered | Choice | Rationale |
|---|----------|-------------------|--------|-----------|
| 1 | Architecture style | A) Layered monolith, B) Service + Worker (Redis), C) Event-driven pipeline | **A) Layered monolith** | Simplest to build and debug for single-user. Async via subprocess/threading gives 90% of worker benefits without Redis. |
| 2 | LLM provider | A) Claude API direct, B) Claude Code CLI subprocess, C) Pluggable interface, D) Ollama-first | **B) Claude Code CLI subprocess** | User preference. Leverages existing subscription and profiles. CLI supports non-interactive mode (-p), JSON output, and JSON schema validation. |
| 3 | Processing mode | A) Sync only, B) Async only, C) Dual mode | **C) Dual mode** | Step-by-step (default) for control, async for convenience. Same pipeline, different execution model. |
| 4 | File storage | A) Local filesystem, B) Postgres BLOBs, C) Local FS + DB metadata | **B) Postgres BLOBs** | Simplest backup/restore story. Single `pg_dump` captures everything. Acceptable for single-user scale (~100 books). |
| 5 | Content format | A) Markdown, B) HTML, C) Both | **A) Markdown** | Portable, renders in CLI and web, good LLM input format. All parsers output Markdown. |
| 6 | Missing TOC handling | A) LLM only, B) Heuristics only, C) Manual, D) Heuristics + LLM fallback | **D) Heuristics first, LLM fallback** | Cost-effective: heuristics handle 70-80% of cases. LLM fallback for complex layouts. User confirms either way. |
| 7 | Search approach | A) Keyword only, B) Semantic only, C) Hybrid BM25 + semantic | **C) Hybrid with RRF re-ranking** | Best of both worlds. BM25 for exact matches, semantic for conceptual queries. RRF is simple, effective, no ML needed. All in Postgres. |
| 8 | Embedding provider | A) Cloud API, B) Local Ollama | **B) Local Ollama** | Free, private, no API costs. User already has Ollama running locally. nomic-embed-text provides good quality. |
| 9 | Summary evaluation | A) ROUGE/BERTScore, B) LLM rubric scoring, C) Binary assertions | **C) Binary pass/fail assertions** | Per Hamel Husain's methodology. Binary tests are clearer, more actionable, easier to aggregate than rubric scores. Traditional metrics correlate poorly with human judgment for abstractive summaries. |
| 10 | Compression ratio | A) Fixed 10-20%, B) Configurable with defaults | **B) Configurable with smart defaults** | Research shows optimal ratio varies by content type. Default ~20% for sections, ~30% for book-from-sections. Auto-retry with higher ratio if quality assertions fail. |
| 11 | ORM | A) SQLAlchemy 2.0, B) SQLModel, C) Tortoise ORM | **A) SQLAlchemy 2.0** | Industry standard, async support, mature Alembic integration. SQLModel is simpler but less flexible. Tortoise has smaller ecosystem. |
| 12 | CLI framework | A) Click, B) Typer, C) argparse | **B) Typer** | Built on Click with type-hint driven API. Less boilerplate, auto-generated help. |
| 13 | Python package manager | A) pip, B) Poetry, C) uv | **C) uv** | Fastest, modern, good monorepo support. Actively developed by Astral (ruff team). |
| 14 | Design system | A) Custom, B) Headless UI, C) PrimeVue, D) shadcn-vue | **A) Custom from scratch** | Maximum control, minimal dependencies. User preference. |
| 15 | Annotation model | A) Section-level only, B) Text-level, C) Rich (text + tags + links) | **C) Rich annotations** | Cross-book linking enables personal knowledge graph. Polymorphic content_type supports annotations on content, summaries, and book-level summaries. |
| 16 | PDF parser | A) PyMuPDF, B) pdfplumber, C) marker-pdf | **C) marker-pdf** | ML-based, best quality for complex layouts with tables and images. Falls back to PyMuPDF for simple text-only PDFs. |
| 17 | Deployment | A) Local only, B) Local primary + cloud-ready, C) Cloud-native | **B) Local primary, cloud-ready** | Docker Compose for daily use, structured for easy cloud deployment if needed later. |
| 18 | Primary interface | A) Web-first, B) CLI-first, C) Equal | **B) CLI-first, then equal** | Build and verify all functionality via CLI first. Service layer ensures feature parity when web is added. |
| 19 | Config location | A) Project-local, B) XDG standard, C) Home directory | **B) XDG standard (~/.config/bookcompanion/)** | Follows platform conventions. Supports env var override. |
| 20 | Annotation anchoring | A) Character offsets only, B) Text fingerprint only, C) Dual (offsets + stored text) | **C) Dual anchoring** | Offsets for speed, stored text as fallback. Handles re-parsing gracefully via fuzzy text search. |
| 21 | Async progress tracking | A) Polling, B) WebSocket, C) Polling now + WebSocket later | **C) Polling now, WebSocket V2** | Polling is simpler, sufficient for single user. 5-second intervals are fine for progress tracking. |
| 22 | Ollama in Docker vs host | A) Docker container, B) Use host Ollama | **B) Use host Ollama** | Already running locally. Avoids duplicate container. Backend connects via host.docker.internal. |
| 23 | MOBI via Calibre | A) Full Calibre, B) ebook-convert CLI only, C) Drop MOBI support | **B) ebook-convert CLI only** | Only the CLI tool is needed, not the full Calibre GUI. Lighter dependency. |
| 24 | Duplicate book handling | A) Reject, B) Replace, C) Warn + offer re-import | **C) Warn + offer re-import** | SHA-256 hash detection. Re-import preserves annotations/tags but marks summaries as stale. |
| 25 | Long section handling | A) Fail, B) Truncate, C) Recursive sub-chunking | **C) Recursive sub-chunking** | Split at paragraph boundaries, summarize sub-chunks, merge. Transparent to user. |
| 26 | Partial processing recovery | A) Restart from scratch, B) Resume from failure point | **B) Resume from failure point** | Skip completed sections, start from first pending/failed. `--force` for full re-run. |
| 27 | CLI output rendering | A) Plain text, B) Rich Markdown, C) Rich + pager | **C) Rich + pager** | `rich` library for Markdown rendering, tables, progress bars. Pager for long content. JSON output for scripting. |
| 28 | Subprocess safety | A) shell=True, B) List args (no shell) | **B) List args** | Prevents command injection. Prompts passed via stdin, not interpolated. |
| 29 | Logging | A) Print statements, B) stdlib logging, C) structlog | **C) structlog** | JSON-formatted structured logs. Daily rotation. Per-book processing logs. |
| 30 | Code quality | A) Black+flake8, B) Ruff | **B) Ruff** | Single tool for formatting + linting. Fast, by Astral (same as uv). |
| 31 | Prompt templates | A) Hardcoded strings, B) External files, C) Jinja2 templates | **C) Jinja2 templates** | Versioned files with defined variable contracts. Enables prompt iteration without code changes. |
| 32 | Cumulative context in summarization | A) Summarize sections independently, B) Include prior context | **B) Include cumulative context** | Inspired by AI Reading Club's progressive summarization. Produces more coherent summaries that reflect the book's narrative arc. Key themes + concepts index from prior sections passed to each prompt. |
| 33 | Concepts index | A) Defer to V2, B) Extract during summarization | **B) Extract during V1 summarization** | Low incremental cost (extracted alongside summary). High value for non-fiction: frameworks, models, key terms searchable across books. Inspired by Dewey's term lookup feature. |
| 34 | Faithfulness strengthening | A) Standard assertions only, B) Add cross-summary consistency | **B) Add sample-and-compare** | Generate 2 summary variants, flag divergences. Per Eugene Yan: consistency is the hardest dimension — even SOTA achieves only 60-75% accuracy. Extra LLM call is worth the quality improvement. |
| 35 | Image captioning | A) Reference images by filename only, B) Generate captions via vision model | **B) Vision model captions** | Non-fiction diagrams/charts carry significant information. Captions are injected into Markdown before summarization so visual content is reflected in summaries. |
| 36 | Specificity evaluation | A) Skip, B) Add specificity assertions | **B) Add `not_generic` + `preserves_author_terminology`** | Catches summaries generic enough to apply to any book. Preserving author's vocabulary is important for non-fiction where terminology carries specific meaning. |
| 37 | Human eval baseline | A) Skip straight to automation, B) Bootstrap with human eval first | **B) Human eval first (non-negotiable)** | Per Hamel Husain: read 20-30 summaries, build golden test set of 10-15 chapters, calibrate LLM judge against human annotations at >80% agreement. |
| 38 | Prompt comparison method | A) Absolute scoring, B) Pairwise comparison | **B) Pairwise LLM-judge comparison** | "Which summary is better?" is more reliable than scoring each 1-5. Eliminates calibration issues, detects smaller quality differences. |
| 39 | Frontend server state | A) Pinia for everything, B) Pinia + TanStack Query | **B) Pinia + Vue Query split** | Pinia for client state (UI), Vue Query for server state (API data). Reduces boilerplate, prevents stale data bugs with automatic caching and background refetching. |

---

## 20. Research Sources

### Consulted During Requirements

| Source | Topic | Key Insight |
|--------|-------|-------------|
| [Eugene Yan - Abstractive Summarization](https://eugeneyan.com/writing/abstractive/) | Summarization approaches | Hierarchical map-reduce is the standard for long documents. Extractive → abstractive pipeline can improve quality. |
| [Eugene Yan - LLM Patterns](https://eugeneyan.com/writing/llm-patterns/) | LLM application patterns | RAG, evaluation, and guardrails patterns applicable to summarization pipeline |
| [Eugene Yan - AI Reading Club / Dewey](https://eugeneyan.com/writing/aireadingclub/) | Project inspiration & patterns | **Deep analysis**: Dewey (aireadingclub.com) is an AI reading companion offering clarification, quizzes, recaps, term lookup, and anchored discussions. Key patterns adopted: (1) Progressive/cumulative summarization with position-aware context, (2) Concepts index as a living artifact growing per section, (3) Dual-context retrieval (local passage + book-level themes), (4) Anchored discussion/annotation history. Dewey's core insight: never summarize in isolation — always ground in both local passage and macro book structure. |
| [Hamel Husain - Evals FAQ](https://hamel.dev/blog/posts/evals-faq/) | Evaluation methodology | Binary pass/fail assertions > rubric scoring. Start simple, iterate. |
| [Hamel Husain - Field Guide](https://hamel.dev/blog/posts/field-guide/) | LLM application development | Practical patterns for building LLM apps with evaluation |
| [Hamel Husain - LLM Judge](https://hamel.dev/blog/posts/llm-judge/) | LLM-as-judge patterns | How to use LLMs to evaluate other LLM outputs effectively |
| Wu et al., 2021 - "Recursively Summarizing Books with Human Feedback" (OpenAI) | Book summarization | Recursive/hierarchical summarization outperforms single-pass for long documents. Each compression stage loses ~10-15% of key info. |
| Kryscinski et al., 2022 - BookSum (ACL) | Book summarization benchmarks | Chapter summaries average 5-10% of source. Full book summaries compress to 1-3%. |
| Grusky et al., 2018 (NAACL) | Compression metrics | News summarization clusters at 10-20% compression. Optimal ratio is task-dependent. |
| marker-pdf GitHub | PDF parsing | ML-based PDF to Markdown conversion with table and image support |
| ebooklib documentation | EPUB parsing | Standard Python library for EPUB manipulation |

### Additional Research To Conduct (During Implementation)

- Optimal chunking strategies for embedding (size, overlap, semantic chunking)
- nomic-embed-text vs other Ollama embedding models for book content
- Tailwind CSS design system patterns for reading-focused UIs
- Claude Code CLI error handling and edge cases in subprocess mode

---

## 21. Open Questions & Risks

### Open Questions

| # | Question | Impact | When to Resolve |
|---|----------|--------|----------------|
| 1 | What is the maximum book size marker-pdf can handle reliably? | May need chunked PDF processing | During implementation — test with large PDFs |
| 2 | How to handle books with heavy mathematical notation? | May need LaTeX/MathJax support in Markdown | During implementation — test with academic books |
| 3 | Should embeddings be generated for original content, summaries, or both? | Affects search quality and storage | During search implementation — start with both, measure |
| 4 | How to handle rate limiting if Claude Code CLI has usage caps? | May need queuing/throttling | During summarization implementation |
| 5 | Optimal prompt templates for different book genres? | Affects summary quality | Iterative — use eval harness to compare |
| 6 | How to handle Calibre ebook-convert CLI-only installation on different OSes? | Affects MOBI support onboarding | During setup — document per-OS installation |
| 7 | Should the concepts index extraction use a separate prompt or be part of the summarization prompt? | Affects cost and quality | During implementation — test both approaches with eval harness |
| 8 | How to handle books in languages other than English? | Affects parsing and summarization quality | Defer — V1 targets English only. Document as limitation. |

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PDF parsing quality varies widely | High | Medium | Use marker-pdf with fallback to PyMuPDF. Allow manual section editing. |
| LLM summarization inconsistency | Medium | High | Binary assertion battery with auto-retry. Prompt versioning for iteration. Cross-summary consistency check. |
| Postgres BLOB performance at scale | Low | Medium | Single user with ~100 books is well within limits. Can migrate to filesystem if needed. |
| Claude Code CLI subprocess reliability | Medium | Medium | Configurable timeouts, retry logic, error logging. Interface allows swapping to direct API. |
| Embedding model quality for domain content | Medium | Medium | nomic-embed-text is a solid default. Can swap models via Ollama without code changes. |
| Cumulative context token bloat | Medium | Low | As more sections are processed, cumulative context grows. Mitigate by summarizing the cumulative context itself, keeping it to a fixed token budget. |
| Cross-summary consistency cost | Low | Low | Generates 2 summary variants for faithfulness check. Doubles cost for this assertion. Can be made optional via config. |
| Claude Code CLI requires internet | High | Medium | Summarization fails if offline. Document as requirement. LLM provider interface allows future swap to local Ollama for offline use. |

### Constraints & Limitations (V1)

- **English only**: Parsing and summarization optimized for English-language books
- **Internet required**: Claude Code CLI needs network access for summarization (embedding via Ollama is local)
- **Single user**: No authentication, no data isolation between users
- **No real-time collaboration**: No shared annotations or collaborative features
