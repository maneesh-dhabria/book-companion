# Book Companion - V1 Technical Specification

**Version:** 1.0
**Date:** 2026-04-01
**Status:** Draft
**Source:** [V1 Requirements](../requirements/2026-04-01_book_companion_v1_requirements.md)

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [Scope & Phasing](#2-scope--phasing)
3. [Glossary](#3-glossary)
4. [Architecture](#4-architecture)
5. [Data Model & Database Design](#5-data-model--database-design)
6. [Book Parsing Pipeline](#6-book-parsing-pipeline)
7. [Summarization Pipeline](#7-summarization-pipeline)
8. [Quality Evaluation (Evals)](#8-quality-evaluation-evals)
9. [Search](#9-search)
10. [CLI Interface](#10-cli-interface)
11. [Configuration & Operations](#11-configuration--operations)
12. [Error Handling, Security & Non-Functional Requirements](#12-error-handling-security--non-functional-requirements)
13. [Infrastructure & Deployment](#13-infrastructure--deployment)
14. [Verification & Testing Plan](#14-verification--testing-plan)
15. [Decision Log](#15-decision-log)
16. [Research Sources](#16-research-sources)
17. [Open Questions & Risks](#17-open-questions--risks)

---

## 1. Overview & Goals

Book Companion is a personal CLI tool that takes a non-fiction book as input, parses its structure, generates section-level and book-level summaries using LLMs, and provides a searchable, annotatable library for efficient knowledge extraction.

### Core Value Proposition

- Skim through a book quickly to understand core ideas, frameworks, and key arguments
- Search for concepts across multiple books and find relevant advice
- Annotate and cross-reference ideas across your personal library

### Target User

Single user (personal tool). No authentication or multi-tenancy.

### Success Criteria

Qualitative self-use: the tool is successful when it replaces the user's current reading workflow and is used weekly. No formal metrics beyond eval pass rates for summary quality.

---

## 2. Scope & Phasing

This spec covers **Phase 1** and **Phase 2** of the CLI-only tool. The web UI and REST API are out of scope and will be specified in a separate design document.

> **Note on concepts index**: Concept extraction happens during Phase 1 summarization (it's part of the summarization prompt output). However, dedicated concepts CLI commands (`concepts <book_id>`, `concepts search`, `concepts edit`) are Phase 2. In Phase 1, extracted concepts are stored in the DB but only surfaced through search results.

### Phase 1: Core Pipeline (CLI)

Upload, parse, summarize, evaluate, and search books via CLI.

| Feature | Description |
|---------|-------------|
| Book upload & parsing | EPUB, MOBI (via Calibre), PDF (via marker-pdf) |
| Structure detection | 3-tier: embedded TOC → heuristics → LLM fallback |
| Quick summary | Single-pass rough book summary (~2 min) |
| Section summarization | Hierarchical map-reduce with cumulative context |
| Book-level summary | Generated from all section summaries |
| Image captioning | Vision model via Claude Code CLI for diagrams/charts |
| Eval assertions | Full 16-assertion battery with trace storage |
| Hybrid search | BM25 + semantic (pgvector) + RRF fusion |
| Duplicate detection | SHA-256 hash, warn + re-import option |
| Processing modes | Step-by-step (default) + fully async (background process) |
| Core CLI commands | add, list, show, read, summary, summarize, search, delete, status, eval, config, init |

### Phase 2: Annotations, Concepts & Enrichment (CLI)

| Feature | Description |
|---------|-------------|
| Annotations | Text highlights + notes + tags + cross-book links (via annotation IDs) |
| Concepts index | Per-book key terms, frameworks, models extracted during summarization |
| External references | Web search for existing summaries/reviews (4-5 curated links) |
| Tags | Polymorphic tagging on books, sections, annotations |
| Export | JSON and Markdown export of library data |
| Backup/restore | pg_dump based backup and restore commands |
| Metadata editing | Edit title, author; accept/reject section structure |
| Summary editing | Edit summaries in $EDITOR with user_edited protection |

### Phase 1 Implementation Order

Features should be implemented in this order due to dependencies:

```
1. Infrastructure & Config
   └── Docker Compose (PostgreSQL), config system (pydantic-settings),
       Alembic migrations, bookcompanion init

2. Data Model (Phase 1 tables)
   └── books, authors, book_authors, book_sections, images,
       processing_jobs, search_index, eval_traces

3. Book Parsing Pipeline
   └── Format detection → EPUB parser → PDF parser → MOBI parser →
       Structure detection → Content segmentation → DB storage
   Dependencies: Data model

4. Embedding Service
   └── Ollama integration, chunking, search_index population
   Dependencies: Data model, parsed content

5. Search Service
   └── BM25 + semantic + RRF fusion
   Dependencies: Embedding service, search_index

6. LLM Provider (Claude Code CLI)
   └── Subprocess invocation, timeout handling, JSON parsing
   Dependencies: Config

7. Image Captioning
   └── Extract images → CLI vision → store captions → inject into Markdown
   Dependencies: LLM provider, parsed images

8. Summarization Pipeline
   └── Section summarization (with cumulative context) → Book summary →
       Quick summary mode → Partial recovery
   Dependencies: LLM provider, image captioning, parsed content

9. Eval Service
   └── 16 assertions → trace storage → auto-retry → aggregation
   Dependencies: LLM provider, summarization

10. CLI Layer
    └── All Phase 1 commands as thin wrappers over services
    Dependencies: All services

11. Async Processing Mode
    └── Background process, PID tracking, status polling
    Dependencies: Full pipeline working synchronously first
```

Each step includes its verification tests (see Section 14).

### Explicitly Out of Scope (This Spec)

- Web UI (Vue 3 SPA) — separate design document
- REST API (FastAPI) — added with web UI
- Multi-user / authentication
- Mobile app
- V2+ features: resume summarization, select-text-ask-LLM, quizzes, summarization modes

---

## 3. Glossary

| Term | Definition |
|------|-----------|
| **Book** | A non-fiction work in EPUB, MOBI, or PDF format uploaded to the system |
| **Book Section** | A logical component within a book (chapter, part, appendix). Sections can be nested via parent_id |
| **Library** | The collection of all books managed by Book Companion |
| **Concepts Index** | Per-book structured glossary of key terms, frameworks, and models extracted during summarization |
| **Summary** | LLM-generated abstractive summary of a book section or entire book |
| **Annotation** | User-created highlight, note, or cross-reference attached to content or summaries (Phase 2) |
| **Eval Assertion** | A binary pass/fail test evaluating a specific quality dimension of a generated summary |
| **Eval Trace** | Complete record of an eval assertion execution: prompt, response, result, metadata |
| **Cumulative Context** | Compact summary of prior sections included when summarizing section N for coherence |
| **Quick Summary** | Rough single-pass book-level summary generated in ~2 min, separate from the full pipeline |
| **RRF** | Reciprocal Rank Fusion — algorithm merging BM25 and semantic search rankings |

---

## 4. Architecture

### Approach: Layered Monolith, CLI-Only, Host-Native

The backend runs directly on the host machine (not in Docker). Only PostgreSQL runs in Docker. This avoids the complexity of bridging the Claude Code CLI from a container to the host.

```
┌─────────────────────────────────────────────────┐
│                  Host Machine                    │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │          Typer CLI (thin layer)           │   │
│  └────────────────┬─────────────────────────┘   │
│                   │                              │
│  ┌────────────────┴─────────────────────────┐   │
│  │           Service Layer                   │   │
│  │  book_service | parser | summarizer |     │   │
│  │  search | embedding | annotation          │   │
│  └────────────────┬─────────────────────────┘   │
│                   │                              │
│  ┌────────────────┴─────────────────────────┐   │
│  │        Data Access Layer                  │   │
│  │  SQLAlchemy 2.0 + Alembic migrations     │   │
│  └────────────────┬─────────────────────────┘   │
│                   │                              │
│  External:        │                              │
│  ┌──────────┐  ┌──┴───────────┐  ┌───────────┐ │
│  │ Claude   │  │ PostgreSQL   │  │ Ollama    │ │
│  │ Code CLI │  │ 16+pgvector  │  │ (local)   │ │
│  │ (local)  │  │ (Docker)     │  │ embeddings│ │
│  └──────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────────────────────────┘
```

### Key Architectural Principles

1. **CLI-first**: All functionality accessible via Typer CLI. Service layer is the single source of business logic.
2. **Thin CLI layer**: CLI commands are thin wrappers that delegate to services. When the API is added later, it will share the same service layer.
3. **Host-native execution**: Backend runs on the host to directly invoke Claude Code CLI and access Ollama. Only PostgreSQL is containerized.
4. **Async via subprocess**: Claude Code CLI calls use `asyncio.create_subprocess_exec()`. The async processing mode uses Python `multiprocessing` to fork a background process.
5. **Configurable LLM**: The LLM provider interface supports swapping Claude Code CLI for other providers. Single profile with `--model` flag to switch models per operation.

### Service Layer Design

```python
# Services are stateless, receive dependencies via constructor injection
class BookService:
    def __init__(self, db: AsyncSession, parser: ParserService, config: Settings): ...
    async def add_book(self, file_path: Path, quick: bool = False, async_mode: bool = False) -> Book: ...
    async def delete_book(self, book_id: int) -> None: ...
    async def list_books(self, tag: str | None, author: str | None) -> list[Book]: ...

class SummarizerService:
    def __init__(self, db: AsyncSession, llm: LLMProvider, config: Settings): ...
    async def summarize_book(self, book_id: int, force: bool = False) -> None: ...
    async def summarize_section(self, book_id: int, section_id: int) -> None: ...

class SearchService:
    def __init__(self, db: AsyncSession, embedding: EmbeddingService, config: Settings): ...
    async def search(self, query: str, book_id: int | None, source_types: list[str] | None, limit: int = 20) -> GroupedSearchResults: ...

class EvalService:
    def __init__(self, db: AsyncSession, llm: LLMProvider, config: Settings): ...
    async def evaluate_summary(self, section_id: int) -> EvalResult: ...
    async def compare_ratios(self, book_id: int, section_id: int, ratios: list[int]) -> ComparisonResult: ...

class EmbeddingService:
    def __init__(self, ollama_url: str, model: str, config: Settings): ...
    async def embed_text(self, text: str) -> list[float]: ...
    async def embed_chunks(self, text: str, chunk_size: int, overlap: int) -> list[EmbeddingChunk]: ...
```

### LLM Provider Interface

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str | None = None,
                       model: str | None = None, json_schema: dict | None = None,
                       timeout: int | None = None) -> LLMResponse: ...

    @abstractmethod
    async def generate_with_image(self, prompt: str, image_path: Path,
                                   system_prompt: str | None = None,
                                   model: str | None = None) -> LLMResponse: ...

class LLMResponse(BaseModel):
    content: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int

class ClaudeCodeCLIProvider(LLMProvider):
    """Invokes Claude Code CLI as a subprocess."""

    def __init__(self, cli_command: str, default_model: str, default_timeout: int): ...

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Invokes: <cli_command> -p "<prompt>" --output-format json --model <model>
                 [--json-schema '<schema>'] [--max-budget-usd <budget>]

        - Uses asyncio.create_subprocess_exec() with list args (no shell=True)
        - Prompt passed via stdin to avoid shell escaping issues
        - Timeout enforced via asyncio.wait_for()
        """
        ...

    async def generate_with_image(self, prompt: str, image_path: Path, **kwargs) -> LLMResponse:
        """
        For image captioning. Invokes Claude Code CLI with --add-dir pointing
        to the directory containing the image, and the prompt references the
        image file path. CLI's Read tool natively handles image files.

        Invokes: <cli_command> -p "Read the image at {image_path} and {prompt}"
                 --add-dir {image_dir} --permission-mode auto --output-format json
                 --model <model>
        """
        ...
```

### Async Processing Architecture

For `--async` mode, the CLI forks a background process:

```python
import multiprocessing
import os

def run_async_pipeline(book_id: int, config_path: str):
    """Runs the full pipeline in a background process."""
    # Detach from parent process
    # Create new DB session
    # Run: parse → summarize → embed
    # Update processing_jobs table throughout
    ...

# In CLI command handler:
process = multiprocessing.Process(
    target=run_async_pipeline,
    args=(book_id, config_path),
    daemon=False  # Survives parent terminal close
)
process.start()
print(f"Processing book (ID: {book_id}). Run `bookcompanion status {book_id}` to check.")
```

The `processing_jobs` table tracks progress. `bookcompanion status <book_id>` queries this table.

---

## 5. Data Model & Database Design

### SQLAlchemy Models

All models use SQLAlchemy 2.0 declarative style with mapped_column. UUIDs are not used — integer PKs with BIGSERIAL for simplicity.

#### Core Entities

```python
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer,
    JSON, LargeBinary, String, Text, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR
import enum
from datetime import datetime


class Base(DeclarativeBase):
    pass


# --- Enums ---

class BookStatus(str, enum.Enum):
    UPLOADING = "uploading"
    PARSING = "parsing"
    PARSED = "parsed"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    PARSE_FAILED = "parse_failed"

class SummaryStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE = "stale"

class ProcessingStep(str, enum.Enum):
    PARSE = "parse"
    SUMMARIZE = "summarize"
    EMBED = "embed"
    EVAL = "eval"
    CAPTION = "caption"
    QUICK_SUMMARY = "quick_summary"
    EXTERNAL_REFS = "external_refs"

class ProcessingJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class SourceType(str, enum.Enum):
    BOOK_TITLE = "book_title"
    BOOK_SUMMARY = "book_summary"
    SECTION_TITLE = "section_title"
    SECTION_CONTENT = "section_content"
    SECTION_SUMMARY = "section_summary"
    CONCEPT = "concept"
    ANNOTATION = "annotation"

class ContentType(str, enum.Enum):
    SECTION_CONTENT = "section_content"
    SECTION_SUMMARY = "section_summary"
    BOOK_SUMMARY = "book_summary"

class AnnotationType(str, enum.Enum):
    HIGHLIGHT = "highlight"
    NOTE = "note"
    FREEFORM = "freeform"


# --- Models ---

class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    books: Mapped[list["Book"]] = relationship(secondary="book_authors", back_populates="authors")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # SHA-256
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)  # epub, mobi, pdf
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cover_image: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[BookStatus] = mapped_column(Enum(BookStatus), default=BookStatus.UPLOADING)
    quick_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_summary_eval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    authors: Mapped[list["Author"]] = relationship(secondary="book_authors", back_populates="books")
    sections: Mapped[list["BookSection"]] = relationship(back_populates="book", cascade="all, delete-orphan")
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="book", cascade="all, delete-orphan")
    concepts: Mapped[list["Concept"]] = relationship(back_populates="book", cascade="all, delete-orphan")
    external_references: Mapped[list["ExternalReference"]] = relationship(back_populates="book", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_books_file_hash", "file_hash"),
        Index("ix_books_status", "status"),
    )


class BookAuthor(Base):
    __tablename__ = "book_authors"

    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True)
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(50), default="author")  # author, editor, translator


class BookSection(Base):
    __tablename__ = "book_sections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=0)  # 0=top-level, 1=chapter, 2=sub-section
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_status: Mapped[SummaryStatus] = mapped_column(Enum(SummaryStatus), default=SummaryStatus.PENDING)
    summary_version: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Prompt version that generated it
    summary_eval: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Assertion results
    summary_model: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Model used
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book: Mapped["Book"] = relationship(back_populates="sections")
    parent: Mapped["BookSection | None"] = relationship(remote_side=[id])
    images: Mapped[list["Image"]] = relationship(back_populates="section", cascade="all, delete-orphan")
    # Phase 2: annotations relationship added via migration
    # annotations: Mapped[list["Annotation"]] = relationship(back_populates="section", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_book_sections_book_id_order", "book_id", "order_index"),
        Index("ix_book_sections_summary_status", "summary_status"),
    )


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("book_sections.id", ondelete="CASCADE"), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM-generated caption
    caption_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    section: Mapped["BookSection"] = relationship(back_populates="images")


class SearchIndex(Base):
    __tablename__ = "search_index"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # FK to source entity
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)  # For multi-chunk content
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)  # pgvector
    tsvector: Mapped[str] = mapped_column(TSVECTOR, nullable=True)  # BM25
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_search_index_source", "source_type", "source_id"),
        Index("ix_search_index_book_id", "book_id"),
        Index("ix_search_index_embedding", "embedding", postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_search_index_tsvector", "tsvector", postgresql_using="gin"),
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    step: Mapped[ProcessingStep] = mapped_column(Enum(ProcessingStep), nullable=False)
    status: Mapped[ProcessingJobStatus] = mapped_column(Enum(ProcessingJobStatus), default=ProcessingJobStatus.PENDING)
    progress: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Per-section status
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Background process PID

    book: Mapped["Book"] = relationship(back_populates="processing_jobs")

    __table_args__ = (
        Index("ix_processing_jobs_book_status", "book_id", "status"),
    )


class EvalTrace(Base):
    """Stores full LLM traces for eval assertions. Enables building datasets
    for prompt improvement and eval calibration."""
    __tablename__ = "eval_traces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("book_sections.id", ondelete="CASCADE"), nullable=False)
    assertion_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "no_hallucinated_facts"
    assertion_category: Mapped[str] = mapped_column(String(50), nullable=False)  # critical, important, advisory
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    prompt_sent: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_response: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)  # Extracted reasoning
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_eval_traces_section", "section_id"),
        Index("ix_eval_traces_assertion", "assertion_name", "passed"),
    )


# --- Phase 2 Models ---

class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # Hex color
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Taggable(Base):
    __tablename__ = "taggables"

    tag_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    taggable_type: Mapped[str] = mapped_column(String(50), primary_key=True)  # book, book_section, annotation
    taggable_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class Annotation(Base):
    """Polymorphic annotation model. content_type + content_id allow annotations on
    section content, section summaries, or book-level summaries without separate tables."""
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # FK to book_sections.id or books.id
    text_start: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Character offset
    text_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Stored for re-anchoring
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[AnnotationType] = mapped_column(Enum(AnnotationType), default=AnnotationType.NOTE)
    linked_annotation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("annotations.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Note: No FK constraint on content_id — polymorphic resolution via content_type:
    #   section_content → book_sections.id
    #   section_summary → book_sections.id
    #   book_summary → books.id

    __table_args__ = (
        Index("ix_annotations_content", "content_type", "content_id"),
    )


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    first_section_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True)
    term: Mapped[str] = mapped_column(String(500), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    related_concepts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    book: Mapped["Book"] = relationship(back_populates="concepts")

    __table_args__ = (
        Index("ix_concepts_book_id", "book_id"),
        UniqueConstraint("book_id", "term", name="uq_concepts_book_term"),
    )


class ConceptSection(Base):
    __tablename__ = "concept_sections"

    concept_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True)
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("book_sections.id", ondelete="CASCADE"), primary_key=True)


class ExternalReference(Base):
    __tablename__ = "external_references"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book: Mapped["Book"] = relationship(back_populates="external_references")
```

### Migration Strategy

- Use Alembic with autogenerate from SQLAlchemy models
- Migration naming: `NNNN_descriptive_name.py` (e.g., `0001_initial_schema.py`)
- Phase 1 creates: books, authors, book_authors, book_sections, images, search_index, processing_jobs, eval_traces, concepts, concept_sections (concepts extracted during summarization)
- Phase 2 adds: tags, taggables, annotations, external_references
- All migrations are idempotent and support rollback
- Run `alembic upgrade head` on `bookcompanion init` and auto-check on every CLI invocation

### Cascading Deletes

When a book is deleted, all related data cascades:

```
Book DELETE →
  ├── book_authors (CASCADE)
  ├── book_sections (CASCADE) →
  │   ├── images (CASCADE)
  │   ├── annotations (CASCADE)
  │   └── eval_traces (CASCADE)
  ├── search_index (CASCADE)
  ├── processing_jobs (CASCADE)
  ├── concepts (CASCADE) → concept_sections (CASCADE)
  └── external_references (CASCADE)
```

### Database Indexes

| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| books | ix_books_file_hash | B-tree | Duplicate detection |
| book_sections | ix_book_sections_book_id_order | B-tree (composite) | Ordered section listing |
| search_index | ix_search_index_embedding | HNSW | Approximate nearest neighbor |
| search_index | ix_search_index_tsvector | GIN | Full-text search |
| eval_traces | ix_eval_traces_assertion | B-tree (composite) | Assertion analytics |

---

## 6. Book Parsing Pipeline

### Supported Formats & Libraries

| Format | Library | Notes |
|--------|---------|-------|
| EPUB | `ebooklib` + `markdownify` | Extract TOC from toc.ncx/nav.xhtml, content as HTML, convert to Markdown |
| MOBI | `calibre` (ebook-convert CLI) | Convert MOBI to EPUB first via `ebook-convert`, then process as EPUB |
| PDF | `marker-pdf` | ML-based PDF to Markdown. Fallback to `PyMuPDF` for simple text-only PDFs |

### Parser Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ParsedSection:
    title: str
    content_md: str
    depth: int
    order_index: int
    images: list["ParsedImage"]

@dataclass
class ParsedImage:
    data: bytes
    mime_type: str
    filename: str | None
    width: int | None
    height: int | None

@dataclass
class ParsedBook:
    title: str
    authors: list[str]
    sections: list[ParsedSection]
    cover_image: bytes | None
    metadata: dict  # Additional metadata from file

class BookParser(ABC):
    @abstractmethod
    async def parse(self, file_path: Path) -> ParsedBook: ...

    @abstractmethod
    def supports_format(self, file_format: str) -> bool: ...

class EPUBParser(BookParser): ...
class PDFParser(BookParser): ...
class MOBIParser(BookParser): ...  # Delegates to EPUBParser after conversion
```

### Parsing Flow

```
1. Format Detection
   - File extension + magic bytes validation
   - Reject if mismatch or unsupported format

2. Pre-processing (MOBI only)
   - Convert to EPUB via: ebook-convert input.mobi output.epub
   - Use temporary directory for conversion
   - Process resulting EPUB

3. Content Extraction
   - Parse to Markdown + extract images as binary blobs
   - Compute SHA-256 hash of original file
   - Check for duplicates in DB

4. Structure Detection (3-tier fallback)
   - Tier 1: Parse embedded TOC (EPUB toc.ncx/nav.xhtml, PDF bookmarks)
   - Tier 2: Heuristic detection (heading patterns, font sizes, numbering)
   - Tier 3: LLM-assisted (send first ~5000 tokens to Claude Code CLI)
     Prompt (`detect_structure_v1.txt`):
     ```
     Analyze the following text from the beginning of a book. Identify the
     chapter/section structure. Return a JSON array of sections with title
     and approximate character offset. Look for: numbered chapters, named
     parts, heading patterns, topic transitions.
     ```
   - Record which tier was used

5. User Review (step-by-step mode only)
   - Present detected structure with section count and nesting
   - User can: accept (y), reject and re-detect (n), or skip to auto-accept
   - In async mode: auto-accept detected structure

6. Content Segmentation
   - Split content into sections based on confirmed structure
   - Estimate token count per section (1 token ≈ 4 chars)
   - Link images to their sections

7. Storage
   - Save book + sections + images to database
   - Generate embeddings for section titles + content chunks
   - Update book status to 'parsed'
```

### Image Captioning

Before summarization, images are processed to generate text descriptions:

```
1. Extract images during parsing → store as BLOBs in images table
2. For each image:
   a. Save to temp file
   b. Invoke Claude Code CLI with --add-dir pointing to temp dir:
      <cli> -p "Read the image at {path}. Describe what this image shows
             in the context of: {surrounding_paragraph_text}. Focus on
             key information, data, frameworks, or concepts depicted.
             Be concise (1-3 sentences)."
      --add-dir {temp_dir} --permission-mode auto --model <model>
   c. Store generated caption in images.caption
3. Inject captions into section Markdown:
   Replace ![](blob:{uuid}) with ![{generated_caption}](blob:{uuid})
4. Pass enriched Markdown to summarization pipeline
```

Image captioning is non-blocking: if captioning fails for an image, the summary proceeds without it.

### Title & Metadata Extraction

Priority order for metadata:
1. EPUB OPF metadata / PDF document info
2. File-level metadata
3. Cover page OCR (fallback, via Claude Code CLI vision)

User can edit parsed metadata via `bookcompanion edit <book_id> --title "..." --author "..."` (Phase 2).

### Duplicate Detection & Re-import

- SHA-256 hash computed on upload
- If hash exists: `"This book already exists (ID: X). Re-import? [y/N]"`
- Re-import: replaces parsed content/sections, marks summaries as `stale`, preserves annotations/tags (Phase 2), deletes old embeddings
- Re-import triggers re-embedding of all content

---

## 7. Summarization Pipeline

### Approach: Hierarchical Map-Reduce with Cumulative Context

```
Phase 1 (Map): Each Book Section → Individual Section Summary
               (with cumulative context from prior sections)
Phase 2 (Reduce): All Section Summaries → Book-Level Summary
```

### Quick Summary Mode

```bash
bookcompanion add --quick <file_path>
```

**Flow:**
1. Parse and extract full content as Markdown
2. Estimate total token count
3. If under model context limit (~200K tokens): single-pass summary via Claude Code CLI
4. If over: chunk into ~100K-token blocks, summarize each, merge into book summary
5. Store as `quick_summary` on the book (separate from `overall_summary`)
6. Quick summary model configurable separately via `llm.quick_summary_model`

Quick summary skips: section-level processing, eval assertions, concepts extraction, cumulative context, image captioning.

**Prompt template** (`quick_summary_v1.txt`):

```jinja2
You are creating a quick overview summary of the book "{{ book_title }}" by {{ book_author }}.

{{ book_content }}

## Instructions

Create a concise but informative overview of this book. Include:

### Main Thesis
What is this book fundamentally about? (2-3 sentences)

### Key Ideas (5-10 bullet points)
The most important concepts, arguments, and frameworks in the book.

### Who Should Read This
One sentence on who would benefit from reading this book.

This is a rough overview, not a detailed summary. Prioritize breadth over depth.
Output as JSON matching the provided schema.
```

### Section Summarization (Phase 1 - Map)

For each section, invoke Claude Code CLI with a structured prompt:

**Prompt template** (`summarize_section_v1.txt`):

```jinja2
You are summarizing a section of the book "{{ book_title }}" by {{ book_author }}.

{% if cumulative_context %}
## Context from prior sections
{{ cumulative_context }}
{% endif %}

## Current Section: {{ section_title }}

{{ section_content }}

## Instructions

Summarize this section with the following structure. Target approximately {{ compression_target }}% of the source length.

### Key Concepts (3-5 bullet points)
List the most important ideas, arguments, or takeaways.

### Detailed Summary
Write a comprehensive summary proportional to the source content. Use the author's terminology. Reference specific examples, frameworks, and models mentioned.

### Frameworks & Models
List any named frameworks, models, or methodologies introduced or discussed. If none, write "None mentioned."

### Key Quotes
Include 2-3 verbatim notable passages from the source that capture the section's essence. Format as blockquotes.

{% if image_captions %}
### Visual Content
The section contains images/diagrams. Describe their significance:
{% for caption in image_captions %}
- {{ caption }}
{% endfor %}
{% endif %}

Output as JSON matching the provided schema.
```

**JSON output schema:**

```json
{
  "type": "object",
  "properties": {
    "key_concepts": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 3,
      "maxItems": 5
    },
    "detailed_summary": {"type": "string"},
    "frameworks": {
      "type": "array",
      "items": {"type": "string"}
    },
    "key_quotes": {
      "type": "array",
      "items": {"type": "string"}
    },
    "image_references": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": ["key_concepts", "detailed_summary", "frameworks", "key_quotes"]
}
```

### Concepts Extraction (Phase 1 summarization, Phase 2 CLI)

During section summarization, the prompt also requests structured concept entries. These are included in the summarization JSON output:

```json
{
  "key_concepts": [...],
  "detailed_summary": "...",
  "frameworks": [...],
  "key_quotes": [...],
  "concepts": [
    {
      "term": "System 1 / System 2",
      "definition": "Two modes of thinking: fast/intuitive (System 1) vs slow/deliberate (System 2)",
      "related_concepts": ["cognitive bias", "heuristics"]
    }
  ]
}
```

In **Phase 1**: Concepts are extracted and stored in the `concepts` table during summarization. They appear in search results (indexed in `search_index` with `source_type=concept`).

In **Phase 2**: Dedicated CLI commands (`concepts <book_id>`, `concepts search`, `concepts edit`) provide direct access. The concepts index is also included in cumulative context for subsequent sections.

### Cumulative Context

When summarizing section N, include a compact context from sections 1..N-1:

```jinja2
The book so far has covered:
{% for prev in prior_sections %}
- **{{ prev.title }}**: {{ prev.one_line_summary }}
{% endfor %}

Key themes identified: {{ themes_list }}
Key terminology introduced: {{ terms_list }}
```

This context is generated by extracting the first sentence of each prior section's `detailed_summary` plus aggregating `key_concepts`. Kept to ~500 tokens max to avoid bloating the prompt.

The purpose is coherence: the LLM can reference prior concepts without re-explaining them, and can note how the current section builds on earlier content.

### Handling Long Sections

If a section exceeds ~150K tokens:

1. Split at paragraph boundaries into sub-chunks (~100K tokens each)
2. Summarize each sub-chunk independently
3. Merge sub-chunk summaries into a single section summary via a merge prompt
4. Transparent to the user — output is still one section summary

### Compression Ratios

| Detail Level | Section Ratio | Book Ratio | Use Case |
|-------------|---------------|------------|----------|
| Brief | ~10% | ~20% | Quick reference |
| Standard (default) | ~20% | ~30% | Regular reading |
| Detailed | ~30% | ~40% | Deep study |

If a summary fails quality assertions at current ratio, system auto-retries with the next higher ratio.

### Book Summary (Phase 2 - Reduce)

Concatenate all section summaries and invoke Claude Code CLI:

**Prompt template** (`summarize_book_v1.txt`):

```jinja2
You are creating an overall summary of "{{ book_title }}" by {{ book_author }}.

Below are summaries of each section:

{{ all_section_summaries }}

## Instructions

Create a comprehensive book-level summary with:

### Book Thesis / Main Argument
What is this book fundamentally arguing? (2-3 sentences)

### Chapter-by-Chapter Overview
For each section, provide a 2-3 line overview of its contribution to the book's argument.

### Key Frameworks & Models
List all named frameworks, models, and methodologies from across the book.

### Cross-Cutting Themes
Identify 3-5 themes that recur across multiple sections.

### Who Should Read This
One paragraph on who would benefit most from this book and why.

Target approximately {{ compression_target }}% of the combined section summaries.
Output as JSON matching the provided schema.
```

### Claude Code CLI Invocation

```python
async def invoke_cli(self, prompt: str, model: str | None = None,
                     json_schema: dict | None = None) -> LLMResponse:
    cmd = [
        self.cli_command, "-p", prompt,
        "--output-format", "json",
        "--model", model or self.default_model,
        "--print",
    ]
    if json_schema:
        cmd.extend(["--json-schema", json.dumps(json_schema)])
    if self.max_budget_usd:
        cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(),
        timeout=self.timeout
    )

    if proc.returncode != 0:
        raise LLMProviderError(f"CLI failed: {stderr.decode()}")

    return self._parse_response(stdout.decode())
```

### Prompt Management

Prompts stored as Jinja2 templates in `backend/app/services/summarizer/prompts/`:

```
├── summarize_section_v1.txt
├── summarize_book_v1.txt
├── quick_summary_v1.txt
├── detect_structure_v1.txt
├── caption_image_v1.txt
├── eval_faithfulness_v1.txt
├── eval_completeness_v1.txt
├── eval_coherence_v1.txt
├── eval_specificity_v1.txt
├── eval_format_v1.txt
└── discover_references_v1.txt
```

**Phase 2 prompt** (`discover_references_v1.txt`):

```jinja2
Search the web for existing summaries and reviews of "{{ book_title }}" by {{ book_author }}.

Find 4-5 high-quality external references. Prioritize (in order):
1. Dedicated summary services: Shortform, Blinkist, getAbstract
2. Notable reviewer blogs: Nat Eliason, Derek Sivers, Farnam Street
3. Publisher/author summaries
4. Quality blog posts with substantive reviews
5. Academic reviews (for technical/academic books)

Do NOT include: Amazon reviews, SEO-generated summaries, affiliate marketing content.

For each reference, return: url, title, source_name, snippet (1-2 sentences).
Output as JSON array.
```

### Processing Cost Estimates (Reference)

Approximate Claude API cost per book (via CLI subscription):

| Operation | Model | Typical Cost (300-page book) |
|-----------|-------|------------------------------|
| Quick summary (single-pass) | Sonnet | ~$0.30-0.80 |
| Section summarization (15 sections) | Sonnet | ~$1.00-2.50 |
| Eval assertions (16 x 15 sections) | Sonnet | ~$1.50-3.00 |
| Book-level summary | Sonnet | ~$0.20-0.50 |
| Image captioning (10 images) | Sonnet | ~$0.50-1.00 |
| **Total (full pipeline)** | **Sonnet** | **~$3.50-8.00** |

*Note: Costs are approximate. Embedding via Ollama is free (local).*

Conventions:
- Version as `{purpose}_v{N}.txt`
- Each summary records which prompt version generated it
- Old versions kept for reproducibility

### Partial Processing Recovery

If summarization fails midway (e.g., on section 7 of 12):

1. Sections 1-6 retain completed summaries
2. Section 7 marked as `summary_failed` with error
3. Sections 8-12 remain `summary_pending`
4. `bookcompanion summarize <book_id>` resumes from first pending/failed section
5. `bookcompanion summarize <book_id> --force` re-summarizes all sections
6. Book-level summary generated only after all sections complete

---

## 8. Quality Evaluation (Evals)

### Approach: Full Binary Assertion Battery with Trace Storage

All 16 assertions run for every section summary. Each assertion is a separate LLM call. Full traces (prompt + response + metadata) stored in `eval_traces` table for dataset building.

### Assertion Battery

**Faithfulness (Critical — auto-regenerate on failure):**

| Assertion | Description | Prompt Approach |
|-----------|-------------|-----------------|
| `no_hallucinated_facts` | Summary contains no claims absent from source | Send source + summary, ask LLM to identify any unsupported claims |
| `no_contradictions` | Summary doesn't contradict source | Send source + summary, ask LLM to identify contradictions |
| `accurate_quotes` | Quoted passages match source verbatim | Extract quotes from summary, fuzzy-match against source text |
| `cross_summary_consistency` | Two independently generated summaries don't diverge significantly | Generate a second summary variant, ask LLM to compare for divergences |

**Completeness (Important — flag for review):**

| Assertion | Description |
|-----------|-------------|
| `covers_main_argument` | Summary captures the section's primary thesis |
| `covers_key_concepts` | All major concepts from source appear |
| `covers_frameworks` | Frameworks/models in source are reflected |
| `covers_examples` | Key supporting examples referenced |

**Coherence (Advisory — log only):**

| Assertion | Description |
|-----------|-------------|
| `standalone_readable` | Summary makes sense without reading source |
| `logical_flow` | Ideas follow a logical progression |
| `no_dangling_references` | No unresolvable "above"/"below" references |

**Specificity (Important — flag for review):**

| Assertion | Description |
|-----------|-------------|
| `not_generic` | Contains details specific to THIS book/section |
| `preserves_author_terminology` | Uses author's key terms, not generic paraphrasing |

**Format (Advisory):**

| Assertion | Description |
|-----------|-------------|
| `has_key_concepts` | Contains a key concepts section |
| `reasonable_length` | Length within target compression ratio (±20% tolerance) |
| `image_refs_preserved` | Referenced images from source noted in summary |

### Evaluation Flow

```
Summary Generated
    ├── Run all 16 assertions in parallel (concurrent LLM calls)
    ├── Store each assertion result + full trace in eval_traces table
    ├── Store aggregated results in book_sections.summary_eval JSON
    │
    ├── Any Critical assertion failed?
    │   └── Yes → Auto-regenerate summary (up to 2 retries)
    │         → Retry with adjusted prompt: "Previous summary had issue: {failure_reason}"
    │         → If still failing after retries: mark as failed, log, continue
    │
    ├── Any Important assertion failed?
    │   └── Yes → Flag for user review (show in CLI with failure details)
    │
    └── Advisory failures → Log, display as quality indicators
```

### Eval Assertion Prompt Template

Example for `no_hallucinated_facts`:

```jinja2
You are evaluating the faithfulness of a book summary.

## Source Text
{{ source_text }}

## Summary
{{ summary_text }}

## Task
Carefully compare the summary against the source text. Identify any claims, facts, statistics, or statements in the summary that are NOT supported by the source text.

If the summary is faithful (all claims supported by source): respond with {"passed": true, "reasoning": "All claims in the summary are supported by the source text."}

If the summary contains unsupported claims: respond with {"passed": false, "reasoning": "The summary claims [specific claim] but the source text [what source actually says].", "unsupported_claims": ["claim1", "claim2"]}
```

### Eval Trace Storage

Every eval assertion call stores a full trace:

```python
EvalTrace(
    section_id=section.id,
    assertion_name="no_hallucinated_facts",
    assertion_category="critical",
    passed=True,
    prompt_sent=rendered_prompt,  # Full rendered Jinja2 template
    prompt_version="eval_faithfulness_v1",
    llm_response=raw_response,  # Full LLM output
    reasoning=parsed_reasoning,
    model_used="sonnet",
    input_tokens=response.input_tokens,
    output_tokens=response.output_tokens,
    latency_ms=response.latency_ms,
)
```

This dataset enables:
- Analyzing which assertions fail most frequently
- Identifying patterns in failures (e.g., certain book types)
- Calibrating eval prompts against human judgments
- Building a golden dataset for automated eval testing

### Eval Development Harness

```bash
# Compare summaries at different compression ratios
bookcompanion eval compare --book <id> --section <id> --ratios 10,20,30

# Show full eval results for a section
bookcompanion eval <book_id> <section_id>

# Show eval trace details for debugging
bookcompanion eval trace <book_id> <section_id> --assertion no_hallucinated_facts
```

### Human Evaluation Baseline

Referenced as a separate activity (not detailed in this spec):
- Read 20-30 generated summaries manually before automating
- Curate 10-15 chapters as golden test corpus (from public domain books)
- Calibrate LLM judge at >80% agreement with human annotations
- Re-validate every 5-10 prompt iterations

---

## 9. Search

### Hybrid Search: BM25 + Semantic + Reciprocal Rank Fusion

Implemented from Phase 1 using PostgreSQL tsvector (BM25) and pgvector (semantic).

### Indexed Content Types (Phase 1)

| Source Type | Content Indexed | When Indexed |
|-------------|----------------|--------------|
| `book_title` | Book title + author names | On book creation |
| `book_summary` | Book-level summary (chunked) | After book summary generated |
| `section_title` | Section titles | After parsing |
| `section_content` | Original content (chunked ~512 tokens, 50 overlap) | After parsing |
| `section_summary` | Section summaries (chunked) | After summarization |

Phase 2 adds: `concept` (term + definition), `annotation` (note + selected text).

### Embedding Generation

```python
class EmbeddingService:
    """Generates embeddings via local Ollama."""

    def __init__(self, ollama_url: str = "http://localhost:11434",
                 model: str = "nomic-embed-text"):
        self.ollama_url = ollama_url
        self.model = model

    async def embed_text(self, text: str) -> list[float]:
        """Single text → 768-dim vector via Ollama API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.model, "prompt": text}
            )
            return response.json()["embedding"]

    async def chunk_and_embed(self, text: str, chunk_size: int = 512,
                               overlap: int = 50) -> list[tuple[str, list[float]]]:
        """Split text into overlapping chunks, embed each."""
        chunks = self._split_into_chunks(text, chunk_size, overlap)
        embeddings = await asyncio.gather(
            *[self.embed_text(chunk) for chunk in chunks]
        )
        return list(zip(chunks, embeddings))
```

### Search Query Flow

```python
async def search(self, query: str, book_id: int | None = None,
                 source_types: list[SourceType] | None = None,
                 limit: int = 20) -> GroupedSearchResults:
    # 1. Generate query embedding
    query_embedding = await self.embedding_service.embed_text(query)

    # 2. BM25 search via tsvector
    bm25_query = func.plainto_tsquery("english", query)
    bm25_results = await self._bm25_search(bm25_query, book_id, source_types, limit * 2)

    # 3. Semantic search via pgvector
    semantic_results = await self._semantic_search(query_embedding, book_id, source_types, limit * 2)

    # 4. Reciprocal Rank Fusion
    fused = self._rrf_merge(bm25_results, semantic_results, k=self.config.search.rrf_k)

    # 5. Return top-K grouped by source type
    return self._group_results(fused[:limit])
```

**RRF formula:**
```
RRF_score(doc) = 1/(k + rank_bm25) + 1/(k + rank_semantic)
```
where `k=60`.

### Search Result Format

```python
@dataclass
class SearchResult:
    source_type: SourceType
    source_id: int
    book_id: int
    book_title: str
    section_title: str | None
    chunk_text: str
    score: float
    highlight: str  # Snippet with match context

@dataclass
class GroupedSearchResults:
    """Results grouped by book for CLI display. Each book group contains
    top 2-3 results with 'and N more...' collapse."""
    query: str
    books: dict[int, list[SearchResult]]  # book_id → results for that book
    total_count: int
```

### Embedding Lifecycle

| Event | Action |
|-------|--------|
| Book parsed | Embed section titles + section content chunks |
| Summary generated | Embed summary chunks |
| Summary regenerated | Delete old summary embeddings, create new |
| Book re-imported | Delete all embeddings, re-embed everything |
| Book deleted | Delete all embeddings (cascading) |

---

## 10. CLI Interface

### Installation

```bash
# From project directory
uv tool install .

# Verify
bookcompanion --version
bookcompanion --help
```

After `uv tool install`, `bookcompanion` is available globally in the terminal.

### Phase 1 Commands

```bash
# === Book Management ===
bookcompanion add <file_path>              # Upload + parse (step-by-step: user reviews TOC)
bookcompanion add <file_path> --quick      # Parse + generate rough book summary (~2 min)
bookcompanion add <file_path> --async      # Parse + summarize + embed (background process)
bookcompanion list                          # List all books (table: ID, title, author, status, sections)
bookcompanion list --recent                 # Sort by last accessed
bookcompanion show <book_id>                # Book details + section list + eval summary
bookcompanion delete <book_id>              # Cascade delete with confirmation prompt

# === Reading & Summaries ===
bookcompanion read <book_id> [section_id]   # Read original content (paged via rich)
bookcompanion read <book_id> <section_id> --with-summary  # Side-by-side content + summary
bookcompanion summary <book_id>             # Book-level summary (falls back to quick_summary)
bookcompanion summary <book_id> <section_id> # Section summary
bookcompanion summary <book_id> --copy      # Copy to clipboard
bookcompanion summary <book_id> --export <file.md>  # Export to file
bookcompanion summarize <book_id>           # Trigger full section-level summarization
bookcompanion summarize <book_id> <section_id>  # Re-summarize specific section
bookcompanion summarize <book_id> --force   # Re-summarize all sections
bookcompanion summarize <book_id> <section_id> --detail detailed  # Higher compression

# === Search ===
bookcompanion search "query"                # Hybrid search across all books
bookcompanion search "query" --book <id>    # Search within a book
bookcompanion search "query" --source <type>  # Filter: content|summary

# === Authors ===
bookcompanion authors                       # List all authors with book counts

# === Processing & Evaluation ===
bookcompanion status <book_id>              # Processing status + progress
bookcompanion eval <book_id> [section_id]   # Show eval results
bookcompanion eval compare --book <id> --section <id> --ratios 10,20,30
bookcompanion eval trace <book_id> <section_id> --assertion <name>

# === Configuration ===
bookcompanion config                        # Show current config
bookcompanion config set <key> <value>      # Set config value
bookcompanion init                          # First-time setup

# === Output Modifiers (available on most commands) ===
--format json                               # JSON output for piping
--no-pager                                  # Disable paging
--verbose                                   # Increase log output
```

### Phase 2 Commands (Additional)

```bash
# === Annotations ===
bookcompanion annotate <book_id> <section_id> --text "..." --note "..." --tag "..."
bookcompanion annotate <book_id> <section_id> --note "..." --type freeform  # Freeform note
bookcompanion annotate <book_id> <section_id> --link-to <annotation_id>     # Cross-book link
bookcompanion annotations <book_id>         # List annotations for a book
bookcompanion annotations --tag <tag>       # List by tag across all books

# === Tags ===
bookcompanion tag <book_id> <tag_name>      # Add tag to book
bookcompanion tags                          # List all tags

# === Concepts ===
bookcompanion concepts <book_id>            # Show concepts index
bookcompanion concepts search "term"        # Search concepts across all books
bookcompanion concepts edit <book_id>       # Edit concepts in $EDITOR (marks as user_edited)

# === External References ===
bookcompanion references <book_id>          # List external references
bookcompanion discover-references <book_id> # Run/re-run external discovery

# === Search (Phase 2 additions) ===
bookcompanion search "query" --tag <tag>    # Filter by tag
bookcompanion search "query" --annotations-only  # Search only annotations/notes

# === Eval (Phase 2 additions) ===
bookcompanion eval compare-prompts --book <id> --section <id> --prompt-a v1 --prompt-b v2

# === Metadata Editing ===
bookcompanion edit <book_id> --title "..." --author "..."
bookcompanion edit-summary <book_id> [section_id]  # Edit in $EDITOR

# === Export & Backup ===
bookcompanion export [--format json|markdown] [--output /path]
bookcompanion export <book_id> [--format json|markdown]
bookcompanion backup [--output path]
bookcompanion restore <backup_file>
bookcompanion backup list
```

### CLI Output Formatting

| Output Type | Implementation |
|-------------|---------------|
| Long content (read, summary) | `rich.Markdown` + system pager (`$PAGER` or `less`) |
| Side-by-side view | `rich.Columns` (wide terminal) or stacked `rich.Panel` (narrow) |
| Tables (list, search, annotations) | `rich.Table` |
| Progress (summarize) | `rich.Progress` with per-section granularity + ETA |
| Search results | Grouped by book, top 2-3 per book, "and N more..." collapse |
| Markdown rendering | `rich.Markdown` with syntax highlighting |

### Step-by-Step Flow Example

```
$ bookcompanion add ~/books/art-of-war.epub

Parsing "art-of-war.epub"...
Title: "The Art of War"
Author(s): Sun Tzu
Format: EPUB

Detected structure (13 sections) via embedded TOC:
  1. Introduction
  2. I. Laying Plans
  3. II. Waging War
  ...
  13. XIII. The Use of Spies

Accept this structure? [Y/n]: y

Book saved (ID: 1). 13 sections parsed and stored.
Embeddings generated for 13 sections (47 chunks).
Run `bookcompanion summarize 1` to generate summaries.
```

### Empty States

| Scenario | CLI Output |
|----------|-----------|
| No books in library | `No books in your library yet. Run: bookcompanion add <file_path>` |
| No search results | `No results found for "{query}". Try a broader search term.` |
| No summary available | `No summary for this section yet. Run: bookcompanion summarize <book_id>` |
| No eval results | `No eval results. Summaries must be generated first.` |
| Processing not started | `Book parsed but not yet summarized. Run: bookcompanion summarize <book_id>` |

### First-Time User Experience

```
$ bookcompanion init

Checking dependencies...
  ✓ Docker: v27.1.0
  ✓ Ollama: running at http://localhost:11434
  ✓ ebook-convert: Calibre 7.x
  ✓ Claude Code CLI: claude → Claude Code v2.1.x

Starting PostgreSQL container...
  ✓ PostgreSQL 16 + pgvector: running on port 5438

Running database migrations...
  ✓ 1 migration applied

Pulling embedding model...
  ✓ nomic-embed-text: ready

Configuration saved to: ~/.config/bookcompanion/config.yaml

Setup complete! Here's how to get started:

  1. Add your first book:    bookcompanion add ~/path/to/book.epub
  2. Quick overview:         bookcompanion add --quick ~/path/to/book.epub
  3. Full summarization:     bookcompanion summarize <book_id>
  4. Browse your library:    bookcompanion list
  5. Search across books:    bookcompanion search "query"

Run `bookcompanion --help` for all commands.
```

### CLI Command Reference (Help Documentation)

This section provides the complete help output for each command, enabling coding agents to understand all available flags and options during development and testing.

#### `bookcompanion` (root)

```
Usage: bookcompanion [OPTIONS] COMMAND [ARGS]...

  Book Companion - Personal book summarization and knowledge extraction tool.

Options:
  --version          Show version and exit.
  --verbose          Enable verbose (DEBUG) logging.
  --format TEXT      Output format: text (default) or json.
  --no-pager         Disable pager for long output.
  --help             Show this message and exit.

Commands:
  add          Upload and parse a book file.
  annotate     Create an annotation on a book section. (Phase 2)
  annotations  List annotations. (Phase 2)
  backup       Create or list database backups. (Phase 2)
  concepts     Show or search concepts index. (Phase 2)
  config       View or set configuration values.
  delete       Delete a book and all related data.
  discover-references  Search web for external summaries/reviews. (Phase 2)
  edit         Edit book metadata or section structure. (Phase 2)
  edit-summary Edit a summary in $EDITOR. (Phase 2)
  eval         Show or compare evaluation results.
  export       Export library data. (Phase 2)
  init         First-time setup: database, migrations, dependencies.
  list         List all books in the library.
  read         Read original book content.
  references   List external summary/review references. (Phase 2)
  restore      Restore database from backup. (Phase 2)
  search       Search across all books (hybrid BM25 + semantic).
  show         Show book details and section list.
  status       Show processing status for a book.
  summarize    Generate or regenerate summaries.
  summary      Display a book or section summary.
  tag          Add a tag to a book. (Phase 2)
  tags         List all tags. (Phase 2)
```

#### `bookcompanion init`

```
Usage: bookcompanion init [OPTIONS]

  First-time setup: start PostgreSQL container, run migrations, verify
  dependencies, pull embedding model.

Options:
  --database-url TEXT  Override database URL (default: from config or
                       postgresql://bookcompanion:bookcompanion@localhost:5438/bookcompanion)
  --help               Show this message and exit.

Steps performed:
  1. Check/create config file at ~/.config/bookcompanion/config.yaml
  2. Verify system dependencies (Docker, Ollama, Calibre, Claude Code CLI)
  3. Start PostgreSQL Docker container if not running
  4. Run Alembic migrations
  5. Pull Ollama embedding model (nomic-embed-text)
  6. Run health check
  7. Print getting-started guide
```

#### `bookcompanion add`

```
Usage: bookcompanion add [OPTIONS] FILE_PATH

  Upload and parse a book file (EPUB, MOBI, or PDF).

  Default (step-by-step): Parses book, detects structure, asks user to
  review and accept/reject the detected TOC, then stores in database.

Arguments:
  FILE_PATH  Path to the book file. [required]

Options:
  --quick    Parse + generate a rough book-level summary in ~2 minutes.
             Skips section-level summarization, evals, and concepts extraction.
  --async    Parse + summarize + embed in background. Auto-accepts detected
             structure. Returns immediately with book ID.
  --force    Two uses: (1) Re-import even if duplicate detected (replaces
             content, marks summaries stale). (2) Retry a previously failed
             parse (overwrite parse_failed book).
  --help     Show this message and exit.

Supported formats: .epub, .mobi, .pdf
Maximum file size: 200 MB (configurable via storage.max_file_size_mb)
```

#### `bookcompanion list`

```
Usage: bookcompanion list [OPTIONS]

  List all books in the library.

Options:
  --recent         Sort by most recently accessed.
  --tag TEXT        Filter by tag name. (Phase 2)
  --author TEXT     Filter by author name (partial match).
  --status TEXT     Filter by status: uploading, parsing, parsed, summarizing,
                    completed, parse_failed.
  --help            Show this message and exit.

Output columns: ID, Title, Author(s), Status, Sections, Created
```

#### `bookcompanion show`

```
Usage: bookcompanion show [OPTIONS] BOOK_ID

  Show book details: metadata, section list with summaries status, eval
  summary, and processing status.

Arguments:
  BOOK_ID  Book ID. [required]

Options:
  --help  Show this message and exit.
```

#### `bookcompanion read`

```
Usage: bookcompanion read [OPTIONS] BOOK_ID [SECTION_ID]

  Read original book content. If SECTION_ID is omitted, shows the full book
  content (all sections concatenated).

Arguments:
  BOOK_ID     Book ID. [required]
  SECTION_ID  Section ID. If omitted, shows all sections.

Options:
  --with-summary  Show content and summary side-by-side (or stacked on
                  narrow terminals).
  --copy          Copy content to clipboard.
  --export FILE   Export content to a file.
  --help          Show this message and exit.
```

#### `bookcompanion summary`

```
Usage: bookcompanion summary [OPTIONS] BOOK_ID [SECTION_ID]

  Display a book-level or section-level summary. If no summary is available,
  falls back to quick_summary (if exists).

Arguments:
  BOOK_ID     Book ID. [required]
  SECTION_ID  Section ID. If omitted, shows book-level summary.

Options:
  --copy          Copy summary to clipboard.
  --export FILE   Export summary to a Markdown file.
  --help          Show this message and exit.
```

#### `bookcompanion summarize`

```
Usage: bookcompanion summarize [OPTIONS] BOOK_ID [SECTION_ID]

  Generate or regenerate summaries via LLM. If SECTION_ID is provided,
  summarizes only that section. Otherwise, summarizes all pending/failed
  sections and generates book-level summary.

Arguments:
  BOOK_ID     Book ID. [required]
  SECTION_ID  Section ID. If omitted, processes all sections.

Options:
  --force              Re-summarize all sections, even completed ones.
  --detail TEXT        Detail level: brief, standard (default), detailed.
  --model TEXT         Override model for this run (e.g., opus, sonnet).
  --skip-eval          Skip eval assertions (faster, no quality checks).
  --help               Show this message and exit.

Behavior:
  - Resumes from first pending/failed section (skips completed)
  - Runs all 16 eval assertions per section (unless --skip-eval)
  - Auto-retries on critical eval failures (up to 2 retries)
  - Generates book-level summary after all sections complete
  - Shows progress bar with per-section status and ETA
```

#### `bookcompanion search`

```
Usage: bookcompanion search [OPTIONS] QUERY

  Hybrid search (BM25 + semantic + RRF) across all books.

Arguments:
  QUERY  Search query text. [required]

Options:
  --book INTEGER       Search within a specific book only.
  --source TEXT        Filter by source type: content, summary, title,
                       concept, annotation. Can be specified multiple times.
  --limit INTEGER      Maximum results (default: 20).
  --help               Show this message and exit.

Output: Results grouped by book, showing source type, snippet with
highlighted match, book title, and section context.
```

#### `bookcompanion delete`

```
Usage: bookcompanion delete [OPTIONS] BOOK_ID

  Delete a book and ALL related data (sections, summaries, annotations,
  embeddings, eval traces, processing jobs).

Arguments:
  BOOK_ID  Book ID. [required]

Options:
  --yes    Skip confirmation prompt.
  --help   Show this message and exit.
```

#### `bookcompanion status`

```
Usage: bookcompanion status [OPTIONS] BOOK_ID

  Show processing status for a book: current step, progress per section,
  eval results so far, estimated time remaining.

Arguments:
  BOOK_ID  Book ID. [required]

Options:
  --help  Show this message and exit.
```

#### `bookcompanion eval`

```
Usage: bookcompanion eval [OPTIONS] BOOK_ID [SECTION_ID]

  Show evaluation results. If SECTION_ID is provided, shows detailed
  per-assertion results. Otherwise, shows summary across all sections.

Arguments:
  BOOK_ID     Book ID. [required]
  SECTION_ID  Section ID for detailed results.

Options:
  --help  Show this message and exit.

Subcommands:
  compare   Compare summaries at different compression ratios.
  trace     Show full eval trace for a specific assertion.
```

#### `bookcompanion eval compare`

```
Usage: bookcompanion eval compare [OPTIONS]

  Generate and compare summaries at multiple compression ratios for the
  same section. Displays assertion results side-by-side.

Options:
  --book INTEGER     Book ID. [required]
  --section INTEGER  Section ID. [required]
  --ratios TEXT      Comma-separated ratios (default: "10,20,30").
  --help             Show this message and exit.
```

#### `bookcompanion eval trace`

```
Usage: bookcompanion eval trace [OPTIONS] BOOK_ID SECTION_ID

  Show full evaluation trace for a specific assertion, including the
  prompt sent, LLM response, reasoning, and metadata.

Arguments:
  BOOK_ID     Book ID. [required]
  SECTION_ID  Section ID. [required]

Options:
  --assertion TEXT  Assertion name (e.g., no_hallucinated_facts). [required]
  --help            Show this message and exit.
```

#### `bookcompanion authors`

```
Usage: bookcompanion authors [OPTIONS]

  List all authors in the library with their book counts.

Options:
  --help  Show this message and exit.

Output columns: Author Name, Book Count, Book Titles
```

#### `bookcompanion config`

```
Usage: bookcompanion config [OPTIONS] [COMMAND]

  View or modify configuration.

  Without arguments: displays current configuration.

Subcommands:
  set   Set a configuration value.

Options:
  --help  Show this message and exit.
```

#### `bookcompanion config set`

```
Usage: bookcompanion config set [OPTIONS] KEY VALUE

  Set a configuration value. Uses dot notation for nested keys.

Arguments:
  KEY    Config key in dot notation (e.g., llm.model, search.rrf_k).
  VALUE  New value.

Options:
  --help  Show this message and exit.

Examples:
  bookcompanion config set llm.cli_command "claude-personal"
  bookcompanion config set llm.model "opus"
  bookcompanion config set summarization.default_detail_level "detailed"
  bookcompanion config set embedding.model "nomic-embed-text"
```

#### Phase 2 Commands (Brief Reference)

```
bookcompanion annotate BOOK_ID SECTION_ID  Create annotation
  --text TEXT          Highlighted text passage
  --note TEXT          Annotation note
  --tag TEXT           Tag name (repeatable)
  --type TEXT          highlight | note | freeform (default: note)
  --link-to INTEGER    Link to another annotation by ID
  --content-type TEXT  section_content | section_summary | book_summary

bookcompanion annotations [BOOK_ID]       List annotations
  --tag TEXT           Filter by tag
  --type TEXT          Filter by type

bookcompanion tag BOOK_ID TAG_NAME        Add tag to book
bookcompanion tags                        List all tags

bookcompanion concepts BOOK_ID            Show concepts index for a book
bookcompanion concepts search TERM        Search concepts across all books

bookcompanion references BOOK_ID          List external references
bookcompanion discover-references BOOK_ID Run external discovery

bookcompanion edit BOOK_ID                Edit book metadata
  --title TEXT         New title
  --author TEXT        New author

bookcompanion edit-summary BOOK_ID [SECTION_ID]  Edit in $EDITOR

bookcompanion export [BOOK_ID]            Export library data
  --format TEXT        json | markdown (default: json)
  --output PATH        Output directory

bookcompanion backup [--output PATH]      Create database backup
bookcompanion backup list                 List available backups
bookcompanion restore BACKUP_FILE         Restore from backup
```

---

## 11. Configuration & Operations

### Config File Location

Following XDG Base Directory Specification:

- **Primary**: `~/.config/bookcompanion/config.yaml`
- **Fallback**: `~/.bookcompanion/config.yaml`
- **Override**: `BOOKCOMPANION_CONFIG` environment variable

### Configuration Schema

```yaml
# ~/.config/bookcompanion/config.yaml

database:
  url: "postgresql://bookcompanion:bookcompanion@localhost:5438/bookcompanion"

llm:
  provider: "claude_cli"                # Active provider: claude_cli (only option in V1)
  cli_command: "claude"                 # Claude Code CLI command/alias
  model: "sonnet"                       # Default model for summarization + evals
  quick_summary_model: "sonnet"         # Model for quick summary mode
  timeout_seconds: 300                  # Per-operation timeout
  max_retries: 2                        # Auto-retry on critical eval failures
  max_budget_usd: 5.0                  # Per-book budget cap (passed as --max-budget-usd to CLI)
  cross_summary_consistency: true       # Enable cross-summary faithfulness check (doubles cost for that assertion)

summarization:
  default_detail_level: "standard"      # brief | standard | detailed
  prompt_version: "v1"                  # Active prompt version
  eval_prompt_version: "v1"             # Active eval prompt version

embedding:
  ollama_url: "http://localhost:11434"
  model: "nomic-embed-text"
  chunk_size: 512                       # Tokens per embedding chunk
  chunk_overlap: 50                     # Token overlap between chunks

search:
  rrf_k: 60                            # RRF constant
  default_limit: 20                    # Default results per query

storage:
  max_file_size_mb: 200                # Maximum book file size

logging:
  level: "INFO"                        # DEBUG | INFO | WARNING | ERROR
  log_dir: "~/.config/bookcompanion/logs/"
  json_format: true
  rotation: "daily"
```

### Configuration Loading (via pydantic-settings)

Priority (highest to lowest):
1. CLI flags (e.g., `--model opus`)
2. Environment variables (prefix `BOOKCOMPANION_`, e.g., `BOOKCOMPANION_LLM__MODEL`)
3. Config file values
4. Hardcoded defaults

### Logging (structlog)

```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
```

- **Log levels**: DEBUG (parser details), INFO (milestones), WARNING (eval failures), ERROR (crashes)
- **Log location**: `~/.config/bookcompanion/logs/` with daily rotation
- **Per-book processing log**: Structured entries in processing_jobs + log files
- **CLI verbosity**: `--verbose` increases to DEBUG

---

## 12. Error Handling, Security & Non-Functional Requirements

### Error Handling & Recovery

| Failure Scenario | Behavior | Recovery |
|-----------------|----------|----------|
| **Parse failure** (corrupted file, unsupported content) | Mark book as `parse_failed`, log error with details | `bookcompanion add <file> --force` to retry |
| **Structure detection failure** (no TOC, heuristics fail) | Fall through to LLM tier. If LLM also fails, create single flat section with all content | User can re-import or manually accept flat structure |
| **MOBI conversion failure** (Calibre error) | Log error, suggest user convert manually or try different file | Provide error message with Calibre version info |
| **Summarization timeout** (Claude CLI >300s) | Mark section as `summary_failed`, log timeout | `bookcompanion summarize <book_id>` resumes from failed section |
| **Summarization LLM error** (CLI crash, rate limit) | Mark section as `summary_failed`, store error | Auto-resume on next `summarize` call. Exponential backoff not needed (user-triggered) |
| **Critical eval failure** (faithfulness) | Auto-retry summary with adjusted prompt (up to 2x) | If still failing: mark `summary_failed`, user can retry with `--detail detailed` |
| **Embedding failure** (Ollama down) | Log error, skip embedding step | `bookcompanion summarize <book_id>` re-runs embedding for un-embedded content |
| **DB connection failure** | Immediate error with connection details | Check Docker container: `docker compose ps` |
| **Background process crash** (async mode) | Process exits, PID removed. Job stays `running` in DB | `bookcompanion status` detects orphaned job (PID no longer running), marks as `failed` |
| **Disk full during BLOB storage** | Transaction rollback, error message | Free disk space, retry |

### Orphan Process Detection

On every CLI invocation, check for orphaned background processes:
1. Query `processing_jobs` for status `running`
2. For each, check if PID is still alive: `os.kill(pid, 0)`
3. If PID dead: mark job as `failed` with error "Process terminated unexpectedly"

### Security Considerations

| Concern | Mitigation |
|---------|-----------|
| **File upload validation** | Verify magic bytes match claimed format. Enforce max file size (200MB configurable). Reject files that fail format detection. |
| **CLI command injection** | `subprocess.run()` with list args (no `shell=True`). Prompt content passed via stdin, not interpolated into command string. CLI alias from config, not user input. |
| **SQL injection** | SQLAlchemy ORM with parameterized queries. No raw SQL string interpolation. |
| **Path traversal** | File paths from uploads sanitized via `Path.resolve()`. Backup/restore paths validated. |
| **Resource exhaustion** | Configurable timeouts on all external calls. Max file size limit. Background process count limited to 1 per book. |

### Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Book parsing (300-page EPUB) | < 2 minutes | Excluding image captioning |
| Section summarization | 30-60 seconds per section | Dependent on Claude Code CLI |
| Quick summary | ~2 minutes total | Single-pass for under-context-limit books |
| Hybrid search | < 500ms | pgvector HNSW + tsvector GIN indexes |
| Embedding generation (per chunk) | < 1 second | Local Ollama |
| CLI startup time | < 500ms | To first output (excluding DB operations) |

### Storage Estimates (per book)

| Content | Size Estimate |
|---------|--------------|
| Original file (BLOB) | 1-50 MB |
| Extracted images | 5-100 MB |
| Markdown content | 200 KB - 2 MB |
| Summaries | 50-500 KB |
| Eval traces | 100 KB - 1 MB (16 assertions x response text) |
| Embeddings | ~50 KB (768-dim vectors) |
| **Total per book** | **~10-150 MB** |

For ~100 books: **1-15 GB total** — within single PostgreSQL capacity.

### Data Integrity

- All processing is idempotent — re-running summarization replaces existing summaries
- Database transactions for multi-step operations (e.g., re-import)
- `processing_jobs` table tracks state for retry on failure
- Full backup via `pg_dump` (single Postgres with all data)

---

## 13. Infrastructure & Deployment

### Docker Compose (PostgreSQL only)

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    ports:
      - "5438:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: bookcompanion
      POSTGRES_USER: bookcompanion
      POSTGRES_PASSWORD: bookcompanion
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bookcompanion"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

### Port Assignment

| Service | Port | Rationale |
|---------|------|-----------|
| PostgreSQL | 5438 | Avoids conflict with host PG (5432) and other projects |
| Ollama | 11434 (host) | Already running, no container needed |

### System Dependencies

| Dependency | Required For | Verification |
|-----------|-------------|--------------|
| Docker + Docker Compose | PostgreSQL container | `docker --version` |
| Ollama | Local embeddings | `curl http://localhost:11434/api/tags` |
| Calibre (ebook-convert) | MOBI support | `ebook-convert --version` |
| Claude Code CLI | LLM summarization/eval | `claude --version` |
| Python 3.12+ | Backend runtime | `python3 --version` |
| uv | Package management | `uv --version` |

### Project Structure

```
book-companion/
├── backend/
│   ├── pyproject.toml                  # Python project config (uv)
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                   # Settings (pydantic-settings)
│   │   ├── db/
│   │   │   ├── models.py              # SQLAlchemy ORM models
│   │   │   ├── session.py             # DB session management
│   │   │   └── repositories/          # Data access layer
│   │   │       ├── book_repo.py
│   │   │       ├── section_repo.py
│   │   │       ├── search_repo.py
│   │   │       └── eval_repo.py
│   │   ├── services/
│   │   │   ├── book_service.py
│   │   │   ├── parser/
│   │   │   │   ├── base.py
│   │   │   │   ├── epub_parser.py
│   │   │   │   ├── pdf_parser.py
│   │   │   │   └── mobi_parser.py
│   │   │   ├── summarizer/
│   │   │   │   ├── base.py            # LLMProvider interface
│   │   │   │   ├── claude_cli.py
│   │   │   │   ├── prompts/           # Jinja2 templates
│   │   │   │   └── evaluator.py
│   │   │   ├── search_service.py
│   │   │   ├── embedding_service.py
│   │   │   └── annotation_service.py  # Phase 2
│   │   └── cli/
│   │       ├── main.py                # Typer app entry point
│   │       └── commands/
│   │           ├── books.py
│   │           ├── summarize.py
│   │           ├── search.py
│   │           ├── eval.py
│   │           ├── config_cmd.py
│   │           └── annotations.py     # Phase 2
│   └── tests/
│       ├── conftest.py                # Shared fixtures
│       ├── fixtures/                  # Test book files
│       │   ├── sample_epub/
│       │   ├── sample_pdf/
│       │   └── golden_set/            # Human-evaluated samples
│       ├── unit/
│       │   ├── test_epub_parser.py
│       │   ├── test_pdf_parser.py
│       │   ├── test_summarizer.py
│       │   ├── test_search.py
│       │   └── test_evaluator.py
│       ├── integration/
│       │   ├── test_book_pipeline.py
│       │   ├── test_search_integration.py
│       │   └── test_db_operations.py
│       └── e2e/
│           └── test_cli_flows.py
├── docker-compose.yml
├── docs/
│   ├── 2026-04-01_initial_thoughts.txt
│   ├── requirements/
│   ├── specs/
│   └── wireframes/
├── .gitignore
└── CLAUDE.md
```

### Tech Stack Summary

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| CLI framework | Typer |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Settings | pydantic-settings |
| Package manager | uv |
| Database | PostgreSQL 16 + pgvector (Docker) |
| Embedding | Ollama (nomic-embed-text, local) |
| LLM | Claude Code CLI (subprocess) |
| EPUB parsing | ebooklib + markdownify |
| PDF parsing | marker-pdf (fallback: PyMuPDF) |
| MOBI parsing | Calibre ebook-convert |
| CLI output | rich |
| Logging | structlog |
| Prompt templates | Jinja2 |
| Linting/formatting | ruff |
| Type checking | mypy (strict) |
| Testing | pytest + pytest-asyncio |

---

## 14. Verification & Testing Plan

### Testing Strategy Overview

| Test Type | Scope | Tools | When to Run |
|-----------|-------|-------|-------------|
| Unit tests | Service functions, parsers, evaluator | pytest, pytest-asyncio | Every code change |
| Integration tests | DB operations, full pipelines, search | pytest + Docker Postgres | Before merge |
| E2E tests (CLI) | Full CLI command flows | pytest + typer.testing.CliRunner | Before release |
| Eval regression | Summary quality regression | Custom harness + golden books | On prompt changes |
| Linting | Code style, formatting | ruff check, ruff format --check | Every code change |
| Type checking | Type safety | mypy --strict | Every code change |

### Test Infrastructure

- **Test database**: Separate PostgreSQL in Docker (reuse same image, different port or database name)
- **Test fixtures**: Public domain books from Project Gutenberg (The Art of War, Meditations by Marcus Aurelius)
- **LLM mocking**: Mock the LLMProvider interface for unit tests. Use real CLI calls for integration/e2e tests (with small test content)
- **CI**: GitHub Actions running unit + integration + lint + type check on push

### Phase 1: Detailed Test Plan

#### 6.1 Book Parsing

**Unit Tests** (`test_epub_parser.py`, `test_pdf_parser.py`):

| Test | Description |
|------|-------------|
| `test_epub_parse_basic` | Parse sample EPUB, verify title, author, section count |
| `test_epub_parse_toc` | Verify TOC extraction produces correct section hierarchy |
| `test_epub_parse_images` | Verify image extraction (count, mime types, dimensions) |
| `test_epub_markdown_quality` | Verify HTML→Markdown conversion preserves headings, lists, emphasis |
| `test_pdf_parse_basic` | Parse sample PDF, verify title extraction |
| `test_pdf_parse_structure` | Verify heuristic structure detection on a known PDF |
| `test_mobi_conversion` | Verify MOBI→EPUB conversion produces valid EPUB |
| `test_format_detection` | Verify magic bytes validation (accept valid, reject fake extensions) |
| `test_sha256_hash` | Verify hash computation is deterministic |
| `test_duplicate_detection` | Upload same file twice, verify duplicate warning |
| `test_large_section_splitting` | Verify long sections are split at paragraph boundaries |

**Integration Tests** (`test_book_pipeline.py`):

| Test | Description |
|------|-------------|
| `test_full_epub_pipeline` | Upload EPUB → parse → store → verify DB state |
| `test_full_pdf_pipeline` | Upload PDF → parse → store → verify DB state |
| `test_re_import_preserves_data` | Re-import book, verify annotations/tags preserved, summaries marked stale |
| `test_delete_cascades` | Delete book, verify all related records removed |

#### 7.1 Summarization

**Unit Tests** (`test_summarizer.py`):

| Test | Description |
|------|-------------|
| `test_prompt_template_rendering` | Verify Jinja2 templates render with all variables |
| `test_cumulative_context_generation` | Verify cumulative context is compact and correct |
| `test_compression_ratio_calculation` | Verify ratio computation for different detail levels |
| `test_long_section_chunking` | Verify sub-chunking at paragraph boundaries |
| `test_cli_invocation_args` | Verify correct CLI args constructed (no shell injection) |
| `test_json_schema_validation` | Verify summary JSON output matches schema |
| `test_partial_recovery` | Verify resume skips completed sections |
| `test_quick_summary_mode` | Verify quick summary skips section-level processing |

**Integration Tests** (requires real Claude Code CLI):

| Test | Description |
|------|-------------|
| `test_summarize_single_section` | Summarize one section of test book, verify output structure |
| `test_summarize_full_book` | End-to-end summarization of small test book (3-4 sections) |
| `test_image_captioning` | Caption a test image via CLI, verify caption quality |
| `test_cli_timeout_handling` | Verify graceful timeout handling |

#### 8.1 Evaluation

**Unit Tests** (`test_evaluator.py`):

| Test | Description |
|------|-------------|
| `test_eval_prompt_rendering` | Verify all 16 assertion prompts render correctly |
| `test_eval_result_parsing` | Verify JSON response parsing for pass/fail |
| `test_eval_trace_storage` | Verify full trace stored in eval_traces table |
| `test_critical_failure_triggers_retry` | Verify auto-retry on critical assertion failure |
| `test_retry_limit_respected` | Verify max 2 retries, then mark as failed |
| `test_eval_aggregation` | Verify summary_eval JSON aggregates all assertion results |

#### 9.1 Search

**Unit Tests** (`test_search.py`):

| Test | Description |
|------|-------------|
| `test_text_chunking` | Verify overlapping chunk generation (size, overlap, boundaries) |
| `test_rrf_merge` | Verify RRF scoring with known rank inputs |
| `test_result_grouping` | Verify results grouped by source type |
| `test_search_filters` | Verify book_id and source_type filters |

**Integration Tests** (`test_search_integration.py`):

| Test | Description |
|------|-------------|
| `test_bm25_search` | Index content, search via tsvector, verify relevant results |
| `test_semantic_search` | Index content, search via embedding, verify relevant results |
| `test_hybrid_search` | Full hybrid search, verify RRF ranking improves over single method |
| `test_embedding_lifecycle` | Verify embeddings created/deleted at correct trigger points |
| `test_search_after_re_import` | Verify search works correctly after book re-import |

#### 10.1 CLI

**E2E Tests** (`test_cli_flows.py`):

| Test | Description |
|------|-------------|
| `test_init_command` | Run init, verify DB setup, config created |
| `test_add_book_step_by_step` | Add book with structure review (simulated input) |
| `test_add_book_quick` | Add with --quick, verify quick_summary generated |
| `test_list_books` | Add 2 books, verify list output |
| `test_show_book` | Verify book detail output format |
| `test_read_content` | Verify content rendering |
| `test_summary_output` | Verify summary rendering |
| `test_search_cli` | Verify search results formatting |
| `test_delete_with_confirmation` | Verify delete confirmation prompt |
| `test_status_command` | Verify processing status output |
| `test_json_output` | Verify --format json on key commands |
| `test_config_set` | Verify config set/get cycle |

### Verification Commands

```bash
# Run all tests
uv run pytest

# Run by category
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/e2e

# Run with coverage
uv run pytest --cov=app --cov-report=term-missing

# Linting + formatting
uv run ruff check .
uv run ruff format --check .

# Type checking
uv run mypy app/

# Full verification (CI-equivalent)
uv run ruff check . && uv run ruff format --check . && uv run mypy app/ && uv run pytest
```

### Test Fixtures

Public domain books for testing:

| Book | Format | Sections | Use Case |
|------|--------|----------|----------|
| The Art of War (Sun Tzu) | EPUB | 13 chapters | Standard test — short, well-structured |
| Meditations (Marcus Aurelius) | EPUB | 12 books | Standard test — philosophical, nested structure |
| The Republic (Plato) | PDF | 10 books | PDF parsing — dialogue format, complex structure |

These are sourced from Project Gutenberg and included in `tests/fixtures/`. Small enough to include in the repo without copyright issues.

---

## 15. Decision Log

| # | Decision | Options Considered | Choice | Rationale |
|---|----------|-------------------|--------|-----------|
| 1 | Runtime architecture | Backend in Docker / Backend on host / Hybrid | **Backend on host, Postgres in Docker** | Backend must invoke Claude Code CLI directly. Docker-to-host CLI bridging is too complex. |
| 2 | Phasing strategy | All V1 at once / 3-phase / 2-phase | **2-phase CLI-only** | Phase 1: core pipeline (parse+summarize+eval+search). Phase 2: annotations, concepts, refs. Web UI separate spec. |
| 3 | API layer | Include API / CLI only | **CLI only in this spec** | Shared service layer makes API easy to add later. No need to build unused API endpoints. |
| 4 | Success criteria | Book count / Journey completion / Quality metrics / Self-use | **Qualitative self-use** | Personal tool — success = weekly use replacing current reading workflow. |
| 5 | Frontend depth | Full spec / Wireframes / Separate doc / Minimal | **Separate design document** | Frontend hasn't been detailed enough. Will brainstorm and spec separately. |
| 6 | Image captioning | Defer / API direct / CLI / Skip | **Via Claude Code CLI** | CLI's Read tool natively handles images. --add-dir provides file access. No cloud API dependency. |
| 7 | CLI installation | uv run / uv tool install / pipx / alias | **uv tool install** | Global CLI availability for daily use. Best DX for personal tool. |
| 8 | Test fixtures | Public domain / Synthetic / Own books / CC | **Public domain** | Project Gutenberg books. Free, legal, but validate with modern non-fiction during human eval baseline. |
| 9 | Logging | Minimal / Simple file / structlog / Per-book | **structlog as specified** | JSON structured logging with daily rotation. Worth the setup for debugging LLM pipeline issues. |
| 10 | Eval scope | Core subset / All 16 / Configurable / Faithfulness only | **All 16 assertions** | Quality is paramount. Full battery provides comprehensive coverage. |
| 11 | Eval traces | Result only / Result+reasoning / Full traces | **Full traces** | Enables building datasets for prompt improvement and eval calibration. Store prompts + full LLM responses. |
| 12 | Cumulative context | Default on / Opt-in / Lightweight | **Default on** | Essential for coherent summaries. Prior context helps LLM reference earlier concepts without re-explaining. |
| 13 | Search | Hybrid / Semantic only / BM25 only | **Full hybrid from Phase 1** | Both tsvector and pgvector in Postgres — minimal infrastructure cost. Better search quality. |
| 14 | Testing detail | High-level / Per-feature / TDD list | **Detailed per-feature** | Each feature includes specific test cases. Developer knows exactly what to test. |
| 15 | External refs | Phase 1 / Phase 2 / Phase 3 | **Phase 2** | Nice-to-have, not core pipeline. |
| 16 | Cost tracking | Track / Estimate / Skip | **Skip** | Budget cap via CLI flag is sufficient. Don't add complexity for cost tracking. |
| 17 | Cross-book linking | Defer / CLI with IDs / Tags only | **CLI with annotation IDs** | `--link-to <anno_id>` allows linking. Users search/list to find target ID. |
| 18 | Section editing | Accept/reject only / Basic / Full | **Accept/reject only (Phase 1)** | If structure is wrong, re-run detection with different tier. Manual editing in Phase 2. |
| 19 | DB migrations | SQLAlchemy models / SQL DDL / ERD only | **SQLAlchemy models + strategy** | Models in spec, Alembic auto-generates migrations. Most practical approach. |
| 20 | Quick summary | Flag on add / Separate command / Both | **Flag on add** | `bookcompanion add --quick` for new books. Natural workflow. |
| 21 | PostgreSQL hosting | Docker only / Docker+host / Host only | **Docker only** | Consistent pgvector version. Simple docker-compose.yml with just DB service. |
| 22 | CLI profiles | Single+model flag / Multiple profiles / Single fixed | **Single profile, model flag** | One CLI alias, `--model` flag for per-operation model selection. |
| 23 | Async processing | multiprocessing / threading / daemon / nohup | **multiprocessing (fork)** | Survives terminal close. Status via DB polling. Simple, robust. |
| 24 | Spec structure | One spec phased / Separate per phase / Phase 1 detailed | **One spec, Phase 1+2** | Single document, features tagged by phase. No web UI in this spec. |
| 25 | Tag filtering phase | Phase 1 / Phase 2 | **Phase 2** | Tags are a Phase 2 feature. All tag-related filtering (search --tag, list --tag) moves to Phase 2 for consistent phasing. |
| 26 | Pairwise prompt comparison | Phase 1 / Phase 2 | **Phase 2** | Development/tuning tool. Basic `eval compare --ratios` covers most Phase 1 needs. |
| 27 | Eval enabled config | Persistent config / CLI flag only | **CLI flag only** | `--skip-eval` on summarize command. Evals should run by default; skipping is a conscious per-run choice. |
| 28 | Annotation model | Direct FK / Polymorphic | **Polymorphic (content_type + content_id)** | Enables annotations on section content, section summaries, AND book-level summaries without separate tables. |
| 29 | Concepts extraction phase | Phase 1 during summarization / Phase 2 only | **Extraction in Phase 1, CLI commands in Phase 2** | Concepts are extracted as part of summarization prompts. Dedicated browse/search commands are Phase 2. |
| 30-47 | (Inherited from requirements) | See [requirements decision log](../requirements/2026-04-01_book_companion_v1_requirements.md#20-decision-log) | — | All prior decisions from requirements document are carried forward unless overridden above. |

---

## 16. Research Sources

### Consulted During Spec Creation

| Source | Topic | Key Insight |
|--------|-------|-------------|
| Claude Code CLI `--help` | CLI capabilities | Supports -p (print mode), --output-format json, --json-schema, --model flag, --add-dir for file access. Read tool handles images natively. |
| Requirements doc research sources | Summarization, evals, search | All sources from requirements Section 21 carry forward |
| marker-pdf GitHub | PDF parsing | ML-based PDF→Markdown. Latest versions support tables, images, complex layouts |
| ebooklib docs | EPUB parsing | Standard Python EPUB library. TOC extraction via toc.ncx/nav.xhtml |
| pgvector docs | Vector search | HNSW index type recommended for production. Supports cosine, L2, inner product ops |
| Ollama API docs | Embedding generation | `/api/embeddings` endpoint for nomic-embed-text. 768-dim output |
| Hamel Husain eval methodology | Binary assertions | Pass/fail > rubric scoring. Bootstrap with human eval. Trace storage for improvement |

### Sources from Requirements (Carried Forward)

All sources listed in the [requirements research section](../requirements/2026-04-01_book_companion_v1_requirements.md#21-research-sources) apply to this spec.

### Documentation Deliverable: Sample Output

Include sample output in `docs/sample-output/` showing what a processed book looks like:
- Sample book summary (from a public domain test book)
- Sample section summary with eval results
- Sample concepts index
- Sample search results
- Sample CLI output for key commands

This allows evaluation of the tool's value before committing to full setup.

### Additional Research To Conduct During Implementation

- Optimal chunking strategies for embedding (size, overlap, semantic chunking)
- nomic-embed-text vs other Ollama embedding models for book content
- Claude Code CLI error handling and edge cases in subprocess mode
- Effective prompt patterns for different non-fiction genres

---

## 17. Open Questions & Risks

### Open Questions

| # | Question | Impact | When to Resolve |
|---|----------|--------|----------------|
| 1 | Maximum book size marker-pdf handles reliably? | May need chunked PDF processing | During implementation — test with large PDFs |
| 2 | Heavy mathematical notation handling? | May need LaTeX/MathJax in Markdown | During implementation — test with academic books |
| 3 | Claude Code CLI rate limiting / usage caps? | May need throttling | During summarization implementation |
| 4 | Optimal prompt templates per book genre? | Affects summary quality | Iterative — use eval harness to compare |
| 5 | Calibre ebook-convert installation per OS? | Affects MOBI onboarding | During setup — document per-OS |
| 6 | Concepts extraction: separate prompt or part of summarization? | Cost vs quality | Test both approaches with eval harness |
| 7 | Optimal Ollama embedding model for book content? | Search quality | Test nomic-embed-text vs alternatives |

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PDF parsing quality varies | High | Medium | marker-pdf + PyMuPDF fallback. Accept/reject structure. |
| LLM summarization inconsistency | Medium | High | 16-assertion battery + auto-retry. Prompt versioning. Trace storage. |
| Claude Code CLI subprocess reliability | Medium | Medium | Configurable timeouts, retry logic. Provider interface for future swap. |
| Cumulative context token bloat | Medium | Low | Cap cumulative context at ~500 tokens. Summarize prior context itself if needed. |
| Cross-summary consistency cost | Low | Low | Doubles faithfulness eval cost. Can disable via config if needed. |
| Claude Code CLI requires internet | High | Medium | Document as requirement. Offline = no summarization (embeddings still work locally). |
| Background process management | Medium | Low | PID tracking in processing_jobs. Orphan process detection on startup. |
| Public domain test books not representative | Medium | Low | Validate with real modern non-fiction during human eval baseline (local, .gitignored). |

### Constraints (V1)

- English only
- Internet required for summarization (Claude Code CLI)
- Single user, no auth
- CLI only (no web UI in this spec)
