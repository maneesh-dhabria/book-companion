"""GET /api/v1/summarize/presets — list available summarization YAML presets."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.preset_service import PresetService

router = APIRouter(prefix="/api/v1/summarize", tags=["summarize-presets"])

DEFAULT_PRESET_ID = "practitioner_bullets"


class PresetItem(BaseModel):
    id: str
    label: str
    description: str
    facets: dict[str, str]
    system: bool


class PresetListResponse(BaseModel):
    presets: list[PresetItem]
    default_id: str | None


def _title_case(stem: str) -> str:
    """Fallback human label derived from a file stem (``brief_notes`` → ``Brief Notes``)."""
    return " ".join(part.capitalize() for part in stem.split("_"))


@router.get("/presets", response_model=PresetListResponse)
async def list_presets() -> PresetListResponse:
    """Return every loadable preset in the summarizer prompts/presets directory.

    Malformed YAML files are logged at WARNING and skipped (see
    ``PresetService.list_all``). The client always gets a 200 even when some
    files are invalid — the response includes only the good ones.
    """
    svc = PresetService()
    items = svc.list_all()
    presets: list[PresetItem] = []
    for preset in items:
        stem = preset.file_path.stem
        # ``preset.name`` is the human-readable YAML label; fall back to the
        # file stem title-cased when the label is missing.
        label = preset.name if preset.name and preset.name != stem else _title_case(stem)
        presets.append(
            PresetItem(
                id=stem,
                label=label,
                description=preset.description,
                facets=preset.facets,
                system=preset.system,
            )
        )

    stems = {p.id for p in presets}
    if DEFAULT_PRESET_ID in stems:
        default_id: str | None = DEFAULT_PRESET_ID
    else:
        default_id = presets[0].id if presets else None

    return PresetListResponse(presets=presets, default_id=default_id)
