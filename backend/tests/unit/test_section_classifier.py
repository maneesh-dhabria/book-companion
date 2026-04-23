import pytest

from app.services.parser.section_classifier import (
    FRONT_MATTER_TYPES,
    SUMMARIZABLE_TYPES,
    detect_section_type,
)


@pytest.mark.parametrize(
    "title,content_md,expected",
    [
        ("Copyright", "", "copyright"),
        ("© 2021 ...", "", "copyright"),
        ("Acknowledgments", "", "acknowledgments"),
        ("Acknowledgements", "", "acknowledgments"),
        ("Dedication", "", "dedication"),
        ("Title Page", "", "title_page"),
        ("Table of Contents", "", "table_of_contents"),
        ("Contents", "", "table_of_contents"),
        ("Contents of Chapter 1", "", "chapter"),
        ("What This Book Contains", "", "chapter"),
        ("Colophon", "", "colophon"),
        ("Cover", "", "cover"),
        ("Book Cover", "", "cover"),
        ("Discover", "", "chapter"),
        ("Part One", "short intro", "part_header"),
        ("Part 3", "", "part_header"),
        ("Part One: Foundations", "x" * 1500, "chapter"),
        ("Part One", "x" * 1000, "chapter"),
        ("Part One", "x" * 999, "part_header"),
        ("Introduction to Copyright", "", "copyright"),
        ("Introduction", "", "introduction"),
        ("Glossary", "", "glossary"),
        ("Chapter 1: The Right Mindset", "", "chapter"),
        ("Random Title", "", "chapter"),
        ("", "", "chapter"),
    ],
)
def test_detect_section_type(title, content_md, expected):
    assert detect_section_type(title, content_md) == expected


def test_front_matter_types_set():
    assert {
        "copyright",
        "acknowledgments",
        "dedication",
        "title_page",
        "table_of_contents",
        "colophon",
        "cover",
        "part_header",
        "license",
    } == FRONT_MATTER_TYPES


def test_summarizable_types_set():
    assert {
        "chapter",
        "introduction",
        "preface",
        "foreword",
        "epilogue",
        "conclusion",
    } == SUMMARIZABLE_TYPES


def test_front_matter_and_summarizable_disjoint():
    assert FRONT_MATTER_TYPES.isdisjoint(SUMMARIZABLE_TYPES)


def test_none_content_md_treated_as_empty():
    assert detect_section_type("Part One", None) == "part_header"


# ---------------------------------------------------------------------------
# T24 / FR-F4 — Gutenberg edge cases
# ---------------------------------------------------------------------------


def test_classify_all_caps_byline_as_title_page():
    assert detect_section_type("LIONEL GILES, M.A.", "") == "title_page"


def test_classify_titlecase_translator_byline_as_title_page():
    assert (
        detect_section_type("Jane Doe, Translator", "x" * 50) == "title_page"
    )


def test_classify_long_byline_style_title_stays_chapter():
    """Name-shaped title with a real chapter body must stay 'chapter'."""
    assert detect_section_type("Joan Magretta: A Memoir", "x" * 5000) == "chapter"


def test_classify_footnotes_as_notes():
    assert detect_section_type("Footnotes", "1. ...") == "notes"


def test_classify_gutenberg_license_as_license():
    assert (
        detect_section_type("THE FULL PROJECT GUTENBERG LICENSE", "...")
        == "license"
    )
    assert (
        detect_section_type("End of the Project Gutenberg", "text")
        == "license"
    )


def test_all_caps_single_word_is_not_a_byline():
    """Single ALL CAPS word like "CHAPTER" must not be treated as a byline."""
    assert detect_section_type("CHAPTER", "") == "chapter"


def test_summarizable_types_still_excludes_new_types():
    assert "license" not in SUMMARIZABLE_TYPES
    assert "title_page" not in SUMMARIZABLE_TYPES
    assert "notes" not in SUMMARIZABLE_TYPES
