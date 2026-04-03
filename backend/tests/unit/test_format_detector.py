"""Tests for file format detection."""

import pytest

from app.services.parser.format_detector import FormatDetectionError, detect_format


def test_detect_epub_by_extension(tmp_path):
    epub = tmp_path / "test.epub"
    # EPUB magic bytes: PK (zip archive) with mimetype entry
    epub.write_bytes(b"PK\x03\x04" + b"\x00" * 26 + b"mimetypeapplication/epub+zip")
    assert detect_format(epub) == "epub"


def test_detect_pdf_by_extension(tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake content")
    assert detect_format(pdf) == "pdf"


def test_detect_mobi_by_extension(tmp_path):
    mobi = tmp_path / "test.mobi"
    # MOBI magic: BOOKMOBI at offset 60
    data = b"\x00" * 60 + b"BOOKMOBI" + b"\x00" * 100
    mobi.write_bytes(data)
    assert detect_format(mobi) == "mobi"


def test_reject_unsupported_format(tmp_path):
    txt = tmp_path / "test.txt"
    txt.write_text("plain text")
    with pytest.raises(FormatDetectionError, match="Unsupported"):
        detect_format(txt)


def test_reject_fake_extension(tmp_path):
    fake_epub = tmp_path / "fake.epub"
    fake_epub.write_text("this is not an epub")
    with pytest.raises(FormatDetectionError, match="Magic bytes"):
        detect_format(fake_epub)
