"""Book and Author repository — data access layer."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Author, Book, BookAuthor, BookSection, BookStatus


class BookRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, book: Book) -> Book:
        self.session.add(book)
        await self.session.flush()
        return book

    async def get_by_id(self, book_id: int) -> Book | None:
        result = await self.session.execute(
            select(Book)
            .options(
                selectinload(Book.authors),
                selectinload(Book.sections).selectinload(BookSection.images),
            )
            .where(Book.id == book_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, file_hash: str) -> Book | None:
        result = await self.session.execute(select(Book).where(Book.file_hash == file_hash))
        return result.scalar_one_or_none()

    async def list_all(
        self,
        author: str | None = None,
        status: BookStatus | None = None,
        order_by_recent: bool = False,
    ) -> list[Book]:
        query = select(Book).options(selectinload(Book.authors), selectinload(Book.sections))
        if author:
            query = query.join(Book.authors).where(Author.name.ilike(f"%{author}%"))
        if status:
            query = query.where(Book.status == status)
        if order_by_recent:
            query = query.order_by(Book.updated_at.desc())
        else:
            query = query.order_by(Book.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().unique().all())

    async def delete(self, book: Book) -> None:
        await self.session.delete(book)
        await self.session.flush()

    async def update_status(self, book_id: int, status: BookStatus) -> None:
        book = await self.get_by_id(book_id)
        if book:
            book.status = status
            await self.session.flush()

    async def update_default_summary(self, book_id: int, summary_id: int | None) -> None:
        book = await self.get_by_id(book_id)
        if book:
            book.default_summary_id = summary_id
            await self.session.flush()


class AuthorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, name: str) -> Author:
        result = await self.session.execute(select(Author).where(Author.name == name))
        author = result.scalar_one_or_none()
        if not author:
            author = Author(name=name)
            self.session.add(author)
            await self.session.flush()
        return author

    async def list_with_book_counts(self) -> list[tuple[Author, int]]:
        result = await self.session.execute(
            select(Author, func.count(BookAuthor.book_id))
            .outerjoin(BookAuthor)
            .group_by(Author.id)
            .order_by(Author.name)
        )
        return list(result.all())
