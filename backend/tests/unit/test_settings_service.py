"""Unit tests for SettingsService."""

import yaml

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


def test_get_safe_settings_includes_cli_command(tmp_path):
    """FR-F1.1 / FR-F1.2: cli_command surfaces in API; config_dir does not."""
    s = Settings()
    object.__setattr__(s.llm, "cli_command", "claude-personal")
    svc = SettingsService(settings=s, config_path=tmp_path / "settings.yaml")
    data = svc.get_safe_settings()
    assert data["llm"]["cli_command"] == "claude-personal"
    assert "config_dir" not in data["llm"]


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
