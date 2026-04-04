"""Text cleaning utilities shared across parser and summarizer."""

import re

_XML_DECL = re.compile(r"<\?xml[^?]*\?>")
_PROCESSING_INST = re.compile(r"<\?[^?]*\?>")
_IMAGE_ONLY_LINE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$", re.MULTILINE)


def strip_non_content(text: str) -> str:
    """Remove XML declarations, processing instructions, image-only lines."""
    text = _XML_DECL.sub("", text)
    text = _PROCESSING_INST.sub("", text)
    text = _IMAGE_ONLY_LINE.sub("", text)
    return text.strip()


def text_char_count(text: str) -> int:
    """Character count of text after stripping non-content."""
    return len(strip_non_content(text))
