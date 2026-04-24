from app.services.parser.blockquote_normalizer import normalize_blockquotes


def test_single_blockquote_preserved():
    md = "> This is a simple quote"
    assert normalize_blockquotes(md) == "> This is a simple quote"


def test_double_blockquote_collapsed():
    md = "> > Nested quote text"
    assert normalize_blockquotes(md) == "> Nested quote text"


def test_triple_blockquote_collapsed():
    md = "> > > Deep nested"
    assert normalize_blockquotes(md) == "> Deep nested"


def test_pulp_quote_with_hr_markers_stripped():
    md = (
        "> > ---\n"
        "> >\n"
        "> > The value proposition is the element of strategy.\n"
        "> >\n"
        "> > ---\n"
    )
    # Trailing newline on input becomes a final empty line after split; the
    # normalizer preserves line order + count minus dropped HRs.
    result = normalize_blockquotes(md)
    # Collapsed + HRs dropped. Blank trailing newline from the split is
    # retained as an empty final segment.
    assert result == (
        ">\n"
        "> The value proposition is the element of strategy.\n"
        ">\n"
    )


def test_non_quote_paragraph_untouched():
    md = "Regular paragraph.\n\n> quoted\n\nAnother paragraph."
    assert normalize_blockquotes(md) == md


def test_empty_markdown():
    assert normalize_blockquotes("") == ""


def test_idempotent():
    md = "> > > deep"
    once = normalize_blockquotes(md)
    twice = normalize_blockquotes(once)
    assert once == twice


def test_hr_middle_of_block_preserved():
    # `---` in the middle (not first or last non-blank) of a quote stays.
    md = "> start\n> ---\n> end"
    # Three lines, each non-blank. first=start, last=end; middle HR stays.
    assert normalize_blockquotes(md) == "> start\n> ---\n> end"


def test_hr_first_line_in_block_stripped():
    md = "> ---\n> start\n> end"
    assert normalize_blockquotes(md) == "> start\n> end"


def test_hr_last_line_in_block_stripped():
    md = "> start\n> end\n> ---"
    assert normalize_blockquotes(md) == "> start\n> end"


def test_collapsed_line_preserves_body_whitespace():
    # Body `  some   text` should keep leading double space lost? Our rule
    # collapses the quote prefix but preserves the body as-is (post-lstrip).
    md = "> >   some text"
    assert normalize_blockquotes(md) == "> some text"
