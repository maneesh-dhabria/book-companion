"""Grep gate: no `cli_command` references in backend source (T4, FR-B07, §13.5)."""

import subprocess
from pathlib import Path


def test_no_cli_command_references_in_backend_source():
    repo_root = Path(__file__).resolve().parents[3]
    backend_app = repo_root / "backend" / "app"
    result = subprocess.run(
        ["grep", "-rn", "cli_command", str(backend_app)],
        capture_output=True,
        text=True,
    )
    # Filter the built static dir if it exists (vite build output, not source)
    lines = [
        line
        for line in result.stdout.splitlines()
        if "/static/" not in line and "/__pycache__/" not in line
    ]
    assert lines == [], "Orphan cli_command refs in backend source:\n" + "\n".join(lines)
