import pytest

from app.services.export_service import ExportSelection


class TestExportSelection:
    def test_default_includes_all(self):
        sel = ExportSelection()
        assert sel.include_book_summary is True
        assert sel.include_toc is True
        assert sel.include_annotations is True
        assert sel.exclude_section_ids == frozenset()

    def test_immutable(self):
        sel = ExportSelection()
        with pytest.raises((AttributeError, Exception)):
            sel.include_toc = False  # type: ignore

    def test_with_excludes(self):
        sel = ExportSelection(exclude_section_ids=frozenset({1, 2, 3}))
        assert 2 in sel.exclude_section_ids
