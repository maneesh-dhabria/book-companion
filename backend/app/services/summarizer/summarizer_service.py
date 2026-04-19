"""Summarizer service — section + book summarization orchestration."""

import difflib
import json
import re
import time
from collections.abc import Callable
from pathlib import Path

import jinja2
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookSection, Summary, SummaryContentType
from app.db.repositories.book_repo import BookRepository
from app.db.repositories.section_repo import SectionRepository
from app.db.repositories.summary_repo import SummaryRepository
from app.services.parser.section_classifier import SUMMARIZABLE_TYPES
from app.services.summarizer.llm_provider import LLMProvider
from app.services.summary_service import SummaryService

logger = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Max tokens before sub-chunking is triggered
MAX_SECTION_TOKENS = 150_000


class SummarizerService:
    def __init__(self, db: AsyncSession, llm: LLMProvider, config, captioner=None):
        self.db = db
        self.llm = llm
        self.config = config
        self.captioner = captioner
        self._jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(PROMPTS_DIR)))
        self._summary_repo = SummaryRepository(db)
        self._section_repo = SectionRepository(db)
        self._book_repo = BookRepository(db)

    async def summarize_book(
        self,
        book_id: int,
        preset_name: str | None = None,
        facets: dict[str, str] | None = None,
        force: bool = False,
        model: str | None = None,
        skip_eval: bool = False,
        no_retry: bool = False,
        eval_service=None,
        on_section_start: Callable | None = None,
        on_section_complete: Callable | None = None,
        on_section_skip: Callable | None = None,
        on_section_fail: Callable | None = None,
        on_section_retry: Callable | None = None,
        scope: str = "all",
        section_id: int | None = None,
    ) -> dict:
        """Orchestrate full book summarization using map-reduce with faceted prompts."""
        # Resolve facets from preset_name if caller didn't provide a complete set.
        # Validates all required facet dimensions (style, audience, compression,
        # content_focus) and raises PresetError if any are missing or invalid.
        from app.services.preset_service import FACET_DIMENSIONS, PresetService

        facets = facets or {}
        missing_dims = [d for d in FACET_DIMENSIONS if d not in facets]
        if missing_dims:
            preset_to_use = preset_name or self.config.summarization.default_preset
            preset_svc = PresetService()
            _, facets = preset_svc.resolve_facets(
                preset_to_use, {d: None for d in FACET_DIMENSIONS}, preset_to_use
            )

        sections = await self._section_repo.get_by_book_id(book_id)

        if scope == "section":
            if section_id is None:
                raise ValueError("scope='section' requires section_id")
            sections = [s for s in sections if s.id == section_id]
            if not sections:
                raise ValueError(
                    f"section_id={section_id} does not belong to book {book_id}"
                )
        elif scope == "pending":
            sections = [
                s
                for s in sections
                if s.default_summary_id is None
                and s.section_type in SUMMARIZABLE_TYPES
            ]
        else:
            sections = [s for s in sections if s.section_type in SUMMARIZABLE_TYPES]

        total = len(sections)

        completed = 0
        skipped = 0
        failed: list[int] = []
        retried_sections: list[int] = []
        cumulative_parts: list[str] = []

        for i, section in enumerate(sections):
            # Idempotency: skip if a summary already exists for these facets
            if not force:
                existing = await self._summary_repo.get_latest_by_content_and_facets(
                    SummaryContentType.SECTION, section.id, facets
                )
                if existing:
                    skipped += 1
                    # Still add to cumulative context
                    cumulative_parts.append(
                        f"- {section.title}: {existing.summary_md[:500]}..."
                        if len(existing.summary_md) > 500
                        else f"- {section.title}: {existing.summary_md}"
                    )
                    if on_section_skip:
                        on_section_skip(
                            section.id, i + 1, total, section.title, "already summarized"
                        )
                    continue

            # Minimum content threshold
            from app.services.parser.text_utils import text_char_count

            char_count = text_char_count(section.content_md or "")
            min_chars = self.config.summarization.min_section_chars
            if not force and char_count < min_chars:
                skipped += 1
                if on_section_skip:
                    on_section_skip(
                        section.id,
                        i + 1,
                        total,
                        section.title,
                        f"{char_count} chars < {min_chars} min",
                    )
                logger.info(
                    "section_skipped_insufficient_content",
                    section_id=section.id,
                    char_count=char_count,
                )
                continue

            cumulative_context = "\n".join(cumulative_parts)

            # Capture primitives up-front — a rollback on mid-loop failure
            # expires ORM attributes and would MissingGreenlet on access.
            section_id = section.id
            section_title = section.title

            if on_section_start:
                on_section_start(section_id, i + 1, total, section_title)

            try:
                start = time.monotonic()
                summary = await self._summarize_single_section(
                    book_id=book_id,
                    section=section,
                    facets=facets,
                    preset_name=preset_name,
                    model=model,
                    cumulative_context=cumulative_context,
                )
                elapsed = time.monotonic() - start

                # Set as default summary for this section
                await self._section_repo.update_default_summary(section.id, summary.id)

                # Inline eval + retry
                if not skip_eval and eval_service:
                    try:
                        from app.services.summarizer.evaluator import EvalService

                        section_type = getattr(section, "section_type", "chapter")
                        eval_results = await eval_service.evaluate_summary(
                            section_id=section.id,
                            source_text=section.content_md or "",
                            summary_text=summary.summary_md,
                            image_count=len(section.images) if section.images else 0,
                            facets_used=facets,
                            summary_id=summary.id,
                            preset_name=preset_name,
                            cumulative_context=cumulative_context,
                            section_type=section_type,
                        )
                        summary.eval_json = EvalService.compute_eval_json(eval_results)

                        # Auto-retry if critical/important assertion failed
                        if not no_retry and EvalService._should_retry(eval_results):
                            fix_prompt = EvalService._build_fix_prompt(eval_results)
                            retry_summary = await self._summarize_single_section(
                                book_id=book_id,
                                section=section,
                                facets=facets,
                                preset_name=preset_name,
                                model=model,
                                cumulative_context=cumulative_context,
                                fix_instructions=fix_prompt,
                            )
                            retry_summary.retry_of_id = summary.id
                            await self._section_repo.update_default_summary(
                                section.id, retry_summary.id
                            )
                            # Re-eval the retry
                            retry_eval = await eval_service.evaluate_summary(
                                section_id=section.id,
                                source_text=section.content_md or "",
                                summary_text=retry_summary.summary_md,
                                image_count=len(section.images) if section.images else 0,
                                facets_used=facets,
                                summary_id=retry_summary.id,
                                preset_name=preset_name,
                                cumulative_context=cumulative_context,
                                section_type=section_type,
                            )
                            retry_summary.eval_json = EvalService.compute_eval_json(retry_eval)
                            summary = retry_summary  # Use retry for cumulative context
                            retried_sections.append(section.id)
                            if on_section_retry:
                                on_section_retry(
                                    section.id, i + 1, total, section.title
                                )
                    except Exception as eval_err:
                        logger.warning(
                            "inline_eval_failed",
                            section_id=section.id,
                            error=str(eval_err),
                        )

                completed += 1
                # Add to cumulative context
                summary_text = summary.summary_md
                cumulative_parts.append(
                    f"- {section.title}: {summary_text[:500]}..."
                    if len(summary_text) > 500
                    else f"- {section.title}: {summary_text}"
                )

                if on_section_complete:
                    comp = (
                        summary.summary_char_count / summary.input_char_count
                        if summary.input_char_count
                        else 0
                    )
                    on_section_complete(
                        section.id, i + 1, total, section.title, elapsed, comp
                    )

                # Commit per-section so partial progress is durable and
                # existing skip-completed logic works across runs (G2, G3).
                await self.db.commit()

                logger.info(
                    "section_summarized",
                    section_id=section.id,
                    book_id=book_id,
                )
            except Exception as e:
                await self.db.rollback()
                failed.append(section_id)
                error_msg = str(e)
                logger.error(
                    "section_summarization_failed",
                    section_id=section_id,
                    error=error_msg,
                )
                if on_section_fail:
                    on_section_fail(
                        section_id, i + 1, total, section_title, error_msg
                    )
                # Rollback expires every identity-mapped ORM object in this
                # session. Issuing a fresh SELECT refreshes them in place via
                # the identity map so the next iteration's `section.*` access
                # doesn't MissingGreenlet. Returned list is discarded on
                # purpose — the existing `sections` iterator keeps going.
                await self._section_repo.get_by_book_id(book_id)

        # High retry rate warning
        if retried_sections and len(retried_sections) > total / 2:
            logger.warning(
                "high_retry_rate",
                retried=len(retried_sections),
                total=total,
                message="Consider adjusting your preset or prompt.",
            )

        await self.db.commit()

        return {
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "retried": retried_sections,
        }

    # Compression targets by facet name (fraction of source length)
    COMPRESSION_TARGETS = {"brief": 0.10, "standard": 0.20, "detailed": 0.30}

    async def _summarize_single_section(
        self,
        book_id: int,
        section: BookSection,
        facets: dict[str, str],
        preset_name: str | None,
        model: str | None,
        cumulative_context: str,
        fix_instructions: str | None = None,
    ) -> Summary:
        """Core LLM call to summarize a single section. Returns persisted Summary."""
        book = await self._book_repo.get_by_id(book_id)
        author = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"

        image_captions = await self._get_image_captions(section) if self.captioner else []
        source_chars = len(section.content_md or "")
        compression_frac = self.COMPRESSION_TARGETS.get(facets.get("compression", "standard"), 0.20)
        target_chars = int(source_chars * compression_frac) if source_chars > 0 else None

        template = self._jinja_env.get_template("base/summarize_section.txt")
        prompt = template.render(
            book_title=book.title,
            author=author,
            section_title=section.title,
            section_content=section.content_md or "",
            cumulative_context=cumulative_context,
            image_captions=image_captions,
            target_chars=target_chars,
            **facets,
        )

        if fix_instructions:
            prompt = f"{prompt}\n\n{fix_instructions}"

        effective_model = model or self.config.llm.model
        start = time.monotonic()
        response = await self.llm.generate(prompt, model=effective_model)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        summary_text = self._extract_summary_text(response)

        # Retry once if summary is longer than source content
        if source_chars > 0 and len(summary_text) >= source_chars:
            max_chars = int(source_chars * min(compression_frac * 2, 0.50))
            retry_prompt = (
                f"{prompt}\n\n"
                f"IMPORTANT: Your previous summary was {len(summary_text):,} characters "
                f"but the source is only {source_chars:,} characters. "
                f"You MUST keep your summary under {max_chars:,} characters."
            )
            logger.warning(
                "summary_too_long_retrying",
                section_id=section.id,
                source_chars=source_chars,
                summary_chars=len(summary_text),
                max_chars=max_chars,
            )
            retry_start = time.monotonic()
            response = await self.llm.generate(retry_prompt, model=effective_model)
            elapsed_ms += int((time.monotonic() - retry_start) * 1000)
            summary_text = self._extract_summary_text(response)

        concepts = SummaryService.extract_concepts(summary_text)
        eval_json_data = {"concepts": sorted(concepts)} if concepts else None

        # Check for paraphrased quotes
        quality_warnings = None
        quote_warnings = self._check_paraphrased_quotes(section.content_md or "", summary_text)
        if quote_warnings:
            quality_warnings = {"paraphrased_quotes": quote_warnings}

        summary = Summary(
            content_type=SummaryContentType.SECTION,
            content_id=section.id,
            book_id=book_id,
            preset_name=preset_name,
            facets_used=facets,
            prompt_text_sent=prompt,
            model_used=effective_model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            input_char_count=len(section.content_md or ""),
            summary_char_count=len(summary_text),
            summary_md=summary_text,
            latency_ms=elapsed_ms,
            eval_json=eval_json_data,
            quality_warnings=quality_warnings,
        )
        return await self._summary_repo.create(summary)

    async def _generate_book_summary(
        self,
        book_id: int,
        facets: dict[str, str],
        preset_name: str | None,
        model: str | None,
        eval_service=None,
        skip_eval: bool = False,
        no_retry: bool = False,
    ) -> Summary:
        """Reduce step: combine section summaries into overall book summary."""
        book = await self._book_repo.get_by_id(book_id)
        sections = await self._section_repo.get_by_book_id(book_id)
        author = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"

        section_data = []
        for s in sections:
            if s.default_summary_id:
                summary = await self._summary_repo.get_by_id(s.default_summary_id)
                if summary:
                    section_data.append({"title": s.title, "summary": summary.summary_md})

        template = self._jinja_env.get_template("base/summarize_book.txt")
        prompt = template.render(
            book_title=book.title,
            author=author,
            section_count=len(section_data),
            sections=section_data,
            **facets,
        )

        effective_model = model or self.config.llm.model
        start = time.monotonic()
        response = await self.llm.generate(prompt, model=effective_model)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        summary_text = self._extract_summary_text(response)
        combined_input = "\n".join(s["summary"] for s in section_data)

        concepts = SummaryService.extract_concepts(summary_text)
        eval_json_data = {"concepts": sorted(concepts)} if concepts else None

        summary = Summary(
            content_type=SummaryContentType.BOOK,
            content_id=book_id,
            book_id=book_id,
            preset_name=preset_name,
            facets_used=facets,
            prompt_text_sent=prompt,
            model_used=effective_model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            input_char_count=len(combined_input),
            summary_char_count=len(summary_text),
            summary_md=summary_text,
            latency_ms=elapsed_ms,
            eval_json=eval_json_data,
        )
        saved = await self._summary_repo.create(summary)
        await self._book_repo.update_default_summary(book_id, saved.id)

        # Book-level eval
        if not skip_eval and eval_service:
            try:
                from app.services.summarizer.evaluator import EvalService

                source_for_eval = "\n\n".join(
                    f"## {s['title']}\n{s['summary']}" for s in section_data
                )
                eval_results = await eval_service.evaluate_summary(
                    section_id=None,  # book-level, no specific section
                    source_text=source_for_eval,
                    summary_text=summary_text,
                    facets_used=facets,
                    summary_id=saved.id,
                    preset_name=preset_name,
                    eval_scope="book",
                    section_count=len(section_data),
                )
                saved.eval_json = EvalService.compute_eval_json(eval_results)

                # Retry if needed
                if not no_retry and EvalService._should_retry(eval_results):
                    fix_prompt = EvalService._build_fix_prompt(eval_results)
                    retry_prompt = f"{prompt}\n\n{fix_prompt}"
                    retry_start = time.monotonic()
                    retry_response = await self.llm.generate(retry_prompt, model=effective_model)
                    retry_elapsed = int((time.monotonic() - retry_start) * 1000)
                    retry_text = self._extract_summary_text(retry_response)

                    retry_summary = Summary(
                        content_type=SummaryContentType.BOOK,
                        content_id=book_id,
                        book_id=book_id,
                        preset_name=preset_name,
                        facets_used=facets,
                        prompt_text_sent=retry_prompt,
                        model_used=effective_model,
                        input_tokens=retry_response.input_tokens,
                        output_tokens=retry_response.output_tokens,
                        input_char_count=len(combined_input),
                        summary_char_count=len(retry_text),
                        summary_md=retry_text,
                        latency_ms=retry_elapsed,
                        retry_of_id=saved.id,
                    )
                    retry_saved = await self._summary_repo.create(retry_summary)
                    await self._book_repo.update_default_summary(book_id, retry_saved.id)

                    # Re-eval retry
                    retry_eval = await eval_service.evaluate_summary(
                        section_id=None,
                        source_text=source_for_eval,
                        summary_text=retry_text,
                        facets_used=facets,
                        summary_id=retry_saved.id,
                        preset_name=preset_name,
                        eval_scope="book",
                        section_count=len(section_data),
                    )
                    retry_saved.eval_json = EvalService.compute_eval_json(retry_eval)
                    saved = retry_saved
            except Exception as eval_err:
                logger.warning("book_eval_failed", error=str(eval_err))

        return saved

    async def quick_summary(self, book_id: int) -> None:
        """Deprecated: runs summarize with executive_brief preset."""
        await self.summarize_book(
            book_id=book_id,
            preset_name="executive_brief",
            facets={
                "style": "bullet_points",
                "audience": "executive",
                "compression": "brief",
                "content_focus": "key_concepts",
            },
        )

    def _extract_summary_text(self, response) -> str:
        """Extract summary text from LLM response. Handles markdown, JSON, code-fenced."""
        content = response.content.strip()
        # Strip code fence wrapping
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[-1].strip() == "```":
                content = "\n".join(lines[1:-1]).strip()
        # Try JSON extraction (backward compat)
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                for key in ("summary", "detailed_summary", "content"):
                    if key in parsed:
                        return parsed[key]
                return content
        except (json.JSONDecodeError, AttributeError):
            pass
        return content

    @staticmethod
    def _check_paraphrased_quotes(source_text: str, summary_text: str) -> list[dict]:
        """Detect paraphrased quotes in summary by comparing with source text."""
        # Extract double-quoted strings from summary (10-200 chars)
        quote_pattern = re.compile(r'\u201c([^\u201d]{10,200})\u201d|"([^"]{10,200})"')
        matches = quote_pattern.findall(summary_text)
        quotes = [m[0] or m[1] for m in matches]

        if not quotes:
            return []

        # Strip markdown from source for comparison
        clean_source = re.sub(r"[#*_`\[\]()]", "", source_text)

        warnings = []
        for quote in quotes:
            # Check exact match first
            if quote in clean_source:
                continue

            # Sliding window fuzzy match
            quote_words = quote.split()
            window_size = len(quote_words) + 2
            source_words = clean_source.split()

            best_similarity = 0.0
            best_match = ""
            for i in range(max(0, len(source_words) - window_size + 1)):
                window = " ".join(source_words[i : i + window_size])
                similarity = difflib.SequenceMatcher(None, quote.lower(), window.lower()).ratio()
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = window

            if best_similarity >= 0.85:
                warnings.append(
                    {
                        "type": "paraphrased_quote",
                        "quote": quote,
                        "best_match": best_match,
                        "similarity": round(best_similarity, 2),
                        "message": (
                            f"Possible paraphrased quote ({int(best_similarity * 100)}% match): "
                            f'"{quote[:50]}..."'
                        ),
                    }
                )

        return warnings

    async def _get_image_captions(self, section) -> list[dict]:
        """Get image captions for a section. Captions uncaptioned images if captioner available.

        Uses caption_section_images for batch processing with dedup.
        Only loads image binary data for images that pass metadata pre-filter.

        Returns list of {"caption": str, "relevance": str, "image_id": int}
        for non-decorative images.
        """
        from app.services.summarizer.image_captioner import compute_content_hash

        images = section.images or []
        if not images:
            return []

        # Check config toggle
        if hasattr(self.config, "images") and not self.config.images.captioning_enabled:
            return []

        # Collect already-captioned non-decorative images
        captions = []
        needs_captioning = []

        for img in images:
            if img.caption and img.relevance:
                if img.relevance in ("key", "supplementary"):
                    captions.append(
                        {
                            "caption": img.caption,
                            "relevance": img.relevance,
                            "image_id": img.id,
                        }
                    )
                continue

            # Only attempt captioning if captioner available
            if self.captioner:
                # Compute content hash if not set (requires data)
                if not img.content_hash:
                    img.content_hash = compute_content_hash(img.data)

                needs_captioning.append(
                    {
                        "id": img.id,
                        "data": img.data,
                        "mime_type": img.mime_type,
                        "width": img.width,
                        "height": img.height,
                        "filename": img.filename,
                        "alt_text": img.alt_text,
                        "content_hash": img.content_hash,
                        "existing_caption": None,
                        "existing_relevance": None,
                    }
                )

        # Batch caption uncaptioned images (handles pre-filter + dedup)
        if needs_captioning and self.captioner:
            results = await self.captioner.caption_section_images(
                images=needs_captioning,
                section_context=f"Section: {section.title}",
            )
            # Persist results to DB
            img_map = {img.id: img for img in images}
            for img_id, result in results.items():
                if img_id in img_map:
                    orm_img = img_map[img_id]
                    orm_img.caption = result["caption"]
                    orm_img.caption_model = "claude-vision"
                    orm_img.relevance = result["relevance"]
                    await self.db.flush()

                    if result["relevance"] in ("key", "supplementary"):
                        captions.append(
                            {
                                "caption": result["caption"],
                                "relevance": result["relevance"],
                                "image_id": img_id,
                            }
                        )

        return captions
