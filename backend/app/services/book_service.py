"""Book service — orchestrates the full book lifecycle."""

import hashlib
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Book, BookSection, BookStatus, Image
from app.db.repositories.book_repo import AuthorRepository, BookRepository
from app.exceptions import ParseError, StorageError
from app.services.parser.base import BookParser, ParsedBook
from app.services.parser.epub_parser import EPUBParser
from app.services.parser.format_detector import detect_format
from app.services.parser.image_url_rewrite import from_placeholder
from app.services.parser.mobi_parser import MOBIParser
from app.services.parser.pdf_parser import PDFParser
from app.services.parser.structure_detector import StructureDetector

logger = structlog.get_logger()

PARSERS: list[BookParser] = [EPUBParser(), PDFParser(), MOBIParser()]


class BookService:
    def __init__(self, db: AsyncSession, config: Settings):
        self.db = db
        self.config = config
        self.book_repo = BookRepository(db)
        self.author_repo = AuthorRepository(db)

    async def add_book(
        self, file_path: Path, quick: bool = False, async_mode: bool = False, force: bool = False
    ) -> Book:
        """Upload, parse, and store a book."""
        file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
        # 1. Validate file
        file_data = file_path.read_bytes()
        if not self._validate_file_size(len(file_data)):
            raise StorageError(
                f"File too large: {len(file_data) / 1024 / 1024:.1f}MB "
                f"(max: {self.config.storage.max_file_size_mb}MB)"
            )

        # 2. Format detection
        file_format = detect_format(file_path)

        # 3. Duplicate detection + re-import + parse_failed retry
        file_hash = hashlib.sha256(file_data).hexdigest()
        existing = await self.book_repo.get_by_hash(file_hash)
        if existing and not force:
            raise StorageError(
                f"This book already exists (ID: {existing.id}). Use --force to re-import."
            )
        if existing and force:
            return await self._re_import_book(existing, file_data, file_path, file_format)

        # Also handle --force retry for parse_failed books
        if force:
            from sqlalchemy import select

            result = await self.db.execute(
                select(Book).where(
                    Book.status == BookStatus.PARSE_FAILED,
                    Book.title.ilike(f"%{file_path.stem}%"),
                )
            )
            failed_book = result.scalar_one_or_none()
            if failed_book:
                await self.book_repo.delete(failed_book)
                await self.db.flush()

        # 4. Parse
        parser = self._get_parser(file_format)
        parsed = await parser.parse(file_path)

        # 5. Structure detection
        detector = StructureDetector()
        parsed.sections = detector.validate_structure(parsed.sections)

        # 6. Store
        book = await self._store_book(parsed, file_data, file_hash, file_format)
        logger.info(
            "book_added", book_id=book.id, title=parsed.title, sections=len(parsed.sections)
        )

        return book

    async def delete_book(self, book_id: int) -> None:
        from app.services.tag_service import TagService

        book = await self.book_repo.get_by_id(book_id)
        if not book:
            raise StorageError(f"Book not found: {book_id}")

        tag_service = TagService(self.db)
        # Cascade taggables before the SQL delete — Taggable.taggable_id has
        # no FK (polymorphic), so ORM cascade wouldn't pick it up. Sections
        # first (they disappear with the book's cascade), then the book row.
        section_ids = [s.id for s in book.sections]
        for sid in section_ids:
            await tag_service.remove_all_for_entity("section", sid)
        await tag_service.remove_all_for_entity("book", book_id)

        await self.book_repo.delete(book)
        await self.db.commit()
        logger.info("book_deleted", book_id=book_id, cascaded_sections=len(section_ids))

    async def list_books(
        self, author: str | None = None, status: str | None = None, recent: bool = False
    ) -> list[Book]:
        status_enum = BookStatus(status) if status else None
        return await self.book_repo.list_all(
            author=author,
            status=status_enum,
            order_by_recent=recent,
        )

    async def get_book(self, book_id: int) -> Book | None:
        return await self.book_repo.get_by_id(book_id)

    async def update_book_status(self, book_id: int) -> None:
        """Derive status from default_summary_id state."""
        book = await self.book_repo.get_by_id(book_id)
        if not book:
            raise StorageError(f"Book not found: {book_id}")
        sections = book.sections or []
        all_summarized = all(s.default_summary_id is not None for s in sections)
        book_summarized = book.default_summary_id is not None
        if all_summarized and book_summarized:
            book.status = BookStatus.COMPLETED
        elif book.status not in (
            BookStatus.PARSING,
            BookStatus.PARSE_FAILED,
            BookStatus.UPLOADING,
        ):
            book.status = BookStatus.PARSED
        await self.db.flush()

    async def list_authors(self) -> list[tuple]:
        return await self.author_repo.list_with_book_counts()

    def _get_parser(self, file_format: str) -> BookParser:
        for parser in PARSERS:
            if parser.supports_format(file_format):
                return parser
        raise ParseError(f"No parser for format: {file_format}")

    def _validate_file_size(self, size_bytes: int) -> bool:
        max_bytes = self.config.storage.max_file_size_mb * 1024 * 1024
        return size_bytes <= max_bytes

    async def _store_book(
        self, parsed: ParsedBook, file_data: bytes, file_hash: str, file_format: str
    ) -> Book:
        """Store parsed book, sections, images, and authors in DB."""
        book = Book(
            title=parsed.title,
            file_data=file_data,
            file_hash=file_hash,
            file_format=file_format,
            file_size_bytes=len(file_data),
            cover_image=parsed.cover_image,
            status=BookStatus.PARSED,
            metadata_=parsed.metadata,
        )

        # Authors
        for author_name in parsed.authors:
            author = await self.author_repo.get_or_create(author_name)
            book.authors.append(author)

        self.db.add(book)
        await self.db.flush()

        # Sections + images
        for ps in parsed.sections:
            section = BookSection(
                book_id=book.id,
                title=ps.title,
                order_index=ps.order_index,
                depth=ps.depth,
                content_md=ps.content_md,
                content_token_count=len(ps.content_md) // 4,
                section_type=ps.section_type,
            )
            self.db.add(section)
            await self.db.flush()

            for pi in ps.images:
                image = Image(
                    section_id=section.id,
                    data=pi.data,
                    mime_type=pi.mime_type,
                    filename=pi.filename,
                    width=pi.width,
                    height=pi.height,
                    alt_text=pi.alt_text,
                )
                self.db.add(image)

        await self.db.flush()
        await self._substitute_image_urls(book.id)
        await self.db.commit()
        return book

    async def _re_import_book(
        self, existing: Book, file_data: bytes, file_path: Path, file_format: str
    ) -> Book:
        """Re-import: update sections in-place to preserve IDs, summaries, and evals."""
        from sqlalchemy import delete

        parser = self._get_parser(file_format)
        parsed = await parser.parse(file_path)

        # Re-fetch with eager loading so we can access sections
        existing = await self.book_repo.get_by_id(existing.id)

        # Update book data
        existing.file_data = file_data
        existing.file_size_bytes = len(file_data)
        existing.status = BookStatus.PARSED

        # Delete old search index entries (will be rebuilt)
        from app.db.models import SearchIndex

        await self.db.execute(delete(SearchIndex).where(SearchIndex.book_id == existing.id))

        # Structure detection on new parse
        detector = StructureDetector()
        parsed.sections = detector.validate_structure(parsed.sections)

        # Build lookup of existing sections by order_index
        old_sections = {s.order_index: s for s in (existing.sections or [])}
        new_order_indices = {ps.order_index for ps in parsed.sections}

        # Update existing sections in-place, add new ones
        for ps in parsed.sections:
            if ps.order_index in old_sections:
                # Update in-place — preserves section ID, summaries, evals
                section = old_sections[ps.order_index]
                section.title = ps.title
                section.depth = ps.depth
                section.content_md = ps.content_md
                section.content_token_count = len(ps.content_md) // 4
                section.section_type = ps.section_type
            else:
                # New section
                section = BookSection(
                    book_id=existing.id,
                    title=ps.title,
                    order_index=ps.order_index,
                    depth=ps.depth,
                    content_md=ps.content_md,
                    content_token_count=len(ps.content_md) // 4,
                    section_type=ps.section_type,
                )
                self.db.add(section)
            await self.db.flush()

            # Replace images (delete old, add new from fresh parse)
            await self.db.execute(delete(Image).where(Image.section_id == section.id))
            for pi in ps.images:
                image = Image(
                    section_id=section.id,
                    data=pi.data,
                    mime_type=pi.mime_type,
                    filename=pi.filename,
                    width=pi.width,
                    height=pi.height,
                    alt_text=pi.alt_text,
                )
                self.db.add(image)

        # Remove sections that no longer exist in the new parse
        # Mark eval traces as stale BEFORE deleting sections (cascade-safe)
        from sqlalchemy import update as sa_update

        from app.db.models import EvalTrace

        for order_idx, section in old_sections.items():
            if order_idx not in new_order_indices:
                await self.db.execute(
                    sa_update(EvalTrace)
                    .where(EvalTrace.section_id == section.id)
                    .values(is_stale=True)
                )
                await self.db.execute(delete(BookSection).where(BookSection.id == section.id))

        await self.db.flush()
        await self._substitute_image_urls(existing.id)
        await self.db.commit()
        logger.info("book_reimported", book_id=existing.id)
        return existing

    async def _substitute_image_urls(self, book_id: int) -> None:
        """Replace __IMG_PLACEHOLDER__:<basename>__ tokens in each section's
        content_md with /api/v1/images/{id} absolute URLs. Unknown filenames
        are left as placeholders (will 404 on fetch)."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(BookSection)
            .where(BookSection.book_id == book_id)
            .options(selectinload(BookSection.images))
        )
        for section in result.scalars().all():
            if not section.content_md or "__IMG_PLACEHOLDER__" not in section.content_md:
                continue
            fn_map: dict[str, int] = {}
            for img in section.images:
                if img.filename:
                    fn_map[img.filename.rsplit("/", 1)[-1]] = img.id
            if fn_map:
                section.content_md = from_placeholder(section.content_md, fn_map)
