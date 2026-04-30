"""Unit tests for the is_stale() predicate extracted from orphan_sweep.

Tests verify that the predicate combines PID-liveness checks and an age
heuristic so callers (startup sweep + on-demand /summarize guard) can
share a single source of truth.
"""

from __future__ import annotations

import os
import statistics
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from app.services.summarizer.orphan_sweep import is_stale

NOW = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)
MAX_AGE = timedelta(hours=24)


def _job(pid, started_at):
    j = MagicMock()
    j.pid = pid
    j.started_at = started_at
    return j


def test_is_stale_when_pid_is_none():
    assert is_stale(_job(None, NOW), now=NOW, max_age=MAX_AGE) is True


def test_is_stale_when_pid_dead(monkeypatch):
    def fake_kill(pid, sig):
        raise ProcessLookupError

    monkeypatch.setattr(os, "kill", fake_kill)
    assert is_stale(_job(99999, NOW), now=NOW, max_age=MAX_AGE) is True


def test_is_stale_when_too_old(monkeypatch):
    monkeypatch.setattr(os, "kill", lambda pid, sig: None)
    old = NOW - timedelta(hours=25)
    assert is_stale(_job(os.getpid(), old), now=NOW, max_age=MAX_AGE) is True


def test_is_fresh_when_pid_alive_and_recent(monkeypatch):
    monkeypatch.setattr(os, "kill", lambda pid, sig: None)
    recent = NOW - timedelta(minutes=5)
    assert is_stale(_job(os.getpid(), recent), now=NOW, max_age=MAX_AGE) is False


def test_is_stale_predicate_under_5ms_median(monkeypatch):
    """NFR-03: the predicate itself must be << 5ms median over 1000 calls."""
    monkeypatch.setattr(os, "kill", lambda pid, sig: None)
    job = _job(os.getpid(), datetime.now(UTC))
    times = []
    for _ in range(1000):
        s = time.perf_counter_ns()
        is_stale(job, now=datetime.now(UTC), max_age=MAX_AGE)
        times.append((time.perf_counter_ns() - s) / 1e6)
    assert statistics.median(times) < 5.0
