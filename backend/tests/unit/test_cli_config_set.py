"""CLI parity for strict settings validation (FR-F1.8 / D18)."""

import yaml
from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


def test_cli_config_set_invalid_value_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKCOMPANION_CONFIG", str(tmp_path / "settings.yaml"))
    result = runner.invoke(app, ["config", "set", "llm.timeout_seconds", "bad"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "timeout_seconds" in combined or "validation" in combined.lower()
    assert not (tmp_path / "settings.yaml").exists()


def test_cli_config_set_valid_persists(tmp_path, monkeypatch):
    cfg = tmp_path / "settings.yaml"
    monkeypatch.setenv("BOOKCOMPANION_CONFIG", str(cfg))
    result = runner.invoke(app, ["config", "set", "llm.config_dir", "/tmp/claude-personal"])
    assert result.exit_code == 0, result.output
    assert cfg.exists()
    data = yaml.safe_load(cfg.read_text())
    assert data["llm"]["config_dir"] == "/tmp/claude-personal"


def test_cli_config_set_unknown_key_rejected(tmp_path, monkeypatch):
    """FR-F1.8 / D18: CLI inherits the same extra='forbid' rule as PATCH."""
    cfg = tmp_path / "settings.yaml"
    monkeypatch.setenv("BOOKCOMPANION_CONFIG", str(cfg))
    result = runner.invoke(app, ["config", "set", "llm.bogus", "x"])
    assert result.exit_code != 0
    assert not cfg.exists()
