"""FR-D1.4 — auto-derived thread titles from first user message."""

from app.services.ai_thread_service import (
    _derive_thread_title,
    _is_default_thread_title,
)


def test_is_default_thread_title_recognizes_placeholders():
    assert _is_default_thread_title(None)
    assert _is_default_thread_title("")
    assert _is_default_thread_title("New Thread")
    assert _is_default_thread_title("  Untitled  ")
    assert not _is_default_thread_title("Porter's five forces")


def test_derive_thread_title_short_message_verbatim():
    assert _derive_thread_title("What is Porter's frame?") == "What is Porter's frame?"


def test_derive_thread_title_trims_on_word_boundary():
    content = (
        "What is Porter's five forces framework and why did he create it?"
    )
    title = _derive_thread_title(content)
    assert len(title) <= 41  # up to 40 + trailing ellipsis
    assert title.endswith("…")
    # Should not split in the middle of a word.
    assert " " in title  # at least one word boundary


def test_derive_thread_title_collapses_whitespace():
    content = "What\n\nis   Porter's?"
    title = _derive_thread_title(content)
    assert title == "What is Porter's?"
