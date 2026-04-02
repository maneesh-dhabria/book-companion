"""Tests for 3-tier structure detection."""

import pytest
from app.services.parser.structure_detector import StructureDetector
from app.services.parser.base import ParsedSection


def test_heuristic_heading_detection():
    """Tier 2: Detect chapters from heading patterns."""
    detector = StructureDetector(llm_provider=None)
    content = (
        "# Chapter 1: Introduction\n\nSome content here.\n\n"
        "# Chapter 2: Main Ideas\n\nMore content here.\n\n"
        "## Section 2.1: Details\n\nSub-section content.\n"
    )
    sections = detector.detect_from_heuristics(content)
    assert len(sections) >= 2
    assert sections[0].title == "Chapter 1: Introduction"


def test_embedded_toc_passthrough():
    """Tier 1: If sections already extracted from TOC, pass through."""
    detector = StructureDetector(llm_provider=None)
    existing = [
        ParsedSection(title="Ch1", content_md="content1", depth=0, order_index=0),
        ParsedSection(title="Ch2", content_md="content2", depth=0, order_index=1),
    ]
    result = detector.validate_structure(existing)
    assert result == existing  # No changes needed


def test_flat_content_triggers_heuristic():
    """If only 1 section, try heuristic splitting."""
    detector = StructureDetector(llm_provider=None)
    flat = [
        ParsedSection(
            title="Full Book",
            content_md="# Ch1\n\nContent 1\n\n# Ch2\n\nContent 2\n",
            depth=0,
            order_index=0,
        )
    ]
    result = detector.validate_structure(flat)
    assert len(result) >= 2
