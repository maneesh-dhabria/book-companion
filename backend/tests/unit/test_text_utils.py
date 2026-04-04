"""Tests for app.services.parser.text_utils module."""

import pytest

from app.services.parser.text_utils import strip_non_content, text_char_count


class TestStripNonContent:
    """Tests for strip_non_content."""

    def test_removes_xml_declaration(self):
        text = '<?xml version="1.0" encoding="UTF-8"?>\nHello world'
        assert strip_non_content(text) == "Hello world"

    def test_removes_xml_declaration_with_standalone(self):
        text = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\nContent'
        assert strip_non_content(text) == "Content"

    def test_removes_processing_instruction(self):
        text = '<?xml-stylesheet type="text/css" href="style.css"?>\nParagraph'
        assert strip_non_content(text) == "Paragraph"

    def test_removes_multiple_processing_instructions(self):
        text = "<?pi1 data?>\n<?pi2 data?>\nBody text"
        assert strip_non_content(text) == "Body text"

    def test_removes_image_only_line(self):
        text = "Before\n![alt text](image.png)\nAfter"
        assert strip_non_content(text) == "Before\n\nAfter"

    def test_removes_image_only_line_with_leading_whitespace(self):
        text = "Before\n   ![photo](pic.jpg)   \nAfter"
        assert strip_non_content(text) == "Before\n\nAfter"

    def test_preserves_inline_image(self):
        text = "See this ![icon](icon.png) in the sentence."
        assert strip_non_content(text) == "See this ![icon](icon.png) in the sentence."

    def test_plain_text_passthrough(self):
        text = "Just a normal paragraph with no special content."
        assert strip_non_content(text) == text

    def test_empty_input(self):
        assert strip_non_content("") == ""

    def test_whitespace_only_input(self):
        assert strip_non_content("   \n\n  ") == ""

    def test_strips_surrounding_whitespace(self):
        text = "  \n  Hello  \n  "
        assert strip_non_content(text) == "Hello"

    def test_mixed_content(self):
        text = (
            '<?xml version="1.0"?>\n'
            "# Chapter 1\n"
            "\n"
            "![cover](cover.png)\n"
            "\n"
            "Some real content here.\n"
            "<?processing hint?>\n"
            "More content."
        )
        result = strip_non_content(text)
        assert "Chapter 1" in result
        assert "Some real content here." in result
        assert "More content." in result
        assert "<?xml" not in result
        assert "![cover]" not in result
        assert "<?processing" not in result

    def test_multiple_images_on_separate_lines(self):
        text = "Text\n![a](a.png)\n![b](b.png)\nEnd"
        result = strip_non_content(text)
        assert "![a]" not in result
        assert "![b]" not in result
        assert "Text" in result
        assert "End" in result


class TestTextCharCount:
    """Tests for text_char_count."""

    def test_plain_text_count(self):
        assert text_char_count("Hello") == 5

    def test_count_after_stripping(self):
        text = '<?xml version="1.0"?>\nHello'
        assert text_char_count(text) == 5

    def test_empty_string(self):
        assert text_char_count("") == 0

    def test_only_non_content(self):
        text = '<?xml version="1.0"?>\n![img](img.png)'
        assert text_char_count(text) == 0

    def test_mixed_content_count(self):
        text = "abc\n![img](x.png)\ndef"
        # After stripping: "abc\n\ndef" -> length includes newlines
        result = text_char_count(text)
        assert result > 0
        assert result == len("abc\n\ndef")
