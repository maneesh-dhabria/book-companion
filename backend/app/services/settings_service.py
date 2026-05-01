"""Settings service — read/write YAML config, DB stats, migration status.

Also exposes:
* ``load_models()`` — read the shipped ``backend/app/config/models.yaml``
  LLM candidate list, falling back to a hard-coded minimal set if the
  file is missing or malformed.
* ``load_user_config()`` / ``persist_patch()`` — deep-merge writes to the
  XDG-resolved ``~/.config/bookcompanion/settings.yaml`` (platformdirs).
  Used by PATCH /api/v1/settings + CLI ``model set``.
"""

import tempfile
from pathlib import Path
from typing import Any

import structlog
import yaml
from platformdirs import user_config_dir
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.config import Settings

logger = structlog.get_logger(__name__)

DEFAULT_CONFIG_PATH = Path("~/.config/bookcompanion/settings.yaml").expanduser()

# Fields that should never appear in plain text in API responses
_SENSITIVE_FIELDS = {"password", "access_token", "secret"}

_FALLBACK_MODELS: dict[str, Any] = {
    "providers": {
        "claude": [
            {"id": "sonnet", "label": "Claude Sonnet"},
            {"id": "opus", "label": "Claude Opus"},
            {"id": "haiku", "label": "Claude Haiku"},
        ],
        "codex": [
            {"id": "o4-mini", "label": "OpenAI o4-mini"},
        ],
    }
}


def default_models_yaml_path() -> Path:
    """Path to the shipped models.yaml — valid for editable + wheel installs."""
    return Path(__file__).resolve().parent.parent / "config" / "models.yaml"


def default_user_settings_path() -> Path:
    """XDG-resolved path to the per-user settings.yaml."""
    return Path(user_config_dir("bookcompanion")) / "settings.yaml"


