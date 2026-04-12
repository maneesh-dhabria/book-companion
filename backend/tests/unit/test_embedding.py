"""Tests for embedding service (fastembed-based)."""

import struct
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.embedding_service import (
    EMBEDDING_DIM,
    EmbeddingService,
    deserialize_embedding,
    serialize_embedding,
)


def test_chunk_splitting():
    service = EmbeddingService()
    text = "word " * 1000
    chunks = service._split_into_chunks(text, chunk_size=512, overlap=50)
    assert len(chunks) >= 2
    assert len(chunks[0].split()) == 512


@pytest.fixture
def mock_fastembed():
    with patch("fastembed.TextEmbedding") as mock_cls:
        mock_model = MagicMock()
        mock_model.embed.return_value = [np.zeros(EMBEDDING_DIM)]
        mock_cls.return_value = mock_model
        yield mock_model


@pytest.mark.asyncio
async def test_embed_text_returns_correct_dim(mock_fastembed):
    service = EmbeddingService(cache_dir="/tmp/test-models")
    result = await service.embed_text("test query")
    assert len(result) == EMBEDDING_DIM
    mock_fastembed.embed.assert_called_once()


@pytest.mark.asyncio
async def test_embed_text_returns_list_of_floats(mock_fastembed):
    service = EmbeddingService(cache_dir="/tmp/test-models")
    result = await service.embed_text("test")
    assert isinstance(result, list)
    assert all(isinstance(x, float) for x in result)


def test_no_ollama_url_attribute():
    service = EmbeddingService()
    assert not hasattr(service, "ollama_url")


def test_serialize_deserialize_roundtrip():
    original = [0.1, 0.2, 0.3, -0.5]
    blob = serialize_embedding(original)
    assert isinstance(blob, bytes)
    assert len(blob) == len(original) * 4
    restored = deserialize_embedding(blob)
    for a, b in zip(original, restored):
        assert abs(a - b) < 1e-6


def test_serialize_384_dim():
    emb = [float(i) / 384 for i in range(EMBEDDING_DIM)]
    blob = serialize_embedding(emb)
    assert len(blob) == EMBEDDING_DIM * 4
    restored = deserialize_embedding(blob)
    assert len(restored) == EMBEDDING_DIM
