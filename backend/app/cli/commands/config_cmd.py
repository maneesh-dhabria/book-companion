"""bookcompanion config — view and set configuration.
Uses Typer sub-app: `config` shows all, `config set <key> <value>` modifies."""

from pathlib import Path

import typer
import yaml
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


def _set_config(key: str, value: str):
    config_path = Path("~/.config/bookcompanion/config.yaml").expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if config_path.exists():
        with open(config_path) as f:
            existing = yaml.safe_load(f) or {}

    parts = key.split(".")
    obj = existing
    for part in parts[:-1]:
        obj = obj.setdefault(part, {})
    obj[parts[-1]] = value

    with open(config_path, "w") as f:
        yaml.dump(existing, f, default_flow_style=False)
    console.print(f"Set {key} = {value}")
