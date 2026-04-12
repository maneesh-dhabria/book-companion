from pathlib import Path

import pytest
from typer.testing import CliRunner

import app.cli.commands.serve_cmd as serve_cmd
from app.cli.main import app as cli_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_api_only(monkeypatch):
    monkeypatch.delenv("BOOKCOMPANION_API_ONLY", raising=False)


@pytest.fixture(autouse=True)
def _no_uvicorn(monkeypatch):
    calls = []
    monkeypatch.setattr(serve_cmd.uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setattr(serve_cmd, "_auto_init_if_needed", lambda settings: None)
    return calls


def test_is_installed_mode_detection():
    assert serve_cmd._is_installed_mode(Path("/x/site-packages/app/api/main.py")) is True
    assert serve_cmd._is_installed_mode(Path("/home/dev/repo/backend/app/api/main.py")) is False


def test_serve_exits_when_assets_missing_dev_mode(monkeypatch, _no_uvicorn):
    monkeypatch.setattr(serve_cmd, "_assets_present", lambda: False)
    monkeypatch.setattr(serve_cmd, "_is_installed_mode", lambda p=None: False)
    result = runner.invoke(cli_app, ["serve"])
    assert result.exit_code == 1
    assert "Frontend assets not found" in result.output
    assert "npm run build" in result.output
    assert _no_uvicorn == []


def test_serve_exits_when_assets_missing_installed_mode(monkeypatch, _no_uvicorn):
    monkeypatch.setattr(serve_cmd, "_assets_present", lambda: False)
    monkeypatch.setattr(serve_cmd, "_is_installed_mode", lambda p=None: True)
    result = runner.invoke(cli_app, ["serve"])
    assert result.exit_code == 1
    assert "packaging bug" in result.output.lower()
    assert _no_uvicorn == []


def test_serve_api_only_skips_asset_check(monkeypatch, _no_uvicorn):
    monkeypatch.setattr(serve_cmd, "_assets_present", lambda: False)
    result = runner.invoke(cli_app, ["serve", "--api-only"])
    assert result.exit_code == 0
    assert _no_uvicorn


def test_serve_api_only_env_var(monkeypatch, _no_uvicorn):
    monkeypatch.setattr(serve_cmd, "_assets_present", lambda: False)
    monkeypatch.setenv("BOOKCOMPANION_API_ONLY", "1")
    result = runner.invoke(cli_app, ["serve"])
    assert result.exit_code == 0
    assert _no_uvicorn


def test_serve_starts_when_assets_present(monkeypatch, _no_uvicorn):
    monkeypatch.setattr(serve_cmd, "_assets_present", lambda: True)
    result = runner.invoke(cli_app, ["serve"])
    assert result.exit_code == 0
    assert _no_uvicorn


def test_serve_help_documents_api_only():
    result = runner.invoke(cli_app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--api-only" in result.stdout
    assert "BOOKCOMPANION_API_ONLY" in result.stdout
