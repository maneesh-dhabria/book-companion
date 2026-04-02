"""Tests for configuration system."""

import os
from pathlib import Path

import pytest

from app.config import Settings

# Path where e2e tests may write config
_CONFIG_PATH = Path("~/.config/bookcompanion/config.yaml").expanduser()


@pytest.fixture(autouse=True)
def clean_env():
    """Ensure clean environment for config tests."""
    # Save and remove any env vars set by other tests
    saved_vars = {}
    for key in list(os.environ.keys()):
        if key.startswith("BOOKCOMPANION_"):
            saved_vars[key] = os.environ.pop(key)

    # Remove any config file from e2e tests
    config_backup = None
    if _CONFIG_PATH.exists():
        config_backup = _CONFIG_PATH.read_text()
        _CONFIG_PATH.unlink()

    yield

    # Restore
    for key, val in saved_vars.items():
        os.environ[key] = val
    if config_backup is not None:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(config_backup)


def test_default_settings():
    """Settings load with sensible defaults."""
    settings = Settings()
    assert settings.database.url == "postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion"
    assert settings.llm.cli_command == "claude"
    assert settings.llm.model == "sonnet"
    assert settings.llm.timeout_seconds == 300
    assert settings.embedding.ollama_url == "http://localhost:11434"
    assert settings.embedding.model == "nomic-embed-text"
    assert settings.embedding.chunk_size == 512
    assert settings.embedding.chunk_overlap == 50
    assert settings.search.rrf_k == 60
    assert settings.search.default_limit == 20
    assert settings.storage.max_file_size_mb == 200
    assert settings.summarization.default_detail_level == "standard"


def test_env_var_override():
    """Environment variables override defaults."""
    os.environ["BOOKCOMPANION_LLM__MODEL"] = "opus"
    settings = Settings()
    assert settings.llm.model == "opus"


def test_config_file_loading(tmp_path):
    """Settings load from YAML config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "database:\n  url: postgresql+asyncpg://custom:custom@localhost:5432/custom\n"
        "llm:\n  model: opus\n"
    )
    os.environ["BOOKCOMPANION_CONFIG"] = str(config_file)
    settings = Settings()
    assert settings.llm.model == "opus"
