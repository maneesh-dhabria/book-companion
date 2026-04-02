"""Tests for book service orchestration."""

import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.book_service import BookService
from app.services.parser.base import ParsedBook, ParsedSection


@pytest.mark.asyncio
async def test_add_book_computes_hash():
    mock_session = AsyncMock()
    mock_parser = AsyncMock()
    mock_parser.parse.return_value = ParsedBook(
        title="Test", authors=["Author"], sections=[
            ParsedSection(title="Ch1", content_md="Content", depth=0, order_index=0),
        ], cover_image=None, metadata={},
    )
    mock_config = MagicMock()
    mock_config.storage.max_file_size_mb = 200

    service = BookService(
        db=mock_session, config=mock_config
    )

    file_data = b"fake epub content"
    expected_hash = hashlib.sha256(file_data).hexdigest()

    with patch.object(service, "_get_parser", return_value=mock_parser):
        with patch.object(service, "_store_book", new_callable=AsyncMock) as mock_store:
            mock_store.return_value = MagicMock(id=1)
            with patch("builtins.open", MagicMock()):
                with patch("pathlib.Path.read_bytes", return_value=file_data):
                    with patch("pathlib.Path.stat", return_value=MagicMock(st_size=100)):
                        result_hash = hashlib.sha256(file_data).hexdigest()
                        assert result_hash == expected_hash


@pytest.mark.asyncio
async def test_file_size_validation():
    mock_session = AsyncMock()
    mock_config = MagicMock()
    mock_config.storage.max_file_size_mb = 1  # 1MB limit

    service = BookService(db=mock_session, config=mock_config)
    # File larger than limit should raise
    assert service._validate_file_size(2 * 1024 * 1024) is False  # 2MB
    assert service._validate_file_size(512 * 1024) is True  # 512KB
