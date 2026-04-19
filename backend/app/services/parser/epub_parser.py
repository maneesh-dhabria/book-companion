"""EPUB parser using ebooklib + markdownify."""

import re
from pathlib import Path

import ebooklib
import structlog
from ebooklib import epub
from markdownify import markdownify

from app.services.parser.base import BookParser, ParsedBook, ParsedImage, ParsedSection
from app.services.parser.image_url_rewrite import to_placeholder
from app.services.parser.section_classifier import detect_section_type

logger = structlog.get_logger()


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

    @staticmethod
    def _clean_html(html: str) -> str:
        """Strip XML processing instructions before markdownify."""
        html = re.sub(r"<\?xml[^?]*\?>", "", html)
        html = re.sub(r"<\?[^?]*\?>", "", html)
        return html

    def _merge_stub_sections(self, sections: list[ParsedSection]) -> list[ParsedSection]:
        """Merge stub sections (< 500 chars real text) into adjacent sections."""
        from app.services.parser.text_utils import text_char_count

        merge_threshold = 500
        if len(sections) <= 1:
            return sections

        merged: list[ParsedSection] = []

        i = 0
        while i < len(sections):
            section = sections[i]
            char_count = text_char_count(section.content_md)

            if char_count < merge_threshold:
                if i + 1 < len(sections):
                    # Merge forward: prepend stub content to next section
                    next_sec = sections[i + 1]
                    next_sec.content_md = section.content_md + "\n\n" + next_sec.content_md
                    next_sec.depth = min(section.depth, next_sec.depth)
                    logger.info(
                        "section_merged",
                        stub_title=section.title,
                        into_title=next_sec.title,
                        reason=f"stub_section ({char_count} chars)",
                    )
                    i += 1  # skip stub, next iteration processes the merged next_sec
                    continue
                elif merged:
                    # Last section is stub — merge backward
                    prev = merged[-1]
                    prev.content_md = prev.content_md + "\n\n" + section.content_md
                    logger.info(
                        "section_merged",
                        stub_title=section.title,
                        into_title=prev.title,
                        reason=f"stub_last ({char_count} chars)",
                    )
                    i += 1
                    continue

            merged.append(section)
            i += 1

        # Reindex
        for idx, sec in enumerate(merged):
            sec.order_index = idx

        return merged

    def _aggregate_spine_content(
        self,
        book: epub.EpubBook,
        sections: list[ParsedSection],
        content_map: dict[str, str],
        image_map: dict[str, ParsedImage],
    ) -> list[ParsedSection]:
        """Aggregate spine items between TOC entries into the preceding section.

        Many EPUBs split chapters across multiple spine items but only the first
        is referenced in the TOC. This collects orphan spine items (not referenced
        by any TOC entry) into the section that precedes them in spine order.
        """
        # Build ordered spine file list
        spine_files: list[str] = []
        for item_id, _ in book.spine:
            item = book.get_item_with_id(item_id)
            if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                spine_files.append(item.get_name())

        # Map section → spine file (from href)
        section_files: set[str] = set()
        section_file_map: dict[int, str] = {}  # section index → spine file
        for idx, sec in enumerate(sections):
            # Recover href from content_map key matching
            for fname, content in content_map.items():
                if content == sec.content_md.split("\n\n")[0] or content == sec.content_md:
                    section_file_map[idx] = fname
                    section_files.add(fname)
                    break

        # Alternative: match by looking up the original href stored during walk
        # Since we don't store it, re-derive from TOC
        toc_hrefs: set[str] = set()
        self._collect_toc_hrefs(book.toc, toc_hrefs)

        # Build mapping: spine file → section index (which section owns this file)
        file_to_section: dict[str, int] = {}
        for fname in toc_hrefs:
            # Find which section this file belongs to
            for idx, sec in enumerate(sections):
                content = content_map.get(fname, "")
                if content and content == sec.content_md:
                    file_to_section[fname] = idx
                    break

        # For each spine file NOT in toc_hrefs, assign it to the preceding TOC section
        current_section_idx: int | None = None
        for fname in spine_files:
            if fname in toc_hrefs:
                current_section_idx = file_to_section.get(fname)
            elif current_section_idx is not None:
                # This spine item is between TOC entries — append to current section
                extra_content = content_map.get(fname, "").strip()
                if extra_content:
                    sec = sections[current_section_idx]
                    sec.content_md = sec.content_md + "\n\n" + extra_content
                    # Add images from this content (match on short filename)
                    for img_name, img in image_map.items():
                        short_name = img_name.split("/")[-1]
                        if short_name in extra_content and img not in sec.images:
                            sec.images.append(img)
                    logger.info(
                        "spine_content_aggregated",
                        section_title=sec.title,
                        spine_file=fname,
                        added_chars=len(extra_content),
                    )

        # Recalculate token counts
        for sec in sections:
            sec.content_token_count = len(sec.content_md) // 4

        return sections

    def _collect_toc_hrefs(self, toc_entries: list, hrefs: set[str]) -> None:
        """Collect all file hrefs from TOC (without fragments)."""
        for entry in toc_entries:
            if isinstance(entry, tuple) and len(entry) == 2:
                section_obj, children = entry
                if hasattr(section_obj, "href"):
                    hrefs.add(section_obj.href.split("#")[0])
                self._collect_toc_hrefs(children, hrefs)
            elif isinstance(entry, epub.Link):
                hrefs.add(entry.href.split("#")[0])

    def _extract_alt_text(self, html_content: str) -> dict[str, str]:
        """Extract alt-text from img tags. Returns {filename: alt_text}."""
        import re

        alt_map: dict[str, str] = {}
        # Match img tags with src and alt attributes (in either order)
        for match in re.finditer(
            r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']+)["\']',
            html_content,
        ):
            src, alt = match.group(1), match.group(2).strip()
            if alt and alt.lower() not in ("image", "figure", "img", ""):
                filename = src.split("/")[-1]
                alt_map[filename] = alt
        # Also match alt before src
        for match in re.finditer(
            r'<img[^>]+alt=["\']([^"\']+)["\'][^>]*src=["\']([^"\']+)["\']',
            html_content,
        ):
            alt, src = match.group(1).strip(), match.group(2)
            if alt and alt.lower() not in ("image", "figure", "img", ""):
                filename = src.split("/")[-1]
                alt_map[filename] = alt
        return alt_map

    def _extract_sections(self, book: epub.EpubBook, toc: list) -> list[ParsedSection]:
        """Extract sections from TOC structure."""
        sections: list[ParsedSection] = []
        # Build a map of href -> content for document items
        content_map: dict[str, str] = {}
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            html = item.get_content().decode("utf-8", errors="replace")
            html = self._clean_html(html)
            md = markdownify(html, heading_style="ATX", strip=["script", "style"])
            content_map[item.get_name()] = to_placeholder(md.strip())

        # Build alt-text map from raw HTML
        alt_text_map: dict[str, str] = {}
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            html = item.get_content().decode("utf-8", errors="replace")
            html = self._clean_html(html)
            alt_map = self._extract_alt_text(html)
            alt_text_map.update(alt_map)

        # Build image map for later reference
        image_map: dict[str, ParsedImage] = {}
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            filename = item.get_name()
            short_name = filename.split("/")[-1]
            image_map[filename] = ParsedImage(
                data=item.get_content(),
                mime_type=item.media_type,
                filename=filename,
                alt_text=alt_text_map.get(short_name),
            )

        self._walk_toc(toc, content_map, image_map, sections, order_counter=[0], depth=0)

        # Aggregate spine content between TOC entries
        if sections:
            sections = self._aggregate_spine_content(book, sections, content_map, image_map)

        # If no TOC entries produced sections, fall back to spine order
        if not sections:
            for spine_item_id, _ in book.spine:
                item = book.get_item_with_id(spine_item_id)
                if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                    name = item.get_name()
                    content = content_map.get(name, "")
                    if content.strip():
                        spine_title = name.split("/")[-1].replace(".xhtml", "").replace(".html", "")
                        sections.append(
                            ParsedSection(
                                title=spine_title,
                                content_md=content,
                                depth=0,
                                order_index=len(sections),
                                section_type=detect_section_type(spine_title, content),
                            )
                        )

        sections = self._merge_stub_sections(sections)
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
                self._add_section(
                    section_obj, content_map, image_map, sections, order_counter, depth
                )
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

        # Find images referenced in this content (match on short filename
        # since markdownify converts EPUB paths to relative paths)
        section_images = []
        for img_name, img in image_map.items():
            short_name = img_name.split("/")[-1]
            if short_name in content:
                section_images.append(img)

        effective_title = title or f"Section {order_counter[0]}"
        sections.append(
            ParsedSection(
                title=effective_title,
                content_md=content,
                depth=depth,
                order_index=order_counter[0],
                section_type=detect_section_type(effective_title, content),
                images=section_images,
            )
        )
        order_counter[0] += 1
