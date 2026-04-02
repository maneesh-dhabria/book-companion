"""Summarizer service — section + book summarization orchestration."""

import json
from pathlib import Path

import jinja2
import structlog

from app.db.models import BookSection, SummaryStatus
from app.services.summarizer.llm_provider import LLMProvider
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.db.models import Image

logger = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Compression ratio targets by detail level (percentage of original)
COMPRESSION_TARGETS = {
    "brief": 10,
    "standard": 20,
    "detailed": 30,
}

# Max tokens before sub-chunking is triggered
MAX_SECTION_TOKENS = 150_000

# Auto-escalation: if eval fails, increase detail level
RATIO_ESCALATION = {"brief": "standard", "standard": "detailed", "detailed": "detailed"}


class SummarizerService:
    def __init__(self, db: AsyncSession, llm: LLMProvider, config, captioner=None):
        self.db = db
        self.llm = llm
        self.config = config
        self.captioner = captioner
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(PROMPTS_DIR))
        )

    async def summarize_book(
        self,
        book_id: int,
        force: bool = False,
        detail_level: str | None = None,
        skip_eval: bool = False,
        model: str | None = None,
    ) -> None:
        """Orchestrate full book summarization using map-reduce."""
        detail_level = detail_level or self.config.summarization.default_detail_level

        from sqlalchemy import select
        from app.db.models import Book

        result = await self.db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        if not book:
            raise ValueError(f"Book not found: {book_id}")

        result = await self.db.execute(
            select(BookSection)
            .where(BookSection.book_id == book_id)
            .options(selectinload(BookSection.images).undefer(Image.data))
            .order_by(BookSection.order_index)
        )
        sections = list(result.scalars().all())

        # Map step: summarize each section with cumulative context
        completed = []
        for section in sections:
            if section.user_edited:
                completed.append(section)
                continue
            if not force and section.summary_status == SummaryStatus.COMPLETED:
                completed.append(section)
                continue

            section.summary_status = SummaryStatus.RUNNING
            await self.db.flush()

            try:
                summary = await self._summarize_with_retry(
                    section=section,
                    prior_sections=completed,
                    detail_level=detail_level,
                    skip_eval=skip_eval,
                )
                section.summary_md = summary
                section.summary_status = SummaryStatus.COMPLETED
                section.summary_version = self.config.summarization.prompt_version
            except Exception as e:
                section.summary_status = SummaryStatus.FAILED
                logger.error("section_summarization_failed", section_id=section.id, error=str(e))

            await self.db.flush()
            completed.append(section)

        # Reduce step: generate overall book summary
        book_summary = await self._generate_book_summary(book, completed)
        book.overall_summary = book_summary
        await self.db.commit()

        logger.info("book_summarization_complete", book_id=book_id, sections=len(sections))

    async def summarize_section(
        self,
        book_id: int,
        section_id: int,
        detail_level: str | None = None,
        model: str | None = None,
        force: bool = False,
    ) -> str:
        """Summarize a single section."""
        from sqlalchemy import select

        detail_level = detail_level or self.config.summarization.default_detail_level

        result = await self.db.execute(
            select(BookSection)
            .options(selectinload(BookSection.images).undefer(Image.data))
            .where(BookSection.id == section_id)
        )
        section = result.scalar_one_or_none()
        if not section:
            raise ValueError(f"Section not found: {section_id}")

        # Get prior sections for context
        result = await self.db.execute(
            select(BookSection)
            .where(
                BookSection.book_id == book_id,
                BookSection.order_index < section.order_index,
            )
            .options(selectinload(BookSection.images).undefer(Image.data))
            .order_by(BookSection.order_index)
        )
        prior = list(result.scalars().all())

        summary = await self._summarize_single_section(
            section=section, prior_sections=prior, detail_level=detail_level
        )
        section.summary_md = summary
        section.summary_status = SummaryStatus.COMPLETED
        await self.db.commit()
        return summary

    async def quick_summary(self, book_id: int) -> str:
        """Quick single-pass summary of the entire book."""
        from sqlalchemy import select
        from app.db.models import Book

        result = await self.db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        if not book:
            raise ValueError(f"Book not found: {book_id}")

        result = await self.db.execute(
            select(BookSection)
            .where(BookSection.book_id == book_id)
            .order_by(BookSection.order_index)
        )
        sections = list(result.scalars().all())

        # Concatenate all content (truncated if too long)
        all_content = "\n\n".join(
            f"## {s.title}\n{s.content_md or ''}" for s in sections
        )
        # Truncate to ~100K chars (~25K tokens)
        if len(all_content) > 100_000:
            all_content = all_content[:100_000] + "\n\n[truncated]"

        response = await self.llm.generate(
            prompt=f"Provide a comprehensive summary of this book:\n\n{all_content}",
            model=self.config.llm.quick_summary_model,
        )
        book.quick_summary = response.content
        await self.db.commit()
        return response.content

    async def _summarize_with_retry(
        self,
        section: BookSection,
        prior_sections: list[BookSection],
        detail_level: str,
        skip_eval: bool = False,
        max_retries: int = 2,
    ) -> str:
        """Summarize with auto-retry and compression ratio escalation on eval failure."""
        current_detail = detail_level
        summary = ""
        for attempt in range(max_retries + 1):
            summary = await self._summarize_single_section(
                section=section,
                prior_sections=prior_sections,
                detail_level=current_detail,
            )
            if skip_eval:
                return summary

            # Run eval if evaluator is available
            try:
                from app.services.summarizer.evaluator import EvalService

                eval_service = EvalService(self.db, self.llm, self.config)
                results = await eval_service.evaluate_summary(
                    section.id, section.content_md or "", summary
                )
                if eval_service._should_auto_retry(results, attempt, max_retries):
                    current_detail = RATIO_ESCALATION.get(current_detail, current_detail)
                    logger.info(
                        "eval_retry_escalation",
                        section_id=section.id,
                        attempt=attempt + 1,
                        new_detail=current_detail,
                    )
                    continue
            except Exception as e:
                logger.warning("eval_during_summarization_failed", error=str(e))

            return summary
        return summary

    async def _summarize_single_section(
        self,
        section: BookSection,
        prior_sections: list[BookSection],
        detail_level: str,
    ) -> str:
        """Core LLM call to summarize a single section."""
        cumulative_context = self._build_cumulative_context(prior_sections)
        compression_target = self._get_compression_target(detail_level)

        content = section.content_md or ""

        # Get image captions for this section
        image_captions = await self._get_image_captions(section)

        # Handle long sections via sub-chunking
        token_estimate = len(content) // 4
        if token_estimate > MAX_SECTION_TOKENS:
            return await self._summarize_long_section(
                section, content, cumulative_context, compression_target, detail_level
            )

        try:
            template = self._jinja_env.get_template("summarize_section_v1.txt")
            prompt = template.render(
                section_title=section.title,
                section_content=content,
                cumulative_context=cumulative_context,
                compression_target=compression_target,
                detail_level=detail_level,
                image_captions=image_captions,
            )
        except jinja2.TemplateNotFound:
            # Fallback prompt if template not found
            prompt = (
                f"Summarize the following section at {compression_target}% compression.\n\n"
                f"Section: {section.title}\n\n"
                f"Prior context:\n{cumulative_context}\n\n"
                f"Content:\n{content}\n\n"
                f"Respond with JSON containing: key_concepts (list), detailed_summary (string), "
                f"frameworks (list), key_quotes (list), concepts (list)."
            )

        response = await self.llm.generate(
            prompt=prompt,
            json_schema={
                "type": "object",
                "properties": {
                    "key_concepts": {"type": "array", "items": {"type": "string"}},
                    "detailed_summary": {"type": "string"},
                    "frameworks": {"type": "array", "items": {"type": "string"}},
                    "key_quotes": {"type": "array", "items": {"type": "string"}},
                    "concepts": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["key_concepts", "detailed_summary"],
            },
        )

        try:
            parsed = json.loads(response.content)
            return parsed.get("detailed_summary", response.content)
        except json.JSONDecodeError:
            return response.content

    async def _summarize_long_section(
        self,
        section: BookSection,
        content: str,
        cumulative_context: str,
        compression_target: int,
        detail_level: str,
    ) -> str:
        """Handle sections > 150K tokens by sub-chunking."""
        # Split into chunks of ~100K chars (~25K tokens)
        chunk_size = 100_000
        chunks = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]

        sub_summaries = []
        for i, chunk in enumerate(chunks):
            prompt = (
                f"Summarize part {i + 1}/{len(chunks)} of section '{section.title}' "
                f"at {compression_target}% compression.\n\n"
                f"Content:\n{chunk}"
            )
            response = await self.llm.generate(prompt=prompt)
            sub_summaries.append(response.content)

        # Merge sub-summaries
        merge_prompt = (
            f"Merge these {len(sub_summaries)} partial summaries of section "
            f"'{section.title}' into one coherent summary:\n\n"
            + "\n\n---\n\n".join(sub_summaries)
        )
        response = await self.llm.generate(prompt=merge_prompt)
        return response.content

    def _build_cumulative_context(self, prior_sections: list) -> str:
        """Build compact context from prior section summaries, including key image refs."""
        if not prior_sections:
            return ""

        lines = []
        for s in prior_sections:
            title = getattr(s, "title", "Untitled")
            summary = getattr(s, "summary_md", None) or ""
            if len(summary) > 500:
                summary = summary[:500] + "..."
            lines.append(f"- {title}: {summary}")

            # Include key image refs from prior sections
            images = getattr(s, "images", None) or []
            for img in images:
                if getattr(img, "relevance", None) == "key" and getattr(img, "caption", None):
                    lines.append(f"  [Image: {img.caption}]")

        return "\n".join(lines)

    def _get_compression_target(self, detail_level: str) -> int:
        """Map detail level to compression ratio percentage."""
        return COMPRESSION_TARGETS.get(detail_level, 20)

    async def _get_image_captions(self, section) -> list[dict]:
        """Get image captions for a section. Captions uncaptioned images if captioner available.

        Returns list of {"caption": str, "relevance": str, "image_id": int}
        for non-decorative images.
        """
        from app.services.summarizer.image_captioner import should_skip_image, compute_content_hash

        images = section.images or []
        if not images:
            return []

        # Check config toggle
        if hasattr(self.config, 'images') and not self.config.images.captioning_enabled:
            return []

        captions = []
        for img in images:
            # Skip pre-filtered decorative images
            if should_skip_image(
                data=img.data, width=img.width, height=img.height, filename=img.filename
            ):
                continue

            # Use existing caption if available
            if img.caption and img.relevance:
                if img.relevance in ("key", "supplementary"):
                    captions.append({
                        "caption": img.caption,
                        "relevance": img.relevance,
                        "image_id": img.id,
                    })
                continue

            # Caption via LLM if captioner available
            if self.captioner:
                # Compute content hash if not set
                if not img.content_hash:
                    img.content_hash = compute_content_hash(img.data)

                result = await self.captioner.caption_image(
                    image_data=img.data,
                    mime_type=img.mime_type,
                    context=f"Section: {section.title}",
                    alt_text=img.alt_text,
                )
                img.caption = result["caption"]
                img.caption_model = "claude-vision"
                img.relevance = result["relevance"]
                await self.db.flush()  # Persist immediately for crash safety

                if img.relevance in ("key", "supplementary"):
                    captions.append({
                        "caption": result["caption"],
                        "relevance": result["relevance"],
                        "image_id": img.id,
                    })

        return captions

    async def _generate_book_summary(self, book, sections: list[BookSection]) -> str:
        """Reduce step: combine section summaries into overall book summary."""
        section_summaries = []
        for s in sections:
            if s.summary_md:
                section_summaries.append(f"## {s.title}\n{s.summary_md}")

        combined = "\n\n".join(section_summaries)

        try:
            template = self._jinja_env.get_template("summarize_book_v1.txt")
            prompt = template.render(
                book_title=book.title,
                section_summaries=combined,
            )
        except jinja2.TemplateNotFound:
            prompt = (
                f"Create an overall summary of the book '{book.title}' "
                f"from these section summaries:\n\n{combined}"
            )

        response = await self.llm.generate(prompt=prompt)
        return response.content

    async def generate_book_summary(self, book_id: int) -> str:
        """Generate book-level summary from section summaries."""
        from sqlalchemy import select
        from app.db.models import Book

        result = await self.db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        if not book:
            raise ValueError(f"Book not found: {book_id}")

        result = await self.db.execute(
            select(BookSection)
            .where(BookSection.book_id == book_id)
            .options(selectinload(BookSection.images).undefer(Image.data))
            .order_by(BookSection.order_index)
        )
        sections = list(result.scalars().all())
        summary = await self._generate_book_summary(book, sections)
        book.overall_summary = summary
        await self.db.commit()
        return summary
