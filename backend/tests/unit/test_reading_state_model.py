"""Unit tests for ReadingState model."""

from app.db.models import ReadingState


def test_reading_state_model_exists():
    rs = ReadingState()
    assert hasattr(rs, "id")
    assert hasattr(rs, "user_agent")
    assert hasattr(rs, "book_id")
    assert hasattr(rs, "section_id")
    assert hasattr(rs, "updated_at")
    assert hasattr(rs, "created_at")


def test_reading_state_has_extra_fields():
    rs = ReadingState()
    assert hasattr(rs, "scroll_position")
    assert hasattr(rs, "content_mode")
    assert hasattr(rs, "reading_preset_id")


def test_reading_state_relationships():
    rs = ReadingState()
    assert hasattr(rs, "book")
    assert hasattr(rs, "section")
