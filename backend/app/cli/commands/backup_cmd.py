"""CLI commands for backup and restore (Phase 2)."""

import typer

from app.cli.deps import async_command, get_services
from app.cli.formatting import (
    console,
    print_backup_table,
    print_empty_state,
    print_error,
    print_success,
)

backup_app = typer.Typer(help="Backup and restore commands.")


@backup_app.command("create")
@async_command
async def create_backup(
    output: str = typer.Option(
        None, "--output", "-o", help="Output file path. Default: ~/.config/bookcompanion/backups/"
    ),
):
    """Create a database backup using pg_dump."""
    async with get_services() as svc:
        try:
            path = await svc["backup"].create_backup(output_path=output)
            print_success(f"Backup created: {path}")
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)


@backup_app.command("list")
@async_command
async def list_backups():
    """List available database backups."""
    async with get_services() as svc:
        backups = svc["backup"].list_backups()
        if not backups:
            print_empty_state("No backups found. Run `bookcompanion backup create` to create one.")
            return
        print_backup_table(backups)


@backup_app.command("restore")
@async_command
async def restore_backup(
    backup_file: str = typer.Argument(..., help="Path to the backup file to restore."),
    confirm: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt.",
    ),
):
    """Restore database from a backup file."""
    if not confirm:
        proceed = typer.confirm("This will overwrite the current database. Continue?")
        if not proceed:
            console.print("Restore cancelled.")
            raise typer.Exit(0)

    async with get_services() as svc:
        try:
            await svc["backup"].restore_backup(backup_file)
            print_success(f"Database restored from: {backup_file}")
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)
