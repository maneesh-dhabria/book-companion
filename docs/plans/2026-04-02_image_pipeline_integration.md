# Image Pipeline Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire image captioning into the summarization pipeline so section and book summaries reference key visual content, with proper cost tracking, deduplication, alt-text reuse, search indexing, and user visibility.

**Architecture:** Images are already parsed and stored in the DB. We enhance the pipeline in layers: (1) add `relevance`, `alt_text`, `content_hash` columns to Image model with deferred binary data loading, (2) enhance `ImageCaptioner` with pre-filter heuristics, SHA-256 dedup, alt-text reuse, and relevance classification, (3) wire captioner into `SummarizerService` with incremental persistence and cost logging, (4) update templates with relevance-aware image instructions and markdown image refs, (5) index captions in search, (6) add config toggle + CLI flag + verbose output.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (with `deferred()`), Alembic, Jinja2, pytest, Claude Code CLI (vision)

## Review Decisions

Captured from multi-role review (Principal Architect, DBA, Product Director, Senior Analyst, Designer, DevOps, Security, Extensibility):

| Decision | Rationale |
|----------|-----------|
| Sequential captioning (no concurrency) | Simpler, adequate for personal CLI. Parallelize later if needed. |
| Lazy-load image binary via `deferred()` | Avoid loading hundreds of MB into memory when only metadata is needed. |
| `db.flush()` after each image caption | Crash-safe: already-captioned images keep their data on restart. |
| Python `ImageRelevance(str, Enum)` | Type-safe in code, no DB constraint needed for personal tool. |
| `--verbose` per-section image summary + `show` command image info | User visibility into what's happening with images. |
| `--force` flag also re-captions images | Piggyback on existing UX for re-processing. |
| Skip cover images (add `cover` to decorative patterns) | Covers don't add to content summaries. Preserved in DB for future web UI. |
| Index all non-decorative image captions in search | Captions contain rich semantic content discoverable via hybrid search. |
| Include key image refs in cumulative context | Helps LLM maintain visual narrative coherence across chapters. |
| Embed `![caption](image:ID)` refs in summary markdown | Enables future export/web UI to resolve and render actual images. |
| Log per-image captioning cost to structlog | Audit trail for cost visibility per section and book. |
| Config toggle (`images.captioning_enabled`) + CLI flag (`--skip-images`) | Disable captioning without code changes if broken or too expensive. |
| Extract and store EPUB alt-text during parsing | Reuse existing alt-text as context or substitute for LLM captioning. |
| SHA-256 content hash dedup before captioning | Avoid re-captioning identical images (covers, logos repeated across sections). |
| Skip corrupt images with warning (non-blocking) | Consistent with captioner's existing graceful degradation pattern. |
| No per-section image cap | Let all non-decorative images through; trust relevance classification. |
| No special file storage — DB is fine | Local-only tool; DB binary storage is adequate. |
| Temp file cleanup via `tempfile.TemporaryDirectory` is sufficient | OS handles orphans; no explicit cleanup needed. |

## Research Sources

| Source | What was found | How it informed the plan |
|--------|----------------|--------------------------|
| `app/services/parser/epub_parser.py` (lines 77-84, 145-147) | EPUB parser extracts images into `image_map` by filename but does NOT extract width/height or alt-text | Added Task 2 to extract alt-text; noted pre-filter by dimensions may not work for all books |
| `app/services/parser/pdf_parser.py` (lines 64-71) | PDF parser extracts images via pymupdf4llm, also no width/height | Same limitation applies to PDFs |
| `app/services/book_service.py` (lines 157-166) | Images stored as `Image()` ORM objects with optional width/height fields | Deferred loading on `data` column avoids memory issues |
| `app/db/session.py`, `app/cli/deps.py` (lines 113-228) | Single shared session per CLI invocation, manual flush/commit | Flush-after-each-image strategy works within this transaction model |
| `app/config.py` | No image-related config sections exist | Added new `ImageConfig` section in Task 8 |
| `app/services/embedding_service.py` | Uses semaphore-limited concurrency for Ollama calls | Pattern available if we parallelize captioning later |
| `app/services/search_service.py` | BM25 + semantic search via SearchIndex model | Image captions can be indexed via same mechanism |
| Industry: Marker v2, Docling (document processors) | Pre-filter by size/position; leverage existing captions before LLM; structured JSON output for captions | Adopted heuristic pre-filter + alt-text reuse + JSON structured captioning |
| Industry: imagehash library, SHA-256 dedup | Exact hash catches repeated images in EPUB/PDF (covers, logos, ornaments) | Added SHA-256 dedup in Task 4 |
| Industry: EPUB accessibility (alt-text) | Well-published books have quality alt-text; score quality before calling LLM | Added alt-text extraction in Task 2 and reuse logic in Task 4 |

