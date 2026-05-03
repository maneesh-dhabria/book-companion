"""AnnotationRepository.list_by_book includes book-summary annotations (FR-53)."""

from app.db.models import (
    Annotation,
    AnnotationType,
    Book,
    BookSection,
    ContentType,
    Summary,
    SummaryContentType,
)
from app.db.repositories.annotation_repo import AnnotationRepository


async def _seed(db_session) -> tuple[int, int, int]:
    b = Book(
        title="T",
        status="completed",
        file_data=b"\x00",
        file_hash="h",
        file_size_bytes=1,
        file_format="epub",
    )
    db_session.add(b)
    await db_session.flush()
    s = BookSection(book_id=b.id, title="S1", order_index=1, content_md="hi")
    db_session.add(s)
    await db_session.flush()
    summary = Summary(
        content_type=SummaryContentType.BOOK,
        content_id=b.id,
        book_id=b.id,
        facets_used={"style": "x", "audience": "x", "compression": "x", "content_focus": "x"},
        prompt_text_sent="p",
        model_used="sonnet",
        input_char_count=10,
        summary_char_count=5,
        summary_md="# book summary",
    )
    db_session.add(summary)
    await db_session.flush()
    return b.id, s.id, summary.id


async def test_list_by_book_includes_book_summary_annotations(db_session):
    book_id, section_id, summary_id = await _seed(db_session)
    db_session.add_all(
        [
            Annotation(
                content_type=ContentType.SECTION_CONTENT,
                content_id=section_id,
                selected_text="hl A",
                type=AnnotationType.HIGHLIGHT,
            ),
            Annotation(
                content_type=ContentType.BOOK_SUMMARY,
                content_id=summary_id,
                selected_text="bs hl 1",
                type=AnnotationType.HIGHLIGHT,
            ),
            Annotation(
                content_type=ContentType.BOOK_SUMMARY,
                content_id=summary_id,
                selected_text="bs hl 2",
                type=AnnotationType.HIGHLIGHT,
            ),
        ]
    )
    await db_session.commit()

    repo = AnnotationRepository(db_session)
    rows = await repo.list_by_book(book_id)
    texts = {r.selected_text for r in rows}
    assert texts == {"hl A", "bs hl 1", "bs hl 2"}