class SettingsService:
    def __init__(
        self,
        settings: Settings | None = None,
        config_path: Path | None = None,
        *,
        models_yaml_path: Path | None = None,
        user_config_path: Path | None = None,
        engine: AsyncEngine | None = None,
    ):
        # ``settings`` is optional so unit tests can instantiate with just
        # path kwargs; existing callers pass a Settings as positional arg.
        self.settings = settings
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.models_yaml_path = models_yaml_path or default_models_yaml_path()
        self.user_config_path = user_config_path or default_user_settings_path()
        self.engine = engine

    # --- models.yaml (T8) ---

    def load_models(self) -> dict[str, Any]:
        try:
            with open(self.models_yaml_path) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict) or "providers" not in data:
                raise ValueError("invalid models.yaml shape")
            return data
        except (FileNotFoundError, yaml.YAMLError, ValueError) as e:
            logger.warning(
                "models_yaml_fallback",
                err=str(e),
                path=str(self.models_yaml_path),
            )
            return _FALLBACK_MODELS

    def load_user_config(self) -> dict[str, Any]:
        if self.user_config_path.exists():
            try:
                with open(self.user_config_path) as f:
                    data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
            except yaml.YAMLError as e:
                logger.warning("user_config_yaml_error", err=str(e))
                return {}
        return {}

    def persist_patch(self, patch: dict[str, Any]) -> None:
        current = self.load_user_config()
        merged = self._deep_merge(current, patch)
        self.user_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.user_config_path, "w") as f:
            yaml.safe_dump(merged, f, sort_keys=True)
        logger.info("user_config_persisted", keys=list(patch.keys()))

    @staticmethod
    def _deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = dict(a)
        for k, v in b.items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = SettingsService._deep_merge(out[k], v)
            else:
                out[k] = v
        return out

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
                "config_dir": (
                    str(self.settings.llm.config_dir)
                    if self.settings.llm.config_dir
                    else None
                ),
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
        """Validate + persist a partial settings patch (D17: all-or-nothing).

        Validates every patched section against its own pydantic submodel
        (``extra="forbid"``) before any disk write. Unknown sections, unknown
        nested keys, and type mismatches raise ``pydantic.ValidationError``
        and leave both the in-memory state and the on-disk YAML untouched.
        """
        from pydantic import ValidationError

        # 1. Validate every section in the patch BEFORE any disk write.
        #    Run all sections so we get one ValidationError covering all bad
        #    fields rather than failing on the first.
        # Each value is a validated section submodel (LLMConfig, etc.).
        # Type left untyped here to keep the runtime light — the dict is
        # only consumed in this method and the per-section types differ.
        validated_sections: dict = {}
        errors: list[dict[str, Any]] = []
        for section_name, section_values in updates.items():
            section_obj = getattr(self.settings, section_name, None)
            if section_obj is None:
                errors.append(
                    {
                        "type": "extra_forbidden",
                        "loc": (section_name,),
                        "msg": "Extra inputs are not permitted",
                        "input": section_values,
                    }
                )
                continue
            if not isinstance(section_values, dict):
                errors.append(
                    {
                        "type": "dict_type",
                        "loc": (section_name,),
                        "msg": "Input should be a valid dictionary",
                        "input": section_values,
                    }
                )
                continue
            model_cls = type(section_obj)
            current_dump = section_obj.model_dump()
            try:
                validated_sections[section_name] = model_cls.model_validate(
                    {**current_dump, **section_values}
                )
            except ValidationError as e:
                errors.extend({**err, "loc": (section_name, *err["loc"])} for err in e.errors())

        if errors:
            raise ValidationError.from_exception_data(title=Settings.__name__, line_errors=errors)

        # 2. Read existing YAML and deep-merge ONLY the user's patch.
        existing: dict[str, Any] = {}
        if self.config_path.exists():
            with open(self.config_path) as f:
                existing = yaml.safe_load(f) or {}
        existing = self._deep_merge(existing, updates)

        # 3. Atomic write.
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

        # 4. Apply the validated section values to in-memory Settings.
        for section_name, section_values in updates.items():
            live = getattr(self.settings, section_name)
            fresh = validated_sections[section_name]
            for key in section_values:
                object.__setattr__(live, key, getattr(fresh, key))

        # 5. Invalidate the LLM preflight cache so the next status read
        #    reflects the new provider / config_dir / version-floor outcome
        #    instead of the previous 60s-cached one (FR-B08a).
        try:
            from app.services.llm_preflight import get_preflight_service

            get_preflight_service().invalidate_cache()
        except Exception:  # pragma: no cover - defensive
            logger.warning("preflight_cache_invalidate_failed", exc_info=True)

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
        """Check current vs latest Alembic revision via programmatic API.

        Uses ``ScriptDirectory`` for the head revision (filesystem read) and
        ``MigrationContext`` against the live engine for the current revision.
        Never invokes a subprocess. On any error, returns
        ``{current: None, latest: None, is_behind: False, error: <str>}``.
        """
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        try:
            migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
            ini_path = migrations_dir / "alembic.ini"
            if not ini_path.exists():
                raise FileNotFoundError(f"alembic.ini not found at {ini_path}")

            cfg = Config(str(ini_path))
            cfg.set_main_option("script_location", str(migrations_dir))
            script_dir = ScriptDirectory.from_config(cfg)
            latest = script_dir.get_current_head()

            engine = self.engine
            if engine is None:
                if self.settings is None:
                    raise RuntimeError("no engine and no settings — cannot read current revision")
                from sqlalchemy.ext.asyncio import create_async_engine

                engine = create_async_engine(self.settings.database.url)

            try:
                async with engine.connect() as conn:
                    current = await conn.run_sync(
                        lambda sc: MigrationContext.configure(sc).get_current_revision()
                    )
            finally:
                # Only dispose if we created the engine here.
                if self.engine is None:
                    await engine.dispose()

            return {
                "current": current,
                "latest": latest,
                "is_behind": (
                    current != latest if (current is not None and latest is not None) else False
                ),
                "error": None,
            }
        except Exception as exc:
            logger.exception("migration_status_failed")
            return {
                "current": None,
                "latest": None,
                "is_behind": False,
                "error": str(exc),
            }
