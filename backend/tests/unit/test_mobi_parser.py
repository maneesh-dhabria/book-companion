"""Tests for MOBI parser (delegates to EPUB after Calibre conversion)."""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.parser.mobi_parser import MOBIParser


@pytest.fixture
def parser():
    return MOBIParser()


def test_supports_mobi(parser):
    assert parser.supports_format("mobi") is True
    assert parser.supports_format("epub") is False


@pytest.mark.asyncio
async def test_mobi_converts_to_epub(parser, tmp_path):
    """MOBI parser should convert to EPUB then delegate."""
    mobi_file = tmp_path / "test.mobi"
    mobi_file.write_bytes(b"\x00" * 60 + b"BOOKMOBI" + b"\x00" * 100)

    with patch("app.services.parser.mobi_parser.EPUBParser") as MockEPUB:
        mock_epub_parser = AsyncMock()
        MockEPUB.return_value = mock_epub_parser
        mock_epub_parser.parse.return_value = AsyncMock(
            title="Test", authors=["Author"], sections=[], cover_image=None, metadata={}
        )
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            await parser.parse(mobi_file)
            # Verify ebook-convert was called
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0]
            assert call_args[0] == "ebook-convert"
