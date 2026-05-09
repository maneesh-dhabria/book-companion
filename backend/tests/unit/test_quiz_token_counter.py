"""Unit tests for quiz token counter (tiktoken cl100k_base)."""

from app.services.quiz.token_counter import count_tokens


def test_count_tokens_empty_string():
    assert count_tokens("") == 0


def test_count_tokens_short_phrase():
    n = count_tokens("loss aversion")
    assert 2 <= n <= 4  # cl100k typically tokenizes this as 2-3 tokens


def test_count_tokens_long_text_within_30pct_of_chars_div_4():
    text = "The book emphasizes loss aversion as a core finding. " * 100
    n = count_tokens(text)
    approx = len(text) // 4
    assert 0.7 * approx <= n <= 1.3 * approx
