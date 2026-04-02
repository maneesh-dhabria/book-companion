# Book Companion

Personal CLI tool for book summarization and knowledge extraction.

## Project Structure

- `backend/` -- Python backend (CLI + services)
- `backend/app/` -- Application code
  - `app/cli/` -- Typer CLI commands (thin wrappers over services)
  - `app/cli/commands/` -- Individual command modules
  - `app/db/` -- SQLAlchemy models, session management, repositories
  - `app/services/` -- Business logic layer
  - `app/services/summarizer/` -- LLM summarization + eval
  - `app/services/parser/` -- Book parsing (EPUB, PDF, MOBI)
- `backend/tests/` -- Test suite (unit, integration, e2e)
- `docs/` -- Specifications and documentation

## Quick Start

```bash
cd backend
uv sync --dev                    # Install dependencies
uv run bookcompanion init        # First-time setup (DB, migrations, embedding model)
uv run bookcompanion add ~/books/book.epub   # Add a book
uv run bookcompanion summarize 1             # Generate summaries
uv run bookcompanion list                    # Browse library
```

## Development Commands

```bash
cd backend
uv sync --dev                    # Install dependencies
uv run pytest                    # Run all tests
uv run pytest tests/unit/        # Run unit tests only
uv run pytest tests/integration/ # Run integration tests only
uv run pytest tests/e2e/         # Run end-to-end CLI tests
uv run pytest -m "not integration_llm"  # Skip tests needing real LLM
uv run ruff check .              # Lint
uv run ruff format --check .     # Format check
uv run mypy app/                 # Type check
```

## CLI Command Reference

### Phase 1 (Core Pipeline)
```bash
bookcompanion init                          # First-time setup
bookcompanion add <file_path>               # Upload + parse
bookcompanion add <file_path> --quick       # Parse + quick summary
bookcompanion add <file_path> --async       # Background processing
bookcompanion list [--recent] [--author X] [--status X] [--tag X]
bookcompanion show <book_id>                # Book details
bookcompanion read <book_id> [section_id] [--with-summary] [--copy] [--export FILE]
bookcompanion summary <book_id> [section_id] [--copy] [--export FILE]
bookcompanion summarize <book_id> [section_id] [--force] [--detail X] [--skip-eval]
bookcompanion search "query" [--book ID] [--source TYPE] [--tag TAG] [--annotations-only]
bookcompanion authors                       # List authors
bookcompanion eval <book_id> [section_id]   # Show eval results
bookcompanion status <book_id>              # Processing status
bookcompanion config                        # Show config
bookcompanion config set <key> <value>      # Set config value
bookcompanion delete <book_id> [--yes]      # Delete with confirmation
```

### Phase 2 (Annotations, Concepts, Enrichment)
```bash
bookcompanion annotate add <book_id> <section_id> [--text X] [--note X] [--tag X] [--type X]
bookcompanion annotate list [book_id] [--tag X] [--type X]
bookcompanion tag add <book_id> <tag_name> [--color X]
bookcompanion tag list
bookcompanion tag remove <book_id> <tag_name>
bookcompanion concepts list <book_id>       # Show concepts index
bookcompanion concepts search "term"        # Search across books
bookcompanion concepts edit <book_id>       # Edit in $EDITOR
bookcompanion export book <book_id> [--format json|markdown] [--output FILE]
bookcompanion export library [--format json|markdown] [--output FILE]
bookcompanion backup create [--output FILE]
bookcompanion backup list
bookcompanion backup restore <file> [--yes]
bookcompanion references list <book_id>     # Show external references
bookcompanion references discover <book_id> # LLM-powered discovery
bookcompanion edit metadata <book_id> [--title X] [--author X]
bookcompanion edit summary <book_id> [section_id]  # Edit in $EDITOR
bookcompanion eval-compare compare-prompts --book ID --section ID --prompt-a v1 --prompt-b v2
```

## Key Conventions

- All services are async and receive dependencies via constructor injection
- CLI commands are thin wrappers -- business logic lives in services
- SQLAlchemy 2.0 declarative style with `mapped_column`
- Prompts are Jinja2 templates in `app/services/summarizer/prompts/`
- Tests use a separate `bookcompanion_test` database
- Config via pydantic-settings: env vars > YAML config file > defaults
- Config file locations: `$BOOKCOMPANION_CONFIG` > `~/.config/bookcompanion/config.yaml`

## Database Migration Workflow

```bash
cd backend
# Generate a new migration after model changes
uv run alembic revision --autogenerate -m "description"
# Apply migrations
uv run alembic upgrade head
# Downgrade
uv run alembic downgrade -1
```

## Prompt Template Conventions

- Templates live in `app/services/summarizer/prompts/`
- Use Jinja2 syntax with versioned filenames: `summarize_section_v1.txt`
- Variables: `section_title`, `section_content`, `cumulative_context`, etc.
- All LLM calls go through `LLMProvider` (supports Claude Code CLI subprocess)

## Configuration Override Patterns

Precedence: environment variables > YAML config file > defaults

```bash
# Override via env vars
export BOOKCOMPANION_DATABASE__URL="postgresql+asyncpg://..."
export BOOKCOMPANION_LLM__MODEL="opus"

# Override via config file (~/.config/bookcompanion/config.yaml)
# database:
#   url: "postgresql+asyncpg://..."
# llm:
#   model: "opus"
```

## Infrastructure

- PostgreSQL 16 + pgvector runs in Docker (port 5438)
- Ollama runs on host (port 11434) with nomic-embed-text
- Claude Code CLI runs on host for LLM calls
- Backups stored at `~/.config/bookcompanion/backups/`
