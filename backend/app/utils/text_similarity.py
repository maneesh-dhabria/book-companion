"""Small-string similarity helpers used by AI-tag fuzzy dedupe.

Hand-rolled Levenshtein distance (no new runtime deps). Bounded to the
sub-40-char tag space so the O(len_a*len_b) cost is trivial.
"""

from __future__ import annotations


def levenshtein(a: str, b: str) -> int:
    """Classic dynamic-programming edit distance."""
    if len(a) < len(b):
        return levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]


def fuzzy_dedupe_against(
    candidates: list[str], against: list[str], threshold: int = 2
) -> list[str]:
    """Return items from ``candidates`` that are not within ``threshold`` edits
    of any string in ``against`` (case-insensitive).

    Preserves input order; stable for UI display.
    """
    against_lower = {s.lower() for s in against if s}
    if not against_lower:
        return [c for c in candidates if c]
    out: list[str] = []
    for c in candidates:
        if not c:
            continue
        cl = c.lower()
        if any(levenshtein(cl, al) <= threshold for al in against_lower):
            continue
        out.append(c)
    return out
