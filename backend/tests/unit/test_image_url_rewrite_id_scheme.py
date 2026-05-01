"""Unit tests for from_image_id_scheme — legacy image:N rewriter.

Covers FR-05/FR-09: existing-id rewrite, orphan-id strip-with-link
fallback, malformed-token leave-alone, empty alt, idempotency,
multiple-images-per-doc.
"""

from __future__ import annotations

from app.services.parser.image_url_rewrite import from_image_id_scheme


def test_rewrites_existing_id():
    out = from_image_id_scheme("![cap](image:42)", {"a.jpg": 42})
    assert out == "![cap](/api/v1/images/42)"


def test_orphan_id_strips_to_link_with_alt():
    out = from_image_id_scheme("before ![alt](image:99) after", {"a.jpg": 42}, on_missing="strip")
    assert out == "before [alt](#) after"


def test_orphan_id_keep_mode_leaves_token():
    out = from_image_id_scheme("![alt](image:99)", {"a.jpg": 42}, on_missing="keep")
    assert out == "![alt](image:99)"


def test_malformed_id_left_untouched():
    assert from_image_id_scheme("![x](image:abc)", {}) == "![x](image:abc)"
    assert from_image_id_scheme("![x](image:)", {}) == "![x](image:)"


def test_empty_alt_handled():
    out = from_image_id_scheme("![](image:42)", {"a.jpg": 42})
    assert out == "![](/api/v1/images/42)"


def test_idempotent():
    once = from_image_id_scheme("![x](image:42)", {"a.jpg": 42})
    twice = from_image_id_scheme(once, {"a.jpg": 42})
    assert once == twice == "![x](/api/v1/images/42)"


def test_multiple_images_in_one_doc():
    md = "![a](image:1) text ![b](image:2)"
    out = from_image_id_scheme(md, {"x": 1, "y": 2})
    assert out == "![a](/api/v1/images/1) text ![b](/api/v1/images/2)"
