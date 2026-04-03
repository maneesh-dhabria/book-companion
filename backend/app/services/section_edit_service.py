"""Section editing -- merge, split, reorder, delete (in-memory and DB-backed)."""

import re
from dataclasses import dataclass, field

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookSection
from app.db.repositories.section_repo import SectionRepository
from app.exceptions import SectionEditError

logger = structlog.get_logger()


@dataclass
class EditCommand:
    action: str  # merge, split, move, delete, undo, show, done
    indices: list[int] = field(default_factory=list)
    title: str | None = None
    split_mode: str | None = None  # "heading", "char", "paragraph"
    split_value: int | None = None
    target_after: int | None = None


def parse_command(raw: str) -> EditCommand:
    """Parse a REPL command string into an EditCommand."""
    raw = raw.strip()
    if not raw:
        raise SectionEditError("Empty command")

    parts = raw.split()
    action = parts[0].lower()

    if action == "done":
        return EditCommand(action="done")

    if action == "show":
        return EditCommand(action="show")

    if action == "undo":
        return EditCommand(action="undo")

    if action == "merge":
        if len(parts) < 2:
            raise SectionEditError("merge requires indices, e.g. merge 1,2,3")
        indices = [int(x) for x in parts[1].split(",")]
        if len(indices) < 2:
            raise SectionEditError("merge requires at least 2 indices")
        # Extract optional quoted title
        title = None
        title_match = re.search(r'"([^"]+)"', raw)
        if title_match:
            title = title_match.group(1)
        return EditCommand(action="merge", indices=indices, title=title)

    if action == "split":
        if len(parts) < 3:
            raise SectionEditError("split requires index and mode, e.g. split 3 --at-heading")
        index = int(parts[1])
        mode_flag = parts[2]
        if mode_flag == "--at-heading":
            return EditCommand(action="split", indices=[index], split_mode="heading")
        elif mode_flag == "--at-char":
            if len(parts) < 4:
                raise SectionEditError("--at-char requires a position value")
            return EditCommand(
                action="split",
                indices=[index],
                split_mode="char",
                split_value=int(parts[3]),
            )
        elif mode_flag == "--at-paragraph":
            if len(parts) < 4:
                raise SectionEditError("--at-paragraph requires a position value")
            return EditCommand(
                action="split",
                indices=[index],
                split_mode="paragraph",
                split_value=int(parts[3]),
            )
        else:
            raise SectionEditError(f"Unknown split mode: {mode_flag}")

    if action == "move":
        if len(parts) < 4 or parts[2] != "--after":
            raise SectionEditError("move requires: move <index> --after <index>")
        return EditCommand(
            action="move",
            indices=[int(parts[1])],
            target_after=int(parts[3]),
        )

    if action == "delete":
        if len(parts) < 2:
            raise SectionEditError("delete requires indices, e.g. delete 7,8")
        indices = [int(x) for x in parts[1].split(",")]
        return EditCommand(action="delete", indices=indices)

    raise SectionEditError(f"Unknown command: {action}")


@dataclass
class SectionItem:
    index: int
    id: int | None
    title: str
    content: str
    depth: int
    char_count: int
    derived_from: list[int] | None = None


