"""Sanitizer anti-pattern fixtures + sentence-offset + version-constant tests."""

import time

import pytest

from app.services.tts.markdown_to_speech import (
    SANITIZER_VERSION,
    EmptySanitizedTextError,
    sanitize,
)

CASES = [
    ("Smith argued[3] that ideas matter.", ["Smith argued"], ["[3]"]),
    ("```python\nx=1\n```", ["code block"], ["python", "x=1"]),
    ("![diagram](/api/v1/images/42)", ["figure: diagram"], ["/api/v1/images"]),
    ("![](/api/v1/images/9) and more text.", ["more text"], ["figure:"]),
    ("Apples e.g. Granny.", ["for example"], ["e.g."]),
    ("Mass is $E=mc^2$ here.", ["equation"], ["E=mc"]),
    ("Equation \\[F=ma\\] block here.", ["equation"], ["F=ma"]),
    ("Dr. Smith met Mr. Jones on St. Paul Rd.", ["Doctor", "Mister", "Saint"], ["Dr.", "Mr.", "St."]),
    ("See https://example.com here.", ["See"], ["https://", "example.com"]),
    ("[link text](https://example.com) is good.", ["link text"], ["https://"]),
]


@pytest.mark.parametrize("md, expected_in, forbidden", CASES)
def test_sanitizer_anti_patterns(md, expected_in, forbidden):
    result = sanitize(md)
    for s in expected_in:
        assert s in result.text, f"missing {s!r} in {result.text!r}"
    for s in forbidden:
        assert s not in result.text, f"forbidden {s!r} present in {result.text!r}"


def test_empty_input_raises():
    with pytest.raises(EmptySanitizedTextError):
        sanitize("")


def test_whitespace_only_raises():
    with pytest.raises(EmptySanitizedTextError):
        sanitize("   \n\n   ")


def test_only_code_raises():
    with pytest.raises(EmptySanitizedTextError):
        sanitize("```py\n```")


def test_sanitizer_version_constant():
    assert SANITIZER_VERSION == "1.0"


def test_sentence_offsets_present():
    result = sanitize("First sentence. Second sentence. Third one.")
    assert len(result.sentence_offsets_chars) == 3
    assert result.sentence_offsets_chars[0] == 0
    for off in result.sentence_offsets_chars:
        assert 0 <= off < len(result.text)


def test_abbreviation_does_not_split_sentence():
    result = sanitize("Mr. Smith arrived. He left.")
    assert len(result.sentence_offsets_chars) == 2


def test_perf_under_200ms_on_5kb():
    large = "Body text. " * 500
    t0 = time.perf_counter()
    sanitize(large)
    assert (time.perf_counter() - t0) < 0.200
