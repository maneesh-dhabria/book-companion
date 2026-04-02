"""End-to-end CLI flow tests."""

import pytest
from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "bookcompanion" in result.stdout


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "add" in result.stdout
    assert "search" in result.stdout
    assert "summarize" in result.stdout
    assert "summary" in result.stdout
    assert "list" in result.stdout
    assert "show" in result.stdout
    assert "delete" in result.stdout
    assert "read" in result.stdout
    assert "authors" in result.stdout
    assert "eval" in result.stdout
    assert "status" in result.stdout
    assert "config" in result.stdout
    assert "init" in result.stdout


def test_config_show():
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "database" in result.stdout


def test_config_set():
    result = runner.invoke(app, ["config", "set", "llm.model", "opus"])
    assert result.exit_code == 0
    assert "Set llm.model = opus" in result.stdout


def test_add_missing_file():
    result = runner.invoke(app, ["add", "/nonexistent/path/book.epub"])
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower() or "Error" in result.stdout


def test_add_unsupported_format():
    # Create a temp file with unsupported extension
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"not a book")
        tmp_path = f.name

    try:
        result = runner.invoke(app, ["add", tmp_path])
        assert result.exit_code != 0
        assert "Unsupported" in result.stdout or "Error" in result.stdout
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_delete_nonexistent():
    result = runner.invoke(app, ["delete", "99999", "--yes"])
    # Should fail with error (book not found) or non-zero exit
    assert result.exit_code != 0 or "not found" in result.stdout.lower()


def test_search_requires_query():
    result = runner.invoke(app, ["search"])
    # Missing required argument
    assert result.exit_code != 0


def test_annotate_help():
    result = runner.invoke(app, ["annotate", "--help"])
    assert result.exit_code == 0
    # Should show the annotate sub-app help
    assert "annotat" in result.stdout.lower() or "help" in result.stdout.lower()


# --- Phase 2 Command Help Tests ---


def test_tag_help():
    result = runner.invoke(app, ["tag", "--help"])
    assert result.exit_code == 0


def test_concepts_help():
    result = runner.invoke(app, ["concepts", "--help"])
    assert result.exit_code == 0


def test_export_help():
    result = runner.invoke(app, ["export", "--help"])
    assert result.exit_code == 0


def test_backup_help():
    result = runner.invoke(app, ["backup", "--help"])
    assert result.exit_code == 0


def test_references_help():
    result = runner.invoke(app, ["references", "--help"])
    assert result.exit_code == 0


def test_edit_help():
    result = runner.invoke(app, ["edit", "--help"])
    assert result.exit_code == 0


# --- Empty State Tests (skip if no running DB) ---


class TestEmptyStates:
    """Verify empty state messages per spec Section 10."""

    @pytest.mark.skipif(True, reason="Requires running DB and full service wiring")
    def test_empty_state_no_books(self):
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No books in your library yet" in result.stdout

    @pytest.mark.skipif(True, reason="Requires running DB and search service")
    def test_empty_state_no_search_results(self):
        result = runner.invoke(app, ["search", "xyznonexistent"])
        assert "No results found" in result.stdout

    @pytest.mark.skipif(True, reason="Requires running DB with a book")
    def test_empty_state_no_summary(self):
        result = runner.invoke(app, ["summary", "1"])
        assert ("No summary" in result.stdout) or ("quick_summary" in result.stdout)

    @pytest.mark.skipif(True, reason="Requires running DB with a book")
    def test_empty_state_no_eval(self):
        result = runner.invoke(app, ["eval", "1"])
        assert ("No eval results" in result.stdout) or ("generated first" in result.stdout)
