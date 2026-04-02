"""File format detection via magic bytes + extension."""

from pathlib import Path

from app.exceptions import ParseError


class FormatDetectionError(ParseError):
    """Raised when file format cannot be determined or is unsupported."""


MAGIC_SIGNATURES = {
    "epub": (b"PK", 0),        # ZIP archive (EPUB is zipped)
    "pdf": (b"%PDF", 0),       # PDF header
    "mobi": (b"BOOKMOBI", 60), # MOBI identifier at offset 60
}

SUPPORTED_EXTENSIONS = {"epub", "mobi", "pdf"}


def detect_format(file_path: Path) -> str:
    """Detect book format by extension + magic bytes validation.

    Returns: format string ('epub', 'mobi', 'pdf')
    Raises: FormatDetectionError if unsupported or magic bytes mismatch
    """
    ext = file_path.suffix.lower().lstrip(".")
    if ext not in SUPPORTED_EXTENSIONS:
        raise FormatDetectionError(f"Unsupported file format: .{ext}")

    with open(file_path, "rb") as f:
        magic, offset = MAGIC_SIGNATURES[ext]
        f.seek(offset)
        header = f.read(len(magic))
        if header != magic:
            raise FormatDetectionError(
                f"Magic bytes mismatch for .{ext}: expected {magic!r} at offset {offset}, "
                f"got {header!r}"
            )
    return ext
