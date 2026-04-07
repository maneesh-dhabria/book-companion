from app.services.parser.epub_parser import EPUBParser


class TestSectionTypeDetection:
    def test_detect_glossary(self):
        assert EPUBParser._detect_section_type("Glossary") == "glossary"

    def test_detect_notes(self):
        assert EPUBParser._detect_section_type("Chapter Notes") == "notes"

    def test_detect_endnotes(self):
        assert EPUBParser._detect_section_type("Endnotes") == "notes"

    def test_detect_about_author(self):
        assert EPUBParser._detect_section_type("About the Author") == "about_author"

    def test_detect_default_chapter(self):
        assert EPUBParser._detect_section_type("Chapter 3: Strategy") == "chapter"

    def test_detect_case_insensitive(self):
        assert EPUBParser._detect_section_type("APPENDIX A") == "appendix"

    def test_detect_introduction(self):
        assert EPUBParser._detect_section_type("Introduction") == "introduction"

    def test_detect_foreword(self):
        assert EPUBParser._detect_section_type("Foreword") == "foreword"

    def test_detect_bibliography(self):
        assert EPUBParser._detect_section_type("Works Cited") == "bibliography"
