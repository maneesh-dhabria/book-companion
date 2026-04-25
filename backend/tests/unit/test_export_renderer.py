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
        body, _ = await svc._render_summary_markdown(_book_data(authors=[]), ExportSelection())
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
            {
                "id": 10,
                "title": "Chapter 1",
                "order_index": 0,
                "depth": 0,
                "has_summary": True,
                "summary_md": "Chapter 1 content.",
            },
            {
                "id": 11,
                "title": "Chapter 2",
                "order_index": 1,
                "depth": 0,
                "has_summary": True,
                "summary_md": "Chapter 2 content.",
            },
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
            {
                "id": 10,
                "title": "Pending",
                "order_index": 0,
                "depth": 0,
                "has_summary": False,
                "summary_md": None,
            },
            {
                "id": 11,
                "title": "Done",
                "order_index": 1,
                "depth": 0,
                "has_summary": True,
                "summary_md": "Real content.",
            },
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
            {
                "id": 10,
                "title": "Keep",
                "order_index": 0,
                "depth": 0,
                "has_summary": True,
                "summary_md": "K",
            },
            {
                "id": 11,
                "title": "Drop",
                "order_index": 1,
                "depth": 0,
                "has_summary": True,
                "summary_md": "D",
            },
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
            {
                "id": 10,
                "title": "Ch",
                "order_index": 0,
                "depth": 0,
                "has_summary": True,
                "summary_md": "See ![figure](/api/v1/images/3) below.",
            },
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
            _book_data(
                summary="x",
                sections=[
                    {
                        "id": 1,
                        "title": "S",
                        "order_index": 0,
                        "depth": 0,
                        "has_summary": True,
                        "summary_md": "y",
                    }
                ],
            ),
            ExportSelection(
                include_book_summary=False,
                include_toc=False,
                include_annotations=False,
                exclude_section_ids=frozenset({1}),
            ),
        )
        assert is_empty is True


class TestRenderSummaryMarkdownTOC:
    @pytest.mark.asyncio
    async def test_toc_emitted_with_anchors(self, db_session):
        sections = [
            {
                "id": 1,
                "title": "Chapter 1",
                "order_index": 0,
                "depth": 0,
                "has_summary": True,
                "summary_md": "x",
            },
            {
                "id": 2,
                "title": "Chapter 2",
                "order_index": 1,
                "depth": 0,
                "has_summary": True,
                "summary_md": "y",
            },
        ]
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=sections), ExportSelection()
        )
        assert "## Table of Contents" in body
        assert "- [Chapter 1](#chapter-1)" in body
        assert "- [Chapter 2](#chapter-2)" in body

    @pytest.mark.asyncio
    async def test_toc_indents_by_depth(self, db_session):
        sections = [
            {
                "id": 1,
                "title": "Part 1",
                "order_index": 0,
                "depth": 0,
                "has_summary": True,
                "summary_md": "a",
            },
            {
                "id": 2,
                "title": "Sub",
                "order_index": 1,
                "depth": 1,
                "has_summary": True,
                "summary_md": "b",
            },
        ]
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=sections), ExportSelection()
        )
        assert "- [Part 1](#part-1)" in body
        assert "  - [Sub](#sub)" in body

    @pytest.mark.asyncio
    async def test_toc_omitted_when_no_sections_render(self, db_session):
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(_book_data(), ExportSelection())
        assert "## Table of Contents" not in body

    @pytest.mark.asyncio
    async def test_toc_omitted_when_toggle_off(self, db_session):
        sections = [
            {
                "id": 1,
                "title": "Chapter 1",
                "order_index": 0,
                "depth": 0,
                "has_summary": True,
                "summary_md": "x",
            },
        ]
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=sections), ExportSelection(include_toc=False)
        )
        assert "## Table of Contents" not in body
        assert "## Chapter 1" in body

    @pytest.mark.asyncio
    async def test_duplicate_titles_disambiguate_with_dash_n(self, db_session):
        sections = [
            {
                "id": 1,
                "title": "Intro",
                "order_index": 0,
                "depth": 0,
                "has_summary": True,
                "summary_md": "a",
            },
            {
                "id": 2,
                "title": "Intro",
                "order_index": 1,
                "depth": 0,
                "has_summary": True,
                "summary_md": "b",
            },
            {
                "id": 3,
                "title": "Intro",
                "order_index": 2,
                "depth": 0,
                "has_summary": True,
                "summary_md": "c",
            },
        ]
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=sections), ExportSelection()
        )
        assert "(#intro)" in body
        assert "(#intro-1)" in body
        assert "(#intro-2)" in body

    @pytest.mark.asyncio
    async def test_empty_slug_falls_back_to_section_orderindex(self, db_session):
        sections = [
            {
                "id": 1,
                "title": "🚀🎯",
                "order_index": 7,
                "depth": 0,
                "has_summary": True,
                "summary_md": "a",
            },
        ]
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=sections), ExportSelection()
        )
        assert "[🚀🎯](#section-007)" in body

    @pytest.mark.asyncio
    async def test_toc_emitted_flag_drives_emptiness(self, db_session):
        sections = [
            {
                "id": 1,
                "title": "Ch",
                "order_index": 0,
                "depth": 0,
                "has_summary": True,
                "summary_md": "a",
            },
        ]
        svc = ExportService(db_session)
        _, is_empty = await svc._render_summary_markdown(
            _book_data(sections=sections),
            ExportSelection(include_book_summary=False, include_annotations=False),
        )
        assert is_empty is False


