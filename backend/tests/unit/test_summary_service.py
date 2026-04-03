"""Tests for SummaryService concept diff and extraction."""

import pytest
from app.services.summary_service import SummaryService, BOLD_PATTERN, HEADER_PATTERN, NAMED_ENTITY_PATTERN


class TestConceptExtraction:
    def setup_method(self):
        self.svc = SummaryService.__new__(SummaryService)

    def test_extracts_bold_terms(self):
        text = "The **Five Forces** framework and **Value Chain** analysis"
        concepts = self.svc.extract_concepts(text)
        assert "Five Forces" in concepts
        assert "Value Chain" in concepts

    def test_extracts_headers(self):
        text = "## Strategic Positioning\nContent here\n### Cost Leadership"
        concepts = self.svc.extract_concepts(text)
        assert "Strategic Positioning" in concepts
        assert "Cost Leadership" in concepts

    def test_extracts_named_entities(self):
        text = "Michael Porter argues that Competitive Advantage is key"
        concepts = self.svc.extract_concepts(text)
        assert "Michael Porter" in concepts
        assert "Competitive Advantage" in concepts

    def test_concept_diff(self):
        from unittest.mock import MagicMock
        a = MagicMock()
        a.summary_md = "The **Five Forces** drive **Competitive Advantage**"
        b = MagicMock()
        b.summary_md = "The **Five Forces** and **Value Chain** are central"
        diff = self.svc.concept_diff(a, b)
        assert "Competitive Advantage" in diff["only_in_a"]
        assert "Value Chain" in diff["only_in_b"]
        assert "Five Forces" in diff["shared"]

    def test_empty_text(self):
        concepts = self.svc.extract_concepts("")
        assert concepts == set()
