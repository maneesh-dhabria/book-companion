"""Preset CRUD + raw-template endpoints.

Routes:
- GET    /api/v1/summarize/presets             — list (with warnings[])
- POST   /api/v1/summarize/presets             — create user preset (201)
- PUT    /api/v1/summarize/presets/{name}      — update user preset (200)
- DELETE /api/v1/summarize/presets/{name}      — delete user preset (204)
- GET    /api/v1/summarize/presets/{name}/template — raw base + fragments
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.exceptions import PresetError
from app.services.preset_service import FACET_DIMENSIONS, PresetService

router = APIRouter(prefix="/api/v1/summarize", tags=["summarize-presets"])

DEFAULT_PRESET_ID = "practitioner_bullets"


class PresetItem(BaseModel):
    id: str
    label: str
    description: str
    facets: dict[str, str]
    system: bool


class PresetListWarning(BaseModel):
    file: str
    error: str


class PresetListResponse(BaseModel):
    presets: list[PresetItem]
    default_id: str | None
    warnings: list[PresetListWarning] = Field(default_factory=list)


class PresetUpsertRequest(BaseModel):
    name: str
    label: str
    description: str = ""
    facets: dict[str, str]


class PresetTemplateFragment(BaseModel):
    dimension: str
    value: str
    path: str
    source: str


class PresetTemplateBase(BaseModel):
    path: str
    source: str


class PresetTemplateResponse(BaseModel):
    name: str
    is_system: bool
    base_template: PresetTemplateBase
    fragments: list[PresetTemplateFragment]


def _title_case(stem: str) -> str:
    return " ".join(part.capitalize() for part in stem.split("_"))


def get_preset_service() -> PresetService:
    """FastAPI dependency — overridable in tests via ``app.dependency_overrides``."""
    return PresetService()


def _to_item(preset) -> PresetItem:
    stem = preset.file_path.stem
    label = preset.name if preset.name and preset.name != stem else _title_case(stem)
    return PresetItem(
        id=stem,
        label=label,
        description=preset.description,
        facets=preset.facets,
        system=preset.system,
    )


@router.get("/presets", response_model=PresetListResponse)
async def list_presets(
    svc: PresetService = Depends(get_preset_service),
) -> PresetListResponse:
    items, warnings = svc.list_all_with_warnings()
    presets = [_to_item(p) for p in items]
    stems = {p.id for p in presets}
    default_id = (
        DEFAULT_PRESET_ID
        if DEFAULT_PRESET_ID in stems
        else (presets[0].id if presets else None)
    )
    return PresetListResponse(
        presets=presets,
        default_id=default_id,
        warnings=[PresetListWarning(**w) for w in warnings],
    )


def _validate_facets_or_422(facets: dict[str, str]) -> None:
    for dim, valid in FACET_DIMENSIONS.items():
        if dim not in facets:
            raise HTTPException(status_code=422, detail=f"Missing facet: {dim}")
        if facets[dim] not in valid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid value for {dim}: {facets[dim]}",
            )


@router.post("/presets", response_model=PresetItem, status_code=201)
async def create_preset(
    payload: PresetUpsertRequest,
    svc: PresetService = Depends(get_preset_service),
) -> PresetItem:
    # Slug check (mirrors PresetService.create regex)
    import re

    if not re.match(r"^[a-z][a-z0-9_]*$", payload.name):
        raise HTTPException(
            status_code=422,
            detail="Use lowercase letters, digits, and underscores (must start with a letter).",
        )
    _validate_facets_or_422(payload.facets)

    # Collision: any existing preset (system or user) with same stem
    if (svc.presets_dir / f"{payload.name}.yaml").exists():
        raise HTTPException(
            status_code=409,
            detail=f'A preset named "{payload.name}" already exists.',
        )
    try:
        preset = svc.create(
            name=payload.name,
            description=payload.description,
            facets=payload.facets,
        )
    except PresetError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    # Optional label override: rewrite YAML name field if provided
    if payload.label:
        svc.update(name=payload.name, label=payload.label)
        preset = svc.load(payload.name)
    return _to_item(preset)


@router.put("/presets/{name}", response_model=PresetItem)
async def update_preset(
    name: str,
    payload: PresetUpsertRequest,
    svc: PresetService = Depends(get_preset_service),
) -> PresetItem:
    path = svc.presets_dir / f"{name}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f'Preset "{name}" not found.')
    _validate_facets_or_422(payload.facets)
    try:
        preset = svc.update(
            name=name,
            description=payload.description,
            label=payload.label,
            facets=payload.facets,
        )
    except PresetError as e:
        msg = str(e)
        status = 403 if "system" in msg.lower() else 422
        raise HTTPException(status_code=status, detail=msg) from e
    return _to_item(preset)


@router.delete("/presets/{name}", status_code=204)
async def delete_preset(
    name: str,
    svc: PresetService = Depends(get_preset_service),
) -> Response:
    path = svc.presets_dir / f"{name}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f'Preset "{name}" not found.')
    try:
        svc.delete(name)
    except PresetError as e:
        msg = str(e)
        status = 403 if "system" in msg.lower() else 422
        raise HTTPException(status_code=status, detail=msg) from e
    return Response(status_code=204)


@router.get("/presets/{name}/template", response_model=PresetTemplateResponse)
async def get_preset_template(
    name: str,
    svc: PresetService = Depends(get_preset_service),
) -> PresetTemplateResponse:
    path = svc.presets_dir / f"{name}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f'Preset "{name}" not found.')
    data = svc.get_template_source(name)
    return PresetTemplateResponse(
        name=data["name"],
        is_system=data["is_system"],
        base_template=PresetTemplateBase(**data["base_template"]),
        fragments=[PresetTemplateFragment(**f) for f in data["fragments"]],
    )
