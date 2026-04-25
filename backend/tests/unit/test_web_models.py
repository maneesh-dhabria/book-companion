"""Tests for web interface DB models."""

from app.db.models import (
    AIMessage,
    AIThread,
    LibraryView,
    ReadingPreset,
    ReadingState,
    RecentSearch,
)


def test_library_view_instantiation():
    view = LibraryView(
        name="Test View",
        display_mode="grid",
        sort_field="updated_at",
        sort_direction="desc",
        is_default=False,
    )
    assert view.name == "Test View"
    assert view.display_mode == "grid"
    assert view.sort_field == "updated_at"
    assert view.sort_direction == "desc"
    assert view.is_default is False


def test_reading_preset_instantiation():
    preset = ReadingPreset(
        name="Test",
        font_family="Georgia",
        font_size_px=16,
        line_spacing=1.6,
        content_width_px=720,
    )
    assert preset.name == "Test"
    assert preset.font_family == "Georgia"
    assert preset.font_size_px == 16
    assert preset.line_spacing == 1.6
    assert preset.content_width_px == 720


def test_ai_thread_creation():
    thread = AIThread(book_id=1, title="Test Thread")
    assert thread.title == "Test Thread"
    assert thread.book_id == 1


def test_ai_message_creation():
    msg = AIMessage(thread_id=1, role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_recent_search_creation():
    search = RecentSearch(query="test query")
    assert search.query == "test query"


def test_reading_state_creation():
    state = ReadingState(user_agent="Mozilla/5.0")
    assert state.user_agent == "Mozilla/5.0"