---

### Task 1: Add `relevance`, `alt_text`, `content_hash` columns + `ImageRelevance` enum + deferred data loading

**Files:**
- Modify: `backend/app/db/models.py:212-232`
- Create: `backend/alembic/versions/<auto>_add_image_columns.py`
- Create: `backend/tests/unit/test_image_model.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_image_model.py`:

```python
"""Tests for Image model new fields."""

import pytest
from app.db.models import Image, ImageRelevance


def test_image_relevance_enum_values():
    assert ImageRelevance.KEY == "key"
    assert ImageRelevance.SUPPLEMENTARY == "supplementary"
    assert ImageRelevance.DECORATIVE == "decorative"


def test_image_has_relevance_field():
    img = Image(
        section_id=1,
        data=b"fake",
        mime_type="image/png",
        relevance=ImageRelevance.KEY,
    )
    assert img.relevance == "key"


def test_image_relevance_defaults_to_none():
    img = Image(section_id=1, data=b"fake", mime_type="image/png")
    assert img.relevance is None


def test_image_has_alt_text_field():
    img = Image(
        section_id=1, data=b"fake", mime_type="image/png",
        alt_text="A diagram of the five forces.",
    )
    assert img.alt_text == "A diagram of the five forces."


def test_image_has_content_hash_field():
    img = Image(
        section_id=1, data=b"fake", mime_type="image/png",
        content_hash="abc123",
    )
    assert img.content_hash == "abc123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_image_model.py -v`
Expected: FAIL — `ImageRelevance` not defined, `Image()` does not accept new fields.

- [ ] **Step 3: Add ImageRelevance enum and update Image model**

In `backend/app/db/models.py`:

Add enum near other enums (after `SourceType`):

```python
class ImageRelevance(str, enum.Enum):
    KEY = "key"
    SUPPLEMENTARY = "supplementary"
    DECORATIVE = "decorative"
```

Update `Image` model — add new columns after `caption_model` (line 227), and add `deferred()` to `data`:

```python
from sqlalchemy.orm import deferred

class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    section_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("book_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    data: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    relevance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    section: Mapped["BookSection"] = relationship(back_populates="images")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_image_model.py -v`
Expected: PASS

- [ ] **Step 5: Generate and run Alembic migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_image_relevance_alttext_hash"
cd backend && uv run alembic upgrade head
```

Review migration — should add `relevance` (String 20), `alt_text` (Text), `content_hash` (String 64) columns. Verify `data` column is NOT affected (deferred is ORM-level, not schema-level).

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models.py backend/alembic/versions/*_add_image_relevance_alttext_hash.py backend/tests/unit/test_image_model.py
git commit -m "feat: add relevance, alt_text, content_hash columns to Image model with deferred data loading"
```

---

### Task 2: Extract alt-text during EPUB parsing

**Files:**
- Modify: `backend/app/services/parser/epub_parser.py`
- Modify: `backend/tests/unit/test_epub_parser.py` (or create if not exists)

EPUB `<img>` tags often have `alt` attributes. Extract these during parsing and store on the `Image` model so the captioner can use them as context or skip captioning for well-described images.

- [ ] **Step 1: Write the failing test**

Add to the epub parser tests:

```python
def test_parsed_section_images_include_alt_text():
    """Images extracted from EPUB should include alt-text if available."""
    # Create a minimal EPUB-like HTML with an image that has alt text
    from app.services.parser.epub_parser import EPUBParser
    from unittest.mock import MagicMock

    parser = EPUBParser.__new__(EPUBParser)
    # Test the alt-text extraction helper
    html = '<html><body><p>Text</p><img src="fig1.png" alt="Porter Five Forces diagram"/></body></html>'
    alt_map = parser._extract_alt_text(html)
    assert alt_map.get("fig1.png") == "Porter Five Forces diagram"


def test_alt_text_extraction_handles_missing_alt():
    from app.services.parser.epub_parser import EPUBParser

    parser = EPUBParser.__new__(EPUBParser)
    html = '<html><body><img src="fig1.png"/><img src="fig2.png" alt=""/></body></html>'
    alt_map = parser._extract_alt_text(html)
    assert "fig1.png" not in alt_map  # No alt attribute
    assert "fig2.png" not in alt_map  # Empty alt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_epub_parser.py -v -k alt_text`
Expected: FAIL — `_extract_alt_text` not defined.

- [ ] **Step 3: Add `_extract_alt_text` method to EPUBParser**

