"""Unit tests for SettingsService."""

import pytest
import yaml
from pydantic import ValidationError

from app.config import Settings
from app.services.settings_service import SettingsService


def test_get_safe_settings_excludes_password():
    svc = SettingsService(settings=Settings())
    safe = svc.get_safe_settings()
    assert "password" not in str(safe).lower() or "***" in str(safe)
    assert "network" in safe
    assert "llm" in safe


def test_get_safe_settings_masks_access_token(tmp_path):
    config_path = tmp_path / "config.yaml"
    settings = Settings()
    object.__setattr__(settings.network, "access_token", "super-secret-token")
    svc = SettingsService(settings=settings, config_path=config_path)
    safe = svc.get_safe_settings()
    assert "super-secret-token" not in str(safe)
    assert safe["network"]["access_token"] == "***"


def test_update_settings_writes_yaml(tmp_path):
    config_path = tmp_path / "config.yaml"
    svc = SettingsService(settings=Settings(), config_path=config_path)
    svc.update_settings({"network": {"allow_lan": True}})
    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert data["network"]["allow_lan"] is True


def test_update_settings_persists_on_re_read(tmp_path):
    config_path = tmp_path / "config.yaml"
    svc = SettingsService(settings=Settings(), config_path=config_path)
    svc.update_settings({"web": {"show_cost_estimates": True}})
    with open(config_path) as f:
        persisted = yaml.safe_load(f)
    assert persisted["web"]["show_cost_estimates"] is True


def test_partial_update_does_not_wipe_other_fields(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"network": {"allow_lan": False, "host": "127.0.0.1"}}))
    svc = SettingsService(settings=Settings(), config_path=config_path)
    svc.update_settings({"network": {"allow_lan": True}})
    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert data["network"]["allow_lan"] is True
    assert data["network"]["host"] == "127.0.0.1"


def test_update_settings_updates_in_memory(tmp_path):
    config_path = tmp_path / "config.yaml"
    settings = Settings()
    svc = SettingsService(settings=settings, config_path=config_path)
    svc.update_settings({"network": {"allow_lan": True}})
    assert settings.network.allow_lan is True


def test_update_settings_invalidates_preflight_cache(tmp_path):
    """FR-B08a: settings PATCH must clear the in-process preflight cache."""
    from app.services.llm_preflight import (
        PreflightResult,
        get_preflight_service,
    )

    config_path = tmp_path / "config.yaml"
    svc = SettingsService(settings=Settings(), config_path=config_path)
    preflight = get_preflight_service()
    preflight._cache["claude"] = (
        9999999999.0,
        PreflightResult(
            ok=True,
            provider="claude",
            binary="claude",
            binary_resolved=True,
            version="2.1.0",
            version_ok=True,
            reason=None,
        ),
    )
    svc.update_settings({"llm": {"model": "haiku"}})
    assert preflight._cache == {}


def test_get_safe_settings_includes_config_dir(tmp_path):
    """FR-B01a: config_dir surfaces in API as a string (or None); cli_command does not."""
    from pathlib import Path
    s = Settings()
    object.__setattr__(s.llm, "config_dir", Path("/tmp/claude-personal"))
    svc = SettingsService(settings=s, config_path=tmp_path / "settings.yaml")
    data = svc.get_safe_settings()
    assert data["llm"]["config_dir"] == "/tmp/claude-personal"
    assert "cli_command" not in data["llm"]


def test_get_safe_settings_config_dir_default_none(tmp_path):
    s = Settings()
    object.__setattr__(s.llm, "config_dir", None)
    svc = SettingsService(settings=s, config_path=tmp_path / "settings.yaml")
    data = svc.get_safe_settings()
    assert data["llm"]["config_dir"] is None


def test_update_settings_round_trips_config_dir(tmp_path):
    """FR-B01a: PATCH path persists config_dir and surfaces it back."""
    config_path = tmp_path / "settings.yaml"
    settings = Settings()
    svc = SettingsService(settings=settings, config_path=config_path)
    svc.update_settings({"llm": {"config_dir": "/tmp/claude-personal"}})
    assert str(settings.llm.config_dir) == "/tmp/claude-personal"
    with open(config_path) as f:
        assert yaml.safe_load(f)["llm"]["config_dir"] == "/tmp/claude-personal"


def test_update_settings_rejects_unknown_key(tmp_path):
    """FR-F1.4 / D17: unknown nested key raises ValidationError; YAML untouched."""
    cfg = tmp_path / "settings.yaml"
    svc = SettingsService(settings=Settings(), config_path=cfg)
    with pytest.raises(ValidationError):
        svc.update_settings({"llm": {"foo": "bar"}})
    assert not cfg.exists()


