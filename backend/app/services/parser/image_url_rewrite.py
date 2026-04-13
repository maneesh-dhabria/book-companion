"""Image URL rewriting between parse-time placeholders and stored absolute URLs."""

from __future__ import annotations

import re

# Markdown image: ![alt](path "optional title")
_MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# HTML <img src="path">
_HTML_IMG = re.compile(
    r'(<img\s[^>]*?src=)(["\'])([^"\']+)(["\'])([^>]*>)',
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"__IMG_PLACEHOLDER__:([^_]+(?:_[^_]+)*?)__")


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def to_placeholder(md: str) -> str:
    """Replace local image refs with __IMG_PLACEHOLDER__:<basename>__ tokens."""

    def md_repl(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        return f"![{alt}](__IMG_PLACEHOLDER__:{_basename(src)}__)"

    def html_repl(m: re.Match) -> str:
        prefix, q1, src, q2, suffix = m.groups()
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        return f"{prefix}{q1}__IMG_PLACEHOLDER__:{_basename(src)}__{q2}{suffix}"

    out = _MD_IMG.sub(md_repl, md)
    out = _HTML_IMG.sub(html_repl, out)
    return out


def from_placeholder(md: str, filename_to_image_id: dict[str, int]) -> str:
    """Substitute placeholders with /api/v1/images/{id}; leave unknown untouched."""

    def repl(m: re.Match) -> str:
        fn = m.group(1)
        image_id = filename_to_image_id.get(fn)
        if image_id is None:
            return m.group(0)
        return f"/api/v1/images/{image_id}"

    return _PLACEHOLDER.sub(repl, md)