In `backend/app/services/parser/epub_parser.py`, add a helper method:

```python
def _extract_alt_text(self, html_content: str) -> dict[str, str]:
    """Extract alt-text from img tags. Returns {filename: alt_text}."""
    from markdownify import markdownify  # already a dependency
    import re

    alt_map = {}
    # Use regex to find img tags with alt attributes (avoid adding bs4 dependency)
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']+)["\']', html_content):
        src, alt = match.group(1), match.group(2).strip()
        if alt and alt.lower() not in ("image", "figure", "img", ""):
            filename = src.split("/")[-1]
            alt_map[filename] = alt
    # Also match alt before src
    for match in re.finditer(r'<img[^>]+alt=["\']([^"\']+)["\'][^>]*src=["\']([^"\']+)["\']', html_content):
        alt, src = match.group(1).strip(), match.group(2)
        if alt and alt.lower() not in ("image", "figure", "img", ""):
            filename = src.split("/")[-1]
            alt_map[filename] = alt
    return alt_map
```

Then, in the section-building loop where images are associated with sections, pass the alt-text to `ParsedImage`:

```python
alt_map = self._extract_alt_text(chapter_html)
# When creating ParsedImage:
alt_text = alt_map.get(img_filename, None)
```

And in `backend/app/services/book_service.py` `_store_book()`, pass alt_text when creating the Image:

```python
image = Image(
    section_id=section.id,
    data=pi.data,
    mime_type=pi.mime_type,
    filename=pi.filename,
    width=pi.width,
    height=pi.height,
    alt_text=pi.alt_text,  # NEW
)
```

This requires adding `alt_text: str | None = None` to the `ParsedImage` dataclass (check `app/services/parser/base.py` or wherever `ParsedImage` is defined).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_epub_parser.py -v -k alt_text`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser/epub_parser.py backend/app/services/parser/base.py backend/app/services/book_service.py backend/tests/unit/test_epub_parser.py
git commit -m "feat: extract and store EPUB alt-text during parsing"
```

---

### Task 3: Add pre-filter heuristic with cover detection

**Files:**
- Modify: `backend/app/services/summarizer/image_captioner.py`
- Modify: `backend/tests/unit/test_image_captioner.py`

Pre-filter skips obviously decorative images before any LLM call:
- Dimensions: skip if both width and height < 50px
- File size: skip if < 5KB
- Filename patterns: decorative patterns + `cover`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/unit/test_image_captioner.py`:

```python
from app.services.summarizer.image_captioner import should_skip_image


def test_skip_tiny_image():
    assert should_skip_image(data=b"x" * 100, width=20, height=20, filename="img.png") is True


def test_skip_small_filesize():
    assert should_skip_image(data=b"x" * 1000, width=200, height=200, filename="chart.png") is True


def test_skip_decorative_filename():
    assert should_skip_image(data=b"x" * 10000, width=200, height=200, filename="separator.png") is True
    assert should_skip_image(data=b"x" * 10000, width=200, height=200, filename="header-divider.gif") is True
    assert should_skip_image(data=b"x" * 10000, width=200, height=200, filename="bullet_icon.png") is True


def test_skip_cover_image():
    assert should_skip_image(data=b"x" * 50000, width=600, height=900, filename="cover.jpg") is True
    assert should_skip_image(data=b"x" * 50000, width=600, height=900, filename="book-cover.png") is True


def test_keep_normal_image():
    assert should_skip_image(data=b"x" * 10000, width=400, height=300, filename="figure_1.png") is False


def test_keep_image_with_no_dimensions():
    """Images without dimension metadata should not be skipped."""
    assert should_skip_image(data=b"x" * 10000, width=None, height=None, filename="chart.png") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_image_captioner.py -v -k skip`
Expected: FAIL — `should_skip_image` not defined.

- [ ] **Step 3: Implement the pre-filter function**

Add to `backend/app/services/summarizer/image_captioner.py` before the `ImageCaptioner` class:

```python
import re

MIN_DIMENSION_PX = 50
MIN_FILE_SIZE_BYTES = 5120  # 5KB

DECORATIVE_PATTERNS = re.compile(
    r"(separator|divider|spacer|logo|icon|bullet|ornament|border|header-bg|footer-bg|rule|cover)",
    re.IGNORECASE,
)


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_image_captioner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/summarizer/image_captioner.py backend/tests/unit/test_image_captioner.py
git commit -m "feat: add pre-filter heuristic to skip decorative and cover images"
```

---

### Task 4: Enhance ImageCaptioner with relevance classification, dedup, and alt-text reuse

**Files:**
- Modify: `backend/app/services/summarizer/image_captioner.py`
- Modify: `backend/app/services/summarizer/prompts/caption_image_v1.txt`
- Modify: `backend/tests/unit/test_image_captioner.py`

The captioner returns `{"caption": str, "relevance": str}`. It also:
- Deduplicates by SHA-256 content hash (if same hash already captioned, reuse caption)
- Uses existing alt-text as context when calling the LLM
- Logs per-image cost (input/output tokens, latency)

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/unit/test_image_captioner.py`:

