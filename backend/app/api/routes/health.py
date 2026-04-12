"""Health check endpoint."""

from fastapi import APIRouter

from app.services.summarizer import detect_llm_provider

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health():
    """Health check with LLM provider status."""
    provider = detect_llm_provider()
    return {
        "status": "ok",
        "llm_provider": provider,
        "llm_available": provider is not None,
        "database": "sqlite",
        "embedding_model": "all-MiniLM-L6-v2",
    }
