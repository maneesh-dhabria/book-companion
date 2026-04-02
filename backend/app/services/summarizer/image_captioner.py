"""Image captioning via Claude Code CLI vision capabilities."""

import tempfile
from pathlib import Path

import structlog

from app.services.summarizer.llm_provider import LLMProvider

logger = structlog.get_logger()


class ImageCaptioner:
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    async def caption_image(
        self,
        image_data: bytes,
        mime_type: str,
        context: str = "",
    ) -> str:
        """Generate a caption for an image. Non-blocking: returns empty string on failure."""
        ext = mime_type.split("/")[-1] if "/" in mime_type else "png"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                image_path = Path(tmpdir) / f"image.{ext}"
                image_path.write_bytes(image_data)

                prompt = (
                    f"Describe what this image shows in the context of: {context}. "
                    "Focus on key information, data, frameworks, or concepts depicted. "
                    "Be concise (1-3 sentences)."
                )
                response = await self.llm_provider.generate_with_image(
                    prompt=prompt,
                    image_path=image_path,
                )
                return response.content.strip()
        except Exception as e:
            logger.warning("image_captioning_failed", error=str(e))
            return ""

    async def caption_section_images(
        self,
        images: list[dict],
        section_context: str,
    ) -> dict[int, str]:
        """Caption multiple images for a section. Returns {image_id: caption}."""
        captions = {}
        for img in images:
            caption = await self.caption_image(
                image_data=img["data"],
                mime_type=img["mime_type"],
                context=section_context,
            )
            if caption:
                captions[img["id"]] = caption
        return captions
