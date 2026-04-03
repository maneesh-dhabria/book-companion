"""3-tier structure detection: embedded TOC -> heuristics -> LLM fallback."""

import json
import re

from app.services.parser.base import ParsedSection
from app.services.summarizer.llm_provider import LLMProvider


class StructureDetector:
    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm_provider = llm_provider

    def validate_structure(self, sections: list[ParsedSection]) -> list[ParsedSection]:
        """Validate and potentially re-detect structure.

        Tier 1: If multiple sections exist (from embedded TOC), keep them.
        Tier 2: If single flat section, try heuristic heading detection.
        Tier 3: LLM fallback (async, called separately).
        """
        if len(sections) > 1:
            return sections  # Tier 1: TOC extraction worked

        if len(sections) == 1:
            # Tier 2: Try heuristic detection on the flat content
            heuristic_sections = self.detect_from_heuristics(sections[0].content_md)
            if len(heuristic_sections) > 1:
                return heuristic_sections

        return sections  # Return as-is if nothing worked

    def detect_from_heuristics(self, content: str) -> list[ParsedSection]:
        """Tier 2: Detect chapters using Markdown heading patterns."""
        heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
        matches = list(heading_pattern.finditer(content))

        if len(matches) < 2:
            return []

        sections = []
        for i, match in enumerate(matches):
            depth = len(match.group(1)) - 1  # # = 0, ## = 1, ### = 2
            title = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start:end].strip()

            if section_content:
                sections.append(
                    ParsedSection(
                        title=title,
                        content_md=section_content,
                        depth=depth,
                        order_index=len(sections),
                    )
                )
        return sections

    async def detect_via_llm(self, content: str, max_tokens: int = 5000) -> list[dict]:
        """Tier 3: LLM-assisted structure detection. Returns JSON section markers."""
        if not self.llm_provider:
            return []

        truncated = content[: max_tokens * 4]  # ~4 chars per token
        from pathlib import Path

        prompt_path = (
            Path(__file__).parent.parent / "summarizer" / "prompts" / "detect_structure_v1.txt"
        )
        if prompt_path.exists():
            import jinja2

            template = jinja2.Template(prompt_path.read_text())
            prompt = template.render(book_text=truncated)
        else:
            prompt = (
                "Analyze the following text from the beginning of a book. Identify the "
                "chapter/section structure. Return a JSON array of sections with 'title' "
                "and approximate 'char_offset' keys.\n\n" + truncated
            )

        response = await self.llm_provider.generate(
            prompt=prompt,
            json_schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "char_offset": {"type": "integer"},
                    },
                    "required": ["title", "char_offset"],
                },
            },
        )
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return []
