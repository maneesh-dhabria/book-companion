"""Tests for section editing REPL command parser."""

import pytest

from app.exceptions import SectionEditError
from app.services.section_edit_service import parse_command


def test_parse_merge():
    cmd = parse_command('merge 3,4,5 "Combined Title"')
    assert cmd.action == "merge"
    assert cmd.indices == [3, 4, 5]
    assert cmd.title == "Combined Title"


def test_parse_merge_no_title():
    cmd = parse_command("merge 1,2")
    assert cmd.indices == [1, 2]
    assert cmd.title is None


def test_parse_split_heading():
    cmd = parse_command("split 3 --at-heading")
    assert cmd.action == "split"
    assert cmd.indices == [3]
    assert cmd.split_mode == "heading"


def test_parse_split_char():
    cmd = parse_command("split 3 --at-char 5000")
    assert cmd.split_mode == "char"
    assert cmd.split_value == 5000


def test_parse_split_paragraph():
    cmd = parse_command("split 3 --at-paragraph 5000")
    assert cmd.split_mode == "paragraph"
    assert cmd.split_value == 5000


def test_parse_move():
    cmd = parse_command("move 5 --after 2")
    assert cmd.action == "move"
    assert cmd.indices == [5]
    assert cmd.target_after == 2


def test_parse_delete():
    cmd = parse_command("delete 7,8")
    assert cmd.action == "delete"
    assert cmd.indices == [7, 8]


def test_parse_done():
    assert parse_command("done").action == "done"


def test_parse_show():
    assert parse_command("show").action == "show"


def test_parse_undo():
    assert parse_command("undo").action == "undo"


def test_parse_unknown_raises():
    with pytest.raises(SectionEditError, match="Unknown command"):
        parse_command("invalid_cmd")


def test_parse_empty_raises():
    with pytest.raises(SectionEditError):
        parse_command("")


def test_parse_merge_single_index_raises():
    with pytest.raises(SectionEditError, match="at least 2"):
        parse_command("merge 3")
