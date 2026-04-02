"""MOBI parser — converts to EPUB via Calibre, then delegates to EPUBParser."""

import asyncio
import tempfile
from pathlib import Path

from app.exceptions import ParseError
from app.services.parser.base import BookParser, ParsedBook
from app.services.parser.epub_parser import EPUBParser


class MOBIParser(BookParser):
    def supports_format(self, file_format: str) -> bool:
        return file_format == "mobi"

    async def parse(self, file_path: Path) -> ParsedBook:
        with tempfile.TemporaryDirectory() as tmpdir:
            epub_path = Path(tmpdir) / f"{file_path.stem}.epub"
            await self._convert_to_epub(file_path, epub_path)
            epub_parser = EPUBParser()
            return await epub_parser.parse(epub_path)

    async def _convert_to_epub(self, mobi_path: Path, epub_path: Path) -> None:
        proc = await asyncio.create_subprocess_exec(
            "ebook-convert", str(mobi_path), str(epub_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise ParseError(
                f"Calibre ebook-convert failed (rc={proc.returncode}): {stderr.decode()}"
            )
