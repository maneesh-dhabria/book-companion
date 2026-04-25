import pytest

from app.services.export_service import (
    ExportSelection,
    ExportService,
    _sanitize_image_urls,
)


def _book_data(title="Test Book", authors=None, summary=None, sections=None):
    return {
        "id": 1,
        "title": title,
        "authors": authors if authors is not None else ["Test Author"],
        "quick_summary": summary,
        "sections": sections or [],
        "annotations": [],
    }


class TestExportSelection:
    def test_default_includes_all(self):
        sel = ExportSelection()
        assert sel.include_book_summary is True
        assert sel.include_toc is True
        assert sel.include_annotations is True
        assert sel.exclude_section_ids == frozenset()

    def test_immutable(self):
        sel = ExportSelection()
        with pytest.raises((AttributeError, Exception)):
            sel.include_toc = False  # type: ignore

    def test_with_excludes(self):
        sel = ExportSelection(exclude_section_ids=frozenset({1, 2, 3}))
        assert 2 in sel.exclude_section_ids


class TestSanitizeImageUrls:
    def test_md_image_with_alt(self):
        result = _sanitize_image_urls("Body ![figure 3](/api/v1/images/17) text")
        assert result == "Body [Image: figure 3] text"
        assert "/api/v1/images/" not in result

    def test_md_image_empty_alt(self):
        assert _sanitize_image_urls("![](/api/v1/images/5)") == "[Image]"

    def test_md_image_with_title_attr(self):
        result = _sanitize_image_urls('![figure](/api/v1/images/17 "Title text")')
        assert result == "[Image: figure]"
        assert "/api/v1/images/" not in result

    def test_md_image_special_chars_in_alt(self):
        result = _sanitize_image_urls("![alt with parens (here)](/api/v1/images/9)")
        assert result == "[Image: alt with parens (here)]"

    def test_html_img_with_alt(self):
        result = _sanitize_image_urls('<img src="/api/v1/images/12" alt="diagram" />')
        assert result == "[Image: diagram]"

    def test_html_img_no_alt(self):
        result = _sanitize_image_urls('<img src="/api/v1/images/12" />')
        assert result == "[Image]"

    def test_html_img_single_quotes(self):
        result = _sanitize_image_urls("<img src='/api/v1/images/12' alt='x' />")
        assert result == "[Image: x]"

    def test_html_img_extra_attrs(self):
        src = '<img class="big" src="/api/v1/images/12" alt="t" width="200" />'
        assert _sanitize_image_urls(src) == "[Image: t]"

    def test_multiple_images_in_one_text(self):
        src = "First ![a](/api/v1/images/1) middle ![b](/api/v1/images/2) end"
        assert _sanitize_image_urls(src) == "First [Image: a] middle [Image: b] end"

    def test_no_images_passthrough(self):
        assert _sanitize_image_urls("plain text") == "plain text"

    def test_zero_substring_invariant(self):
        src = '![x](/api/v1/images/1) <img src="/api/v1/images/2"/> ![](/api/v1/images/3 "t")'
        assert "/api/v1/images/" not in _sanitize_image_urls(src)


