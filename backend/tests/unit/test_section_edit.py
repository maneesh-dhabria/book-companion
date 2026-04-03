"""Tests for SectionEditService in-memory operations."""

import pytest

from app.exceptions import SectionEditError
from app.services.section_edit_service import SectionEditService, SectionItem


def _make_sections(count=5):
    return [
        SectionItem(i + 1, i + 100, f"Section {i + 1}", f"Content {i + 1} " * 200, 0, 2000)
        for i in range(count)
    ]


@pytest.fixture
def svc():
    s = SectionEditService()
    s.init_memory_mode(_make_sections())
    return s


def test_merge(svc):
    result = svc.merge([2, 3], "Merged")
    sections = svc.get_sections()
    assert len(sections) == 4
    assert result.title == "Merged"
    assert result.derived_from == [101, 102]
    assert "Content 2" in result.content
    assert "Content 3" in result.content


def test_split_at_char(svc):
    result = svc.split_at_char(1, 500)
    sections = svc.get_sections()
    assert len(sections) == 6
    assert result[0].title == "Section 1 (Part 1)"


def test_split_at_paragraph(svc):
    svc._sections[0].content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    result = svc.split_at_paragraph(1, 20)
    assert len(result) == 2


def test_move(svc):
    svc.move(1, 3)
    sections = svc.get_sections()
    titles = [s.title for s in sections]
    assert titles.index("Section 1") > titles.index("Section 3")


def test_delete(svc):
    count = svc.delete([4, 5])
    assert count == 2
    assert len(svc.get_sections()) == 3


def test_delete_all_raises(svc):
    with pytest.raises(SectionEditError, match="Cannot delete all"):
        svc.delete([1, 2, 3, 4, 5])


def test_undo(svc):
    svc.delete([5])
    assert len(svc.get_sections()) == 4
    assert svc.undo()
    assert len(svc.get_sections()) == 5


def test_undo_no_history(svc):
    assert not svc.undo()


def test_reindex_after_operations(svc):
    svc.delete([3])
    sections = svc.get_sections()
    indices = [s.index for s in sections]
    assert indices == [1, 2, 3, 4]


def test_detect_headings(svc):
    svc._sections[0].content = "Intro text\n\n## Heading One\nContent\n\n## Heading Two\nMore"
    headings = svc.detect_headings(1)
    assert len(headings) == 2
    assert headings[0][0] == "Heading One"
