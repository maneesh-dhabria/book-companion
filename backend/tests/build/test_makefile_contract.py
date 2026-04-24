"""Contract test: `make help` must list every canonical target.

Marked `slow` so it stays out of the default pytest run (the default `addopts`
already excludes slow). Invoke with:
    uv run pytest -m slow --override-ini="addopts=" \
        tests/build/test_makefile_contract.py -v
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_TARGETS = (
    "dev",
    "stop",
    "migrate",
    "build-fe",
    "force-build-fe",
    "clean-fe",
    "reset",
    "test",
    "lint",
    "verify",
    "verify-ladder",
    "verify-slow",
    "verify-all",
    "serve-fresh",
    "help",
)


@pytest.mark.slow
def test_makefile_help_lists_canonical_targets():
    out = subprocess.run(
        ["make", "help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert out.returncode == 0, f"make help failed: stderr={out.stderr!r}"
    for target in CANONICAL_TARGETS:
        assert target in out.stdout, (
            f"make help missing target {target!r}. stdout was:\n{out.stdout}"
        )
