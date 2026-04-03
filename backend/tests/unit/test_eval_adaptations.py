"""Tests for facet-sensitive eval assertion thresholds."""

import pytest


def test_compression_range_brief():
    from app.services.summarizer.evaluator import EvalService
    svc = EvalService.__new__(EvalService)
    low, high = svc._get_compression_range({"compression": "brief", "style": "narrative"})
    assert low == 5.0
    assert high == 15.0


def test_compression_range_tweet_thread_overrides():
    from app.services.summarizer.evaluator import EvalService
    svc = EvalService.__new__(EvalService)
    low, high = svc._get_compression_range({"compression": "detailed", "style": "tweet_thread"})
    assert low == 2.0
    assert high == 8.0


def test_compression_range_standard():
    from app.services.summarizer.evaluator import EvalService
    svc = EvalService.__new__(EvalService)
    low, high = svc._get_compression_range({"compression": "standard", "style": "bullet_points"})
    assert low == 15.0
    assert high == 25.0