def test_update_settings_partial_validity_rejects_all(tmp_path):
    """FR-F1.4 / D17: partial-bad PATCH rejects whole body; YAML on disk unchanged."""
    cfg = tmp_path / "settings.yaml"
    cfg.write_text("llm:\n  config_dir: /tmp/prior\n")
    svc = SettingsService(settings=Settings(), config_path=cfg)
    with pytest.raises(ValidationError):
        svc.update_settings({"llm": {"config_dir": "/tmp/new", "timeout_seconds": "bad"}})
    assert yaml.safe_load(cfg.read_text())["llm"]["config_dir"] == "/tmp/prior"


# --- T8: models.yaml + user settings persistence ---


def test_load_models_yaml_returns_provider_dict(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        "providers:\n"
        "  claude:\n"
        "    - id: sonnet\n"
        "      label: Claude Sonnet\n"
        "  codex:\n"
        "    - id: o3\n"
        "      label: OpenAI o3\n"
    )
    svc = SettingsService(
        models_yaml_path=yaml_path, user_config_path=tmp_path / "user.yaml"
    )
    data = svc.load_models()
    assert data["providers"]["claude"][0]["id"] == "sonnet"
    assert data["providers"]["codex"][0]["id"] == "o3"


def test_load_models_missing_file_returns_fallback(tmp_path):
    svc = SettingsService(
        models_yaml_path=tmp_path / "missing.yaml",
        user_config_path=tmp_path / "user.yaml",
    )
    data = svc.load_models()
    assert "claude" in data["providers"]
    assert "codex" in data["providers"]


def test_load_models_malformed_returns_fallback(tmp_path):
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text("not valid:::[yaml")
    svc = SettingsService(
        models_yaml_path=yaml_path, user_config_path=tmp_path / "u.yaml"
    )
    data = svc.load_models()
    assert "providers" in data


def test_persist_patch_creates_user_yaml(tmp_path):
    svc = SettingsService(
        models_yaml_path=tmp_path / "m.yaml",
        user_config_path=tmp_path / "user.yaml",
    )
    svc.persist_patch({"llm": {"model": "opus"}})
    path = tmp_path / "user.yaml"
    assert path.exists()
    data = yaml.safe_load(path.read_text())
    assert data["llm"]["model"] == "opus"


def test_persist_patch_merges_existing(tmp_path):
    user_path = tmp_path / "user.yaml"
    user_path.write_text("llm:\n  model: sonnet\n  timeout_seconds: 300\n")
    svc = SettingsService(
        models_yaml_path=tmp_path / "m.yaml", user_config_path=user_path
    )
    svc.persist_patch({"llm": {"model": "opus"}})
    data = yaml.safe_load(user_path.read_text())
    assert data["llm"]["model"] == "opus"
    assert data["llm"]["timeout_seconds"] == 300


def test_persist_creates_parent_dir(tmp_path):
    nested = tmp_path / "nested" / "here" / "user.yaml"
    svc = SettingsService(
        models_yaml_path=tmp_path / "m.yaml",
        user_config_path=nested,
    )
    svc.persist_patch({"a": {"b": 1}})
    assert nested.exists()


def test_load_shipped_models_yaml_from_package():
    # Happy path: the shipped models.yaml is loadable without overrides.
    svc = SettingsService(settings=None)
    data = svc.load_models()
    assert "providers" in data
    assert "claude" in data["providers"]


# ---- T1: migration-status programmatic API ----

import pytest as _pytest


@_pytest.mark.asyncio
async def test_get_migration_status_returns_revision_strings(engine, test_settings):
    svc = SettingsService(settings=test_settings, engine=engine)
    result = await svc.get_migration_status()
    assert "error" in result
    assert result["error"] is None
    # latest must be a hex revision when migrations dir is well-formed
    assert result["latest"] is not None and len(result["latest"]) >= 8
    assert isinstance(result["is_behind"], bool)
    # Critical guard: response must never contain alembic's error banner
    for value in (result["current"], result["latest"]):
        assert value is None or not value.startswith("FAILED")


@_pytest.mark.asyncio
async def test_get_migration_status_failure_returns_structured_error(monkeypatch):
    """When Alembic config is broken, returns structured error (not subprocess output)."""
    # Construct a service with no engine and no settings → forces error path.
    svc = SettingsService(settings=None, engine=None)
    result = await svc.get_migration_status()
    assert result["current"] is None
    assert result["latest"] is None
    assert result["is_behind"] is False
    assert isinstance(result["error"], str) and len(result["error"]) > 0
