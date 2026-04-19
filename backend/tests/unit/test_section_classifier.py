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
