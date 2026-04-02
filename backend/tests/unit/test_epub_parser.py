"""Tests for EPUB parser."""

import pytest
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
        '<html><body><p>Text</p>'
        '<img src="fig1.png" alt="Porter Five Forces diagram"/>'
        '</body></html>'
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
        '<html><body>'
        '<img src="a.png" alt="image"/>'
        '<img src="b.png" alt="Figure"/>'
        '<img src="c.png" alt="Real description"/>'
        '</body></html>'
    )
    alt_map = parser._extract_alt_text(html)
    assert "a.png" not in alt_map
    assert "b.png" not in alt_map
    assert alt_map.get("c.png") == "Real description"