class TestRenderSummaryMarkdownFrontMatter:
    @pytest.mark.asyncio
    async def test_single_author_front_matter(self, db_session):
        svc = ExportService(db_session)
        body, is_empty = await svc._render_summary_markdown(
            _book_data(title="The Art of War", authors=["Sun Tzu"], summary=None),
            ExportSelection(),
        )
        assert body.startswith("# The Art of War\n")
        assert "**Author:** Sun Tzu" in body
        assert "**Authors:**" not in body
        assert "**Exported:** " in body
        assert is_empty is True

    @pytest.mark.asyncio
    async def test_multi_author(self, db_session):
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(authors=["A", "B", "C"]), ExportSelection()
        )
        assert "**Authors:** A, B, C" in body

    @pytest.mark.asyncio
    async def test_zero_authors(self, db_session):
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(authors=[]), ExportSelection()
        )
        assert "**Author:** Unknown" in body

    @pytest.mark.asyncio
    async def test_book_summary_renders_under_front_matter(self, db_session):
        svc = ExportService(db_session)
        body, is_empty = await svc._render_summary_markdown(
            _book_data(summary="The book is about strategy."),
            ExportSelection(),
        )
        assert "The book is about strategy." in body
        assert is_empty is False

    @pytest.mark.asyncio
    async def test_book_summary_skipped_when_toggle_off(self, db_session):
        svc = ExportService(db_session)
        body, is_empty = await svc._render_summary_markdown(
            _book_data(summary="Strategy stuff"),
            ExportSelection(include_book_summary=False),
        )
        assert "Strategy stuff" not in body
        assert is_empty is True

    @pytest.mark.asyncio
    async def test_sections_render_with_h2(self, db_session):
        sections = [
            {"id": 10, "title": "Chapter 1", "order_index": 0, "depth": 0,
             "has_summary": True, "summary_md": "Chapter 1 content."},
            {"id": 11, "title": "Chapter 2", "order_index": 1, "depth": 0,
             "has_summary": True, "summary_md": "Chapter 2 content."},
        ]
        svc = ExportService(db_session)
        body, is_empty = await svc._render_summary_markdown(
            _book_data(sections=sections), ExportSelection()
        )
        assert "## Chapter 1" in body
        assert "## Chapter 2" in body
        assert "Chapter 1 content." in body
        assert "Chapter 2 content." in body
        assert is_empty is False

    @pytest.mark.asyncio
    async def test_sections_without_summary_skipped(self, db_session):
        sections = [
            {"id": 10, "title": "Pending", "order_index": 0, "depth": 0,
             "has_summary": False, "summary_md": None},
            {"id": 11, "title": "Done", "order_index": 1, "depth": 0,
             "has_summary": True, "summary_md": "Real content."},
        ]
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=sections), ExportSelection()
        )
        assert "## Pending" not in body
        assert "## Done" in body

    @pytest.mark.asyncio
    async def test_excluded_section_skipped(self, db_session):
        sections = [
            {"id": 10, "title": "Keep", "order_index": 0, "depth": 0,
             "has_summary": True, "summary_md": "K"},
            {"id": 11, "title": "Drop", "order_index": 1, "depth": 0,
             "has_summary": True, "summary_md": "D"},
        ]
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=sections),
            ExportSelection(exclude_section_ids=frozenset({11})),
        )
        assert "## Keep" in body
        assert "## Drop" not in body

    @pytest.mark.asyncio
    async def test_image_sanitization_applies_to_section_summary(self, db_session):
        sections = [
            {"id": 10, "title": "Ch", "order_index": 0, "depth": 0,
             "has_summary": True,
             "summary_md": "See ![figure](/api/v1/images/3) below."},
        ]
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=sections), ExportSelection()
        )
        assert "[Image: figure]" in body
        assert "/api/v1/images/" not in body

    @pytest.mark.asyncio
    async def test_image_sanitization_applies_to_book_summary(self, db_session):
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(summary="Chart ![alt](/api/v1/images/9) is here."),
            ExportSelection(),
        )
        assert "[Image: alt]" in body
        assert "/api/v1/images/" not in body

    @pytest.mark.asyncio
    async def test_emptiness_tuple_invariant(self, db_session):
        svc = ExportService(db_session)
        _, is_empty = await svc._render_summary_markdown(
            _book_data(summary="x", sections=[
                {"id": 1, "title": "S", "order_index": 0, "depth": 0,
                 "has_summary": True, "summary_md": "y"}
            ]),
            ExportSelection(
                include_book_summary=False,
                include_toc=False,
                include_annotations=False,
                exclude_section_ids=frozenset({1}),
            ),
        )
        assert is_empty is True