class SectionEditService:
    """Merge, split, reorder, delete operations for book sections."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._repo: SectionRepository | None = None
        if session is not None:
            self._repo = SectionRepository(session)
        self._sections: list[SectionItem] = []
        self._undo_stack: list[list[SectionItem]] = []

    # --- Snapshot / undo helpers ---

    def _snapshot(self) -> list[SectionItem]:
        """Create a deep copy of current sections."""
        return [
            SectionItem(
                index=s.index,
                id=s.id,
                title=s.title,
                content=s.content,
                depth=s.depth,
                char_count=s.char_count,
                derived_from=list(s.derived_from) if s.derived_from else None,
            )
            for s in self._sections
        ]

    def _save_undo(self) -> None:
        """Push current state onto undo stack before mutation."""
        self._undo_stack.append(self._snapshot())

    def _reindex(self) -> None:
        """Sort by index and renumber 1-based."""
        self._sections.sort(key=lambda s: s.index)
        for i, s in enumerate(self._sections):
            s.index = i + 1

    def _get_by_index(self, index: int) -> SectionItem:
        """Get section by 1-based index."""
        for s in self._sections:
            if s.index == index:
                return s
        raise SectionEditError(f"No section at index {index}")

    # --- In-Memory Operations (pre-save) ---

    def init_memory_mode(self, sections: list[SectionItem]) -> None:
        """Initialize with a list of SectionItems for in-memory editing."""
        self._sections = list(sections)
        self._undo_stack = []

    def get_sections(self) -> list[SectionItem]:
        """Return current section list."""
        return list(self._sections)

    def merge(self, indices: list[int], title: str | None = None) -> SectionItem:
        """Merge sections at given indices into one."""
        if len(indices) < 2:
            raise SectionEditError("merge requires at least 2 indices")

        self._save_undo()

        to_merge = [self._get_by_index(i) for i in sorted(indices)]
        combined_content = "\n\n".join(s.content for s in to_merge)
        merged_title = title or " + ".join(s.title for s in to_merge)
        derived = [s.id for s in to_merge if s.id is not None]

        merged = SectionItem(
            index=to_merge[0].index,
            id=None,
            title=merged_title,
            content=combined_content,
            depth=to_merge[0].depth,
            char_count=len(combined_content),
            derived_from=derived if derived else None,
        )

        # Remove originals and insert merged
        self._sections = [s for s in self._sections if s.index not in indices]
        self._sections.append(merged)
        self._reindex()

        logger.info("sections_merged", indices=indices, new_title=merged_title)
        return merged

    def split_at_char(self, index: int, position: int) -> list[SectionItem]:
        """Split section at exact character position."""
        section = self._get_by_index(index)
        if position <= 0 or position >= len(section.content):
            raise SectionEditError(
                f"Split position {position} out of range for content length {len(section.content)}"
            )

        self._save_undo()

        part1_content = section.content[:position]
        part2_content = section.content[position:]

        part1 = SectionItem(
            index=section.index,
            id=None,
            title=f"{section.title} (Part 1)",
            content=part1_content,
            depth=section.depth,
            char_count=len(part1_content),
            derived_from=[section.id] if section.id else None,
        )
        part2 = SectionItem(
            index=section.index + 1,
            id=None,
            title=f"{section.title} (Part 2)",
            content=part2_content,
            depth=section.depth,
            char_count=len(part2_content),
            derived_from=[section.id] if section.id else None,
        )

        # Shift indices after split point
        for s in self._sections:
            if s.index > section.index:
                s.index += 1

        self._sections = [s for s in self._sections if s.index != index]
        self._sections.extend([part1, part2])
        self._reindex()

        logger.info("section_split_char", index=index, position=position)
        return [part1, part2]

    def split_at_paragraph(self, index: int, target_pos: int) -> list[SectionItem]:
        """Split at nearest paragraph boundary (\\n\\n) to target_pos.

        Falls back to exact char split if nearest boundary is > 500 chars away.
        """
        section = self._get_by_index(index)
        content = section.content

        # Find all paragraph boundaries
        boundaries = [m.start() for m in re.finditer(r"\n\n", content)]
        if not boundaries:
            # No paragraph boundaries, fall back to char split
            return self.split_at_char(index, target_pos)

        # Find nearest boundary to target
        nearest = min(boundaries, key=lambda b: abs(b - target_pos))

        if abs(nearest - target_pos) > 500:
            # Too far, fall back to char split
            return self.split_at_char(index, target_pos)

        # Split at the paragraph boundary (after the \n\n)
        split_pos = nearest + 2
        if split_pos <= 0 or split_pos >= len(content):
            return self.split_at_char(index, target_pos)

        return self.split_at_char(index, split_pos)

    def detect_headings(self, index: int) -> list[tuple[str, int]]:
        """Find markdown headings (## through ######) in a section's content.

        Returns list of (heading_text, char_position) tuples.
        """
        section = self._get_by_index(index)
        headings = []
        for match in re.finditer(r"^#{2,6}\s+(.+)$", section.content, re.MULTILINE):
            headings.append((match.group(1).strip(), match.start()))
        return headings

    def split_at_headings(
        self, index: int, heading_positions: list[int] | None = None
    ) -> list[SectionItem]:
        """Split section at detected headings.

        Creates an intro section (content before first heading) plus one section
        per heading. If heading_positions is provided, only split at those positions.
        """
        section = self._get_by_index(index)
        content = section.content

        headings = self.detect_headings(index)
        if not headings:
            raise SectionEditError(f"No headings found in section {index}")

        if heading_positions is not None:
            headings = [(text, pos) for text, pos in headings if pos in heading_positions]
            if not headings:
                raise SectionEditError("None of the specified heading positions match")

        self._save_undo()

        parts: list[SectionItem] = []
        base_index = section.index

        # Intro (content before first heading)
        first_pos = headings[0][1]
        intro_content = content[:first_pos].strip()
        if intro_content:
            parts.append(
                SectionItem(
                    index=base_index,
                    id=None,
                    title=f"{section.title} (Intro)",
                    content=intro_content,
                    depth=section.depth,
                    char_count=len(intro_content),
                    derived_from=[section.id] if section.id else None,
                )
            )

        # One section per heading
        for i, (heading_text, pos) in enumerate(headings):
            if i + 1 < len(headings):
                end_pos = headings[i + 1][1]
            else:
                end_pos = len(content)
            part_content = content[pos:end_pos].strip()
            parts.append(
                SectionItem(
                    index=base_index + len(parts),
                    id=None,
                    title=heading_text,
                    content=part_content,
                    depth=section.depth + 1,
                    char_count=len(part_content),
                    derived_from=[section.id] if section.id else None,
                )
            )

        if len(parts) < 2:
            # Undo was saved but nothing meaningful to split
            self._undo_stack.pop()
            raise SectionEditError("Split would result in only one section")

        # Shift existing sections to make room
        shift = len(parts) - 1
        for s in self._sections:
            if s.index > section.index:
                s.index += shift

        self._sections = [s for s in self._sections if s.index != index]
        self._sections.extend(parts)
        self._reindex()

        logger.info("section_split_headings", index=index, parts=len(parts))
        return parts

    def move(self, index: int, after: int) -> None:
        """Move section to after another section. after=0 means move to first."""
        section = self._get_by_index(index)
        if after != 0:
            self._get_by_index(after)  # Validate target exists

        self._save_undo()

        # Remove from current position
        self._sections = [s for s in self._sections if s.index != index]

        if after == 0:
            section.index = 0  # Will be renumbered to 1
        else:
            # Set index to place it right after the target
            section.index = after + 0.5  # Temporary fractional for sorting

        self._sections.append(section)
        self._reindex()

        logger.info("section_moved", index=index, after=after)

    def delete(self, indices: list[int]) -> int:
        """Delete sections at given indices. At least 1 must remain."""
        remaining = len(self._sections) - len(indices)
        if remaining < 1:
            raise SectionEditError("Cannot delete all sections; at least 1 must remain")

        # Validate all indices exist
        for i in indices:
            self._get_by_index(i)

        self._save_undo()

        self._sections = [s for s in self._sections if s.index not in indices]
        self._reindex()

        logger.info("sections_deleted", indices=indices)
        return len(indices)

    def undo(self) -> bool:
        """Revert last operation. Returns True if undo was performed."""
        if not self._undo_stack:
            return False
        self._sections = self._undo_stack.pop()
        return True

    # --- DB-Backed Operations (post-save) ---

    def _require_repo(self) -> SectionRepository:
        if self._repo is None:
            raise SectionEditError("DB operations require a session")
        return self._repo

    async def db_merge(
        self, book_id: int, section_ids: list[int], title: str | None = None
    ) -> BookSection:
        """Merge sections in DB. Creates new section, deletes originals, reindexes."""
        repo = self._require_repo()
        sections = await repo.get_by_ids(section_ids)
        if len(sections) != len(section_ids):
            raise SectionEditError("One or more section IDs not found")

        sections.sort(key=lambda s: s.order_index)
        combined_content = "\n\n".join(s.content_md or "" for s in sections)
        merged_title = title or " + ".join(s.title for s in sections)

        new_section = BookSection(
            book_id=book_id,
            title=merged_title,
            order_index=sections[0].order_index,
            depth=sections[0].depth,
            content_md=combined_content,
            content_token_count=len(combined_content) // 4,
            derived_from=[s.id for s in sections],
        )

        await repo.create(new_section)
        await repo.delete_by_ids(section_ids)
        await repo.reindex_order(book_id)

        # Clear book-level default summary since structure changed
        if self._session:
            from app.db.repositories.book_repo import BookRepository

            book_repo = BookRepository(self._session)
            await book_repo.update_default_summary(book_id, None)

        logger.info("db_sections_merged", book_id=book_id, section_ids=section_ids)
        return new_section

    async def db_split_at_char(
        self, book_id: int, section_id: int, position: int
    ) -> list[BookSection]:
        """Split a section at a character position in the DB."""
        repo = self._require_repo()
        section = await repo.get_by_id(section_id)
        if section is None:
            raise SectionEditError(f"Section {section_id} not found")

        content = section.content_md or ""
        if position <= 0 or position >= len(content):
            raise SectionEditError(
                f"Split position {position} out of range for content length {len(content)}"
            )

        part1_content = content[:position]
        part2_content = content[position:]

        part1 = BookSection(
            book_id=book_id,
            title=f"{section.title} (Part 1)",
            order_index=section.order_index,
            depth=section.depth,
            content_md=part1_content,
            content_token_count=len(part1_content) // 4,
            derived_from=[section.id],
        )
        part2 = BookSection(
            book_id=book_id,
            title=f"{section.title} (Part 2)",
            order_index=section.order_index + 1,
            depth=section.depth,
            content_md=part2_content,
            content_token_count=len(part2_content) // 4,
            derived_from=[section.id],
        )

        await repo.create(part1)
        await repo.create(part2)
        await repo.delete_by_ids([section_id])
        await repo.reindex_order(book_id)

        logger.info("db_section_split", book_id=book_id, section_id=section_id)
        return [part1, part2]

    async def db_delete(self, book_id: int, section_ids: list[int]) -> int:
        """Delete sections from DB with minimum-1 validation."""
        repo = self._require_repo()
        total = await repo.count_by_book(book_id)
        if total - len(section_ids) < 1:
            raise SectionEditError("Cannot delete all sections; at least 1 must remain")

        count = await repo.delete_by_ids(section_ids)
        await repo.reindex_order(book_id)

        logger.info("db_sections_deleted", book_id=book_id, count=count)
        return count

    async def db_move(self, book_id: int, section_id: int, after_id: int | None) -> None:
        """Move a section in DB. after_id=None means move to first position."""
        repo = self._require_repo()
        sections = await repo.get_by_book_id(book_id)

        section = None
        after_section = None
        for s in sections:
            if s.id == section_id:
                section = s
            if after_id is not None and s.id == after_id:
                after_section = s

        if section is None:
            raise SectionEditError(f"Section {section_id} not found")
        if after_id is not None and after_section is None:
            raise SectionEditError(f"Target section {after_id} not found")

        # Remove from list and reinsert
        sections = [s for s in sections if s.id != section_id]
        if after_id is None:
            sections.insert(0, section)
        else:
            insert_idx = next(
                (i + 1 for i, s in enumerate(sections) if s.id == after_id),
                len(sections),
            )
            sections.insert(insert_idx, section)

        # Update order indices
        for i, s in enumerate(sections):
            s.order_index = i

        await self._session.flush()
        logger.info(
            "db_section_moved",
            book_id=book_id,
            section_id=section_id,
            after_id=after_id,
        )
