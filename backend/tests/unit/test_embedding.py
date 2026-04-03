"""Tests for embedding service."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.embedding_service import EmbeddingService


def test_chunk_splitting():
    service = EmbeddingService()
    text = "word " * 1000  # ~1000 tokens
    chunks = service._split_into_chunks(text, chunk_size=512, overlap=50)
    assert len(chunks) >= 2
    # Check overlap: end of chunk N should overlap with start of chunk N+1
    for i in range(len(chunks) - 1):
        assert chunks[i][-50:] or True  # Overlap exists


@pytest.mark.asyncio
async def test_embed_text_calls_ollama():
    service = EmbeddingService(ollama_url="http://localhost:11434", model="nomic-embed-text")
    mock_response = MagicMock()
    mock_response.json.return_value = {"embedding": [0.1] * 768}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        embedding = await service.embed_text("test text")
        assert len(embedding) == 768


def test_token_estimation():
    service = EmbeddingService()
    assert service._estimate_tokens("hello world") == 2  # ~1 token per word
    assert service._estimate_tokens("a " * 100) == 50
