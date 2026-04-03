"""bookcompanion preset — manage summarization presets."""

import typer
from rich.console import Console
from rich.table import Table

from app.cli.formatting import print_error, print_success

preset_app = typer.Typer(help="Manage summarization presets.")
console = Console()


@preset_app.command("list")
def preset_list():
    """List all available presets."""
    from app.services.preset_service import PresetService

    svc = PresetService()
    presets = svc.list_all()

    table = Table(title="Available Presets")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("System")
    table.add_column("Style")
    table.add_column("Audience")
    table.add_column("Compression")
    table.add_column("Focus")

    for p in presets:
        table.add_row(
            p.file_path.stem,
            p.description[:50],
            "\u2713" if p.system else "",
            p.facets.get("style", ""),
            p.facets.get("audience", ""),
            p.facets.get("compression", ""),
            p.facets.get("content_focus", ""),
        )
    console.print(table)


@preset_app.command("show")
def preset_show(name: str = typer.Argument(..., help="Preset name.")):
    """Show details of a preset."""
    from app.services.preset_service import PresetService

    svc = PresetService()
    try:
        preset = svc.load(name)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1) from None

    console.print(f"[bold]{preset.name}[/bold]")
    console.print(f"Description: {preset.description}")
    console.print(f"System: {'Yes' if preset.system else 'No'}")
    console.print("\nFacets:")
    for k, v in preset.facets.items():
        console.print(f"  {k}: {v}")


@preset_app.command("create")
def preset_create(
    name: str = typer.Argument(..., help="Preset name (lowercase, underscores)."),
    description: str = typer.Option(None, "--description", help="Preset description."),
    style: str = typer.Option(None, "--style"),
    audience: str = typer.Option(None, "--audience"),
    compression: str = typer.Option(None, "--compression"),
    content_focus: str = typer.Option(None, "--content-focus"),
):
    """Create a new user preset."""
    from app.services.preset_service import FACET_DIMENSIONS, PresetService

    svc = PresetService()

    if not all([style, audience, compression, content_focus]):
        if not description:
            description = typer.prompt("Description")
        if not style:
            options = "/".join(FACET_DIMENSIONS["style"])
            style = typer.prompt(f"Style [{options}]")
        if not audience:
            options = "/".join(FACET_DIMENSIONS["audience"])
            audience = typer.prompt(f"Audience [{options}]")
        if not compression:
            options = "/".join(FACET_DIMENSIONS["compression"])
            compression = typer.prompt(f"Compression [{options}]")
        if not content_focus:
            options = "/".join(FACET_DIMENSIONS["content_focus"])
            content_focus = typer.prompt(f"Content focus [{options}]")

    if not description:
        description = f"Custom preset: {style}, {audience}"

    facets = {
        "style": style,
        "audience": audience,
        "compression": compression,
        "content_focus": content_focus,
    }

    try:
        preset = svc.create(name, description, facets)
        print_success(f'Preset "{name}" created at {preset.file_path}')
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1) from None


@preset_app.command("delete")
def preset_delete(name: str = typer.Argument(..., help="Preset name to delete.")):
    """Delete a user preset. System presets are protected."""
    from app.services.preset_service import PresetService

    svc = PresetService()
    try:
        svc.delete(name)
        print_success(f'Preset "{name}" deleted.')
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1) from None
