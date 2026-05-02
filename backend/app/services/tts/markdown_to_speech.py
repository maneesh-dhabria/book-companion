"""Markdown → speech-clean text sanitizer.

Strips constructs that don't read well aloud (footnote markers, code blocks,
bare URLs, math) and rewrites image/link tokens to short narration. Returns
both the cleaned text and per-sentence character offsets keyed by pysbd.

The version constant is bumped whenever output changes — generated MP3 rows
that record the prior version are flagged stale on lookup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pysbd
from markdown_it import MarkdownIt

SANITIZER_VERSION = "1.0"

_ABBREVIATIONS = [
    (r"\bDr\.\B", "Doctor"),
    (r"\bMr\.\B", "Mister"),
    (r"\bMrs\.\B", "Misses"),
    (r"\bMs\.\B", "Ms"),
    (r"\bSt\.\B", "Saint"),
    (r"\be\.g\.", "for example"),
    (r"\bi\.e\.", "that is"),
    (r"\betc\.", "et cetera"),
]

_FOOTNOTE_BRACKET_RE = re.compile(r"\[\d+\]")
_FOOTNOTE_CARET_RE = re.compile(r"\^\d+")
_BARE_URL_RE = re.compile(r"https?://\S+")
_MATH_INLINE_DOLLAR_RE = re.compile(r"\$[^$\n]+\$")
_MATH_BRACKET_RE = re.compile(r"\\\[[^\]]+\\\]")
_MATH_PAREN_RE = re.compile(r"\\\([^)]+\\\)")
_WHITESPACE_RE = re.compile(r"\s+")


class EmptySanitizedTextError(Exception):
    pass


@dataclass
class SanitizedText:
    text: str
    sentence_offsets_chars: list[int] = field(default_factory=list)
    sanitizer_version: str = SANITIZER_VERSION


_md = MarkdownIt("commonmark", {"breaks": False, "html": False})
_segmenter = pysbd.Segmenter(language="en", clean=False)


def _walk_inline(tokens) -> str:
    parts: list[str] = []
    for tok in tokens:
        if tok.type == "image":
            alt = (tok.content or "").strip()
            if alt:
                parts.append(f"figure: {alt}")
            continue
        if tok.type == "code_inline":
            continue
        if tok.children:
            parts.append(_walk_inline(tok.children))
        elif tok.content:
            parts.append(tok.content)
    return " ".join(p for p in parts if p)


def _walk_blocks(tokens) -> str:
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type in ("fence", "code_block"):
            content = tok.content or ""
            if content.strip():
                line_count = content.rstrip("\n").count("\n") + 1
                out.append(f"code block, {line_count} lines, skipped.")
        elif tok.type == "inline":
            out.append(_walk_inline(tok.children or []))
        elif tok.type == "heading_open":
            j = i + 1
            inner_text = ""
            while j < len(tokens) and tokens[j].type != "heading_close":
                if tokens[j].type == "inline":
                    inner_text = _walk_inline(tokens[j].children or [])
                j += 1
            if inner_text:
                out.append(inner_text)
            i = j
        i += 1
    return "\n".join(s for s in out if s)


def sanitize(md: str) -> SanitizedText:
    if not md or not md.strip():
        raise EmptySanitizedTextError("input is empty")

    pre = md
    pre = _MATH_INLINE_DOLLAR_RE.sub(" equation, omitted. ", pre)
    pre = _MATH_BRACKET_RE.sub(" equation, omitted. ", pre)
    pre = _MATH_PAREN_RE.sub(" equation, omitted. ", pre)
    pre = _FOOTNOTE_BRACKET_RE.sub("", pre)
    pre = _FOOTNOTE_CARET_RE.sub("", pre)

    tokens = _md.parse(pre)
    text = _walk_blocks(tokens)

    text = _BARE_URL_RE.sub("", text)
    for pattern, replacement in _ABBREVIATIONS:
        text = re.sub(pattern, replacement, text)
    text = _WHITESPACE_RE.sub(" ", text).strip()

    if not text:
        raise EmptySanitizedTextError("sanitized text is empty")

    sentences = _segmenter.segment(text)
    offsets: list[int] = []
    cursor = 0
    for sent in sentences:
        idx = text.find(sent, cursor)
        if idx == -1:
            idx = cursor
        offsets.append(idx)
        cursor = idx + len(sent)

    if not offsets:
        raise EmptySanitizedTextError("zero sentences after segmentation")

    return SanitizedText(text=text, sentence_offsets_chars=offsets)
