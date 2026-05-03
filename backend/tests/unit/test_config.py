"""Tests for configuration system."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import LLMConfig, Settings, TTSConfig

# Paths where Settings looks for YAML config (mirrors app.config._load_yaml_config)
_YAML_PATHS = [
    Path("~/.config/bookcompanion/settings.yaml").expanduser(),
    Path("~/.config/bookcompanion/config.yaml").expanduser(),
    Path("~/.bookcompanion/settings.yaml").expanduser(),
    Path("~/.bookcompanion/config.yaml").expanduser(),
]


@pytest.fixture(autouse=True)
def clean_env():
    """Ensure clean environment for config tests."""
    # Save and remove any env vars set by other tests
    saved_vars = {}
    for key in list(os.environ.keys()):
        if key.startswith("BOOKCOMPANION_"):
            saved_vars[key] = os.environ.pop(key)

    # Stash + remove any user YAML configs so default-settings tests are deterministic
    backups: dict[Path, str] = {}
    for p in _YAML_PATHS:
        if p.exists():
            backups[p] = p.read_text()
            p.unlink()

    yield

    # Restore env + YAML files
    for key, val in saved_vars.items():
        os.environ[key] = val
    for p, content in backups.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def test_default_settings():
    """Settings load with sensible defaults."""
    settings = Settings()
    # Data directory uses platformdirs
    assert "bookcompanion" in settings.data.directory
    # Database URL is SQLite in data dir
    assert "sqlite+aiosqlite" in settings.database.url
    assert "library.db" in settings.database.url
    # LLM config
    assert settings.llm.config_dir is None
    assert not hasattr(settings.llm, "cli_command")
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


def test_llm_config_accepts_config_dir(tmp_path):
    cfg = LLMConfig(config_dir=tmp_path)
    assert cfg.config_dir == tmp_path


def test_llm_config_config_dir_default_none():
    cfg = LLMConfig()
    assert cfg.config_dir is None


def test_llm_config_rejects_cli_command():
    with pytest.raises(ValidationError):
        LLMConfig(cli_command="claude")


def test_llm_config_accepts_path_string():
    cfg = LLMConfig(config_dir="/tmp/some-claude-config")
    assert isinstance(cfg.config_dir, Path)


def test_tts_config_defaults():
    settings = Settings()
    assert settings.tts.engine == "web-speech"
    assert settings.tts.voice == ""
    assert settings.tts.default_speed == 1.0
    assert settings.tts.auto_advance is True
    assert settings.tts.prewarm_on_startup is True
    assert settings.tts.annotation_context == "span"


def test_tts_config_env_override(monkeypatch):
    monkeypatch.setenv("BOOKCOMPANION_TTS__ENGINE", "kokoro")
    monkeypatch.setenv("BOOKCOMPANION_TTS__VOICE", "af_sarah")
    settings = Settings()
    assert settings.tts.engine == "kokoro"
    assert settings.tts.voice == "af_sarah"


def test_tts_config_invalid_engine_rejected():
    with pytest.raises(ValidationError):
        TTSConfig(engine="bogus")


def test_tts_config_speed_bounds():
    with pytest.raises(ValidationError):
        TTSConfig(default_speed=0.4)
    with pytest.raises(ValidationError):
        TTSConfig(default_speed=2.1)
