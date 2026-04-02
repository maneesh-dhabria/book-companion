"""EPUB parser using ebooklib + markdownify."""

from pathlib import Path

import ebooklib
from ebooklib import epub
from markdownify import markdownify

from app.services.parser.base import BookParser, ParsedBook, ParsedImage, ParsedSection


class EPUBParser(BookParser):
    def supports_format(self, file_format: str) -> bool:
        return file_format == "epub"

    async def parse(self, file_path: Path) -> ParsedBook:
        book = epub.read_epub(str(file_path))

        title = book.get_metadata("DC", "title")
        title_str = title[0][0] if title else file_path.stem

        creators = book.get_metadata("DC", "creator")
        authors = [c[0] for c in creators] if creators else ["Unknown"]

        # Extract cover image
        cover_image = self._extract_cover(book)

        # Extract TOC and map to sections
        toc = book.toc
        sections = self._extract_sections(book, toc)

        # Build metadata dict
        metadata = {}
        for ns in ["DC", "OPF"]:
            for key in ["language", "publisher", "date", "description", "subject"]:
                val = book.get_metadata(ns, key)
                if val:
                    metadata[key] = val[0][0] if isinstance(val[0], tuple) else val[0]

        return ParsedBook(
            title=title_str,
            authors=authors,
            sections=sections,
            cover_image=cover_image,
            metadata=metadata,
        )

    def _extract_cover(self, book: epub.EpubBook) -> bytes | None:
        # Try to find cover image from metadata
        cover_id = None
        for meta in book.get_metadata("OPF", "cover") or []:
            if meta and meta[1]:
                cover_id = meta[1].get("content")
        if cover_id:
            item = book.get_item_with_id(cover_id)
            if item:
                return item.get_content()

        # Fallback: look for items with 'cover' in filename
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            if "cover" in (item.get_name() or "").lower():
                return item.get_content()
        return None

    def _extract_sections(
        self, book: epub.EpubBook, toc: list
    ) -> list[ParsedSection]:
        """Extract sections from TOC structure."""
        sections: list[ParsedSection] = []
        # Build a map of href -> content for document items
        content_map: dict[str, str] = {}
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            html = item.get_content().decode("utf-8", errors="replace")
            md = markdownify(html, heading_style="ATX", strip=["script", "style"])
            content_map[item.get_name()] = md.strip()

        # Build image map for later reference
        image_map: dict[str, ParsedImage] = {}
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            image_map[item.get_name()] = ParsedImage(
                data=item.get_content(),
                mime_type=item.media_type,
                filename=item.get_name(),
            )

        self._walk_toc(toc, content_map, image_map, sections, order_counter=[0], depth=0)

        # If no TOC entries produced sections, fall back to spine order
        if not sections:
            for spine_item_id, _ in book.spine:
                item = book.get_item_with_id(spine_item_id)
                if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                    name = item.get_name()
                    content = content_map.get(name, "")
                    if content.strip():
                        sections.append(ParsedSection(
                            title=name.split("/")[-1].replace(".xhtml", "").replace(".html", ""),
                            content_md=content,
                            depth=0,
                            order_index=len(sections),
                        ))

        return sections

    def _walk_toc(
        self,
        toc_entries: list,
        content_map: dict[str, str],
        image_map: dict[str, ParsedImage],
        sections: list[ParsedSection],
        order_counter: list[int],
        depth: int,
    ) -> None:
        """Recursively walk TOC to build section list."""
        for entry in toc_entries:
            if isinstance(entry, tuple) and len(entry) == 2:
                # Nested: (Section, [children])
                section_obj, children = entry
                self._add_section(section_obj, content_map, image_map, sections, order_counter, depth)
                self._walk_toc(children, content_map, image_map, sections, order_counter, depth + 1)
            elif isinstance(entry, epub.Link):
                self._add_section(entry, content_map, image_map, sections, order_counter, depth)
            elif isinstance(entry, epub.Section):
                # Section header without direct content
                pass

    def _add_section(
        self,
        entry,
        content_map: dict[str, str],
        image_map: dict[str, ParsedImage],
        sections: list[ParsedSection],
        order_counter: list[int],
        depth: int,
    ) -> None:
        href = entry.href.split("#")[0] if hasattr(entry, "href") else ""
        title = entry.title if hasattr(entry, "title") else str(entry)
        content = content_map.get(href, "")

        if not content.strip():
            return

        # Find images referenced in this content
        section_images = []
        for img_name, img in image_map.items():
            if img_name in content:
                section_images.append(img)

        sections.append(ParsedSection(
            title=title or f"Section {order_counter[0]}",
            content_md=content,
            depth=depth,
            order_index=order_counter[0],
            images=section_images,
        ))
        order_counter[0] += 1
