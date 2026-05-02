"""GET /api/v1/spikes/tts — newest-by-mtime glob of docs/spikes/*tts-engine-spike.md."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

router = APIRouter()


def _repo_root() -> Path:
    """Climb out of backend/ to the repo root that holds docs/."""
    return Path(__file__).resolve().parents[4]


@router.get("/api/v1/spikes/tts")
def get_tts_spike():
    spikes_dir = _repo_root() / "docs" / "spikes"
    if not spikes_dir.exists():
        return {"available": False}
    matches = list(spikes_dir.glob("*tts-engine-spike.md"))
    if not matches:
        return {"available": False}
    newest = max(matches, key=lambda p: p.stat().st_mtime)
    return {
        "available": True,
        "path": str(newest),
        "content_md": newest.read_text(),
    }
