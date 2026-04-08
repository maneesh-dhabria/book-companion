"""Preset management — load, validate, create, delete YAML preset files."""

import re
from dataclasses import dataclass
from pathlib import Path

import structlog
import yaml

from app.exceptions import PresetError

logger = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent / "summarizer" / "prompts"
PRESETS_DIR = PROMPTS_DIR / "presets"
FRAGMENTS_DIR = PROMPTS_DIR / "fragments"

KNOWN_ASSERTIONS = {
    "no_hallucinated_facts",
    "no_contradictions",
    "accurate_quotes",
    "cross_summary_consistency",
    "covers_main_argument",
    "covers_key_concepts",
    "covers_frameworks",
    "covers_examples",
    "standalone_readable",
    "logical_flow",
    "no_dangling_references",
    "not_generic",
    "preserves_author_terminology",
    "has_key_concepts",
    "reasonable_length",
    "image_refs_preserved",
}

FACET_DIMENSIONS = {
    "style": [
        "bullet_points",
        "narrative",
        "podcast_dialogue",
        "cornell_notes",
        "mind_map_outline",
        "tweet_thread",
    ],
    "audience": ["practitioner", "academic", "executive"],
    "compression": ["brief", "standard", "detailed"],
    "content_focus": ["key_concepts", "frameworks_examples", "full_coverage"],
}


@dataclass
class Preset:
    name: str
    description: str
    system: bool
    facets: dict[str, str]
    file_path: Path
    skip_assertions: list[str] = None

    def __post_init__(self):
        if self.skip_assertions is None:
            self.skip_assertions = []


class PresetService:
    def __init__(self, presets_dir: Path | None = None):
        self.presets_dir = presets_dir or PRESETS_DIR
        self.fragments_dir = FRAGMENTS_DIR

    def load(self, name: str) -> Preset:
        path = self.presets_dir / f"{name}.yaml"
        if not path.exists():
            available = ", ".join(self.list_names())
            raise PresetError(f'Preset "{name}" not found. Available presets: {available}')
        return self._parse_file(path)

    def list_all(self) -> list[Preset]:
        presets = []
        for path in sorted(self.presets_dir.glob("*.yaml")):
            try:
                presets.append(self._parse_file(path))
            except Exception as e:
                logger.warning("preset_load_failed", path=str(path), error=str(e))
        presets.sort(key=lambda p: (not p.system, p.name))
        return presets

    def list_names(self) -> list[str]:
        return [p.stem for p in sorted(self.presets_dir.glob("*.yaml"))]

    def create(self, name: str, description: str, facets: dict[str, str]) -> Preset:
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            raise PresetError(
                f'Invalid preset name "{name}". Use lowercase letters, numbers, and underscores.'
            )
        path = self.presets_dir / f"{name}.yaml"
        if path.exists():
            raise PresetError(
                f'Preset "{name}" already exists. Use a different name or '
                f"delete it first with: bookcompanion preset delete {name}"
            )
        self._validate_facets(facets)
        data = {
            "name": name.replace("_", " ").title(),
            "description": description,
            "system": False,
            "facets": facets,
        }
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
        return self._parse_file(path)

    def delete(self, name: str) -> None:
        preset = self.load(name)
        if preset.system:
            raise PresetError(f'Cannot delete system preset "{name}".')
        preset.file_path.unlink()

    def resolve_facets(
        self, preset_name: str | None, overrides: dict[str, str | None], default_preset: str
    ) -> tuple[str | None, dict[str, str]]:
        if preset_name:
            preset = self.load(preset_name)
            facets = dict(preset.facets)
        elif any(v is not None for v in overrides.values()):
            preset = self.load(default_preset)
            preset_name = None
            facets = dict(preset.facets)
        else:
            preset = self.load(default_preset)
            preset_name = default_preset
            facets = dict(preset.facets)

        for key, value in overrides.items():
            if value is not None:
                facets[key] = value
                preset_name = None

        self._validate_facets(facets)
        return preset_name, facets

    def _validate_facets(self, facets: dict[str, str]) -> None:
        for dim, valid_values in FACET_DIMENSIONS.items():
            if dim not in facets:
                raise PresetError(f"Missing facet: {dim}")
            if facets[dim] not in valid_values:
                available = ", ".join(valid_values)
                raise PresetError(
                    f"Fragment not found: fragments/{dim}/{facets[dim]}.txt. "
                    f"Available {dim}s: {available}"
                )

    def _parse_file(self, path: Path) -> Preset:
        with open(path) as f:
            data = yaml.safe_load(f)
        if not data or "facets" not in data:
            raise PresetError(f"Invalid preset file: {path}")

        skip_assertions = data.get("skip_assertions", [])
        if not isinstance(skip_assertions, list):
            skip_assertions = []

        # Validate assertion names
        unknown = set(skip_assertions) - KNOWN_ASSERTIONS
        if unknown:
            logger.warning(
                "unknown_skip_assertions",
                preset=path.stem,
                unknown=sorted(unknown),
            )

        if len(skip_assertions) > 12:
            logger.warning(
                "too_many_skip_assertions",
                preset=path.stem,
                count=len(skip_assertions),
            )

        return Preset(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            system=data.get("system", False),
            facets=data["facets"],
            file_path=path,
            skip_assertions=skip_assertions,
        )
