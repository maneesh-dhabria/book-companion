from app.services.parser.epub_parser import EPUBParser


def test_epub_parser_no_longer_defines_local_classifier():
    """EPUBParser._detect_section_type should be gone; module-level
    SECTION_TYPE_PATTERNS should be gone. Both are imported from
    section_classifier now."""
    import app.services.parser.epub_parser as mod
    from app.services.parser import section_classifier

    assert not hasattr(EPUBParser, "_detect_section_type"), (
        "EPUBParser still defines _detect_section_type — must delegate to "
        "section_classifier.detect_section_type"
    )
    local = getattr(mod, "SECTION_TYPE_PATTERNS", None)
    if local is not None:
        assert local is section_classifier.SECTION_TYPE_PATTERNS, (
            "local SECTION_TYPE_PATTERNS must be a re-export"
        )


def test_epub_parser_add_section_passes_content_md_to_classifier(monkeypatch):
    """_add_section must call detect_section_type(title, content_md), not just title."""
    captured = []

    def fake_detect(title, content_md=None):
        captured.append((title, content_md))
        return "chapter"

    monkeypatch.setattr(
        "app.services.parser.epub_parser.detect_section_type", fake_detect
    )
    parser = EPUBParser()

    class FakeEntry:
        href = "part-1.xhtml"
        title = "Part One"

    sections = []
    order = [0]
    parser._add_section(
        FakeEntry(),
        content_map={"part-1.xhtml": "short content"},
        image_map={},
        sections=sections,
        order_counter=order,
        depth=0,
    )
    assert captured, "detect_section_type was not called"
    title, content_md = captured[0]
    assert title == "Part One"
    assert content_md == "short content"
