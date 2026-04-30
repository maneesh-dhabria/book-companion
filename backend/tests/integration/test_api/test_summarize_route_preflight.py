"""T9 / FR-B10: POST /books/:id/summarize must 400 when no LLM CLI is usable."""

from unittest.mock import patch

import pytest

from app.services.llm_preflight import get_preflight_service


@pytest.fixture
async def seeded_book(app):
    """Insert a minimal book so the summarize route can route to a real id."""
    from app.db.models import Book, BookStatus

    factory = app.state.session_factory
    async with factory() as session:
        book = Book(
            title="T",
            file_data=b"",
            file_hash="hash-preflight-test",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.PARSED,
        )
        session.add(book)
        await session.commit()
        book_id = book.id
    yield book_id


@pytest.fixture(autouse=True)
def _force_auto_provider(app):
    """Force provider=auto on both app.state.settings and the module-level
    `app.api.deps._settings` cache, since the route reaches settings via
    the latter."""
    from app.api import deps as api_deps

    object.__setattr__(app.state.settings.llm, "provider", "auto")
    if api_deps._settings is not None:
        object.__setattr__(api_deps._settings.llm, "provider", "auto")
    get_preflight_service().invalidate_cache()
    yield
    get_preflight_service().invalidate_cache()


@pytest.mark.asyncio
async def test_summarize_returns_400_when_no_cli(client, seeded_book):
    with (
        patch("app.services.llm_preflight.shutil.which", lambda b: None),
        patch("app.services.summarizer.shutil.which", lambda b: None),
    ):
        r = await client.post(
            f"/api/v1/books/{seeded_book}/summarize",
            json={"preset_name": "practitioner_bullets"},
        )
    assert r.status_code == 400
    body = r.json()
    detail = body["detail"]
    assert detail["error_code"] == "llm_provider_unavailable"
    assert detail["preflight"]["binary_resolved"] is False
    assert detail["preflight"]["reason"]


@pytest.mark.asyncio
async def test_summarize_passes_preflight_when_cli_present(client, seeded_book):
    """When CLI is present and version-ok, the route should NOT 400 with
    the preflight error code. (It may still fail later for real reasons,
    but not at the preflight gate.)"""
    from unittest.mock import AsyncMock

    proc = AsyncMock()
    proc.communicate.return_value = (b"claude 2.1.0\n", b"")
    proc.returncode = 0

    def which(b):
        return "/usr/local/bin/claude" if b == "claude" else None

    with (
        patch("app.services.llm_preflight.shutil.which", which),
        patch("app.services.summarizer.shutil.which", which),
        patch("asyncio.create_subprocess_exec", return_value=proc),
    ):
        r = await client.post(
            f"/api/v1/books/{seeded_book}/summarize",
            json={"preset_name": "practitioner_bullets"},
        )
    # Either 200 (job created) or 409 (concurrent job) is acceptable; what
    # matters is the preflight gate did NOT fire.
    if r.status_code == 400:
        assert r.json().get("detail", {}).get("error_code") != "llm_provider_unavailable"


@pytest.mark.asyncio
async def test_summarize_blocked_for_unknown_book_returns_404_not_400(
    client, seeded_book
):
    """The 404 (book not found) check happens before preflight, so a non-existent
    book must NOT leak preflight info even when the CLI is missing."""
    with patch("app.services.llm_preflight.shutil.which", lambda b: None):
        r = await client.post(
            "/api/v1/books/999999/summarize",
            json={"preset_name": "practitioner_bullets"},
        )
    assert r.status_code == 404
