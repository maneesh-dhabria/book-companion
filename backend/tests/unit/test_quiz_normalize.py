"""Unit tests for FR-34 concept_label normalization pipeline."""

from app.services.quiz.normalize import normalize_concept_label


def test_strip_lower():
    assert normalize_concept_label("  Loss Aversion  ") == "loss aversion"


def test_trailing_parenthetical_dropped():
    assert normalize_concept_label("loss aversion (Kahneman)") == "loss aversion"
    assert normalize_concept_label("Anchoring (cf. Tversky 1974)") == "anchoring"


def test_internal_parenthetical_kept():
    assert normalize_concept_label("loss (asymmetric) aversion") == "loss (asymmetric) aversion"


def test_hyphens_underscores_become_spaces():
    assert normalize_concept_label("loss-aversion") == "loss aversion"
    assert normalize_concept_label("loss_aversion") == "loss aversion"
    assert normalize_concept_label("loss--aversion") == "loss aversion"


def test_collapse_internal_whitespace():
    assert normalize_concept_label("loss     aversion") == "loss aversion"


def test_combined():
    assert normalize_concept_label("  Loss-Aversion  (Kahneman 1979)  ") == "loss aversion"


def test_empty_returns_empty():
    assert normalize_concept_label("") == ""
    assert normalize_concept_label("   ") == ""
