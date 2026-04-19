from app.services.parser.pdf_parser import PDFParser


def test_pdf_parser_pages_to_sections_classifies_titles():
    parser = PDFParser()
    pages = [
        {"text": "# Copyright\n\u00a9 2023 ...", "images": []},
        {"text": "# Introduction\nThis book explores ...", "images": []},
        {"text": "# The Mindset Shift\nchapter body", "images": []},
    ]
    sections = parser._pages_to_sections(pages)
    titles_to_types = {s.title: s.section_type for s in sections}
    assert titles_to_types.get("Copyright") == "copyright"
    assert titles_to_types.get("Introduction") == "introduction"
    assert titles_to_types.get("The Mindset Shift") == "chapter"


def test_pdf_parser_chunk_by_pages_classifies_default_to_chapter():
    parser = PDFParser()
    pages = [{"text": "body text " * 20, "images": []} for _ in range(12)]
    sections = parser._chunk_by_pages(pages, pages_per_section=5)
    assert all(s.section_type == "chapter" for s in sections)