```python
import json
from unittest.mock import AsyncMock
from app.services.summarizer.llm_provider import LLMResponse


@pytest.mark.asyncio
async def test_caption_image_returns_caption_and_relevance():
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.return_value = LLMResponse(
        content=json.dumps({
            "caption": "A diagram showing Porter's Five Forces framework.",
            "relevance": "key",
        }),
        model="sonnet",
        latency_ms=500,
        input_tokens=100,
        output_tokens=50,
    )
    captioner = ImageCaptioner(llm_provider=mock_llm)
    result = await captioner.caption_image(
        image_data=b"fake_image_data",
        mime_type="image/png",
        context="Competitive strategy frameworks.",
    )
    assert result["caption"] == "A diagram showing Porter's Five Forces framework."
    assert result["relevance"] == "key"


@pytest.mark.asyncio
async def test_caption_failure_returns_empty_result():
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.side_effect = Exception("CLI failed")
    captioner = ImageCaptioner(llm_provider=mock_llm)
    result = await captioner.caption_image(
        image_data=b"fake", mime_type="image/png", context="test"
    )
    assert result["caption"] == ""
    assert result["relevance"] == "decorative"


@pytest.mark.asyncio
async def test_caption_section_images_with_prefilter():
    """Pre-filter should skip tiny images, caption the rest."""
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.return_value = LLMResponse(
        content=json.dumps({
            "caption": "A chart showing market share data.",
            "relevance": "key",
        }),
        model="sonnet",
        latency_ms=500,
    )
    captioner = ImageCaptioner(llm_provider=mock_llm)
    images = [
        {"id": 1, "data": b"x" * 100, "mime_type": "image/png",
         "width": 10, "height": 10, "filename": "dot.png", "alt_text": None, "content_hash": None},
        {"id": 2, "data": b"x" * 10000, "mime_type": "image/png",
         "width": 400, "height": 300, "filename": "figure1.png", "alt_text": None, "content_hash": None},
    ]
    results = await captioner.caption_section_images(
        images=images, section_context="Market analysis"
    )
    assert 1 not in results
    assert 2 in results
    assert results[2]["relevance"] == "key"
    mock_llm.generate_with_image.assert_called_once()


@pytest.mark.asyncio
async def test_dedup_skips_already_captioned_hash():
    """If two images share the same content_hash and one is already captioned, reuse."""
    mock_llm = AsyncMock()
    captioner = ImageCaptioner(llm_provider=mock_llm)
    images = [
        {"id": 1, "data": b"x" * 10000, "mime_type": "image/png",
         "width": 400, "height": 300, "filename": "fig1.png",
         "alt_text": None, "content_hash": "abc123",
         "existing_caption": "A framework diagram.", "existing_relevance": "key"},
        {"id": 2, "data": b"x" * 10000, "mime_type": "image/png",
         "width": 400, "height": 300, "filename": "fig1_copy.png",
         "alt_text": None, "content_hash": "abc123",
         "existing_caption": None, "existing_relevance": None},
    ]
    results = await captioner.caption_section_images(
        images=images, section_context="Test"
    )
    # Image 1 already has caption — returned as-is
    # Image 2 has same hash — should reuse image 1's caption, no LLM call
    mock_llm.generate_with_image.assert_not_called()
    assert results[1]["caption"] == "A framework diagram."
    assert results[2]["caption"] == "A framework diagram."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_image_captioner.py -v -k "caption_image_returns or caption_failure or section_images_with or dedup"`
Expected: FAIL

- [ ] **Step 3: Update the caption prompt template**

Replace `backend/app/services/summarizer/prompts/caption_image_v1.txt`:

```
Describe what this image shows in the context of: {{ context }}.

{% if alt_text %}
The image has existing alt-text: "{{ alt_text }}"
Use this as a starting point but provide a richer description.
{% endif %}

Classify the image into one of these categories:
- **key**: Diagrams, frameworks, charts, data visualizations, tables, or models that convey core concepts
- **supplementary**: Photos, illustrations, or examples that support the text but aren't essential
- **decorative**: Ornamental elements, headers, backgrounds, or purely aesthetic content

Respond with JSON:
{
  "caption": "1-3 sentence description focusing on key information, data, frameworks, or concepts depicted.",
  "relevance": "key | supplementary | decorative"
}
```

