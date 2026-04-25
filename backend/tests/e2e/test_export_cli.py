"""E2E tests for `bookcompanion export` CLI."""
from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


def test_help_lists_new_flags():
    result = runner.invoke(app, ["export", "book", "--help"])
    assert result.exit_code == 0
    assert "--no-book-summary" in result.stdout
    assert "--no-toc" in result.stdout
    assert "--no-annotations" in result.stdout
    assert "--exclude-section" in result.stdout
    assert "Flags only valid with --format markdown" in result.stdout


def test_format_json_with_no_toc_exits_2():
    result = runner.invoke(app, ["export", "book", "1", "--format", "json", "--no-toc"])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "only valid with --format markdown" in combined


def test_format_json_with_exclude_section_exits_2():
    result = runner.invoke(
        app, ["export", "book", "1", "--format", "json", "--exclude-section", "5"]
    )
    assert result.exit_code == 2


def test_library_markdown_subcommand_exits_2():
    result = runner.invoke(app, ["export", "library", "--format", "markdown"])
    assert result.exit_code == 2
    out = result.stdout + (result.stderr or "")
    assert "removed in v1.6" in out


def test_library_json_still_works():
    """The format guard must not be triggered for json."""
    result = runner.invoke(app, ["export", "library", "--format", "json"])
    # May exit 0 (works on empty DB) or 1 (no DB yet); must not be the format-2 guard.
    assert result.exit_code != 2
