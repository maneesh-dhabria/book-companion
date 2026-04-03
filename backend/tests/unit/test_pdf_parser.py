"""Tests for PDF parser."""

import pytest

from app.services.parser.pdf_parser import PDFParser


@pytest.fixture
def parser():
    return PDFParser()


def test_supports_pdf(parser):
    assert parser.supports_format("pdf") is True
    assert parser.supports_format("epub") is False


@pytest.mark.asyncio
async def test_parse_republic_pdf(parser, sample_pdf_path):
    result = await parser.parse(sample_pdf_path)
    assert result.title
    assert len(result.sections) >= 1
    # Should have extracted some content
    total_content = sum(len(s.content_md) for s in result.sections)
    assert total_content > 100  # Gutenberg PDFs may be short


@pytest.mark.asyncio
async def test_pdf_sections_ordered(parser, sample_pdf_path):
    result = await parser.parse(sample_pdf_path)
    for i in range(1, len(result.sections)):
        assert result.sections[i].order_index > result.sections[i - 1].order_index
