"""bookcompanion config — view and set configuration.
Uses Typer sub-app: `config` shows all, `config set <key> <value>` modifies."""

import os
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.syntax import Syntax

from app.cli.deps import get_settings

console = Console()
config_app = typer.Typer(help="View or modify configuration.")


@config_app.callback(invoke_without_command=True)
def config(ctx: typer.Context):
    """View current configuration (when called without subcommand)."""
    if ctx.invoked_subcommand is not None:
        return
    settings = get_settings()
    config_dict = {
        "database": settings.database.model_dump(),
        "llm": settings.llm.model_dump(),
        "summarization": settings.summarization.model_dump(),
        "embedding": settings.embedding.model_dump(),
        "search": settings.search.model_dump(),
        "storage": settings.storage.model_dump(),
        "logging": settings.logging.model_dump(),
    }
    yaml_str = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
    console.print(Syntax(yaml_str, "yaml"))


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key in dot notation (e.g., llm.model)."),
    value: str = typer.Argument(..., help="New value."),
):
    """Set a configuration value."""
    _set_config(key, value)


def _get_config(key: str, settings):
    parts = key.split(".")
    obj = settings
    for part in parts:
        obj = getattr(obj, part, None)
        if obj is None:
            console.print(f"[red]Unknown config key: {key}[/red]")
            raise typer.Exit(1)
    console.print(f"{key} = {obj}")


def _resolve_settings_yaml_path() -> Path:
    """Honour BOOKCOMPANION_CONFIG env var; otherwise platformdirs default.

    Mirrors ``Settings._load_yaml_config()`` so reads/writes target the same
    file. Falls back to the XDG-resolved default when no env override exists.
    """
    override = os.environ.get("BOOKCOMPANION_CONFIG", "")
    if override:
        return Path(override)
    from app.services.settings_service import default_user_settings_path

    return default_user_settings_path()


def _build_patch(key: str, value: str) -> dict:
    """Turn a dotted ``key`` into a nested dict patch.

    ``llm.config_dir`` → ``{"llm": {"config_dir": value}}``.
    """
    parts = key.split(".")
    patch: dict = {}
    cursor = patch
    for part in parts[:-1]:
        cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value
    return patch


def _set_config(key: str, value: str):
    """Persist a single dotted-key update via ``SettingsService.update_settings``.

    Inherits the strict-validation contract from FR-F1.4 / D17: an invalid
    value or unknown key raises ``ValidationError`` and the YAML on disk
    stays untouched. FR-F1.8 / D18 ensures CLI and HTTP PATCH agree.
    """
    from app.config import Settings
    from app.services.settings_service import SettingsService

    config_path = _resolve_settings_yaml_path()
    patch = _build_patch(key, value)

    try:
        svc = SettingsService(settings=Settings(), config_path=config_path)
        svc.update_settings(patch)
    except ValidationError as e:
        first = e.errors()[0] if e.errors() else {"msg": "validation failed"}
        loc = ".".join(str(p) for p in first.get("loc", ()))
        msg = first.get("msg", "validation failed")
        console.print(f"[red]Invalid setting {loc}: {msg}[/red]")
        raise typer.Exit(1) from e

    console.print(f"Set {key} = {value}")
