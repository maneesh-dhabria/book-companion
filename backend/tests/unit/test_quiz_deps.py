"""Tests for FastAPI quiz DI: graceful degradation when LLM/quiz disabled."""

from app.api import deps as api_deps
from app.config import Settings


def test_get_quiz_service_returns_none_when_no_provider(monkeypatch):
    monkeypatch.setattr(api_deps, "_get_llm_provider", lambda settings: None)
    settings = Settings()
    settings.quiz.enabled = True  # default — but be explicit
    svc = api_deps.get_quiz_service(db=None, settings=settings)
    assert svc is None


def test_get_quiz_service_returns_none_when_quiz_disabled(monkeypatch):
    # Even with a provider, disabled config short-circuits
    class _StubProvider:
        pass

    monkeypatch.setattr(api_deps, "_get_llm_provider", lambda settings: _StubProvider())
    settings = Settings()
    settings.quiz.enabled = False
    svc = api_deps.get_quiz_service(db=None, settings=settings)
    assert svc is None


def test_get_quiz_service_constructs_when_provider_and_enabled(monkeypatch):
    class _StubProvider:
        pass

    monkeypatch.setattr(api_deps, "_get_llm_provider", lambda settings: _StubProvider())
    settings = Settings()
    settings.quiz.enabled = True
    svc = api_deps.get_quiz_service(db="db_sentinel", settings=settings)
    assert svc is not None
    assert svc.session == "db_sentinel"
    assert svc.settings is settings
