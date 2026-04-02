"""Tests for EPUB parser."""

import pytest
from pathlib import Path
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
