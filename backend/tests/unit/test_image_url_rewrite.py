from app.services.parser.image_url_rewrite import from_placeholder, to_placeholder


def test_markdown_image_to_placeholder():
    md = "Here is an image: ![alt](images/foo.jpg) end."
    out = to_placeholder(md)
    assert "__IMG_PLACEHOLDER__:foo.jpg__ENDIMG__" in out
    assert "images/foo.jpg" not in out


def test_html_img_tag_to_placeholder():
    md = '<img src="images/bar.png" alt="b" />'
    out = to_placeholder(md)
    assert "__IMG_PLACEHOLDER__:bar.png__ENDIMG__" in out


def test_path_with_subdirs_uses_basename():
    md = "![](OEBPS/images/baz.jpeg)"
    out = to_placeholder(md)
    assert "__IMG_PLACEHOLDER__:baz.jpeg__ENDIMG__" in out


def test_filename_with_double_underscores_round_trip():
    """Regression: filenames with `__` must survive the placeholder round-trip."""
    md = "![](images/chap__01.png)"
    placeholder_md = to_placeholder(md)
    assert "__IMG_PLACEHOLDER__:chap__01.png__ENDIMG__" in placeholder_md
    out = from_placeholder(placeholder_md, {"chap__01.png": 42})
    assert "/api/v1/images/42" in out
    assert "chap__01" not in out  # fully replaced


def test_non_image_links_untouched():
    md = "[link](https://example.com)"
    assert to_placeholder(md) == md


def test_absolute_image_url_untouched():
    md = "![r](https://example.com/a.jpg)"
    assert to_placeholder(md) == md


def test_from_placeholder_substitutes_known_filenames():
    md = (
        "before __IMG_PLACEHOLDER__:foo.jpg__ENDIMG__ middle "
        "__IMG_PLACEHOLDER__:bar.png__ENDIMG__ end"
    )
    out = from_placeholder(md, {"foo.jpg": 11, "bar.png": 22})
    assert "/api/v1/images/11" in out
    assert "/api/v1/images/22" in out
    assert "__IMG_PLACEHOLDER__" not in out


def test_from_placeholder_leaves_unknown_filenames():
    md = "__IMG_PLACEHOLDER__:missing.jpg__ENDIMG__"
    out = from_placeholder(md, {})
    assert out == md
