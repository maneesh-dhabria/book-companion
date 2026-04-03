"""E2E tests for V1.1 features — runs actual CLI commands."""

import subprocess

CLI = ["uv", "run", "bookcompanion"]


def run_cli(*args, input_text=None):
    result = subprocess.run(
        [*CLI, *args],
        capture_output=True,
        text=True,
        timeout=60,
        input=input_text,
        cwd=".",
    )
    return result


class TestPresetManagement:
    def test_preset_list(self):
        result = run_cli("preset", "list")
        assert result.returncode == 0
        assert "practitioner_bullets" in result.stdout or "Practitioner" in result.stdout

    def test_preset_show(self):
        result = run_cli("preset", "show", "practitioner_bullets")
        assert result.returncode == 0
        assert "bullet_points" in result.stdout

    def test_preset_create_and_delete(self):
        result = run_cli(
            "preset",
            "create",
            "test_e2e",
            "--description",
            "E2E test preset",
            "--style",
            "narrative",
            "--audience",
            "academic",
            "--compression",
            "detailed",
            "--content-focus",
            "full_coverage",
        )
        assert result.returncode == 0

        result = run_cli("preset", "delete", "test_e2e")
        assert result.returncode == 0

    def test_preset_delete_system_fails(self):
        result = run_cli("preset", "delete", "practitioner_bullets")
        assert result.returncode != 0


class TestSummaryCommands:
    def test_summary_list_no_book(self):
        result = run_cli("summary", "list", "99999")
        assert result.returncode != 0


class TestHelpText:
    def test_main_help(self):
        result = run_cli("--help")
        assert result.returncode == 0
        # Check that key commands are listed
        assert "summarize" in result.stdout
        assert "preset" in result.stdout
        assert "summary" in result.stdout

    def test_summarize_help_has_preset(self):
        result = run_cli("summarize", "--help")
        assert result.returncode == 0
        assert "--preset" in result.stdout

    def test_preset_help(self):
        result = run_cli("preset", "--help")
        assert result.returncode == 0

    def test_summary_help(self):
        result = run_cli("summary", "--help")
        assert result.returncode == 0


class TestReadCommand:
    def test_read_nonexistent_book(self):
        result = run_cli("read", "99999", "1")
        assert result.returncode != 0
