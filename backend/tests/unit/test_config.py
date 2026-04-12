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
    # Data directory uses platformdirs
    assert "bookcompanion" in settings.data.directory
    # Database URL is SQLite in data dir
    assert "sqlite+aiosqlite" in settings.database.url
    assert "library.db" in settings.database.url
    # LLM config
    assert settings.llm.cli_command == "claude"
    assert settings.llm.model == "sonnet"
    assert settings.llm.timeout_seconds == 300
    # Embedding config — no more ollama fields
    assert not hasattr(settings.embedding, "ollama_url")
    assert not hasattr(settings.embedding, "model")
    assert settings.embedding.chunk_size == 512
    assert settings.embedding.chunk_overlap == 50
    # Search
    assert settings.search.rrf_k == 60
    assert settings.search.default_limit == 20
    assert settings.storage.max_file_size_mb == 200
    assert settings.summarization.default_preset == "practitioner_bullets"
    # Backup config
    assert settings.backup.frequency == "daily"
    assert settings.backup.max_backups == 5
    assert "backups" in settings.backup.directory


def test_env_var_override():
    """Environment variables override defaults."""
    os.environ["BOOKCOMPANION_LLM__MODEL"] = "opus"
    settings = Settings()
    assert settings.llm.model == "opus"


def test_config_file_loading(tmp_path):
    """Settings load from YAML config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "database:\n  url: sqlite+aiosqlite:///custom.db\n"
        "llm:\n  model: opus\n"
    )
    os.environ["BOOKCOMPANION_CONFIG"] = str(config_file)
    settings = Settings()
    assert settings.llm.model == "opus"


def test_data_dir_env_override():
    """BOOKCOMPANION_DATA__DIRECTORY overrides default."""
    os.environ["BOOKCOMPANION_DATA__DIRECTORY"] = "/tmp/bc-test"
    settings = Settings()
    assert settings.data.directory == "/tmp/bc-test"
    assert "/tmp/bc-test/library.db" in settings.database.url


def test_summarization_default_preset():
    """V1.1: SummarizationConfig uses default_preset instead of default_detail_level."""
    settings = Settings()
    assert settings.summarization.default_preset == "practitioner_bullets"
    assert not hasattr(settings.summarization, "default_detail_level")
    assert not hasattr(settings.summarization, "prompt_version")


def test_config_min_section_chars():
    """V1.2: min_section_chars defaults to 200."""
    settings = Settings()
    assert settings.summarization.min_section_chars == 200
