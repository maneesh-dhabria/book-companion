"""Tests for eval status and results display functions."""

from app.cli.formatting import eval_results, eval_status


def test_eval_status_none():
    assert eval_status(None) == "—"


def test_eval_status_empty():
    assert eval_status({}) == "—"


def test_eval_status_zero_total():
    assert eval_status({"passed": 0, "total": 0}) == "—"


def test_eval_status_all_passed():
    result = eval_status({"passed": 16, "total": 16})
    assert "passed" in result


def test_eval_status_partial():
    result = eval_status(
        {
            "passed": 14,
            "total": 16,
            "results": {"reasonable_length": {"passed": False}},
        }
    )
    assert "partial" in result


def test_eval_status_critical_failed():
    result = eval_status(
        {
            "passed": 12,
            "total": 16,
            "results": {"no_hallucinated_facts": {"passed": False}},
        }
    )
    assert "failed" in result


def test_eval_results_none():
    assert eval_results(None) == "—"


def test_eval_results_data():
    assert eval_results({"passed": 14, "total": 16}) == "14/16"


def test_eval_results_all():
    assert eval_results({"passed": 16, "total": 16}) == "16/16"
