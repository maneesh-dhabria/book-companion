"""Tests for SQLAlchemy models."""

from app.db.models import (
    Author,
    Book,
    BookAuthor,
    BookSection,
    BookStatus,
    Concept,
    ConceptSection,
    EvalTrace,
    Image,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
    SearchIndex,
    SourceType,
)


def test_book_status_enum():
    assert BookStatus.UPLOADING == "uploading"
    assert BookStatus.COMPLETED == "completed"
    assert BookStatus.PARSE_FAILED == "parse_failed"


def test_processing_step_enum():
    assert ProcessingStep.PARSE == "parse"
    assert ProcessingStep.QUICK_SUMMARY == "quick_summary"


def test_source_type_enum():
    assert SourceType.BOOK_TITLE == "book_title"
    assert SourceType.CONCEPT == "concept"


def test_model_tablenames():
    assert Author.__tablename__ == "authors"
    assert Book.__tablename__ == "books"
    assert BookAuthor.__tablename__ == "book_authors"
    assert BookSection.__tablename__ == "book_sections"
    assert Image.__tablename__ == "images"
    assert SearchIndex.__tablename__ == "search_index"
    assert ProcessingJob.__tablename__ == "processing_jobs"
    assert EvalTrace.__tablename__ == "eval_traces"
    assert Concept.__tablename__ == "concepts"
    assert ConceptSection.__tablename__ == "concept_sections"


# --- Phase 2 Model Tests ---

from app.db.models import (
    Annotation,
    AnnotationType,
    ContentType,
    ExternalReference,
    Tag,
    Taggable,
)


def test_annotation_type_enum():
    assert AnnotationType.HIGHLIGHT == "highlight"
    assert AnnotationType.NOTE == "note"
    assert AnnotationType.FREEFORM == "freeform"


def test_content_type_enum():
    assert ContentType.SECTION_CONTENT == "section_content"
    assert ContentType.SECTION_SUMMARY == "section_summary"
    assert ContentType.BOOK_SUMMARY == "book_summary"


def test_phase2_tablenames():
    assert Tag.__tablename__ == "tags"
    assert Taggable.__tablename__ == "taggables"
    assert Annotation.__tablename__ == "annotations"
    assert ExternalReference.__tablename__ == "external_references"


def test_annotation_defaults():
    """Verify Annotation model can be instantiated with defaults."""
    ann = Annotation(
        content_type=ContentType.SECTION_CONTENT,
        content_id=1,
    )
    assert ann.content_type == ContentType.SECTION_CONTENT
    assert ann.content_id == 1
    # Default is set at DB level, not Python init level
    assert ann.type is None or ann.type == AnnotationType.NOTE


def test_tag_model():
    """Verify Tag model fields."""
    tag = Tag(name="philosophy", color="#FF5733")
    assert tag.name == "philosophy"
    assert tag.color == "#FF5733"


def test_taggable_composite_key():
    """Verify Taggable has composite primary key fields."""
    t = Taggable(tag_id=1, taggable_type="book", taggable_id=42)
    assert t.tag_id == 1
    assert t.taggable_type == "book"
    assert t.taggable_id == 42


def test_external_reference_model():
    """Verify ExternalReference model fields."""
    ref = ExternalReference(
        book_id=1,
        url="https://example.com/review",
        title="A Review",
        source_name="Example Blog",
    )
    assert ref.url == "https://example.com/review"
    assert ref.source_name == "Example Blog"


# --- V1.1 Model Tests ---


def test_summary_content_type_enum():
    from app.db.models import SummaryContentType
    assert SummaryContentType.SECTION.value == "section"
    assert SummaryContentType.BOOK.value == "book"
    assert SummaryContentType.CONCEPT.value == "concept"
    assert SummaryContentType.ANNOTATION.value == "annotation"


def test_summary_model_instantiation():
    from app.db.models import Summary, SummaryContentType
    s = Summary(
        content_type=SummaryContentType.SECTION,
        content_id=1, book_id=1,
        facets_used={"style": "bullet_points", "audience": "practitioner",
                     "compression": "standard", "content_focus": "frameworks_examples"},
        prompt_text_sent="test prompt", model_used="sonnet",
        input_char_count=1000, summary_char_count=200, summary_md="# Test summary",
    )
    assert s.content_type == SummaryContentType.SECTION
    assert s.preset_name is None


def test_summary_status_enum_removed():
    import app.db.models as models
    assert not hasattr(models, "SummaryStatus")
