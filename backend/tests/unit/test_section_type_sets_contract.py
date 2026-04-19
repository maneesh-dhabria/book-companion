"""Cross-layer guard: backend classifier sets must match frontend mirror."""

import re
from pathlib import Path

from app.services.parser.section_classifier import (
    FRONT_MATTER_TYPES,
    SUMMARIZABLE_TYPES,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
READER_TS = REPO_ROOT / "frontend" / "src" / "stores" / "reader.ts"


def _extract_set_literal(name: str, source: str) -> set[str]:
    m = re.search(
        rf"export const {re.escape(name)}[^=]+=\s*new Set\(\[(.*?)\]\)",
        source,
        re.DOTALL,
    )
    if not m:
        raise AssertionError(f"could not find {name} in reader.ts")
    body = m.group(1)
    return set(re.findall(r"'([^']+)'", body))


def test_front_matter_types_match_frontend():
    src = READER_TS.read_text()
    frontend_set = _extract_set_literal("FRONT_MATTER_TYPES", src)
    assert frontend_set == set(FRONT_MATTER_TYPES), (
        f"drift: backend={set(FRONT_MATTER_TYPES)} frontend={frontend_set}"
    )


def test_summarizable_types_match_frontend():
    src = READER_TS.read_text()
    frontend_set = _extract_set_literal("SUMMARIZABLE_TYPES", src)
    assert frontend_set == set(SUMMARIZABLE_TYPES), (
        f"drift: backend={set(SUMMARIZABLE_TYPES)} frontend={frontend_set}"
    )
