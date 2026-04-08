"""Golden set regression tests for the eval system."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.summarizer.evaluator import (
    REFERENCE_SECTION_TYPES,
    EvalService,
)
from app.services.summarizer.summarizer_service import SummarizerService

GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden_eval"


def load_fixture(name: str) -> dict:
    with open(GOLDEN_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def eval_service():
    db = AsyncMock()
    llm = AsyncMock()
    config = MagicMock()
    config.llm.cross_summary_consistency = False
    return EvalService(db, llm, config)


class TestGoldenDeterministic:
    @pytest.mark.asyncio
    async def test_golden_deterministic_all_pass(self, eval_service):
        fixture = load_fixture("book2_section_all_pass.json")
        for name, expected in fixture["expected_deterministic_results"].items():
            if name == "reasonable_length":
                result = await eval_service._check_reasonable_length(
                    fixture["source_text"],
                    fixture["summary_text"],
                    fixture["facets_used"],
                    1,
                    1,
                    "golden-1",
                )
            elif name == "has_key_concepts":
                result = await eval_service._check_has_key_concepts(
                    fixture["summary_text"],
                    1,
                    1,
                    "golden-1",
                )
            elif name == "image_refs_preserved":
                result = await eval_service._check_image_refs_preserved(
                    fixture["source_text"],
                    fixture["summary_text"],
                    0,
                    1,
                    1,
                    "golden-1",
                )
            assert result["passed"] == expected, f"{name}: expected {expected}, got {result}"

    @pytest.mark.asyncio
    async def test_golden_reasonable_length_pass(self, eval_service):
        fixture = load_fixture("book2_section_all_pass.json")
        result = await eval_service._check_reasonable_length(
            fixture["source_text"],
            fixture["summary_text"],
            fixture["facets_used"],
            1,
            1,
            "golden-2",
        )
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_golden_glossary_skips_examples(self, eval_service):
        """Glossary section should skip covers_examples."""
        fixture = load_fixture("book2_section_glossary.json")
        assert fixture["section_type"] in REFERENCE_SECTION_TYPES

    @pytest.mark.asyncio
    async def test_golden_paraphrased_quote_detected(self, eval_service):
        fixture = load_fixture("book2_section_paraphrased_quote.json")
        warnings = SummarizerService._check_paraphrased_quotes(
            fixture["source_text"], fixture["summary_text"]
        )
        assert len(warnings) >= 1
        assert warnings[0]["type"] == "paraphrased_quote"

    @pytest.mark.asyncio
    async def test_golden_preset_skips_key_concepts(self, eval_service):
        """practitioner_bullets preset should skip has_key_concepts."""
        skip = eval_service._load_skip_assertions("practitioner_bullets")
        assert "has_key_concepts" in skip


class TestAutoRetryLogic:
    def test_should_retry_critical_failure(self):
        eval_results = {
            "assertions": {
                "no_hallucinated_facts": {
                    "category": "critical",
                    "passed": False,
                    "reasoning": "test",
                },
                "covers_main_argument": {
                    "category": "important",
                    "passed": True,
                    "reasoning": "test",
                },
            }
        }
        assert EvalService._should_retry(eval_results) is True

    def test_should_retry_important_failure(self):
        eval_results = {
            "assertions": {
                "no_hallucinated_facts": {
                    "category": "critical",
                    "passed": True,
                    "reasoning": "test",
                },
                "covers_main_argument": {
                    "category": "important",
                    "passed": False,
                    "reasoning": "test",
                },
            }
        }
        assert EvalService._should_retry(eval_results) is True

    def test_should_retry_advisory_only(self):
        eval_results = {
            "assertions": {
                "standalone_readable": {
                    "category": "advisory",
                    "passed": False,
                    "reasoning": "test",
                },
            }
        }
        assert EvalService._should_retry(eval_results) is False

    def test_should_retry_all_pass(self):
        eval_results = {
            "assertions": {
                "no_hallucinated_facts": {
                    "category": "critical",
                    "passed": True,
                    "reasoning": "ok",
                },
            }
        }
        assert EvalService._should_retry(eval_results) is False

    def test_should_retry_skipped_ignored(self):
        eval_results = {
            "assertions": {
                "no_hallucinated_facts": {
                    "category": "critical",
                    "passed": True,
                    "reasoning": "ok",
                    "skipped": True,
                },
            }
        }
        assert EvalService._should_retry(eval_results) is False

    def test_should_retry_error_ignored(self):
        eval_results = {
            "assertions": {
                "no_hallucinated_facts": {
                    "category": "critical",
                    "passed": False,
                    "reasoning": "error",
                    "error": True,
                },
            }
        }
        assert EvalService._should_retry(eval_results) is False

    def test_build_fix_prompt_uses_suggestions(self):
        eval_results = {
            "assertions": {
                "covers_main_argument": {
                    "category": "important",
                    "passed": False,
                    "reasoning": "missing",
                    "suggestion": "Add the thesis statement",
                },
            }
        }
        prompt = EvalService._build_fix_prompt(eval_results)
        assert "Add the thesis statement" in prompt

    def test_build_fix_prompt_null_suggestion_fallback(self):
        eval_results = {
            "assertions": {
                "covers_main_argument": {
                    "category": "important",
                    "passed": False,
                    "reasoning": "missing",
                },
            }
        }
        prompt = EvalService._build_fix_prompt(eval_results)
        assert "covers_main_argument" in prompt

    def test_build_fix_prompt_multiple_failures(self):
        eval_results = {
            "assertions": {
                "no_hallucinated_facts": {
                    "category": "critical",
                    "passed": False,
                    "reasoning": "test",
                    "suggestion": "Fix hallucinations",
                },
                "covers_main_argument": {
                    "category": "important",
                    "passed": False,
                    "reasoning": "test",
                    "suggestion": "Add thesis",
                },
            }
        }
        prompt = EvalService._build_fix_prompt(eval_results)
        assert "Fix hallucinations" in prompt
        assert "Add thesis" in prompt
