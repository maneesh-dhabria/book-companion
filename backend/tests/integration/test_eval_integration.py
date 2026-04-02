"""Integration tests for eval assertions."""

import pytest

pytestmark = pytest.mark.integration_llm


@pytest.mark.asyncio
async def test_eval_single_assertion(db_session, test_settings):
    """Run one eval assertion with real LLM."""
    pass  # Implement after Task 20
