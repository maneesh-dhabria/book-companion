"""CLI commands for annotations (Phase 2)."""

import typer

from app.cli.deps import async_command, get_services
from app.cli.formatting import (
    console,
    print_annotation_table,
    print_empty_state,
    print_error,
    print_success,
)
from app.db.models import AnnotationType, ContentType

annotations_app = typer.Typer(help="Annotation commands.")


@annotations_app.command("add")
@async_command
async def annotate(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(..., help="Section ID."),
    text: str = typer.Option(None, "--text", help="Selected text to highlight."),
    note: str = typer.Option(None, "--note", help="Annotation note."),
    tag: str = typer.Option(None, "--tag", help="Tag name to associate."),
    ann_type: str = typer.Option(
        "note", "--type", help="Annotation type: highlight, note, freeform."
    ),
    link_to: int = typer.Option(
        None, "--link-to", help="Link to another annotation ID (cross-book)."
    ),
    content_type: str = typer.Option(
        "section_content",
        "--content-type",
        help="Content type: section_content, section_summary, book_summary.",
    ),
):
    """Create an annotation on a book section."""
    try:
        ct = ContentType(content_type)
    except ValueError:
        print_error(
            f"Invalid content_type '{content_type}'. "
            "Use: section_content, section_summary, book_summary."
        )
        raise typer.Exit(1)

    try:
        at = AnnotationType(ann_type)
    except ValueError:
        print_error(
            f"Invalid type '{ann_type}'. Use: highlight, note, freeform."
        )
        raise typer.Exit(1)

    async with get_services() as svc:
        try:
            annotation = await svc["annotation"].create_annotation(
                content_type=ct,
                content_id=section_id,
                selected_text=text,
                note=note,
                annotation_type=at,
                linked_annotation_id=link_to,
                tag_name=tag,
            )
            print_success(f"Annotation created (ID: {annotation.id}).")
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)


@annotations_app.command("list")
@async_command
async def list_annotations(
    book_id: int = typer.Argument(None, help="Book ID (optional)."),
    tag: str = typer.Option(None, "--tag", help="Filter by tag name."),
    ann_type: str = typer.Option(None, "--type", help="Filter by type."),
):
    """List annotations for a book or by tag."""
    at = None
    if ann_type:
        try:
            at = AnnotationType(ann_type)
        except ValueError:
            print_error(f"Invalid type '{ann_type}'.")
            raise typer.Exit(1)

    async with get_services() as svc:
        annotations = await svc["annotation"].list_annotations(
            book_id=book_id, tag=tag, annotation_type=at
        )
        if not annotations:
            print_empty_state("No annotations found.")
            return
        print_annotation_table(annotations)
