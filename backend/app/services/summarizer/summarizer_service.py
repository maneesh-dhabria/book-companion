"""Summarizer service — section + book summarization orchestration."""

import json
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
        on_section_complete: Callable | None = None,
        on_section_skip: Callable | None = None,
        on_section_fail: Callable | None = None,
    ) -> dict:
        """Orchestrate full book summarization using map-reduce with faceted prompts."""
        facets = facets or {}

        sections = await self._section_repo.get_by_book_id(book_id)
        total = len(sections)

        completed = 0
        skipped = 0
        failed: list[int] = []
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
                        on_section_skip(i + 1, total, section.title, "already summarized")
                    continue

            # Minimum content threshold
            from app.services.parser.text_utils import text_char_count

            char_count = text_char_count(section.content_md or "")
            min_chars = self.config.summarization.min_section_chars
            if not force and char_count < min_chars:
                skipped += 1
                if on_section_skip:
                    on_section_skip(
                        i + 1, total, section.title, f"{char_count} chars < {min_chars} min"
                    )
                logger.info(
                    "section_skipped_insufficient_content",
                    section_id=section.id,
                    char_count=char_count,
                )
                continue

            cumulative_context = "\n".join(cumulative_parts)

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
                    on_section_complete(i + 1, total, section.title, elapsed, comp)

                logger.info(
                    "section_summarized",
                    section_id=section.id,
                    book_id=book_id,
                )
            except Exception as e:
                failed.append(section.id)
                error_msg = str(e)
                logger.error(
                    "section_summarization_failed",
                    section_id=section.id,
                    error=error_msg,
                )
                if on_section_fail:
                    on_section_fail(i + 1, total, section.title, error_msg)

        await self.db.commit()

        return {
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
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
        )
        return await self._summary_repo.create(summary)

    async def _generate_book_summary(
        self,
        book_id: int,
        facets: dict[str, str],
        preset_name: str | None,
        model: str | None,
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
