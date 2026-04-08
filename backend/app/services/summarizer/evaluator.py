"""16-assertion evaluation battery with trace storage."""

import asyncio
import json
import re
from pathlib import Path

import jinja2
import structlog
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvalTrace
from app.services.summarizer.llm_provider import LLMProvider

logger = structlog.get_logger()

DETERMINISTIC_ASSERTIONS = {"reasonable_length", "has_key_concepts", "image_refs_preserved"}
FAITHFULNESS_ASSERTIONS = {
    "no_hallucinated_facts",
    "no_contradictions",
    "accurate_quotes",
    "cross_summary_consistency",
}
REFERENCE_SECTION_TYPES = {"glossary", "notes", "bibliography", "index", "appendix"}
BOOK_LEVEL_SKIP = {"image_refs_preserved", "cross_summary_consistency"}
RETRY_ELIGIBLE_CATEGORIES = {"critical", "important"}

ASSERTION_REGISTRY: dict[str, dict] = {
    # Faithfulness (Critical)
    "no_hallucinated_facts": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    "no_contradictions": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    "accurate_quotes": {"category": "critical", "prompt_file": "eval_faithfulness_v1.txt"},
    "cross_summary_consistency": {
        "category": "critical",
        "prompt_file": "eval_faithfulness_v1.txt",
    },
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
    "preserves_author_terminology": {
        "category": "important",
        "prompt_file": "eval_specificity_v1.txt",
    },
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
        self._jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(PROMPTS_DIR)))

    def _load_skip_assertions(self, preset_name: str | None) -> set[str]:
        """Load skip_assertions from a preset YAML file."""
        if not preset_name:
            return set()
        presets_dir = Path(__file__).parent / "prompts" / "presets"
        path = presets_dir / f"{preset_name}.yaml"
        if not path.exists():
            return set()
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            skip = data.get("skip_assertions", [])
            if not isinstance(skip, list):
                return set()
            # Warn on unknown assertion names
            unknown = set(skip) - set(ASSERTION_REGISTRY.keys())
            if unknown:
                logger.warning(
                    "unknown_skip_assertions_in_eval",
                    preset=preset_name,
                    unknown=sorted(unknown),
                )
            return set(skip) & set(ASSERTION_REGISTRY.keys())
        except Exception:
            logger.warning("failed_to_load_preset_skip_assertions", preset=preset_name)
            return set()

    async def _async_skipped_result(
        self,
        assertion_name: str,
        preset_name: str,
        section_id,
        summary_id,
        eval_run_id,
    ) -> dict:
        """Async wrapper for _skipped_result to use in asyncio.gather."""
        return self._skipped_result(
            assertion_name,
            preset_name,
            section_id,
            summary_id,
            eval_run_id,
        )

    def _skipped_result(
        self,
        assertion_name: str,
        preset_name: str,
        section_id,
        summary_id,
        eval_run_id,
    ) -> dict:
        """Create a skipped result for an assertion not applicable to a preset."""
        meta = ASSERTION_REGISTRY[assertion_name]
        reasoning = f"Skipped: not applicable for preset '{preset_name}'"
        trace = EvalTrace(
            section_id=section_id,
            summary_id=summary_id,
            assertion_name=assertion_name,
            assertion_category=meta["category"],
            passed=True,
            reasoning=reasoning,
            model_used="skipped",
            prompt_sent=None,
            prompt_version="skipped",
            llm_response="",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            eval_run_id=eval_run_id,
        )
        self.db.add(trace)
        return {
            "assertion_name": assertion_name,
            "category": meta["category"],
            "passed": True,
            "reasoning": reasoning,
            "skipped": True,
        }

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
        eval_run_id: str | None = None,
        preset_name: str | None = None,
        cumulative_context: str | None = None,
        section_type: str = "chapter",
        eval_scope: str = "section",
        section_count: int | None = None,
    ) -> dict:
        """Run all 16 assertions in parallel. Returns wrapped format with assertions key."""
        import uuid

        if not eval_run_id:
            eval_run_id = str(uuid.uuid4())

        # Build combined skip list
        skip_assertions = self._load_skip_assertions(preset_name)
        if eval_scope == "book":
            skip_assertions |= BOOK_LEVEL_SKIP
        if section_type in REFERENCE_SECTION_TYPES:
            skip_assertions.add("covers_examples")

        # Truncate cumulative context if too long
        if cumulative_context and len(cumulative_context) > 20000:
            cumulative_context = cumulative_context[:20000] + "\n\n[... truncated at 20K chars ...]"

        tasks = []
        task_names = []
        for name in ASSERTION_REGISTRY:
            if name in skip_assertions:
                task_names.append(name)
                tasks.append(
                    self._async_skipped_result(
                        name,
                        preset_name or "default",
                        section_id,
                        summary_id,
                        eval_run_id,
                    )
                )
                continue
            if name in DETERMINISTIC_ASSERTIONS:
                if name == "reasonable_length":
                    tasks.append(
                        self._check_reasonable_length(
                            source_text,
                            summary_text,
                            facets_used,
                            section_id,
                            summary_id,
                            eval_run_id,
                        )
                    )
                elif name == "has_key_concepts":
                    tasks.append(
                        self._check_has_key_concepts(
                            summary_text,
                            section_id,
                            summary_id,
                            eval_run_id,
                        )
                    )
                elif name == "image_refs_preserved":
                    tasks.append(
                        self._check_image_refs_preserved(
                            source_text,
                            summary_text,
                            image_count,
                            section_id,
                            summary_id,
                            eval_run_id,
                        )
                    )
            else:
                # Pass cumulative context only to faithfulness assertions
                ctx = cumulative_context if name in FAITHFULNESS_ASSERTIONS else None
                tasks.append(
                    self._run_single_assertion(
                        name,
                        source_text,
                        summary_text,
                        section_id,
                        image_count=image_count,
                        summary_id=summary_id,
                        eval_run_id=eval_run_id,
                        cumulative_context=ctx,
                        section_type=section_type,
                        eval_scope=eval_scope,
                        section_count=section_count,
                    )
                )
            task_names.append(name)
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        assertions = {}
        passed_count = 0
        total_count = 0
        for name, result in zip(task_names, results_list):
            if isinstance(result, Exception):
                logger.error("assertion_error", assertion=name, error=str(result))
                assertions[name] = {
                    "assertion_name": name,
                    "category": ASSERTION_REGISTRY[name]["category"],
                    "passed": False,
                    "reasoning": f"Eval error: {result}",
                    "error": True,
                }
            else:
                assertions[name] = result
            total_count += 1
            if assertions[name].get("passed"):
                passed_count += 1

        return {
            "passed": passed_count,
            "total": total_count,
            "eval_run_id": eval_run_id,
            "assertions": assertions,
        }

    async def _run_single_assertion(
        self,
        assertion_name: str,
        source_text: str,
        summary_text: str,
        section_id: int,
        image_count: int = 0,
        summary_id: int | None = None,
        eval_run_id: str | None = None,
        cumulative_context: str | None = None,
        section_type: str = "chapter",
        eval_scope: str = "section",
        section_count: int | None = None,
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
                    cumulative_context=cumulative_context,
                    section_type=section_type,
                    eval_scope=eval_scope,
                    section_count=section_count,
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
                cumulative_context=cumulative_context,
                section_type=section_type,
                eval_scope=eval_scope,
                section_count=section_count,
            )

        response = await self.llm.generate(
            prompt=prompt,
            json_schema={
                "type": "object",
                "properties": {
                    "passed": {"type": "boolean"},
                    "reasoning": {"type": "string"},
                    "likely_cause": {"type": ["string", "null"]},
                    "suggestion": {"type": ["string", "null"]},
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
            likely_cause=parsed.get("likely_cause"),
            suggestion=parsed.get("suggestion"),
            eval_run_id=eval_run_id,
        )
        self.db.add(trace)

        return {
            "assertion_name": assertion_name,
            "category": meta["category"],
            "passed": parsed.get("passed", False),
            "reasoning": parsed.get("reasoning", ""),
        }

    async def _check_reasonable_length(
        self,
        source_text: str,
        summary_text: str,
        facets_used: dict | None,
        section_id: int | None,
        summary_id: int | None,
        eval_run_id: str | None,
    ) -> dict:
        """Deterministic check: summary length is within expected compression range."""
        assertion_name = "reasonable_length"
        category = ASSERTION_REGISTRY[assertion_name]["category"]

        if not source_text:
            reasoning = "Source text is empty — nothing to evaluate"
            trace = EvalTrace(
                section_id=section_id,
                summary_id=summary_id,
                assertion_name=assertion_name,
                assertion_category=category,
                passed=True,
                prompt_sent=None,
                prompt_version="deterministic",
                llm_response="",
                reasoning=reasoning,
                model_used="deterministic",
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                eval_run_id=eval_run_id,
            )
            self.db.add(trace)
            return {
                "assertion_name": assertion_name,
                "category": category,
                "passed": True,
                "reasoning": reasoning,
            }

        if not summary_text:
            reasoning = "Summary is empty"
            trace = EvalTrace(
                section_id=section_id,
                summary_id=summary_id,
                assertion_name=assertion_name,
                assertion_category=category,
                passed=False,
                prompt_sent=None,
                prompt_version="deterministic",
                llm_response="",
                reasoning=reasoning,
                model_used="deterministic",
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                eval_run_id=eval_run_id,
                likely_cause="content_quality",
                suggestion="Summary is empty — regenerate the summary",
            )
            self.db.add(trace)
            return {
                "assertion_name": assertion_name,
                "category": category,
                "passed": False,
                "reasoning": reasoning,
            }

        min_pct, max_pct = self._get_compression_range(facets_used or {})
        min_chars = max(50, int(len(source_text) * min_pct / 100 * 0.5))
        max_chars = int(len(source_text) * max_pct / 100 * 1.5)
        summary_len = len(summary_text)
        passed = min_chars <= summary_len <= max_chars

        if passed:
            reasoning = (
                f"Summary is {summary_len} chars, within expected range "
                f"{min_chars}-{max_chars} chars"
            )
        else:
            reasoning = (
                f"Summary is {summary_len} chars, expected {min_chars}-{max_chars} chars "
                f"based on compression settings"
            )

        trace = EvalTrace(
            section_id=section_id,
            summary_id=summary_id,
            assertion_name=assertion_name,
            assertion_category=category,
            passed=passed,
            prompt_sent=None,
            prompt_version="deterministic",
            llm_response="",
            reasoning=reasoning,
            model_used="deterministic",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            eval_run_id=eval_run_id,
            likely_cause="content_quality" if not passed else None,
            suggestion=(
                f"Summary is {summary_len} chars, expected {min_chars}-{max_chars} chars "
                f"based on compression settings"
            )
            if not passed
            else None,
        )
        self.db.add(trace)

        return {
            "assertion_name": assertion_name,
            "category": category,
            "passed": passed,
            "reasoning": reasoning,
        }

    async def _check_has_key_concepts(
        self,
        summary_text: str,
        section_id: int | None,
        summary_id: int | None,
        eval_run_id: str | None,
    ) -> dict:
        """Deterministic check: summary contains structured key concepts."""
        assertion_name = "has_key_concepts"
        category = ASSERTION_REGISTRY[assertion_name]["category"]

        # Check for heading patterns (case-insensitive)
        heading_pattern = re.compile(
            r"(^|\n)\s*#{2,3}\s*(key\s+concepts?|core\s+ideas?|concepts?)\s*$"
            r"|(\*\*Key\s+Concepts?\*\*|\*\*Core\s+Ideas?\*\*)",
            re.IGNORECASE | re.MULTILINE,
        )
        has_heading = bool(heading_pattern.search(summary_text))

        # Check for definition-list patterns: **Term**: Description
        definition_pattern = re.compile(r"\*\*[^*]+\*\*\s*:\s*\S")
        definition_count = len(definition_pattern.findall(summary_text))
        has_definitions = definition_count >= 3

        # Check for bullet points with bold lead terms: - **Term**: text
        bullet_bold_pattern = re.compile(r"^\s*[-*]\s+\*\*[^*]+\*\*\s*:", re.MULTILINE)
        bullet_bold_count = len(bullet_bold_pattern.findall(summary_text))
        has_bullet_bolds = bullet_bold_count >= 3

        passed = has_heading or has_definitions or has_bullet_bolds

        if passed:
            reasons = []
            if has_heading:
                reasons.append("has key concepts heading")
            if has_definitions:
                reasons.append(f"has {definition_count} definition-list entries")
            if has_bullet_bolds:
                reasons.append(f"has {bullet_bold_count} bullet points with bold leads")
            reasoning = "Key concepts structure found: " + ", ".join(reasons)
        else:
            reasoning = "No key concepts structure found in summary"

        trace = EvalTrace(
            section_id=section_id,
            summary_id=summary_id,
            assertion_name=assertion_name,
            assertion_category=category,
            passed=passed,
            prompt_sent=None,
            prompt_version="deterministic",
            llm_response="",
            reasoning=reasoning,
            model_used="deterministic",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            eval_run_id=eval_run_id,
            likely_cause="format_mismatch" if not passed else None,
            suggestion=(
                "Add a 'Key Concepts' section heading or use **Term**: description "
                "format for at least 3 key terms"
            )
            if not passed
            else None,
        )
        self.db.add(trace)

        return {
            "assertion_name": assertion_name,
            "category": category,
            "passed": passed,
            "reasoning": reasoning,
        }

    async def _check_image_refs_preserved(
        self,
        source_text: str,
        summary_text: str,
        image_count: int,
        section_id: int | None,
        summary_id: int | None,
        eval_run_id: str | None,
    ) -> dict:
        """Deterministic check: summary mentions visual elements when source has images."""
        assertion_name = "image_refs_preserved"
        category = ASSERTION_REGISTRY[assertion_name]["category"]

        # Count images in source via regex
        image_patterns = [
            r"!\[",  # Markdown images
            r"<img",  # HTML images
            r"\.png",
            r"\.jpg",
            r"\.jpeg",
            r"\.gif",
            r"\.svg",
            r"\.webp",
        ]
        regex_count = 0
        for pattern in image_patterns:
            regex_count += len(re.findall(pattern, source_text, re.IGNORECASE))

        actual_image_count = max(regex_count, image_count)

        if actual_image_count == 0:
            reasoning = "No images in source — nothing to preserve"
            trace = EvalTrace(
                section_id=section_id,
                summary_id=summary_id,
                assertion_name=assertion_name,
                assertion_category=category,
                passed=True,
                prompt_sent=None,
                prompt_version="deterministic",
                llm_response="",
                reasoning=reasoning,
                model_used="deterministic",
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                eval_run_id=eval_run_id,
            )
            self.db.add(trace)
            return {
                "assertion_name": assertion_name,
                "category": category,
                "passed": True,
                "reasoning": reasoning,
            }

        # Check summary for visual reference keywords (word-boundary matching)
        visual_keywords = [
            "figure",
            "diagram",
            "chart",
            "image",
            "illustration",
            "table",
            "graph",
            "photo",
            "visual",
        ]
        summary_lower = summary_text.lower()
        found_keywords = [
            kw for kw in visual_keywords if re.search(r"\b" + kw + r"s?\b", summary_lower)
        ]
        passed = len(found_keywords) > 0

        if passed:
            reasoning = (
                f"Source has {actual_image_count} image reference(s); "
                f"summary mentions: {', '.join(found_keywords)}"
            )
        else:
            reasoning = (
                f"Source has {actual_image_count} image reference(s) but summary "
                f"does not mention any visual elements"
            )

        trace = EvalTrace(
            section_id=section_id,
            summary_id=summary_id,
            assertion_name=assertion_name,
            assertion_category=category,
            passed=passed,
            prompt_sent=None,
            prompt_version="deterministic",
            llm_response="",
            reasoning=reasoning,
            model_used="deterministic",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            eval_run_id=eval_run_id,
            likely_cause="content_quality" if not passed else None,
            suggestion=(
                "Source has images — mention visual elements "
                "(figures, diagrams, etc.) in the summary"
            )
            if not passed
            else None,
        )
        self.db.add(trace)

        return {
            "assertion_name": assertion_name,
            "category": category,
            "passed": passed,
            "reasoning": reasoning,
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

    @staticmethod
    def _should_retry(eval_results: dict) -> bool:
        """Return True if any critical/important assertion failed (for auto-retry)."""
        assertions = eval_results.get("assertions", {})
        for name, result in assertions.items():
            if result.get("skipped") or result.get("error"):
                continue
            category = result.get("category", ASSERTION_REGISTRY.get(name, {}).get("category", ""))
            if category in RETRY_ELIGIBLE_CATEGORIES and not result.get("passed"):
                return True
        return False

    @staticmethod
    def _build_fix_prompt(eval_results: dict) -> str:
        """Build targeted fix instructions from failing eval results."""
        lines = ["The previous summary had the following issues. Please fix them:\n"]
        assertions = eval_results.get("assertions", {})
        for name, result in assertions.items():
            if result.get("skipped") or result.get("error"):
                continue
            category = result.get("category", ASSERTION_REGISTRY.get(name, {}).get("category", ""))
            if category in RETRY_ELIGIBLE_CATEGORIES and not result.get("passed"):
                suggestion = result.get("suggestion") or f"Fix the failing '{name}' assertion"
                lines.append(f"- [{category}] {name}: {suggestion}")
        return "\n".join(lines)

    @staticmethod
    def compute_eval_json(eval_results: dict) -> dict:
        """Build eval_json dict from evaluate_summary result for storage on Summary."""
        return eval_results
