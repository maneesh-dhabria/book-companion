"""Tests for Image model new fields."""

from app.db.models import Image, ImageRelevance


def test_image_relevance_enum_values():
    assert ImageRelevance.KEY == "key"
    assert ImageRelevance.SUPPLEMENTARY == "supplementary"
    assert ImageRelevance.DECORATIVE == "decorative"


def test_image_has_relevance_field():
    img = Image(
        section_id=1,
        data=b"fake",
        mime_type="image/png",
        relevance=ImageRelevance.KEY,
    )
    assert img.relevance == "key"


def test_image_relevance_defaults_to_none():
    img = Image(section_id=1, data=b"fake", mime_type="image/png")
    assert img.relevance is None


def test_image_has_alt_text_field():
    img = Image(
        section_id=1, data=b"fake", mime_type="image/png",
        alt_text="A diagram of the five forces.",
    )
    assert img.alt_text == "A diagram of the five forces."


def test_image_has_content_hash_field():
    img = Image(
        section_id=1, data=b"fake", mime_type="image/png",
        content_hash="abc123",
    )
    assert img.content_hash == "abc123"