- [ ] **Step 4: Rewrite ImageCaptioner**

Replace `backend/app/services/summarizer/image_captioner.py`:

```python
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
                    alt_context = f'\nThe image has existing alt-text: "{alt_text}"\nUse this as a starting point but provide a richer description.\n'

                prompt = (
                    f"Describe what this image shows in the context of: {context}.\n"
                    f"{alt_context}\n"
                    "Classify the image into one of these categories:\n"
                    "- key: Diagrams, frameworks, charts, data visualizations, tables, or models\n"
                    "- supplementary: Photos, illustrations, or examples that support the text\n"
                    "- decorative: Ornamental elements, headers, backgrounds, purely aesthetic\n\n"
                    'Respond with JSON: {"caption": "1-3 sentence description", "relevance": "key|supplementary|decorative"}'
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
```

- [ ] **Step 5: Update old captioner tests for new return type**

Replace the two original tests in `backend/tests/unit/test_image_captioner.py` with the new versions from Step 1 (they already use the dict return type).

- [ ] **Step 6: Run all captioner tests**

Run: `cd backend && uv run pytest tests/unit/test_image_captioner.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/summarizer/image_captioner.py backend/app/services/summarizer/prompts/caption_image_v1.txt backend/tests/unit/test_image_captioner.py
git commit -m "feat: enhance ImageCaptioner with relevance classification, SHA-256 dedup, alt-text reuse, cost logging"
```

---

### Task 5: Wire image captioning into SummarizerService with incremental persistence

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py`
- Modify: `backend/tests/unit/test_summarizer.py`

SummarizerService needs to:
1. Accept optional `ImageCaptioner` via constructor
2. Lazy-load image data only when captioning is needed (via `deferred()` from Task 1)
3. Caption uncaptioned images, flush each to DB immediately
4. Filter to key + supplementary, pass captions to template
5. Include key image refs in cumulative context
6. Embed `![caption](image:ID)` markdown refs in summary output

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/test_summarizer.py`:

```python
@pytest.mark.asyncio
async def test_summarize_section_passes_image_captions():
    """Image captions should be passed to the Jinja template."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        content=json.dumps({
            "key_concepts": ["concept1"],
            "detailed_summary": "Strategy section with a key diagram. ![Porter Five Forces](image:1)",
            "frameworks": [],
            "key_quotes": [],
            "concepts": [],
        }),
        model="sonnet",
        latency_ms=1000,
    )
    mock_session = AsyncMock()
    mock_config = MagicMock()
    mock_config.summarization.default_detail_level = "standard"
    mock_config.summarization.prompt_version = "v1"

    section = make_mock_section()
    mock_img = MagicMock()
    mock_img.id = 1
    mock_img.data = b"x" * 10000
    mock_img.mime_type = "image/png"
    mock_img.filename = "figure1.png"
    mock_img.width = 400
    mock_img.height = 300
    mock_img.caption = "Porter Five Forces framework diagram."
    mock_img.relevance = "key"
    mock_img.alt_text = None
    mock_img.content_hash = "abc123"
    section.images = [mock_img]

    service = SummarizerService(db=mock_session, llm=mock_llm, config=mock_config)
    result = await service._summarize_single_section(
        section=section, prior_sections=[], detail_level="standard"
    )

    # Verify the LLM prompt includes the image caption
    call_args = mock_llm.generate.call_args
    prompt_sent = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
    assert "porter five forces" in prompt_sent.lower()


@pytest.mark.asyncio
async def test_cumulative_context_includes_key_images():
    """Key image references from prior sections should appear in cumulative context."""
    service = SummarizerService.__new__(SummarizerService)
    prior = [
        MagicMock(
            title="Ch1",
            summary_md="Chapter 1 covers the Five Forces. ![Five Forces diagram](image:5)",
            images=[MagicMock(id=5, caption="Five Forces framework", relevance="key")],
        ),
        MagicMock(
            title="Ch2",
            summary_md="Chapter 2 discusses value chains.",
            images=[],
        ),
    ]
    context = service._build_cumulative_context(prior)
    assert "Ch1" in context
    assert "Five Forces" in context
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_summarizer.py::test_summarize_section_passes_image_captions tests/unit/test_summarizer.py::test_cumulative_context_includes_key_images -v`
Expected: FAIL

- [ ] **Step 3: Update SummarizerService constructor**

```python
class SummarizerService:
    def __init__(self, db: AsyncSession, llm: LLMProvider, config, captioner=None):
        self.db = db
        self.llm = llm
        self.config = config
        self.captioner = captioner
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(PROMPTS_DIR))
        )
```

