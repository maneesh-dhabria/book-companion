"""FR-34: deterministic concept_label normalization for dedup JOINs."""

import re

_TRAILING_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
_DASH_UNDER = re.compile(r"[-_]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_concept_label(s: str) -> str:
    s = s.strip().lower()
    s = _TRAILING_PAREN.sub("", s)
    s = _DASH_UNDER.sub(" ", s)
    s = _WHITESPACE.sub(" ", s).strip()
    return s