class TestRenderSummaryMarkdownAnnotations:
    def _section(self, id_):
        return {
            "id": id_,
            "title": f"S{id_}",
            "order_index": id_,
            "depth": 0,
            "has_summary": True,
            "summary_md": "body",
        }

    @pytest.mark.asyncio
    async def test_section_highlight_with_note(self, db_session):
        ann = {
            "id": 1,
            "content_type": "section_summary",
            "content_id": 1,
            "selected_text": "famous quote",
            "note": "interesting",
            "type": "highlight",
        }
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=[self._section(1)]) | {"annotations": [ann]},
            ExportSelection(),
        )
        assert "### Highlights" in body
        assert "> famous quote" in body
        assert "> — Note: interesting" in body

    @pytest.mark.asyncio
    async def test_section_highlight_no_note(self, db_session):
        ann = {
            "id": 1,
            "content_type": "section_summary",
            "content_id": 1,
            "selected_text": "just a passage",
            "note": "",
            "type": "highlight",
        }
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=[self._section(1)]) | {"annotations": [ann]},
            ExportSelection(),
        )
        assert "> just a passage" in body
        assert "Note:" not in body

    @pytest.mark.asyncio
    async def test_section_annotation_empty_selected_text_skipped(self, db_session):
        ann = {
            "id": 1,
            "content_type": "section_summary",
            "content_id": 1,
            "selected_text": "",
            "note": "stray note",
            "type": "note",
        }
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=[self._section(1)]) | {"annotations": [ann]},
            ExportSelection(),
        )
        assert "### Highlights" not in body
        assert "stray note" not in body

    @pytest.mark.asyncio
    async def test_annotations_toggle_off(self, db_session):
        ann = {
            "id": 1,
            "content_type": "section_summary",
            "content_id": 1,
            "selected_text": "x",
            "note": "y",
            "type": "highlight",
        }
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(sections=[self._section(1)]) | {"annotations": [ann]},
            ExportSelection(include_annotations=False),
        )
        assert "### Highlights" not in body

    @pytest.mark.asyncio
    async def test_excluded_section_drops_its_annotations(self, db_session):
        ann = {
            "id": 1,
            "content_type": "section_summary",
            "content_id": 5,
            "selected_text": "should not appear",
            "note": "",
            "type": "highlight",
        }
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(
                sections=[
                    self._section(1),
                    {
                        "id": 5,
                        "title": "S5",
                        "order_index": 5,
                        "depth": 0,
                        "has_summary": True,
                        "summary_md": "x",
                    },
                ]
            )
            | {"annotations": [ann]},
            ExportSelection(exclude_section_ids=frozenset({5})),
        )
        assert "should not appear" not in body

    @pytest.mark.asyncio
    async def test_book_scope_note_in_notes_footer(self, db_session):
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(),
            ExportSelection(),
            book_annotations=[
                {"id": 1, "selected_text": "", "note": "freeform reader note", "type": "note"}
            ],
        )
        assert "## Notes" in body
        assert "- freeform reader note" in body

    @pytest.mark.asyncio
    async def test_book_scope_highlight_with_and_without_note(self, db_session):
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(),
            ExportSelection(),
            book_annotations=[
                {"id": 1, "selected_text": "great quote", "note": "with note", "type": "highlight"},
                {"id": 2, "selected_text": "lone quote", "note": "", "type": "highlight"},
            ],
        )
        assert '- > "great quote"' in body
        assert "  — with note" in body
        assert '- > "lone quote"' in body

    @pytest.mark.asyncio
    async def test_notes_footer_omitted_when_no_book_anns(self, db_session):
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(), ExportSelection(), book_annotations=[]
        )
        assert "## Notes" not in body

    @pytest.mark.asyncio
    async def test_book_anns_survive_section_exclusion(self, db_session):
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(
                sections=[
                    {
                        "id": 1,
                        "title": "S1",
                        "order_index": 0,
                        "depth": 0,
                        "has_summary": True,
                        "summary_md": "a",
                    },
                ]
            ),
            ExportSelection(exclude_section_ids=frozenset({1})),
            book_annotations=[{"id": 1, "selected_text": "", "note": "kept", "type": "note"}],
        )
        assert "kept" in body

    @pytest.mark.asyncio
    async def test_newlines_in_selected_text_collapse_to_space(self, db_session):
        ann = {
            "id": 1,
            "content_type": "section_summary",
            "content_id": 1,
            "selected_text": "line1\nline2",
            "note": "",
            "type": "highlight",
        }
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(
                sections=[
                    {
                        "id": 1,
                        "title": "S",
                        "order_index": 0,
                        "depth": 0,
                        "has_summary": True,
                        "summary_md": "x",
                    },
                ]
            )
            | {"annotations": [ann]},
            ExportSelection(),
        )
        assert "> line1 line2" in body
        assert "> line1\nline2" not in body

    @pytest.mark.asyncio
    async def test_block_level_chars_escaped(self, db_session):
        ann = {
            "id": 1,
            "content_type": "section_summary",
            "content_id": 1,
            "selected_text": "> nested quote attempt",
            "note": "# heading attempt",
            "type": "highlight",
        }
        svc = ExportService(db_session)
        body, _ = await svc._render_summary_markdown(
            _book_data(
                sections=[
                    {
                        "id": 1,
                        "title": "S",
                        "order_index": 0,
                        "depth": 0,
                        "has_summary": True,
                        "summary_md": "x",
                    },
                ]
            )
            | {"annotations": [ann]},
            ExportSelection(),
        )
        assert r"> \> nested quote attempt" in body
        assert r"\# heading attempt" in body

    @pytest.mark.asyncio
    async def test_emptiness_with_only_book_notes(self, db_session):
        svc = ExportService(db_session)
        _, is_empty = await svc._render_summary_markdown(
            _book_data(),
            ExportSelection(include_book_summary=False, include_toc=False),
            book_annotations=[{"id": 1, "selected_text": "", "note": "x", "type": "note"}],
        )
        assert is_empty is False


class TestExportBookMarkdownPublic:
    @pytest.mark.asyncio
    async def test_returns_body_and_is_empty(self, db_session):
        from app.db.models import Book, BookStatus

        book = Book(
            title="Pub Test",
            file_data=b"",
            file_hash="pub-hash",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.COMPLETED,
        )
        db_session.add(book)
        await db_session.commit()
        svc = ExportService(db_session)
        body, is_empty = await svc.export_book_markdown(book.id, ExportSelection())
        assert body.startswith("# Pub Test\n")
        assert is_empty is True

    @pytest.mark.asyncio
    async def test_raises_export_error_for_missing_book(self, db_session):
        from app.services.export_service import ExportError

        svc = ExportService(db_session)
        with pytest.raises(ExportError, match="not found"):
            await svc.export_book_markdown(99999, ExportSelection())
