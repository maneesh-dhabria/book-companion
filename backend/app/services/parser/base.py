"""Base parser interfaces and data classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedImage:
    data: bytes
    mime_type: str
    filename: str | None = None
    width: int | None = None
    height: int | None = None
    alt_text: str | None = None


@dataclass
class ParsedSection:
    title: str
    content_md: str
    depth: int
    order_index: int
    images: list[ParsedImage] = field(default_factory=list)


@dataclass
class ParsedBook:
    title: str
    authors: list[str]
    sections: list[ParsedSection]
    cover_image: bytes | None = None
    metadata: dict = field(default_factory=dict)


class BookParser(ABC):
    @abstractmethod
    async def parse(self, file_path: Path) -> ParsedBook: ...

    @abstractmethod
    def supports_format(self, file_format: str) -> bool: ...
