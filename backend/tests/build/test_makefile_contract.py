"""Contract tests for the repo-root Makefile.

Marked `slow` so they stay out of the default pytest run
(`addopts = "-m 'not slow'"`). Run via:
    uv run pytest -m slow tests/build/test_makefile_contract.py -v
"""

import os
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


@pytest.mark.slow
def test_makefile_help_survives_windows_os_env():
    # Regression guard for D10 in docs/plans/2026-04-25-makefile-dev-loop-
    # implementation-plan.md: WINDOWS_BAIL must use lazy `=` assignment so
    # $(error) fires only when a recipe references it. A refactor to `:=`
    # fires $(error) at Makefile parse time, crashing `make help` on Windows
    # and violating spec §5 E8 (help must stay usable there).
    env = {**os.environ, "OS": "Windows_NT"}
    out = subprocess.run(
        ["make", "help"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert out.returncode == 0, (
        "OS=Windows_NT make help must exit 0. If this fails with a "
        "$(error) message, WINDOWS_BAIL likely uses `:=` — switch to `=`. "
        f"stderr={out.stderr!r}"
    )
    assert "Windows: run commands directly" in out.stdout, (
        f"help did not print the Windows bail message. stdout={out.stdout!r}"
    )
    combined = out.stdout + out.stderr
    assert "Windows is not supported" not in combined, (
        "$(error) fired during `make help` on simulated Windows — "
        "WINDOWS_BAIL has been changed to eager (`:=`) assignment. "
        f"combined output:\n{combined}"
    )
