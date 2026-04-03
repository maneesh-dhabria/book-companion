"""Tests for faceted prompt fragment system."""

from pathlib import Path

import jinja2
import pytest
import yaml

PROMPTS_DIR = Path(__file__).parents[2] / "app" / "services" / "summarizer" / "prompts"
PRESETS_DIR = PROMPTS_DIR / "presets"

VALID_FACETS = {
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

SYSTEM_PRESETS = [
    "practitioner_bullets",
    "academic_detailed",
    "executive_brief",
    "study_guide",
    "tweet_thread",
]


def _load_preset(name: str) -> dict:
    path = PRESETS_DIR / f"{name}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def _create_jinja_env() -> jinja2.Environment:
    return jinja2.Environment(loader=jinja2.FileSystemLoader(str(PROMPTS_DIR)))


@pytest.mark.parametrize("dimension,values", VALID_FACETS.items())
def test_all_fragment_files_exist(dimension, values):
    for value in values:
        path = PROMPTS_DIR / "fragments" / dimension / f"{value}.txt"
        assert path.exists(), f"Missing fragment: {path}"
        content = path.read_text()
        assert len(content.strip()) > 0, f"Empty fragment: {path}"


@pytest.mark.parametrize("preset_name", SYSTEM_PRESETS)
def test_system_preset_has_valid_fields(preset_name):
    preset = _load_preset(preset_name)
    assert "name" in preset
    assert "description" in preset
    assert preset.get("system") is True
    facets = preset["facets"]
    for dim, valid_values in VALID_FACETS.items():
        assert dim in facets, f"Preset {preset_name} missing facet: {dim}"
        assert facets[dim] in valid_values, f"Preset {preset_name} has invalid {dim}: {facets[dim]}"


@pytest.mark.parametrize("preset_name", SYSTEM_PRESETS)
def test_system_preset_renders(preset_name):
    preset = _load_preset(preset_name)
    env = _create_jinja_env()
    template = env.get_template("base/summarize_section.txt")
    result = template.render(
        book_title="Test Book",
        author="Test Author",
        section_title="Test Section",
        section_content="Sample content.",
        cumulative_context="",
        image_captions=[],
        **preset["facets"],
    )
    assert len(result) > 0
    assert "{{" not in result
    assert "Test Book" in result


@pytest.mark.parametrize("preset_name", SYSTEM_PRESETS)
def test_book_template_renders(preset_name):
    preset = _load_preset(preset_name)
    env = _create_jinja_env()
    template = env.get_template("base/summarize_book.txt")
    result = template.render(
        book_title="Test Book",
        author="Test Author",
        section_count=3,
        sections=[
            {"title": "Ch 1", "summary": "S1"},
            {"title": "Ch 2", "summary": "S2"},
            {"title": "Ch 3", "summary": "S3"},
        ],
        **preset["facets"],
    )
    assert len(result) > 0
    assert "{{" not in result


def test_invalid_fragment_raises():
    env = _create_jinja_env()
    template = env.get_template("base/summarize_section.txt")
    with pytest.raises(jinja2.TemplateNotFound):
        template.render(
            book_title="Test",
            author="Author",
            section_title="S",
            section_content="C",
            cumulative_context="",
            image_captions=[],
            style="nonexistent_style",
            audience="practitioner",
            compression="standard",
            content_focus="key_concepts",
        )
