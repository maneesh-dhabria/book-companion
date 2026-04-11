"""Settings service — read/write YAML config, DB stats, migration status."""

import tempfile
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings

DEFAULT_CONFIG_PATH = Path("~/.config/bookcompanion/config.yaml").expanduser()

# Fields that should never appear in plain text in API responses
_SENSITIVE_FIELDS = {"password", "access_token", "secret"}


class SettingsService:
    def __init__(self, settings: Settings, config_path: Path | None = None):
        self.settings = settings
        self.config_path = config_path or DEFAULT_CONFIG_PATH

    def get_safe_settings(self) -> dict:
        """Return settings with sensitive values masked."""
        data = {
            "network": {
                "host": self.settings.network.host,
                "port": self.settings.network.port,
                "allow_lan": self.settings.network.allow_lan,
                "access_token": "***" if self.settings.network.access_token else None,
            },
            "llm": {
                "provider": self.settings.llm.provider,
                "model": self.settings.llm.model,
                "timeout_seconds": self.settings.llm.timeout_seconds,
                "max_retries": self.settings.llm.max_retries,
                "max_budget_usd": self.settings.llm.max_budget_usd,
            },
            "summarization": {
                "default_preset": self.settings.summarization.default_preset,
            },
            "web": {
                "show_cost_estimates": self.settings.web.show_cost_estimates,
            },
        }
        return data

    def update_settings(self, updates: dict) -> dict:
        """Write partial settings to YAML config file using atomic write.

        Reads existing YAML, deep-merges updates, writes to a temp file,
        then renames for atomicity. Also updates the in-memory Settings.
        """
        # Read existing config
        existing = {}
        if self.config_path.exists():
            with open(self.config_path) as f:
                existing = yaml.safe_load(f) or {}

        # Deep merge updates into existing
        for section, values in updates.items():
            if isinstance(values, dict):
                if section not in existing:
                    existing[section] = {}
                existing[section].update(values)
            else:
                existing[section] = values

        # Atomic write: temp file + rename
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(self.config_path.parent),
            suffix=".yaml",
            delete=False,
        ) as tmp:
            yaml.dump(existing, tmp, default_flow_style=False)
            tmp_path = Path(tmp.name)
        tmp_path.rename(self.config_path)

        # Update in-memory settings
        for section_name, section_values in updates.items():
            if hasattr(self.settings, section_name) and isinstance(section_values, dict):
                section = getattr(self.settings, section_name)
                for key, value in section_values.items():
                    if hasattr(section, key):
                        object.__setattr__(section, key, value)

        return self.get_safe_settings()

    async def get_database_stats(self, session: AsyncSession) -> dict:
        """Count rows in each table."""
        tables = [
            "books",
            "book_sections",
            "summaries",
            "annotations",
            "concepts",
            "eval_traces",
        ]
        stats = {}
        for table in tables:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608
            stats[table] = result.scalar()
        return stats

    async def get_migration_status(self) -> dict:
        """Check current vs latest Alembic revision."""
        import asyncio

        try:
            proc = await asyncio.create_subprocess_exec(
                "uv",
                "run",
                "alembic",
                "heads",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            latest = stdout.decode().strip().split("\n")[0].split(" ")[0] if stdout else None

            proc2 = await asyncio.create_subprocess_exec(
                "uv",
                "run",
                "alembic",
                "current",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout2, _ = await proc2.communicate()
            current_line = stdout2.decode().strip().split("\n")[0] if stdout2 else ""
            current = current_line.split(" ")[0] if current_line else None

            return {
                "current": current,
                "latest": latest,
                "is_behind": current != latest if (current and latest) else False,
            }
        except Exception:
            return {"current": None, "latest": None, "is_behind": False}
