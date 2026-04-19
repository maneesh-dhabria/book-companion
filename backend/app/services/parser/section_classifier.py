"""Shared section-type classifier used by all parsers and Migration B.

Pattern-order contract (FR-07, D13): front-matter patterns are evaluated
before content-body patterns. First match wins. Python 3.7+ dict ordering
is insertion-ordered by guarantee.

Content-aware note (FR-03): `part_header` requires BOTH a title match
AND `len(content_md or "") < 1000`. `len(content_md)` counts markdown
syntax; the ±50-char overhead does not flip the 1000-char decision
in realistic content.

Frontend mirror: `frontend/src/stores/reader.ts` exports the same two
set constants. A cross-layer contract test in
`tests/unit/test_section_type_sets_contract.py` enforces equality.
"""

from __future__ import annotations

import re

SECTION_TYPE_PATTERNS: dict[str, re.Pattern] = {
    "copyright": re.compile(r"\bcopyright\b|©", re.IGNORECASE),
    "acknowledgments": re.compile(r"\backnowledg(e)?ments?\b", re.IGNORECASE),
    "dedication": re.compile(r"\bdedication\b", re.IGNORECASE),
    "title_page": re.compile(r"\btitle\s*page\b", re.IGNORECASE),
    "table_of_contents": re.compile(
        r"^(table\s+of\s+contents|contents)\s*$", re.IGNORECASE
    ),
    "colophon": re.compile(r"\bcolophon\b", re.IGNORECASE),
    "cover": re.compile(r"^cover$|^book\s*cover$", re.IGNORECASE),
    "part_header": re.compile(
        r"^part\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b",
        re.IGNORECASE,
    ),
    "glossary": re.compile(r"\bglossary\b", re.IGNORECASE),
    "notes": re.compile(r"\b(end\s*notes?|chapter\s*notes?|notes?)\b", re.IGNORECASE),
    "appendix": re.compile(r"\bappendix\b", re.IGNORECASE),
    "bibliography": re.compile(
        r"\b(bibliography|works?\s+cited|references)\b", re.IGNORECASE
    ),
    "index": re.compile(r"\bindex\b", re.IGNORECASE),
    "about_author": re.compile(r"\babout\s+the\s+author\b", re.IGNORECASE),
    "foreword": re.compile(r"\bforeword\b", re.IGNORECASE),
    "preface": re.compile(r"\bpreface\b", re.IGNORECASE),
    "introduction": re.compile(r"\bintroduction\b", re.IGNORECASE),
    "epilogue": re.compile(r"\bepilogue\b", re.IGNORECASE),
    "conclusion": re.compile(r"\bconclusion\b", re.IGNORECASE),
}

FRONT_MATTER_TYPES: frozenset[str] = frozenset(
    {
        "copyright",
        "acknowledgments",
        "dedication",
        "title_page",
        "table_of_contents",
        "colophon",
        "cover",
        "part_header",
    }
)

SUMMARIZABLE_TYPES: frozenset[str] = frozenset(
    {
        "chapter",
        "introduction",
        "preface",
        "foreword",
        "epilogue",
        "conclusion",
    }
)


def detect_section_type(title: str, content_md: str | None = None) -> str:
    """Classify a section by its title, with content-aware gate for part_header.

    Returns the first matching pattern's key, else ``"chapter"``. If a title
    matches ``part_header`` but ``len(content_md or "") >= 1000``, returns
    ``"chapter"`` instead (content-aware override per FR-03).
    """
    if not title:
        return "chapter"
    for section_type, pattern in SECTION_TYPE_PATTERNS.items():
        if pattern.search(title):
            if section_type == "part_header" and len(content_md or "") >= 1000:
                return "chapter"
            return section_type
    return "chapter"
