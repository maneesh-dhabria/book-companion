"""Image captioning via Claude Code CLI vision capabilities."""

import hashlib
import json
import re
import tempfile
from pathlib import Path

import structlog

from app.services.summarizer.llm_provider import LLMProvider

logger = structlog.get_logger()

MIN_DIMENSION_PX = 50
MIN_FILE_SIZE_BYTES = 5120  # 5KB

DECORATIVE_PATTERNS = re.compile(
    r"(separator|divider|spacer|logo|icon|bullet|ornament|border|header-bg|footer-bg|rule|cover)",
    re.IGNORECASE,
)

EMPTY_RESULT = {"caption": "", "relevance": "decorative"}


def should_skip_image(
    data: bytes,
    width: int | None,
    height: int | None,
    filename: str | None,
) -> bool:
    """Return True if the image is likely decorative and should skip captioning."""
    if width is not None and height is not None:
        if width < MIN_DIMENSION_PX and height < MIN_DIMENSION_PX:
            return True

    if len(data) < MIN_FILE_SIZE_BYTES:
        return True

    if filename and DECORATIVE_PATTERNS.search(filename):
        return True

    return False


def compute_content_hash(data: bytes) -> str:
    """SHA-256 hash of image bytes for deduplication."""
    return hashlib.sha256(data).hexdigest()


class ImageCaptioner:
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    async def caption_image(
        self,
        image_data: bytes,
        mime_type: str,
        context: str = "",
        alt_text: str | None = None,
    ) -> dict:
        """Generate a caption and relevance classification for an image.

        Returns: {"caption": str, "relevance": "key"|"supplementary"|"decorative"}
        Non-blocking: returns EMPTY_RESULT on failure.
        """
        ext = mime_type.split("/")[-1] if "/" in mime_type else "png"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                image_path = Path(tmpdir) / f"image.{ext}"
                image_path.write_bytes(image_data)

                alt_context = ""
                if alt_text:
                    alt_context = (
                        f'\nThe image has existing alt-text: "{alt_text}"\n'
                        "Use this as a starting point but provide a richer description.\n"
                    )

                prompt = (
                    f"Describe what this image shows in the context of: {context}.\n"
                    f"{alt_context}\n"
                    "Classify the image into one of these categories:\n"
                    "- key: Diagrams, frameworks, charts, data visualizations, tables, or models\n"
                    "- supplementary: Photos, illustrations, or examples that support the text\n"
                    "- decorative: Ornamental elements, headers, backgrounds, purely aesthetic\n\n"
                    'Respond with JSON: {"caption": "1-3 sentence description", '
                    '"relevance": "key|supplementary|decorative"}'
                )
                response = await self.llm_provider.generate_with_image(
                    prompt=prompt,
                    image_path=image_path,
                )

                logger.info(
                    "image_captioned",
                    model=response.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    latency_ms=response.latency_ms,
                )

                try:
                    parsed = json.loads(response.content)
                    return {
                        "caption": parsed.get("caption", response.content.strip()),
                        "relevance": parsed.get("relevance", "supplementary"),
                    }
                except json.JSONDecodeError:
                    return {"caption": response.content.strip(), "relevance": "supplementary"}
        except Exception as e:
            logger.warning("image_captioning_failed", error=str(e))
            return dict(EMPTY_RESULT)

    async def caption_section_images(
        self,
        images: list[dict],
        section_context: str,
    ) -> dict[int, dict]:
        """Caption images for a section with pre-filtering and deduplication.

        Input images are dicts with keys: id, data, mime_type, width, height, filename,
        alt_text, content_hash, existing_caption, existing_relevance.

        Returns: {image_id: {"caption": str, "relevance": str}}
        """
        results = {}
        # Build a hash->caption map for dedup within this batch
        hash_cache: dict[str, dict] = {}

        # First pass: collect already-captioned images into hash_cache
        for img in images:
            if img.get("existing_caption") and img.get("existing_relevance"):
                results[img["id"]] = {
                    "caption": img["existing_caption"],
                    "relevance": img["existing_relevance"],
                }
                content_hash = img.get("content_hash")
                if content_hash:
                    hash_cache[content_hash] = results[img["id"]]

        # Second pass: process uncaptioned images
        for img in images:
            if img["id"] in results:
                continue  # Already has caption

            if should_skip_image(
                data=img["data"],
                width=img.get("width"),
                height=img.get("height"),
                filename=img.get("filename"),
            ):
                logger.debug("image_skipped_by_prefilter", image_id=img["id"])
                continue

            # Check dedup cache
            content_hash = img.get("content_hash")
            if content_hash and content_hash in hash_cache:
                results[img["id"]] = dict(hash_cache[content_hash])
                logger.debug("image_dedup_hit", image_id=img["id"], hash=content_hash[:8])
                continue

            # Caption via LLM
            result = await self.caption_image(
                image_data=img["data"],
                mime_type=img["mime_type"],
                context=section_context,
                alt_text=img.get("alt_text"),
            )

            if result["caption"]:
                results[img["id"]] = result
                if content_hash:
                    hash_cache[content_hash] = result

        return results