- [ ] **Step 4: Add `_get_image_captions` helper with incremental flush**

Add after `_get_compression_target`:

```python
    async def _get_image_captions(self, section: BookSection) -> list[dict]:
        """Get image captions for a section. Captions uncaptioned images if captioner available.

        Uses deferred loading — image.data only loaded when captioner needs it.
        Flushes each newly captioned image to DB immediately for crash safety.

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
            # Skip pre-filtered decorative images (needs data for size check)
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
```

- [ ] **Step 5: Update `_summarize_single_section` to pass image captions**

In `_summarize_single_section`, before the template render block, add:

```python
        # Get image captions for this section
        image_captions = await self._get_image_captions(section)

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
```

- [ ] **Step 6: Update `_build_cumulative_context` to include key image refs**

```python
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
```

- [ ] **Step 7: Run tests**

Run: `cd backend && uv run pytest tests/unit/test_summarizer.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/summarizer/summarizer_service.py backend/tests/unit/test_summarizer.py
git commit -m "feat: wire image captioning into SummarizerService with incremental persistence and cumulative context"
```

---

### Task 6: Update section and book summary templates

**Files:**
- Modify: `backend/app/services/summarizer/prompts/summarize_section_v1.txt`
- Modify: `backend/app/services/summarizer/prompts/summarize_book_v1.txt`

- [ ] **Step 1: Update section template with relevance-aware image instructions**

Replace the `{% if image_captions %}` block in `backend/app/services/summarizer/prompts/summarize_section_v1.txt` (lines 28-34):

```jinja2
{% if image_captions %}
### Visual Content
The section contains the following images/diagrams. Integrate **key** images into your summary by describing what they show and why they matter to the argument. Mention **supplementary** images only if they add meaningful context. When referencing an image, include a markdown image ref: ![brief description](image:ID).

{% for img in image_captions %}
- [{{ img.relevance }}] (image:{{ img.image_id }}) {{ img.caption }}
{% endfor %}
{% endif %}
```

- [ ] **Step 2: Update book template with visual content curation section**

In `backend/app/services/summarizer/prompts/summarize_book_v1.txt`, add between "Practical Takeaways" and "Who Should Read This":

```
## Key Visual Content
If any chapter summaries reference diagrams, frameworks, charts, or other visual content (via `![...](image:...)` refs), select **only the most important visuals** across the entire book — those central to the book's core argument or that represent major frameworks. For each selected visual, describe it and explain its significance to the book's thesis. Preserve the `![...](image:...)` markdown refs so they can be resolved later. If no visual content is referenced in the chapter summaries, omit this section entirely.
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/unit/test_summarizer.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/summarizer/prompts/summarize_section_v1.txt backend/app/services/summarizer/prompts/summarize_book_v1.txt
git commit -m "feat: update templates with relevance-aware image instructions and markdown image refs"
```

---

### Task 7: Eagerly load images in summarizer queries

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py`

The `summarize_section` and `summarize_book` methods query `BookSection` but don't load `images`. With `deferred()` on data, `selectinload(BookSection.images)` loads image metadata without binary data — data is only fetched on `img.data` attribute access.

- [ ] **Step 1: Update `summarize_section` query**

```python
        result = await self.db.execute(
            select(BookSection)
            .options(selectinload(BookSection.images))
            .where(BookSection.id == section_id)
        )
```

- [ ] **Step 2: Update `summarize_book` sections query**

```python
        result = await self.db.execute(
            select(BookSection)
            .where(BookSection.book_id == book_id)
            .options(selectinload(BookSection.images))
            .order_by(BookSection.order_index)
        )
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/summarizer/summarizer_service.py
git commit -m "fix: eagerly load image metadata in summarizer section queries"
```

---

### Task 8: Add image config toggle + CLI flag

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/cli/commands/summarize_cmd.py`
- Modify: `backend/app/cli/deps.py`

- [ ] **Step 1: Add ImageConfig to settings**

In `backend/app/config.py`, add a new config class and include it in `Settings`:

```python
class ImageConfig(BaseModel):
    captioning_enabled: bool = True


class Settings(BaseSettings):
    # ... existing fields ...
    images: ImageConfig = ImageConfig()
```

- [ ] **Step 2: Add `--skip-images` flag to summarize command**

In `backend/app/cli/commands/summarize_cmd.py`, add the flag to the `summarize` function signature:

```python
    skip_images: bool = typer.Option(
        False, "--skip-images", help="Skip image captioning during summarization."
    ),
```

Then, before calling the summarizer, temporarily disable captioning if flag is set:

