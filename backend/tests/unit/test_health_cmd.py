"""Tests for health CLI command."""

from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


def test_health_command_exists():
    result = runner.invoke(app, ["health", "--help"])
    assert result.exit_code == 0
    assert "health" in result.stdout.lower() or "check" in result.stdout.lower()
