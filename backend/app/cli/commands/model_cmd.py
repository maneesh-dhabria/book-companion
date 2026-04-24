"""CLI commands for the LLM model selector (T35 / FR-F1.x)."""

from __future__ import annotations

import typer

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_success

model_app = typer.Typer(help="LLM model selection.")


def _settings_service(svc):
    from app.services.settings_service import SettingsService

    return SettingsService(settings=svc["settings"])


@model_app.command("list")
@async_command
async def list_models(
    provider: str = typer.Option(
        None, "--provider", help="Filter to one provider ('claude' or 'codex')."
    ),
):
    """Print the shipped models.yaml candidates."""
    async with get_services() as svc:
        data = _settings_service(svc).load_models()
        providers = data.get("providers", {})
        for name, entries in providers.items():
            if provider and provider != name:
                continue
            typer.echo(f"[{name}]")
            for e in entries:
                typer.echo(f"  - {e.get('id')}: {e.get('label')}")


@model_app.command("current")
@async_command
async def current_model():
    """Print the currently-configured LLM model."""
    async with get_services() as svc:
        settings = svc["settings"]
        typer.echo(
            f"provider={settings.llm.provider} model={settings.llm.model}"
        )


@model_app.command("set")
@async_command
async def set_model(
    model_id: str = typer.Argument(..., help="Model id to set as default."),
):
    """Persist a new default model to ~/.config/bookcompanion/settings.yaml.

    The change applies to subsequent CLI and server invocations; currently-
    running processes keep the old model until restart.
    """
    async with get_services() as svc:
        service = _settings_service(svc)
        service.persist_patch({"llm": {"model": model_id}})
        print_success(
            f"Set llm.model = {model_id!r}. Restart bookcompanion serve to apply."
        )