```python
        if skip_images:
            summarizer.captioner = None
```

- [ ] **Step 3: Wire ImageCaptioner in deps.py (conditioned on config)**

Update `backend/app/cli/deps.py` summarizer block:

```python
        try:
            from app.services.summarizer.summarizer_service import SummarizerService
            from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider
            from app.services.summarizer.image_captioner import ImageCaptioner

            llm = ClaudeCodeCLIProvider(
                cli_command=settings.llm.cli_command,
                default_model=settings.llm.model,
                default_timeout=settings.llm.timeout_seconds,
                max_budget_usd=settings.llm.max_budget_usd,
            )
            services["llm"] = llm
            captioner = ImageCaptioner(llm_provider=llm) if settings.images.captioning_enabled else None
            services["summarizer"] = SummarizerService(
                db=session, llm=llm, config=settings, captioner=captioner
            )
        except ImportError:
            pass
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/cli/commands/summarize_cmd.py backend/app/cli/deps.py
git commit -m "feat: add image captioning config toggle and --skip-images CLI flag"
```

---

### Task 9: Add verbose image output + show command image info

**Files:**
- Modify: `backend/app/cli/commands/summarize_cmd.py`
- Modify: `backend/app/cli/commands/books.py`

- [ ] **Step 1: Add per-section image summary to summarize command**

In `backend/app/cli/commands/summarize_cmd.py`, after each section is summarized in the all-sections loop (line ~113), add verbose image output:

```python
                    # Report image stats if verbose
                    section_images = section.images or []
                    if section_images:
                        key_count = sum(1 for i in section_images if getattr(i, 'relevance', None) == 'key')
                        supp_count = sum(1 for i in section_images if getattr(i, 'relevance', None) == 'supplementary')
                        skipped = len(section_images) - key_count - supp_count
                        console.print(
                            f"  [dim]Images: {len(section_images)} found, "
                            f"{key_count} key, {supp_count} supplementary, "
                            f"{skipped} skipped[/dim]"
                        )
```

- [ ] **Step 2: Add image info to show command**

In `backend/app/cli/commands/books.py` `show` function, add an "Images" column to the sections table:

```python
            table.add_column("Images", justify="right")

            for section in book.sections:
                img_count = len(section.images) if section.images else 0
                captioned = sum(1 for i in (section.images or []) if i.caption) if img_count else 0
                img_display = f"{captioned}/{img_count}" if img_count else "—"
                table.add_row(
                    str(section.order_index + 1),
                    section.title,
                    section.summary_status.value if section.summary_status else "pending",
                    str(section.content_token_count or "—"),
                    img_display,
                )
```

Note: The `show` command's `get_book()` call must also eagerly load images. Check that `book_service.get_book()` uses `selectinload(BookSection.images)` — if not, add it.

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/cli/commands/summarize_cmd.py backend/app/cli/commands/books.py
git commit -m "feat: add per-section image stats in verbose output and show command"
```

---

### Task 10: Pass image_count to eval `image_refs_preserved` assertion

**Files:**
- Modify: `backend/app/services/summarizer/evaluator.py`
- Modify: `backend/tests/unit/test_evaluator.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/test_evaluator.py`:

```python
@pytest.mark.asyncio
async def test_image_refs_preserved_receives_image_count(mock_session, mock_llm, mock_config):
    mock_llm.generate.return_value = LLMResponse(
        content=json.dumps({"passed": True, "reasoning": "Images referenced."}),
        model="sonnet",
        latency_ms=100,
    )

    eval_service = EvalService(db=mock_session, llm=mock_llm, config=mock_config)
    result = await eval_service._run_single_assertion(
        assertion_name="image_refs_preserved",
        source_text="Text with a figure.",
        summary_text="Summary references the figure.",
        section_id=1,
        image_count=3,
    )

    call_args = mock_llm.generate.call_args
    prompt_sent = call_args.kwargs.get("prompt", "")
    assert "3 image" in prompt_sent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_evaluator.py::test_image_refs_preserved_receives_image_count -v`
Expected: FAIL

- [ ] **Step 3: Update evaluator to accept and pass image_count**

In `backend/app/services/summarizer/evaluator.py`:

Update `_run_single_assertion` signature:

```python
    async def _run_single_assertion(
        self,
        assertion_name: str,
        source_text: str,
        summary_text: str,
        section_id: int,
        image_count: int = 0,
    ) -> dict:
```

Update template render call to pass `image_count`:

```python
            prompt = template.render(
                assertion_name=assertion_name,
                source_text=source_text,
                summary_text=summary_text,
                image_count=image_count,
            )
