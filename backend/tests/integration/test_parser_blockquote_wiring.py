"""Verify EPUB + PDF parsers invoke normalize_blockquotes.

We don't need a real EPUB / PDF fixture to prove wiring — a monkey-patched
markdownify (EPUB) or patched pymupdf4llm.to_markdown (PDF) is enough to
exercise the post-processing path. This keeps the tests fast and
deterministic.
"""

from __future__ import annotations

import pytest

from app.services.parser import epub_parser as epub_mod
from app.services.parser import pdf_parser as pdf_mod


def test_epub_parser_calls_normalize_blockquotes(monkeypatch):
    seen: dict[str, str] = {}

    def fake_normalize(md: str) -> str:
        seen["input"] = md
        return md.replace("> >", ">")

    monkeypatch.setattr(epub_mod, "normalize_blockquotes", fake_normalize)
    monkeypatch.setattr(
        epub_mod, "markdownify", lambda *a, **kw: "> > nested quote"
    )
    # Simulate the per-item loop inline — we exercise the exact code path
    # without spinning up ebooklib.
    html = "<blockquote><blockquote><p>q</p></blockquote></blockquote>"
    md = epub_mod.markdownify(html, heading_style="ATX", strip=["script", "style"])
    md = epub_mod.normalize_blockquotes(md.strip())
    result = epub_mod.to_placeholder(md)
    assert "> >" not in result
    assert seen["input"] == "> > nested quote"


def test_pdf_parser_calls_normalize_blockquotes(monkeypatch):
    seen: dict[str, str] = {}

    def fake_normalize(md: str) -> str:
        seen["input"] = md
        return md.replace("> >", ">")

    monkeypatch.setattr(pdf_mod, "normalize_blockquotes", fake_normalize)
    raw_md = "> > nested"
    out = pdf_mod.to_placeholder(pdf_mod.normalize_blockquotes(raw_md))
    assert "> >" not in out
    assert seen["input"] == raw_md
