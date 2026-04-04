"""Tests for EPUB parser."""

import pytest

from app.services.parser.base import ParsedImage, ParsedSection
from app.services.parser.epub_parser import EPUBParser


@pytest.fixture
def parser():
    return EPUBParser()


def test_supports_epub(parser):
    assert parser.supports_format("epub") is True
    assert parser.supports_format("pdf") is False


@pytest.mark.asyncio
async def test_parse_art_of_war(parser, sample_epub_path):
    result = await parser.parse(sample_epub_path)
    assert result.title  # Title should be extracted
    assert len(result.authors) >= 1
    assert len(result.sections) >= 5  # Art of War has 13+ sections
    for section in result.sections:
        assert section.title
        assert section.content_md  # Content should be non-empty
        assert section.depth >= 0
        assert section.order_index >= 0


@pytest.mark.asyncio
async def test_epub_toc_extraction(parser, sample_epub_path):
    result = await parser.parse(sample_epub_path)
    # Sections should be ordered
    for i in range(1, len(result.sections)):
        assert result.sections[i].order_index > result.sections[i - 1].order_index


@pytest.mark.asyncio
async def test_epub_markdown_quality(parser, sample_epub_path):
    result = await parser.parse(sample_epub_path)
    # At least one section should have substantial content
    long_sections = [s for s in result.sections if len(s.content_md) > 100]
    assert len(long_sections) >= 1


def test_parsed_section_images_include_alt_text():
    """Images extracted from EPUB should include alt-text if available."""
    parser = EPUBParser.__new__(EPUBParser)
    html = (
        "<html><body><p>Text</p>"
        '<img src="fig1.png" alt="Porter Five Forces diagram"/>'
        "</body></html>"
    )
    alt_map = parser._extract_alt_text(html)
    assert alt_map.get("fig1.png") == "Porter Five Forces diagram"


def test_alt_text_extraction_handles_missing_alt():
    """Images without alt or with empty alt should not appear in the map."""
    parser = EPUBParser.__new__(EPUBParser)
    html = '<html><body><img src="fig1.png"/><img src="fig2.png" alt=""/></body></html>'
    alt_map = parser._extract_alt_text(html)
    assert "fig1.png" not in alt_map  # No alt attribute
    assert "fig2.png" not in alt_map  # Empty alt


def test_alt_text_extraction_alt_before_src():
    """Alt attribute appearing before src should still be extracted."""
    parser = EPUBParser.__new__(EPUBParser)
    html = '<html><body><img alt="Revenue chart" src="images/chart.png"/></body></html>'
    alt_map = parser._extract_alt_text(html)
    assert alt_map.get("chart.png") == "Revenue chart"


def test_alt_text_filters_generic_values():
    """Generic alt values like 'image' or 'figure' should be filtered out."""
    parser = EPUBParser.__new__(EPUBParser)
    html = (
        "<html><body>"
        '<img src="a.png" alt="image"/>'
        '<img src="b.png" alt="Figure"/>'
        '<img src="c.png" alt="Real description"/>'
        "</body></html>"
    )
    alt_map = parser._extract_alt_text(html)
    assert "a.png" not in alt_map
    assert "b.png" not in alt_map
    assert alt_map.get("c.png") == "Real description"


class TestCleanHtml:
    def test_strips_xml_declaration(self):
        html = '<?xml version="1.0" encoding="utf-8"?><html><body>Hello</body></html>'
        result = EPUBParser._clean_html(html)
        assert "<?xml" not in result
        assert "<html>" in result

    def test_strips_processing_instructions(self):
        html = '<?mso-application progid="Word"?><p>Content</p>'
        result = EPUBParser._clean_html(html)
        assert "<?mso" not in result
        assert "Content" in result

    def test_preserves_normal_html(self):
        html = "<html><body><p>Normal content</p></body></html>"
        assert EPUBParser._clean_html(html) == html


class TestMergeStubSections:
    def _make_section(self, title, content, depth=0, order=0, images=None):
        return ParsedSection(
            title=title, content_md=content, depth=depth, order_index=order, images=images or []
        )

    def test_merge_stub_into_next(self):
        parser = EPUBParser()
        sections = [
            self._make_section("Cover", "x" * 100, order=0),
            self._make_section("Chapter 1", "y" * 5000, order=1),
        ]
        result = parser._merge_stub_sections(sections)
        assert len(result) == 1
        assert result[0].title == "Chapter 1"
        assert "x" * 100 in result[0].content_md

    def test_merge_part_divider(self):
        parser = EPUBParser()
        sections = [
            self._make_section("Part One", "# Part One\n", order=0),
            self._make_section("Ch 1: Strategy", "Real content " * 200, order=1),
        ]
        result = parser._merge_stub_sections(sections)
        assert len(result) == 1
        assert result[0].title == "Ch 1: Strategy"

    def test_merge_cascading_stubs(self):
        parser = EPUBParser()
        sections = [
            self._make_section("Stub1", "short", order=0),
            self._make_section("Stub2", "also short", order=1),
            self._make_section("Content", "z" * 5000, order=2),
        ]
        result = parser._merge_stub_sections(sections)
        assert len(result) == 1
        assert result[0].title == "Content"

    def test_merge_last_stub_backward(self):
        parser = EPUBParser()
        sections = [
            self._make_section("Content", "z" * 5000, order=0),
            self._make_section("About Author", "Short bio", order=1),
        ]
        result = parser._merge_stub_sections(sections)
        assert len(result) == 1
        assert result[0].title == "Content"

    def test_no_merge_above_threshold(self):
        parser = EPUBParser()
        sections = [
            self._make_section("Ch1", "a" * 1000, order=0),
            self._make_section("Ch2", "b" * 1000, order=1),
        ]
        result = parser._merge_stub_sections(sections)
        assert len(result) == 2

    def test_single_section_no_merge(self):
        parser = EPUBParser()
        sections = [self._make_section("Only", "content", order=0)]
        result = parser._merge_stub_sections(sections)
        assert len(result) == 1

    def test_merge_drops_stub_images(self):
        parser = EPUBParser()
        stub_img = ParsedImage(data=b"img", mime_type="image/png", filename="cover.png")
        content_img = ParsedImage(data=b"img2", mime_type="image/png", filename="fig1.png")
        sections = [
            self._make_section("Cover", "short", order=0, images=[stub_img]),
            self._make_section("Ch1", "z" * 5000, order=1, images=[content_img]),
        ]
        result = parser._merge_stub_sections(sections)
        assert len(result) == 1
        assert len(result[0].images) == 1
        assert result[0].images[0].filename == "fig1.png"

    def test_merge_reindexes_order(self):
        parser = EPUBParser()
        sections = [
            self._make_section("Stub", "x", order=0),
            self._make_section("Ch1", "y" * 1000, order=1),
            self._make_section("Ch2", "z" * 1000, order=2),
        ]
        result = parser._merge_stub_sections(sections)
        assert [s.order_index for s in result] == [0, 1]
