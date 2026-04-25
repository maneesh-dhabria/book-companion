import pytest

from app.services.export_service import ExportSelection, _sanitize_image_urls


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


class TestSanitizeImageUrls:
    def test_md_image_with_alt(self):
        result = _sanitize_image_urls("Body ![figure 3](/api/v1/images/17) text")
        assert result == "Body [Image: figure 3] text"
        assert "/api/v1/images/" not in result

    def test_md_image_empty_alt(self):
        assert _sanitize_image_urls("![](/api/v1/images/5)") == "[Image]"

    def test_md_image_with_title_attr(self):
        result = _sanitize_image_urls('![figure](/api/v1/images/17 "Title text")')
        assert result == "[Image: figure]"
        assert "/api/v1/images/" not in result

    def test_md_image_special_chars_in_alt(self):
        result = _sanitize_image_urls("![alt with parens (here)](/api/v1/images/9)")
        assert result == "[Image: alt with parens (here)]"

    def test_html_img_with_alt(self):
        result = _sanitize_image_urls('<img src="/api/v1/images/12" alt="diagram" />')
        assert result == "[Image: diagram]"

    def test_html_img_no_alt(self):
        result = _sanitize_image_urls('<img src="/api/v1/images/12" />')
        assert result == "[Image]"

    def test_html_img_single_quotes(self):
        result = _sanitize_image_urls("<img src='/api/v1/images/12' alt='x' />")
        assert result == "[Image: x]"

    def test_html_img_extra_attrs(self):
        src = '<img class="big" src="/api/v1/images/12" alt="t" width="200" />'
        assert _sanitize_image_urls(src) == "[Image: t]"

    def test_multiple_images_in_one_text(self):
        src = "First ![a](/api/v1/images/1) middle ![b](/api/v1/images/2) end"
        assert _sanitize_image_urls(src) == "First [Image: a] middle [Image: b] end"

    def test_no_images_passthrough(self):
        assert _sanitize_image_urls("plain text") == "plain text"

    def test_zero_substring_invariant(self):
        src = '![x](/api/v1/images/1) <img src="/api/v1/images/2"/> ![](/api/v1/images/3 "t")'
        assert "/api/v1/images/" not in _sanitize_image_urls(src)
