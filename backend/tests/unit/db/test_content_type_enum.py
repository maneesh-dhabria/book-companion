"""FR-21 / plan T1: ContentType.ANNOTATION enum extension.

Asserts the runtime-only enum value resolves AND that the SQLite CHECK
constraint on ``audio_files`` does not list 'annotation' as a permitted
``content_type`` (annotation lookups never persist; D4).
"""

from sqlalchemy import create_engine, text

from app.db.models import Base, ContentType


def test_annotation_enum_value_exists():
    assert ContentType("annotation") == ContentType.ANNOTATION
    assert ContentType.ANNOTATION.value == "annotation"


def test_annotation_not_in_audio_files_check_constraint():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='audio_files'"
            )
        ).fetchone()
        assert row is not None
        assert "annotation" not in row[0].lower(), (
            f"audio_files schema must NOT include 'annotation' in CHECK: {row[0]}"
        )
