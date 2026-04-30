"""Image URL rewriting between parse-time placeholders and stored absolute URLs."""

from __future__ import annotations

import re
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

OnMissing = Literal["keep", "strip"]

# Markdown image: ![alt](path "optional title")
_MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# HTML <img src="path">
_HTML_IMG = re.compile(
    r'(<img\s[^>]*?src=)(["\'])([^"\']+)(["\'])([^>]*>)',
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"__IMG_PLACEHOLDER__:(.+?)__ENDIMG__")
# Matches a whole markdown image whose src is a placeholder — used by strip
# mode to drop the entire `![alt](__IMG_PLACEHOLDER__:fn__ENDIMG__)` when the
# target filename is unknown.
_MD_PLACEHOLDER_IMG = re.compile(r"!\[[^\]]*\]\(__IMG_PLACEHOLDER__:(.+?)__ENDIMG__\)")
# Legacy ![alt](image:NNN) — emitted by older summarizer prompts.
_LEGACY_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(image:(\d+)\)")


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def to_placeholder(md: str) -> str:
    """Replace local image refs with __IMG_PLACEHOLDER__:<basename>__ENDIMG__ tokens.

    The distinct `__ENDIMG__` terminator (not just `__`) matters because EPUB
    filenames can legitimately contain consecutive underscores.
    """

    def md_repl(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        return f"![{alt}](__IMG_PLACEHOLDER__:{_basename(src)}__ENDIMG__)"

    def html_repl(m: re.Match) -> str:
        prefix, q1, src, q2, suffix = m.groups()
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        return f"{prefix}{q1}__IMG_PLACEHOLDER__:{_basename(src)}__ENDIMG__{q2}{suffix}"

    out = _MD_IMG.sub(md_repl, md)
    out = _HTML_IMG.sub(html_repl, out)
    return out


def from_placeholder(
    md: str,
    filename_to_image_id: dict[str, int],
    on_missing: OnMissing = "keep",
) -> str:
    """Substitute placeholders with /api/v1/images/{id}.

    ``on_missing='keep'`` (default) — unknown placeholders are left in place
    so a later re-index can resolve them. This matches the pre-v1.5 behavior.

    ``on_missing='strip'`` — unknown placeholders are removed. If the
    placeholder is wrapped in a markdown image ``![alt](…)``, the entire
    image is removed; otherwise only the ``__IMG_PLACEHOLDER__…__ENDIMG__``
    token is removed. A structlog warning is emitted per missing filename
    so operators can see what was dropped.
    """

    if on_missing == "strip":

        def md_img_repl(m: re.Match) -> str:
            fn = m.group(1)
            image_id = filename_to_image_id.get(fn)
            if image_id is None:
                logger.warning("image_placeholder_missing", filename=fn)
                return ""
            return f"![]({'/api/v1/images/' + str(image_id)})"

        # First strip missing image wrappers in one pass.
        md = _MD_PLACEHOLDER_IMG.sub(md_img_repl, md)

    def token_repl(m: re.Match) -> str:
        fn = m.group(1)
        image_id = filename_to_image_id.get(fn)
        if image_id is None:
            if on_missing == "strip":
                logger.warning("image_placeholder_missing", filename=fn)
                return ""
            return m.group(0)
        return f"/api/v1/images/{image_id}"

    return _PLACEHOLDER.sub(token_repl, md)


def from_image_id_scheme(
    md: str,
    filename_to_image_id: dict[str, int],
    on_missing: OnMissing = "strip",
) -> str:
    """Rewrite legacy ``![alt](image:NNN)`` markdown into ``![alt](/api/v1/images/NNN)``.

    Pairs with :func:`from_placeholder`: where ``from_placeholder`` resolves
    parser-emitted basename placeholders, this helper resolves the
    summarizer-emitted ``image:NNN`` scheme that older prompts produced.

    Behavior when ``image_id`` is not in the section's image map:

    - ``on_missing='strip'`` (default) — replace the markdown image with
      ``[alt](#)`` (a non-image link with the alt text) so the rendered
      output stays readable. A structlog warning is emitted per orphan id.
    - ``on_missing='keep'`` — leave the original ``![alt](image:NNN)``
      token untouched so a later pass can resolve it.

    Idempotent: rewritten output contains absolute URLs which the regex
    does not match, so re-running is a no-op. Malformed tokens
    (``image:abc``, ``image:``) are also left untouched.
    """
    known_ids = set(filename_to_image_id.values())

    def _replace(m: re.Match) -> str:
        alt, raw_id = m.group(1), m.group(2)
        image_id = int(raw_id)
        if image_id in known_ids:
            return f"![{alt}](/api/v1/images/{image_id})"
        if on_missing == "strip":
            logger.warning("legacy_image_ref_orphan", image_id=image_id)
            return f"[{alt}](#)"
        return m.group(0)

    return _LEGACY_IMAGE_RE.sub(_replace, md)
