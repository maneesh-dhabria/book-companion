"""Slug helpers for filename and TOC anchor derivation.

Two helpers, one intent each (per spec D21):
  - filename_slug: ASCII-only, cross-OS filesystem safety
  - gfm_slug: Unicode-aware, matches GFM viewer auto-anchors
"""

import re

_FILENAME_RE = re.compile(r"[^a-z0-9]+")
_GFM_KEEP_RE = re.compile(r"[^\w\s\-]+", re.UNICODE)
_GFM_WS_RE = re.compile(r"[\s_]+")
_GFM_DASH_RE = re.compile(r"-{2,}")


def filename_slug(title: str) -> str:
    """ASCII-only filesystem-safe slug. Returns empty string for non-ASCII titles."""
    return _FILENAME_RE.sub("-", title.lower()).strip("-")[:80]


def gfm_slug(title: str) -> str:
    """Unicode-aware GFM slug. Lowercase, drop non-(alnum|ws|dash|underscore),
    collapse whitespace/underscores to dashes, collapse consecutive dashes,
    strip leading/trailing dashes."""
    lowered = title.lower()
    stripped = _GFM_KEEP_RE.sub("", lowered)
    dashed = _GFM_WS_RE.sub("-", stripped)
    collapsed = _GFM_DASH_RE.sub("-", dashed)
    return collapsed.strip("-")
