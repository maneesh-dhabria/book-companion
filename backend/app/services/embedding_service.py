"""Embedding service using local fastembed (in-process, no external server)."""

import asyncio
import struct

from app.exceptions import EmbeddingError

EMBEDDING_DIM = 384
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def serialize_embedding(embedding: list[float]) -> bytes:
    """Serialize a float list to compact binary (little-endian float32)."""
    return struct.pack(f"<{len(embedding)}f", *embedding)


def deserialize_embedding(data: bytes) -> list[float]:
    """Deserialize binary embedding back to float list."""
    count = len(data) // 4
    return list(struct.unpack(f"<{count}f", data))


class EmbeddingService:
    def __init__(
        self,
        cache_dir: str | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        max_concurrent: int = 5,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._cache_dir = cache_dir
        self._model = None  # Lazy init

    def _get_model(self):
        """Lazy-initialize the fastembed model (downloads on first use)."""
        if self._model is None:
            from fastembed import TextEmbedding

            kwargs = {"model_name": MODEL_NAME}
            if self._cache_dir:
                kwargs["cache_dir"] = self._cache_dir
            self._model = TextEmbedding(**kwargs)
        return self._model

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text via fastembed."""
        async with self._semaphore:
            try:
                model = self._get_model()
                embeddings = await asyncio.to_thread(
                    lambda: list(model.embed([text]))
                )
                return embeddings[0].tolist()
            except Exception as e:
                raise EmbeddingError(f"Embedding failed: {e}") from e

    async def chunk_and_embed(
        self, text: str, chunk_size: int | None = None, overlap: int | None = None
    ) -> list[tuple[str, list[float]]]:
        """Split text into overlapping chunks and embed each."""
        chunks = self._split_into_chunks(
            text,
            chunk_size=chunk_size or self.chunk_size,
            overlap=overlap or self.chunk_overlap,
        )
        embeddings = await asyncio.gather(
            *[self.embed_text(chunk) for chunk in chunks],
            return_exceptions=True,
        )
        results = []
        for chunk, emb in zip(chunks, embeddings):
            if isinstance(emb, Exception):
                continue  # Skip failed embeddings
            results.append((chunk, emb))
        return results

    def _split_into_chunks(self, text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
        """Split text into overlapping chunks by estimated token count."""
        words = text.split()
        if not words:
            return []

        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk = " ".join(words[start:end])
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap
            if start >= len(words):
                break
        return chunks