```

Update `evaluate_section` to count images and eagerly load them:

```python
    async def evaluate_section(self, book_id: int, section_id: int) -> dict[str, dict]:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.db.models import BookSection

        result = await self.db.execute(
            select(BookSection).options(selectinload(BookSection.images)).where(BookSection.id == section_id)
        )
        section = result.scalar_one_or_none()
        if not section:
            raise ValueError(f"Section not found: {section_id}")
        if not section.summary_md:
            raise ValueError(f"Section {section_id} has no summary to evaluate")

        image_count = sum(
            1 for img in (section.images or [])
            if img.relevance in ("key", "supplementary") or img.relevance is None
        )

        results = await self.evaluate_summary(
            section_id=section_id,
            source_text=section.content_md or "",
            summary_text=section.summary_md,
            image_count=image_count,
        )
        await self.db.commit()
        return results
```

Update `evaluate_summary` to accept and pass `image_count`:

```python
    async def evaluate_summary(
        self, section_id: int, source_text: str, summary_text: str, image_count: int = 0,
    ) -> dict[str, dict]:
        tasks = [
            self._run_single_assertion(name, source_text, summary_text, section_id, image_count=image_count)
            for name in ASSERTION_REGISTRY
        ]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/test_evaluator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/summarizer/evaluator.py backend/tests/unit/test_evaluator.py
git commit -m "feat: pass image_count to eval image_refs_preserved assertion"
```

---

### Task 11: Index non-decorative image captions in search

**Files:**
- Modify: `backend/app/services/search_service.py` (or wherever search indexing happens)
- Modify: `backend/app/services/embedding_service.py` (if embedding captions)

Image captions contain rich semantic content. Add captions of non-decorative images to the search index so they're discoverable via `bookcompanion search`.

- [ ] **Step 1: Identify where search indexing happens**

Check `backend/app/services/search_service.py` for the method that builds or updates search index entries. Also check if there's a separate indexing step in the summarization pipeline.

- [ ] **Step 2: After section summarization, index image captions**

When a section's summary is stored, also index its non-decorative image captions. Append image captions to the section's searchable text, or create separate `SearchIndex` entries for each image caption with `source_type="image_caption"`.

The approach depends on the existing `SearchIndex` model and how `SearchService.index_section()` works. Follow the existing pattern — if sections are indexed as single documents, append image captions to the document text. If chunks are indexed separately, create image caption chunks.

```python
# Example: append captions to section text before indexing
image_text = "\n".join(
    f"[Image: {img.caption}]"
    for img in section.images
    if img.relevance in ("key", "supplementary") and img.caption
)
indexable_text = f"{section.content_md}\n\n{image_text}" if image_text else section.content_md
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/search_service.py
git commit -m "feat: index non-decorative image captions in search"
```

---

### Task 12: End-to-end verification

**Files:** None (manual verification)

- [ ] **Step 1: Run full unit test suite**

```bash
cd backend && uv run pytest tests/unit/ -v
```

Expected: ALL PASS

- [ ] **Step 2: Run migrations**

```bash
cd backend && uv run alembic upgrade head
BOOKCOMPANION_DATABASE__URL=postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test uv run alembic upgrade head
```

- [ ] **Step 3: Test summarization with images**

Pick a book with images:

```bash
cd backend && uv run bookcompanion summarize <book_id> <section_id> --force
```

Verify:
- Per-section image stats printed
- Summary references visual content with `![...](image:...)` refs
- DB: `SELECT id, caption, relevance, content_hash FROM images WHERE section_id = <id>;` shows populated fields

- [ ] **Step 4: Test summarization without images**

```bash
cd backend && uv run bookcompanion summarize 1 14 --force --skip-eval
```

Verify: No errors, no image references.

- [ ] **Step 5: Test --skip-images flag**

```bash
cd backend && uv run bookcompanion summarize <book_id> <section_id> --force --skip-images
```

Verify: No captioning occurs, summary has no image references.

- [ ] **Step 6: Test show command**

```bash
cd backend && uv run bookcompanion show <book_id>
```

Verify: Images column shows `captioned/total` per section.

- [ ] **Step 7: Test config toggle**

```bash
cd backend && uv run bookcompanion config set images.captioning_enabled false
cd backend && uv run bookcompanion summarize <book_id> <section_id> --force
```

Verify: No captioning occurs.

```bash
cd backend && uv run bookcompanion config set images.captioning_enabled true
```

- [ ] **Step 8: Run lint**

```bash
cd backend && uv run ruff check . && uv run ruff format --check .
```

- [ ] **Step 9: Final commit**

```bash
git add -A && git commit -m "fix: lint and final adjustments for image pipeline integration"
```
