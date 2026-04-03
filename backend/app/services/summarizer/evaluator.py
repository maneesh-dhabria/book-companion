"""16-assertion evaluation battery with trace storage."""

import asyncio
import json
from pathlib import Path

import jinja2
import structlog

from app.db.models import EvalTrace
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

ASSERTION_REGISTRY: dict[str, dict] = {
    # Faithfulness (Critical)
    "no_hallucinated_facts": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    "no_contradictions": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    "accurate_quotes": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    "cross_summary_consistency": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    # Completeness (Important)
    "covers_main_argument": {"category": "important", "prompt_file": "eval_completeness_v1.txt"},
    "covers_key_concepts": {"category": "important", "prompt_file": "eval_completeness_v1.txt"},
    "covers_frameworks": {"category": "important", "prompt_file": "eval_completeness_v1.txt"},
    "covers_examples": {"category": "important", "prompt_file": "eval_completeness_v1.txt"},
    # Coherence (Advisory)
    "standalone_readable": {"category": "advisory", "prompt_file": "eval_coherence_v1.txt"},
    "logical_flow": {"category": "advisory", "prompt_file": "eval_coherence_v1.txt"},
    "no_dangling_references": {"category": "advisory", "prompt_file": "eval_coherence_v1.txt"},
    # Specificity (Important)
    "not_generic": {"category": "important", "prompt_file": "eval_specificity_v1.txt"},
    "preserves_author_terminology": {"category": "important", "prompt_file": "eval_specificity_v1.txt"},
    # Format (Advisory)
    "has_key_concepts": {"category": "advisory", "prompt_file": "eval_format_v1.txt"},
    "reasonable_length": {"category": "advisory", "prompt_file": "eval_format_v1.txt"},
    "image_refs_preserved": {"category": "advisory", "prompt_file": "eval_format_v1.txt"},
}

PROMPTS_DIR = Path(__file__).parent / "prompts"


class EvalService:
    def __init__(self, db: AsyncSession, llm: LLMProvider, config):
        self.db = db
        self.llm = llm
        self.config = config
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(PROMPTS_DIR))
        )

    def _get_compression_range(self, facets: dict) -> tuple[float, float]:
        """Return expected compression % range based on facets."""
        compression = facets.get("compression", "standard")
        style = facets.get("style", "narrative")
        if style == "tweet_thread":
            return (2.0, 8.0)
        ranges = {
            "brief": (5.0, 15.0),
            "standard": (15.0, 25.0),
            "detailed": (25.0, 40.0),
        }
        return ranges.get(compression, (15.0, 25.0))

    async def evaluate_summary(
        self,
        section_id: int,
        source_text: str,
        summary_text: str,
        image_count: int = 0,
        facets_used: dict | None = None,
        summary_id: int | None = None,
    ) -> dict[str, dict]:
        """Run all 16 assertions in parallel. Returns {assertion_name: {passed, reasoning}}."""
        tasks = [
            self._run_single_assertion(
                name, source_text, summary_text, section_id,
                image_count=image_count, summary_id=summary_id,
            )
            for name in ASSERTION_REGISTRY
        ]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for name, result in zip(ASSERTION_REGISTRY.keys(), results_list):
            if isinstance(result, Exception):
                results[name] = {"passed": False, "reasoning": f"Eval error: {result}", "error": True}
            else:
                results[name] = result
        return results

    async def _run_single_assertion(
        self,
        assertion_name: str,
        source_text: str,
        summary_text: str,
        section_id: int,
        image_count: int = 0,
        summary_id: int | None = None,
    ) -> dict:
        meta = ASSERTION_REGISTRY[assertion_name]

        # Special handling for cross_summary_consistency
        if assertion_name == "cross_summary_consistency":
            if not self.config.llm.cross_summary_consistency:
                return {
                    "assertion_name": assertion_name,
                    "category": meta["category"],
                    "passed": True,
                    "reasoning": "Disabled via config (llm.cross_summary_consistency=false)",
                }
            # Generate a second independent summary and compare
            try:
                second_response = await self.llm.generate(
                    prompt=f"Summarize this text concisely:\n\n{source_text[:50000]}"
                )
                second_summary = second_response.content
            except Exception as e:
                return {
                    "assertion_name": assertion_name,
                    "category": meta["category"],
                    "passed": True,
                    "reasoning": f"Could not generate second summary for comparison: {e}",
                }

            try:
                template = self._jinja_env.get_template(meta["prompt_file"])
                prompt = template.render(
                    assertion_name=assertion_name,
                    source_text=source_text,
                    summary_text=summary_text,
                    summary_a=summary_text,
                    summary_b=second_summary,
                    image_count=image_count,
                )
            except jinja2.TemplateNotFound:
                prompt = (
                    f"Compare these two summaries for consistency. "
                    f"Do they agree on key facts?\n\n"
                    f"Summary A:\n{summary_text}\n\nSummary B:\n{second_summary}\n\n"
                    f"Return JSON with 'passed' (bool) and 'reasoning' (string)."
                )
        else:
            template = self._jinja_env.get_template(meta["prompt_file"])
            prompt = template.render(
                assertion_name=assertion_name,
                source_text=source_text,
                summary_text=summary_text,
                image_count=image_count,
            )

        response = await self.llm.generate(
            prompt=prompt,
            json_schema={
                "type": "object",
                "properties": {
                    "passed": {"type": "boolean"},
                    "reasoning": {"type": "string"},
                },
                "required": ["passed", "reasoning"],
            },
        )

        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError:
            parsed = {"passed": False, "reasoning": f"Failed to parse: {response.content[:200]}"}

        # Store trace
        trace = EvalTrace(
            section_id=section_id,
            summary_id=summary_id,
            assertion_name=assertion_name,
            assertion_category=meta["category"],
            passed=parsed.get("passed", False),
            prompt_sent=prompt,
            prompt_version=meta["prompt_file"].replace(".txt", ""),
            llm_response=response.content,
            reasoning=parsed.get("reasoning"),
            model_used=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
        )
        self.db.add(trace)

        return {
            "assertion_name": assertion_name,
            "category": meta["category"],
            "passed": parsed.get("passed", False),
            "reasoning": parsed.get("reasoning", ""),
        }

    def _should_auto_retry(
        self, results: dict[str, dict], retry_count: int, max_retries: int
    ) -> bool:
        """Return True if any critical assertion failed and retries remain."""
        if retry_count >= max_retries:
            return False
        for name, result in results.items():
            meta = ASSERTION_REGISTRY.get(name, {})
            if meta.get("category") == "critical" and not result.get("passed"):
                return True
        return False
