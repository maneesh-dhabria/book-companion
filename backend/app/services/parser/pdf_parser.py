"""PDF parser using pymupdf4llm (fast) with marker-pdf fallback (complex layouts)."""

from pathlib import Path

import pymupdf4llm

from app.services.parser.base import BookParser, ParsedBook, ParsedImage, ParsedSection


class PDFParser(BookParser):
    def supports_format(self, file_format: str) -> bool:
        return file_format == "pdf"

    async def parse(self, file_path: Path) -> ParsedBook:
        # Detect if complex layout (tables, multi-column) warrants marker-pdf
        if self._is_complex_layout(file_path):
            return await self._parse_with_marker(file_path)

        # Default: pymupdf4llm for fast conversion (~0.12s/page)
        pages = pymupdf4llm.to_markdown(
            str(file_path),
            page_chunks=True,
            write_images=True,
        )

        title = self._extract_title(pages, file_path)
        sections = self._pages_to_sections(pages)

        return ParsedBook(
            title=title,
            authors=[],  # PDF metadata often lacks author -- filled by structure detection
            sections=sections,
            cover_image=None,
            metadata={"parser": "pymupdf4llm", "page_count": len(pages)},
        )

    def _extract_title(self, pages: list[dict], file_path: Path) -> str:
        """Extract title from PDF metadata or first page."""
        if pages and pages[0].get("metadata", {}).get("title"):
            return pages[0]["metadata"]["title"]
        # Fallback: first heading or filename
        if pages:
            first_page = pages[0].get("text", "")
            for line in first_page.split("\n"):
                line = line.strip()
                if line.startswith("#"):
                    return line.lstrip("#").strip()
                if line and len(line) < 200:
                    return line
        return file_path.stem.replace("_", " ").title()

    def _pages_to_sections(self, pages: list[dict]) -> list[ParsedSection]:
        """Convert page chunks into sections based on heading detection."""
        sections: list[ParsedSection] = []
        current_title = "Introduction"
        current_content: list[str] = []
        current_images: list[ParsedImage] = []
        order = 0

        for page in pages:
            text = page.get("text", "")
            images = page.get("images", [])

            # Collect images from this page
            for img in images:
                if isinstance(img, dict) and "image" in img:
                    current_images.append(ParsedImage(
                        data=img["image"] if isinstance(img["image"], bytes) else b"",
                        mime_type="image/png",
                        filename=img.get("name"),
                    ))

            # Split on major headings (# or ##)
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("# ") and not stripped.startswith("###"):
                    # Save current section
                    if current_content:
                        content = "\n".join(current_content).strip()
                        if content:
                            sections.append(ParsedSection(
                                title=current_title,
                                content_md=content,
                                depth=0,
                                order_index=order,
                                images=current_images,
                            ))
                            order += 1
                            current_images = []
                    current_title = stripped.lstrip("#").strip()
                    current_content = []
                else:
                    current_content.append(line)

        # Don't forget the last section
        if current_content:
            content = "\n".join(current_content).strip()
            if content:
                sections.append(ParsedSection(
                    title=current_title,
                    content_md=content,
                    depth=0,
                    order_index=order,
                    images=current_images,
                ))

        # If no heading-based splits worked, create one section per N pages
        if len(sections) <= 1 and len(pages) > 5:
            return self._chunk_by_pages(pages, pages_per_section=10)

        return sections

    def _is_complex_layout(self, file_path: Path) -> bool:
        """Heuristic: detect complex PDFs that need marker-pdf.
        Check for multi-column layouts, heavy table content, or dense images."""
        import fitz  # pymupdf
        doc = fitz.open(str(file_path))
        sample_pages = min(5, len(doc))
        table_count = 0
        image_density = 0
        for i in range(sample_pages):
            page = doc[i]
            tables = page.find_tables()
            table_count += len(tables.tables) if hasattr(tables, 'tables') else 0
            image_density += len(page.get_images())
        doc.close()
        # Complex if >3 tables or >2 images per page on average
        return table_count > 3 or (image_density / max(sample_pages, 1)) > 2

    async def _parse_with_marker(self, file_path: Path) -> ParsedBook:
        """Fallback: use marker-pdf for complex layouts (~8s/page)."""
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        converter = PdfConverter(artifact_dict=create_model_dict())
        rendered = converter(str(file_path))
        # Convert marker output to ParsedBook format
        sections = self._pages_to_sections([{"text": rendered.markdown}])
        return ParsedBook(
            title=self._extract_title([{"text": rendered.markdown}], file_path),
            authors=[],
            sections=sections,
            metadata={"parser": "marker-pdf"},
        )

    def _chunk_by_pages(
        self, pages: list[dict], pages_per_section: int = 10
    ) -> list[ParsedSection]:
        """Fallback: group pages into sections."""
        sections = []
        for i in range(0, len(pages), pages_per_section):
            chunk = pages[i : i + pages_per_section]
            content = "\n\n".join(p.get("text", "") for p in chunk).strip()
            if content:
                sections.append(ParsedSection(
                    title=f"Pages {i + 1}-{min(i + pages_per_section, len(pages))}",
                    content_md=content,
                    depth=0,
                    order_index=len(sections),
                ))
        return sections
