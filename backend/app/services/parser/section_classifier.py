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
    "license": re.compile(
        r"\b(project\s*gutenberg.*license|full\s*license|end\s+of\s+the\s+project\s+gutenberg)\b",
        re.IGNORECASE,
    ),
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
    "notes": re.compile(
        r"\b(end\s*notes?|chapter\s*notes?|foot\s*notes?|notes?)\b",
        re.IGNORECASE,
    ),
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

# FR-F4.1 — detect short bylines / translator credits commonly found in
# Gutenberg-era books and classify them as title_page so they skip
# summarization. Two signals must BOTH fire:
#   1. Title is short enough to look like a byline (≤5 words, ≤80 chars),
#      AND either all-caps or a "Name, M.A." / "NAME, TRANSLATOR" pattern.
#   2. The section body is shorter than 200 characters — a real chapter
#      named "Joan Magretta: A Memoir" has far more content than a byline.
_BYLINE_TITLE_RE = re.compile(
    r"""
    ^\s*
    (?:
        # All-caps name with ≥1 space (rules out single-word ALL CAPS headings),
        # optional credential/translator suffix.
        [A-Z][A-Z\ \.\'\-]+\s[A-Z][A-Z\ \.\'\-]+
        (?:,\s*[A-Z][A-Z\.\ ]*)?
        |
        # TitleCase name REQUIRING an explicit suffix — otherwise "Random
        # Title" or "What This Book Contains" would match.
        (?:[A-Z][a-z]+\s+){0,3}[A-Z][a-z]+
        ,\s*(?:Translator|M\.A\.|Ph\.D\.|Editor|Trans\.|Ed\.)\s*\.?
    )
    \s*$
    """,
    re.VERBOSE,
)
_BYLINE_CONTENT_GUARD_CHARS = 200

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
        "license",
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
    """Classify a section by its title, with content-aware gates.

    Order of operations:
      1. First matching named pattern wins (copyright, license, ...).
      2. ``part_header`` is downgraded to ``chapter`` when the body has
         ``len(content_md) >= 1000`` (FR-03).
      3. If no pattern matched, try the byline-style title detection
         (FR-F4.1): a title that looks like a name / translator credit
         AND a body shorter than 200 characters both signal a Gutenberg
         title page. A long body with a name-shaped title stays
         ``chapter`` — chapters are occasionally named after people.
      4. Default ``chapter``.
    """
    if not title:
        return "chapter"
    for section_type, pattern in SECTION_TYPE_PATTERNS.items():
        if pattern.search(title):
            if section_type == "part_header" and len(content_md or "") >= 1000:
                return "chapter"
            return section_type

    # FR-F4.1 byline detection — guard-gated by both title shape AND
    # body length.
    stripped = title.strip()
    if (
        len(stripped) <= 80
        and len(stripped.split()) <= 5
        and _BYLINE_TITLE_RE.match(stripped)
        and len(content_md or "") < _BYLINE_CONTENT_GUARD_CHARS
    ):
        return "title_page"

    return "chapter"
