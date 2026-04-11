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
