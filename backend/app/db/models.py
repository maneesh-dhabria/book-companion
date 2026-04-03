"""SQLAlchemy 2.0 ORM models for Book Companion."""

import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, deferred, mapped_column, relationship


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


class ImageRelevance(str, enum.Enum):
    KEY = "key"
    SUPPLEMENTARY = "supplementary"
    DECORATIVE = "decorative"


class ContentType(str, enum.Enum):
    SECTION_CONTENT = "section_content"
    SECTION_SUMMARY = "section_summary"
    BOOK_SUMMARY = "book_summary"


class AnnotationType(str, enum.Enum):
    HIGHLIGHT = "highlight"
    NOTE = "note"
    FREEFORM = "freeform"


class SummaryContentType(str, enum.Enum):
    SECTION = "section"
    BOOK = "book"
    CONCEPT = "concept"        # Reserved for Phase 2
    ANNOTATION = "annotation"  # Reserved for Phase 2


# --- Models ---


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    books: Mapped[list["Book"]] = relationship(
        secondary="book_authors", back_populates="authors"
    )


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cover_image: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    default_summary_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("summaries.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    status: Mapped[BookStatus] = mapped_column(
        Enum(BookStatus), default=BookStatus.UPLOADING
    )
    quick_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    authors: Mapped[list["Author"]] = relationship(
        secondary="book_authors", back_populates="books"
    )
    sections: Mapped[list["BookSection"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    external_references: Mapped[list["ExternalReference"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_books_file_hash", "file_hash"),
        Index("ix_books_status", "status"),
    )


class BookAuthor(Base):
    __tablename__ = "book_authors"

    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(50), default="author")


class BookSection(Base):
    __tablename__ = "book_sections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("book_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_summary_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("summaries.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    derived_from: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    book: Mapped["Book"] = relationship(back_populates="sections")
    parent: Mapped["BookSection | None"] = relationship(remote_side="BookSection.id")
    images: Mapped[list["Image"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        primaryjoin="and_(BookSection.id == foreign(Annotation.content_id), "
        "Annotation.content_type.in_(['section_content', 'section_summary']))",
    )

    __table_args__ = (
        Index("ix_book_sections_book_id_order", "book_id", "order_index"),
    )


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    section_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("book_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    data: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    relevance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    section: Mapped["BookSection"] = relationship(back_populates="images")


class SearchIndex(Base):
    __tablename__ = "search_index"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    tsvector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_search_index_source", "source_type", "source_id"),
        Index("ix_search_index_book_id", "book_id"),
        Index(
            "ix_search_index_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_search_index_tsvector", "tsvector", postgresql_using="gin"),
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    step: Mapped[ProcessingStep] = mapped_column(Enum(ProcessingStep), nullable=False)
    status: Mapped[ProcessingJobStatus] = mapped_column(
        Enum(ProcessingJobStatus), default=ProcessingJobStatus.PENDING
    )
    progress: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)

    book: Mapped["Book"] = relationship(back_populates="processing_jobs")

    __table_args__ = (Index("ix_processing_jobs_book_status", "book_id", "status"),)


class EvalTrace(Base):
    __tablename__ = "eval_traces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    section_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("book_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    summary_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("summaries.id", ondelete="SET NULL"),
        nullable=True,
    )
    assertion_name: Mapped[str] = mapped_column(String(100), nullable=False)
    assertion_category: Mapped[str] = mapped_column(String(50), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    prompt_sent: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_response: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_eval_traces_section", "section_id"),
        Index("ix_eval_traces_assertion", "assertion_name", "passed"),
    )


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content_type: Mapped[SummaryContentType] = mapped_column(
        Enum(SummaryContentType), nullable=False
    )
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    preset_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    facets_used: Mapped[dict] = mapped_column(JSON, nullable=False)
    prompt_text_sent: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_md: Mapped[str] = mapped_column(Text, nullable=False)
    eval_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_summaries_content", "content_type", "content_id"),
        Index("ix_summaries_book_id", "book_id"),
        Index("ix_summaries_created_at", "created_at"),
    )


# --- Phase 2 Models ---


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Taggable(Base):
    __tablename__ = "taggables"

    tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    taggable_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    taggable_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType), nullable=False
    )
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    text_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[AnnotationType] = mapped_column(
        Enum(AnnotationType), default=AnnotationType.NOTE
    )
    linked_annotation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("annotations.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    section: Mapped["BookSection | None"] = relationship(
        back_populates="annotations",
        primaryjoin="and_(foreign(Annotation.content_id) == BookSection.id, "
        "Annotation.content_type.in_(['section_content', 'section_summary']))",
    )

    __table_args__ = (
        Index("ix_annotations_content", "content_type", "content_id"),
    )


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    first_section_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("book_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    term: Mapped[str] = mapped_column(String(500), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    related_concepts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    book: Mapped["Book"] = relationship(back_populates="concepts")

    __table_args__ = (
        Index("ix_concepts_book_id", "book_id"),
        UniqueConstraint("book_id", "term", name="uq_concepts_book_term"),
    )


class ConceptSection(Base):
    __tablename__ = "concept_sections"

    concept_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True
    )
    section_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("book_sections.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ExternalReference(Base):
    __tablename__ = "external_references"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    book: Mapped["Book"] = relationship(back_populates="external_references")

    __table_args__ = (Index("ix_external_references_book_id", "book_id"),)
