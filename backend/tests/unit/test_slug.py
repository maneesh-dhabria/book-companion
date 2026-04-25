from app.services.slug import filename_slug, gfm_slug


class TestFilenameSlug:
    def test_simple_lowercases_and_dashes(self):
        assert filename_slug("The Art of War") == "the-art-of-war"

    def test_strips_punctuation(self):
        assert filename_slug("War & Peace: A Novel!") == "war-peace-a-novel"

    def test_collapses_multiple_spaces_and_dashes(self):
        assert filename_slug("a   b---c") == "a-b-c"

    def test_strips_leading_trailing_dashes(self):
        assert filename_slug("  hello  ") == "hello"

    def test_truncates_to_80_chars(self):
        long = "x" * 200
        assert filename_slug(long) == "x" * 80

    def test_cjk_only_returns_empty(self):
        assert filename_slug("北京概要") == ""

    def test_emoji_only_returns_empty(self):
        assert filename_slug("🚀🎯") == ""

    def test_empty_string_returns_empty(self):
        assert filename_slug("") == ""


class TestGfmSlug:
    def test_simple_lowercases(self):
        assert gfm_slug("Chapter 1") == "chapter-1"

    def test_preserves_unicode_alnum(self):
        assert gfm_slug("Café") == "café"
        assert gfm_slug("北京 概要") == "北京-概要"

    def test_strips_emoji_and_punctuation(self):
        assert gfm_slug("🚀 The Vision!") == "the-vision"

    def test_returns_empty_for_pure_emoji(self):
        assert gfm_slug("🚀🎯") == ""

    def test_collapses_consecutive_dashes(self):
        assert gfm_slug("a -- b") == "a-b"
