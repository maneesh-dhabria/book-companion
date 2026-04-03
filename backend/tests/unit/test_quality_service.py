"""Tests for QualityService quality checks."""

import pytest

from app.services.quality_service import QualityService


@pytest.fixture
def svc():
    return QualityService()


def _section(index, title, content="x" * 1000, depth=0, image_count=0):
    return {
        "index": index,
        "title": title,
        "content": content,
        "depth": depth,
        "char_count": len(content),
        "image_count": image_count,
    }


def test_empty_section(svc):
    sections = [_section(1, "Empty", content="")]
    issues = svc.check_sections(sections)
    assert any(i.check == "empty" and i.severity == "error" for i in issues)


def test_short_section(svc):
    sections = [_section(1, "Short", content="x" * 100)]
    issues = svc.check_sections(sections)
    assert any(i.check == "short" for i in issues)


def test_non_content_section(svc):
    for title in ["Copyright", "About the Author", "Index", "Bibliography", "Acknowledgments"]:
        sections = [_section(1, title)]
        issues = svc.check_sections(sections)
        assert any(i.check == "non-content" for i in issues), f"Failed for: {title}"


def test_normal_title_not_flagged(svc):
    sections = [_section(1, "The Five Forces Framework")]
    issues = svc.check_sections(sections)
    assert not any(i.check == "non-content" for i in issues)


def test_oversized_section(svc):
    sections = [_section(1, "Big", content="x" * 150_000)]
    issues = svc.check_sections(sections)
    assert any(i.check == "oversized" for i in issues)


def test_encoding_issues(svc):
    content = "a" * 90 + "\ufffd" * 15 + "a" * 895
    sections = [_section(1, "Bad Encoding", content=content)]
    issues = svc.check_sections(sections)
    assert any(i.check == "encoding_issues" for i in issues)


def test_repeated_content(svc):
    text = "The quick brown fox jumps over the lazy dog. " * 50
    sections = [_section(1, "A", content=text), _section(2, "B", content=text)]
    issues = svc.check_sections(sections)
    assert any(i.check == "repeated_content" for i in issues)


def test_no_false_positive_on_different_content(svc):
    sections = [
        _section(1, "A", content="Alpha bravo charlie delta echo foxtrot " * 50),
        _section(2, "B", content="Golf hotel india juliet kilo lima " * 50),
    ]
    issues = svc.check_sections(sections)
    assert not any(i.check == "repeated_content" for i in issues)


def test_trigram_jaccard_identical():
    assert QualityService._trigram_jaccard("hello world", "hello world") == 1.0


def test_trigram_jaccard_different():
    assert QualityService._trigram_jaccard("abcdef", "uvwxyz") == 0.0


def test_suggested_actions_groups_deletes(svc):
    sections = [
        _section(1, "Copyright", content="x" * 500),
        _section(2, "Good Chapter"),
        _section(3, "Index", content="x" * 500),
    ]
    issues = svc.check_sections(sections)
    actions = svc.suggested_actions(issues)
    assert any("Delete" in a for a in actions)
