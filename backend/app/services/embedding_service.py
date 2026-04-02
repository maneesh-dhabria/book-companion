"""Embedding service using local Ollama."""

import asyncio

import httpx

from app.exceptions import EmbeddingError


class EmbeddingService:
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        max_concurrent: int = 5,
    ):
        self.ollama_url = ollama_url
        self.model = model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text via Ollama API."""
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.post(
                        f"{self.ollama_url}/api/embeddings",
                        json={"model": self.model, "prompt": text},
                    )
                    response.raise_for_status()
                    return response.json()["embedding"]
                except httpx.HTTPError as e:
                    raise EmbeddingError(f"Ollama embedding failed: {e}")

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

    def _split_into_chunks(
        self, text: str, chunk_size: int = 512, overlap: int = 50
    ) -> list[str]:
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

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation: ~1 token per 4 chars (spec requirement)."""
        return len(text) // 4
