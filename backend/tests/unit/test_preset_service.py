"""Tests for PresetService."""

import pytest
import yaml
from pathlib import Path
from app.services.preset_service import PresetService, FACET_DIMENSIONS
from app.exceptions import PresetError


@pytest.fixture
def preset_dir(tmp_path):
    d = tmp_path / "presets"
    d.mkdir()
    (d / "test_system.yaml").write_text(yaml.dump({
        "name": "Test System", "description": "A test preset",
        "system": True,
        "facets": {"style": "bullet_points", "audience": "practitioner",
                   "compression": "standard", "content_focus": "key_concepts"},
    }))
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
    facets = {"style": "narrative", "audience": "academic", "compression": "detailed", "content_focus": "full_coverage"}
    preset = service.create("my_custom", "Custom preset", facets)
    assert preset.system is False
    assert (preset_dir / "my_custom.yaml").exists()


def test_create_duplicate_raises(service):
    with pytest.raises(PresetError, match="already exists"):
        service.create("test_system", "Dup", {"style": "narrative", "audience": "academic", "compression": "detailed", "content_focus": "full_coverage"})


def test_create_invalid_facet_raises(service):
    with pytest.raises(PresetError, match="Fragment not found"):
        service.create("bad", "Bad preset", {"style": "haiku", "audience": "academic", "compression": "detailed", "content_focus": "full_coverage"})


def test_delete_user_preset(service, preset_dir):
    facets = {"style": "narrative", "audience": "academic", "compression": "detailed", "content_focus": "full_coverage"}
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
    name, facets = service.resolve_facets(None, {"style": None, "audience": None, "compression": None, "content_focus": None}, "test_system")
    assert name == "test_system"
