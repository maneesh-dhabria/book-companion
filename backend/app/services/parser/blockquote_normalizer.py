"""Collapse nested ``>`` blockquote chains and strip boundary HRs.

Publishers often use CSS-hack HTML like::

    <blockquote><blockquote>
      <hr/>
      <p>The value proposition is the element of strategy.</p>
      <hr/>
    </blockquote></blockquote>

markdownify renders this as::

    > > ---
    > >
    > > The value proposition is the element of strategy.
    > >
    > > ---

Visually the nested bars look like a double quote marker and the
boundary ``---`` lines render as decorative rules that clash with the
quote indentation. This module normalises both: every line's leading
``>`` chain of length 2+ is collapsed to a single ``>``, and any
``---`` that appears as the first or last line of a contiguous
blockquote block (post-collapse) is dropped.

The function is intentionally pure and line-based so it is trivially
idempotent and unit-testable.
"""

from __future__ import annotations

import re

# Match one or more ``>`` markers at the start of a line, optionally
# separated by whitespace. ``> > > text`` / ``>>> text`` / ``> >text`` all
# collapse to ``> text``. Captures the rest of the line (content after the
# last ``>``-and-optional-space).
_QUOTE_PREFIX = re.compile(r"^((?:>\s*)+)(.*)$")


def _quote_level(line: str) -> int:
    """Number of leading ``>`` markers; 0 if the line is not a blockquote."""
    count = 0
    i = 0
    while i < len(line):
        if line[i] == ">":
            count += 1
            i += 1
            # consume optional single space after the marker
            if i < len(line) and line[i] == " ":
                i += 1
            continue
        break
    return count


def _strip_quote_prefix(line: str) -> str:
    """Return the line with a single collapsed ``> `` prefix and the remaining body.

    Preserves body whitespace exactly; returns ``"> "`` for empty-body quote
    lines.
    """
    m = _QUOTE_PREFIX.match(line)
    if not m:
        return line
    body = m.group(2)
    if body == "":
        return ">"
    return "> " + body.lstrip()


def normalize_blockquotes(md: str) -> str:
    """Collapse nested ``>`` chains and strip boundary-HR lines.

    Empty input returns empty output. Idempotent.
    """
    if not md:
        return md

    lines = md.split("\n")

    # Phase 1: collapse any line with ``>`` prefix to a single-level quote.
    collapsed: list[str] = []
    for line in lines:
        if _quote_level(line) >= 1:
            collapsed.append(_strip_quote_prefix(line))
        else:
            collapsed.append(line)

    # Phase 2: for each contiguous run of blockquote lines, drop a leading
    # or trailing ``> ---`` / ``>---`` marker.
    result: list[str] = []
    i = 0
    n = len(collapsed)
    while i < n:
        line = collapsed[i]
        is_quote = line.startswith(">")
        if not is_quote:
            result.append(line)
            i += 1
            continue
        # Collect the contiguous quote block (including blank `>` lines).
        block_start = i
        while i < n and collapsed[i].startswith(">"):
            i += 1
        block = collapsed[block_start:i]
        # Identify first and last non-blank lines within the block.
        first_idx = None
        last_idx = None
        for j, bl in enumerate(block):
            body = bl[1:].lstrip() if len(bl) > 1 else ""
            if body != "":
                if first_idx is None:
                    first_idx = j
                last_idx = j
        # Drop HR at first or last non-blank if it's a bare '---'.
        drops: set[int] = set()
        for idx in (first_idx, last_idx):
            if idx is None:
                continue
            body = block[idx][1:].lstrip() if len(block[idx]) > 1 else ""
            if body == "---":
                drops.add(idx)
        for j, bl in enumerate(block):
            if j not in drops:
                result.append(bl)

    return "\n".join(result)
