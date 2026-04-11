"""bookcompanion search — hybrid search across all books."""

import typer
from rich.console import Console
from rich.table import Table

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_empty_state, print_error, should_json

console = Console()


@async_command
async def search(
    query: str = typer.Argument(..., help="Search query text."),
    book: int = typer.Option(None, "--book", help="Search within a specific book only."),
    source: str = typer.Option(
        None,
        "--source",
        help="Filter by source type: content, summary, title, concept, annotation.",
    ),
    tag: str = typer.Option(None, "--tag", help="Filter by tag name. (Phase 2)"),
    annotations_only: bool = typer.Option(
        False, "--annotations-only", help="Search only annotations and notes. (Phase 2)"
    ),
    limit: int = typer.Option(20, "--limit", help="Maximum results."),
):
    """Hybrid search (BM25 + semantic + RRF) across all books."""
    async with get_services() as svc:
        search_service = svc.get("search")
        if not search_service:
            print_error("Search service not available. Service layer may not be implemented yet.")
            raise typer.Exit(1)

        # Phase 2: override source filter if --annotations-only
        effective_source = source
        if annotations_only:
            effective_source = "annotation"

        try:
            results = await search_service.search(
                query=query,
                book_id=book,
                source_type=effective_source,
                tag=tag,
                limit=limit,
            )
        except Exception as e:
            print_error(f"Search failed: {e}")
            raise typer.Exit(1)

        if not results or results.total_count == 0:
            print_empty_state(f'No results found for "{query}". Try a broader search term.')
            return

        if should_json():
            import json

            all_items = [
                vars(r) for book_results in results.books.values() for r in book_results
            ]
            console.print(json.dumps(all_items, indent=2, default=str))
            return

        # Results are already grouped by book_id
        for _book_id, book_results in results.books.items():
            book_title = book_results[0].book_title if book_results else "Unknown"
            table = Table(title=f"Results from: {book_title}")
            table.add_column("Source", style="cyan")
            table.add_column("Snippet")
            table.add_column("Score", justify="right")

            shown = 0
            for r in book_results:
                if shown >= 3:
                    remaining = len(book_results) - shown
                    table.add_row("", f"... and {remaining} more results", "")
                    break
                source_type = getattr(r, "source_type", "")
                chunk_text = getattr(r, "chunk_text", str(r))
                score = getattr(r, "score", "")
                table.add_row(
                    str(source_type),
                    chunk_text[:200] + ("..." if len(chunk_text) > 200 else ""),
                    f"{score:.3f}" if isinstance(score, float) else str(score),
                )
                shown += 1

            console.print(table)
            console.print()
