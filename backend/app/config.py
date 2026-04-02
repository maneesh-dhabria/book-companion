"""Configuration management via pydantic-settings with YAML file support."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion"


class LLMConfig(BaseModel):
    provider: str = "claude_cli"
    cli_command: str = "claude"
    model: str = "sonnet"
    quick_summary_model: str = "sonnet"
    timeout_seconds: int = 300
    max_retries: int = 2
    max_budget_usd: float = 5.0
    cross_summary_consistency: bool = True


class SummarizationConfig(BaseModel):
    default_detail_level: str = "standard"  # brief | standard | detailed
    prompt_version: str = "v1"
    eval_prompt_version: str = "v1"


class EmbeddingConfig(BaseModel):
    ollama_url: str = "http://localhost:11434"
    model: str = "nomic-embed-text"
    chunk_size: int = 512
    chunk_overlap: int = 50


class SearchConfig(BaseModel):
    rrf_k: int = 60
    default_limit: int = 20


class StorageConfig(BaseModel):
    max_file_size_mb: int = 200


class LoggingConfig(BaseModel):
    level: str = "INFO"
    log_dir: str = "~/.config/bookcompanion/logs/"
    json_format: bool = True
    rotation: str = "daily"


def _load_yaml_config() -> dict[str, Any]:
    """Load config from YAML file if it exists. Priority: env var > XDG > fallback."""
    candidates = [
        os.environ.get("BOOKCOMPANION_CONFIG", ""),
        os.path.expanduser("~/.config/bookcompanion/config.yaml"),
        os.path.expanduser("~/.bookcompanion/config.yaml"),
    ]
    for config_path in candidates:
        if not config_path:
            continue
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f) or {}
    return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOOKCOMPANION_",
        env_nested_delimiter="__",
    )

    database: DatabaseConfig = DatabaseConfig()
    llm: LLMConfig = LLMConfig()
    summarization: SummarizationConfig = SummarizationConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    search: SearchConfig = SearchConfig()
    storage: StorageConfig = StorageConfig()
    logging: LoggingConfig = LoggingConfig()

    def model_post_init(self, __context: Any) -> None:
        """Merge YAML config file values (lower priority than env vars)."""
        yaml_config = _load_yaml_config()
        if not yaml_config:
            return
        for section_name, section_values in yaml_config.items():
            if hasattr(self, section_name) and isinstance(section_values, dict):
                section = getattr(self, section_name)
                for key, value in section_values.items():
                    if hasattr(section, key):
                        env_key = f"BOOKCOMPANION_{section_name.upper()}__{key.upper()}"
                        if env_key not in os.environ:
                            object.__setattr__(section, key, value)
