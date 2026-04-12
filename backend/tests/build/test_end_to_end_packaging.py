"""Slow regression test: build a real sdist and install it in a fresh venv.

Catches the kind of packaging bugs (missing package data, broken entry points,
build hook failures on install-from-sdist) that unit tests cannot. ~60 seconds
on a warm machine; gated behind the `slow` marker so it stays out of the default
pytest run.

Run with: `uv run pytest -m slow`.
"""

import subprocess
import sys
import venv
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.mark.slow
def test_built_sdist_installs_and_runs(tmp_path):
    dist = tmp_path / "dist"
    # Build sdist + wheel from the real backend/ dir.
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist)],
        cwd=str(BACKEND_DIR),
        check=True,
        capture_output=True,
    )
    sdists = list(dist.glob("*.tar.gz"))
    assert len(sdists) == 1, f"expected one sdist, got {sdists}"
    wheels = list(dist.glob("*.whl"))
    assert len(wheels) == 1, f"expected one wheel, got {wheels}"

    # Sdist must contain the generated frontend assets AND migrations.
    list_result = subprocess.run(
        ["tar", "-tzf", str(sdists[0])], capture_output=True, text=True, check=True
    )
    entries = set(list_result.stdout.splitlines())
    assert any(e.endswith("app/static/index.html") for e in entries), (
        "sdist missing app/static/index.html"
    )
    assert any(e.endswith("app/migrations/alembic.ini") for e in entries), (
        "sdist missing app/migrations/alembic.ini"
    )

    # Fresh venv install from the sdist (this triggers the build hook's
    # prebuilt-detection branch, since the extract has no ../frontend).
    env_dir = tmp_path / "venv"
    venv.create(str(env_dir), with_pip=True)
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    pip = env_dir / bin_dir / "pip"
    bc = env_dir / bin_dir / "bookcompanion"

    subprocess.run(
        [str(pip), "install", "--no-cache-dir", "--quiet", str(sdists[0])],
        check=True,
    )

    result = subprocess.run(
        [str(bc), "--help"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, f"bookcompanion --help failed: {result.stderr}"
    assert "bookcompanion" in result.stdout.lower()
