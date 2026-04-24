"""Regression (B2): CLI `summarize` lambdas must accept section_id as first positional.

Verifies each callback in `summarize_cmd.run()` has an arity compatible with the
service invocation pattern `cb(section_id, index, total, title, ...)`. Without this
check, a signature drift would explode at runtime on the very first section.
"""

import inspect
from pathlib import Path


def _lambdas_from_source(source: str, arg_counts: dict[str, int]) -> None:
    """Assert each on_section_* lambda in the CLI has the given positional arity."""
    for cb, expected in arg_counts.items():
        # Locate the "on_section_*=lambda ...:" fragment.
        needle = f"{cb}=lambda "
        idx = source.find(needle)
        assert idx != -1, f"{cb} lambda not found in summarize_cmd.py"
        after = source[idx + len(needle) :]
        header = after.split(":", 1)[0]
        # Count comma-separated params (ignoring trailing whitespace)
        params = [p.strip() for p in header.split(",") if p.strip()]
        assert len(params) == expected, (
            f"{cb} has {len(params)} params, expected {expected}. Header: {header!r}"
        )


def test_cli_summarize_callbacks_accept_section_id_first():
    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "cli"
        / "commands"
        / "summarize_cmd.py"
    ).read_text()
    # Service calls: (section_id, index, total, title, ...). Per-callback arity:
    #   complete: +elapsed, comp     → 6
    #   skip:     +reason            → 5
    #   fail:     +err               → 5
    #   retry:    (nothing extra)    → 4
    _lambdas_from_source(
        src,
        {
            "on_section_complete": 6,
            "on_section_skip": 5,
            "on_section_fail": 5,
            "on_section_retry": 4,
        },
    )


def test_service_invokes_callbacks_with_section_id_first():
    """Each callback invocation in summarizer_service.py must pass section_id
    (or its captured alias) as the first positional argument."""
    from app.services.summarizer import summarizer_service

    src = inspect.getsource(summarizer_service)
    # Normalize whitespace for resilient matching
    compact = " ".join(src.split())
    # Accept both "multi-line formatted" spacing (` section.id,`) and
    # "single-line formatted" spacing (`section.id,`) — ruff format collapses
    # short call sites to single lines in newer versions.
    fragments = [
        ("on_section_start(section_id,",),
        ("on_section_skip( section.id,", "on_section_skip(section.id,"),
        ("on_section_complete( section.id,", "on_section_complete(section.id,"),
        ("on_section_retry( section.id,", "on_section_retry(section.id,"),
        ("on_section_fail( section_id,", "on_section_fail(section_id,"),
    ]
    for options in fragments:
        assert any(opt in compact for opt in options), (
            f"service call-site drift: expected one of {options!r}"
        )
