"""Tests for summarizer service."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import BookSection
from app.services.summarizer.llm_provider import LLMResponse
from app.services.summarizer.summarizer_service import SummarizerService


def make_mock_section(section_id=1, title="Chapter 1", content="Test content " * 50):
    section = MagicMock(spec=BookSection)
    section.id = section_id
    section.title = title
    section.content_md = content
    section.content_token_count = len(content.split())
    section.default_summary_id = None
    section.images = []
    return section


def make_mock_book(book_id=1, title="Test Book", authors=None):
    book = MagicMock()
    book.id = book_id
    book.title = title
    if authors is None:
        author = MagicMock()
        author.name = "Test Author"
        book.authors = [author]
    else:
        book.authors = authors
    return book


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.llm.model = "sonnet"
    return config


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate.return_value = LLMResponse(
        content=json.dumps(
            {
                "key_concepts": ["concept1"],
                "detailed_summary": "This section covers strategy.",
                "frameworks": [],
                "key_quotes": [],
                "concepts": [],
            }
        ),
        model="sonnet",
        input_tokens=100,
        output_tokens=50,
        latency_ms=1000,
    )
    return llm


def test_service_instantiation(mock_config, mock_llm):
    """SummarizerService can be instantiated with the new signature."""
    session = AsyncMock()
    service = SummarizerService(db=session, llm=mock_llm, config=mock_config, captioner=None)
    assert service._summary_repo is not None
    assert service._section_repo is not None
    assert service._book_repo is not None


def test_extract_summary_text_json():
    """_extract_summary_text extracts detailed_summary from JSON response."""
    service = SummarizerService.__new__(SummarizerService)
    response = MagicMock()
    response.content = json.dumps({"detailed_summary": "The summary."})
    assert service._extract_summary_text(response) == "The summary."


def test_extract_summary_text_plain():
    """_extract_summary_text falls back to raw content on non-JSON."""
    service = SummarizerService.__new__(SummarizerService)
    response = MagicMock()
    response.content = "Just plain text."
    assert service._extract_summary_text(response) == "Just plain text."


def test_imports_clean():
    """All new imports resolve without errors."""
    from app.db.models import Summary, SummaryContentType
    from app.db.repositories.book_repo import BookRepository
    from app.db.repositories.section_repo import SectionRepository
    from app.db.repositories.summary_repo import SummaryRepository

    assert Summary is not None
    assert SummaryContentType is not None
    assert SummaryRepository is not None
    assert SectionRepository is not None
    assert BookRepository is not None


@pytest.mark.asyncio
async def test_summarize_book_accepts_facets(mock_config, mock_llm):
    """summarize_book accepts preset_name and facets dict."""
    session = AsyncMock()
    service = SummarizerService(db=session, llm=mock_llm, config=mock_config)

    # Mock repos
    service._section_repo = AsyncMock()
    service._section_repo.get_by_book_id.return_value = []

    result = await service.summarize_book(
        book_id=1,
        preset_name="practitioner_bullets",
        facets={
            "style": "bullet_points",
            "audience": "practitioner",
            "compression": "standard",
            "content_focus": "actionable",
        },
    )
    assert result == {"completed": 0, "skipped": 0, "failed": []}


@pytest.mark.asyncio
async def test_summarize_book_skips_existing(mock_config, mock_llm):
    """summarize_book skips sections that already have a summary for the given facets."""
    session = AsyncMock()
    service = SummarizerService(db=session, llm=mock_llm, config=mock_config)

    section = make_mock_section()
    service._section_repo = AsyncMock()
    service._section_repo.get_by_book_id.return_value = [section]

    existing_summary = MagicMock()
    existing_summary.summary_md = "Already summarized."
    service._summary_repo = AsyncMock()
    service._summary_repo.get_latest_by_content_and_facets.return_value = existing_summary

    skip_cb = MagicMock()
    result = await service.summarize_book(
        book_id=1,
        facets={
            "style": "bullet_points",
            "audience": "practitioner",
            "compression": "standard",
            "content_focus": "actionable",
        },
        on_section_skip=skip_cb,
    )
    assert result["skipped"] == 1
    assert result["completed"] == 0
    skip_cb.assert_called_once_with(1, 1, "Chapter 1", "already summarized")


@pytest.mark.asyncio
async def test_summarize_book_force_resumes(mock_config, mock_llm):
    """summarize_book with force=True does not skip even if summary exists."""
    session = AsyncMock()
    service = SummarizerService(db=session, llm=mock_llm, config=mock_config)

    section = make_mock_section()
    service._section_repo = AsyncMock()
    service._section_repo.get_by_book_id.return_value = [section]
    service._summary_repo = AsyncMock()
    service._book_repo = AsyncMock()
    service._book_repo.get_by_id.return_value = make_mock_book()

    # Mock _summarize_single_section to avoid template rendering
    created_summary = MagicMock()
    created_summary.id = 42
    created_summary.summary_md = "New summary."
    created_summary.summary_char_count = 12
    created_summary.input_char_count = 100
    service._summarize_single_section = AsyncMock(return_value=created_summary)

    facets = {
        "style": "bullet_points",
        "audience": "practitioner",
        "compression": "standard",
        "content_focus": "key_concepts",
    }
    result = await service.summarize_book(
        book_id=1,
        facets=facets,
        force=True,
    )
    assert result["completed"] == 1
    assert result["skipped"] == 0
    service._summary_repo.get_latest_by_content_and_facets.assert_not_called()
    service._summarize_single_section.assert_called_once()


def test_extract_summary_text_code_fenced():
    svc = SummarizerService.__new__(SummarizerService)
    response = LLMResponse(content='```json\n{"summary": "extracted text"}\n```', model="test")
    assert svc._extract_summary_text(response) == "extracted text"


def test_extract_summary_text_summary_key():
    svc = SummarizerService.__new__(SummarizerService)
    response = LLMResponse(content='{"summary": "the summary"}', model="test")
    assert svc._extract_summary_text(response) == "the summary"


def test_extract_summary_text_markdown_passthrough():
    svc = SummarizerService.__new__(SummarizerService)
    response = LLMResponse(content="# Chapter Summary\n\nThis is markdown.", model="test")
    result = svc._extract_summary_text(response)
    assert "# Chapter Summary" in result
    assert "This is markdown." in result
