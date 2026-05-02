"""Tests for PresetService."""

import pytest
import yaml

from app.exceptions import PresetError
from app.services.preset_service import PresetService


@pytest.fixture
def preset_dir(tmp_path):
    d = tmp_path / "presets"
    d.mkdir()
    (d / "test_system.yaml").write_text(
        yaml.dump(
            {
                "name": "Test System",
                "description": "A test preset",
                "system": True,
                "facets": {
                    "style": "bullet_points",
                    "audience": "practitioner",
                    "compression": "standard",
                    "content_focus": "key_concepts",
                },
            }
        )
    )
    return d


@pytest.fixture
def service(preset_dir):
    return PresetService(presets_dir=preset_dir)


def test_load_existing_preset(service):
    preset = service.load("test_system")
    assert preset.system is True
    assert preset.facets["style"] == "bullet_points"


def test_load_nonexistent_raises(service):
    with pytest.raises(PresetError, match="not found"):
        service.load("nonexistent")


def test_list_all(service):
    presets = service.list_all()
    assert len(presets) == 1
    assert presets[0].name == "Test System"


def test_create_user_preset(service, preset_dir):
    facets = {
        "style": "narrative",
        "audience": "academic",
        "compression": "detailed",
        "content_focus": "full_coverage",
    }
    preset = service.create("my_custom", "Custom preset", facets)
    assert preset.system is False
    assert (preset_dir / "my_custom.yaml").exists()


def test_create_duplicate_raises(service):
    with pytest.raises(PresetError, match="already exists"):
        service.create(
            "test_system",
            "Dup",
            {
                "style": "narrative",
                "audience": "academic",
                "compression": "detailed",
                "content_focus": "full_coverage",
            },
        )


def test_create_invalid_facet_raises(service):
    with pytest.raises(PresetError, match="Fragment not found"):
        service.create(
            "bad",
            "Bad preset",
            {
                "style": "haiku",
                "audience": "academic",
                "compression": "detailed",
                "content_focus": "full_coverage",
            },
        )


def test_delete_user_preset(service, preset_dir):
    facets = {
        "style": "narrative",
        "audience": "academic",
        "compression": "detailed",
        "content_focus": "full_coverage",
    }
    service.create("deletable", "To delete", facets)
    service.delete("deletable")
    assert not (preset_dir / "deletable.yaml").exists()


def test_delete_system_preset_raises(service):
    with pytest.raises(PresetError, match="Cannot delete system preset"):
        service.delete("test_system")


def test_resolve_facets_with_preset(service):
    name, facets = service.resolve_facets("test_system", {}, "test_system")
    assert name == "test_system"
    assert facets["style"] == "bullet_points"


def test_resolve_facets_with_overrides(service):
    overrides = {"style": "narrative", "audience": None, "compression": None, "content_focus": None}
    name, facets = service.resolve_facets("test_system", overrides, "test_system")
    assert name is None
    assert facets["style"] == "narrative"
    assert facets["audience"] == "practitioner"


def test_resolve_facets_default(service):
    name, facets = service.resolve_facets(
        None,
        {"style": None, "audience": None, "compression": None, "content_focus": None},
        "test_system",
    )
    assert name == "test_system"


def test_load_preset_with_skip_assertions():
    """Load practitioner_bullets preset and verify skip_assertions."""
    from app.services.preset_service import PRESETS_DIR

    service = PresetService(presets_dir=PRESETS_DIR)
    preset = service.load("practitioner_bullets")
    assert preset.skip_assertions == ["has_key_concepts"]


def test_load_preset_without_skip_assertions(tmp_path):
    """Preset without skip_assertions field returns empty list."""
    d = tmp_path / "presets"
    d.mkdir()
    (d / "no_skip.yaml").write_text(
        yaml.dump(
            {
                "name": "No Skip",
                "description": "No skip assertions",
                "system": False,
                "facets": {
                    "style": "bullet_points",
                    "audience": "practitioner",
                    "compression": "standard",
                    "content_focus": "key_concepts",
                },
            }
        )
    )
    service = PresetService(presets_dir=d)
    preset = service.load("no_skip")
    assert preset.skip_assertions == []


def test_invalid_assertion_name_warns(tmp_path, capsys):
    """Unknown assertion name in skip_assertions logs a warning."""
    d = tmp_path / "presets"
    d.mkdir()
    (d / "bad_skip.yaml").write_text(
        yaml.dump(
            {
                "name": "Bad Skip",
                "description": "Has unknown assertion",
                "system": False,
                "facets": {
                    "style": "bullet_points",
                    "audience": "practitioner",
                    "compression": "standard",
                    "content_focus": "key_concepts",
                },
                "skip_assertions": ["nonexistent_assertion", "has_key_concepts"],
            }
        )
    )
    service = PresetService(presets_dir=d)
    preset = service.load("bad_skip")
    assert preset.skip_assertions == ["nonexistent_assertion", "has_key_concepts"]
    captured = capsys.readouterr()
    assert "unknown_skip_assertions" in captured.out


# ---- T2: update, template viewer, malformed-YAML resilience ----


def test_update_existing_user_preset(tmp_path):
    svc = PresetService(presets_dir=tmp_path)
    svc.create(
        name="myfoo",
        description="orig",
        facets={
            "style": "bullet_points",
            "audience": "practitioner",
            "compression": "standard",
            "content_focus": "frameworks_examples",
        },
    )
    updated = svc.update(
        name="myfoo",
        description="updated",
        label="Foo Updated",
        facets={
            "style": "narrative",
            "audience": "practitioner",
            "compression": "brief",
            "content_focus": "frameworks_examples",
        },
    )
    assert updated.description == "updated"
    assert updated.facets["style"] == "narrative"
    assert updated.facets["compression"] == "brief"
    reloaded = svc.load("myfoo")
    assert reloaded.facets["style"] == "narrative"


def test_update_system_preset_raises():
    svc = PresetService()
    with pytest.raises(PresetError):
        svc.update(
            name="practitioner_bullets",
            description="hijacked",
        )


def test_get_template_source_returns_base_and_fragments():
    svc = PresetService()
    result = svc.get_template_source("practitioner_bullets")
    assert result["name"] == "practitioner_bullets"
    assert result["is_system"] is True
    assert "source" in result["base_template"]
    assert len(result["base_template"]["source"]) > 0
    assert len(result["fragments"]) == 4
    dims = {f["dimension"] for f in result["fragments"]}
    assert dims == {"style", "audience", "compression", "content_focus"}
    for frag in result["fragments"]:
        assert "source" in frag and len(frag["source"]) > 0


def test_list_all_skips_malformed_yaml_with_warnings(tmp_path):
    good = tmp_path / "good.yaml"
    good.write_text(
        "name: good\n"
        "description: ok\n"
        "system: false\n"
        "facets:\n"
        "  style: bullet_points\n"
        "  audience: practitioner\n"
        "  compression: standard\n"
        "  content_focus: frameworks_examples\n"
    )
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: valid: yaml: ::: [\n")
    svc = PresetService(presets_dir=tmp_path)
    presets, warnings = svc.list_all_with_warnings()
    assert len(presets) == 1
    assert presets[0].name == "good"
    assert len(warnings) == 1
    assert "bad.yaml" in warnings[0]["file"]
    assert warnings[0]["error"]
