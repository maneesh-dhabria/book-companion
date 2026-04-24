from app.utils.text_similarity import fuzzy_dedupe_against, levenshtein


def test_levenshtein_identical():
    assert levenshtein("a", "a") == 0


def test_levenshtein_one_edit():
    assert levenshtein("porter", "porters") == 1


def test_levenshtein_empty_vs_string():
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3


def test_exact_match_removed():
    assert fuzzy_dedupe_against(["strategy", "porter"], against=["strategy"]) == ["porter"]


def test_case_insensitive_match_removed():
    assert fuzzy_dedupe_against(["Strategy"], against=["strategy"]) == []


def test_levenshtein_leq_2_removed():
    # 'porters' vs 'porter' -> dist=1
    assert fuzzy_dedupe_against(["porters"], against=["porter"]) == []


def test_levenshtein_gt_2_kept():
    # 'strategies' vs 'strategy' -> dist=3
    assert fuzzy_dedupe_against(["strategies"], against=["strategy"]) == ["strategies"]


def test_empty_against_returns_input():
    assert fuzzy_dedupe_against(["a", "b"], against=[]) == ["a", "b"]


def test_preserves_input_order():
    out = fuzzy_dedupe_against(["c", "a", "b"], against=[])
    assert out == ["c", "a", "b"]


def test_drops_empty_candidates():
    assert fuzzy_dedupe_against(["a", "", "b"], against=[]) == ["a", "b"]
