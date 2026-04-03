# Book Companion V1.1 Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Book Companion CLI from monolithic summarization to a faceted preset system with append-only summary log, section editing, quality validation, and summary comparison — all specified in [V1.1 Enhancements Spec](../specs/2026-04-02_book_companion_v1.1_enhancements_spec.md).

**Architecture:** Extends the existing layered monolith (Typer CLI → Service Layer → SQLAlchemy 2.0 → PostgreSQL 16). New `summaries` table replaces inline `summary_md` columns. Faceted Jinja2 fragments replace monolithic prompt templates. Four new services (PresetService, QualityService, SummaryService, SectionEditService) plus modifications to SummarizerService, EvalService, BookService, and ExportService. No REST API — CLI only.

**Tech Stack:** Python 3.12+, Typer, SQLAlchemy 2.0 async, Alembic, pydantic-settings, PostgreSQL 16 + pgvector, Ollama, Claude Code CLI, Jinja2, Rich, structlog, pytest + pytest-asyncio, uv

**Spec Reference:** `docs/specs/2026-04-02_book_companion_v1.1_enhancements_spec.md`
**V1 Plan Reference:** `docs/plans/2026-04-02_book_companion_v1_implementation.md`

---

## Table of Contents

1. [Decision Log](#decision-log)
2. [File Structure](#file-structure)
3. [Task 1: Models, Enums, Migration & Config](#task-1-models-enums-migration--config)
4. [Task 2: Prompt Fragment System & Preset Files](#task-2-prompt-fragment-system--preset-files)
5. [Task 3: Repositories](#task-3-repositories)
6. [Task 4: PresetService & QualityService](#task-4-presetservice--qualityservice)
7. [Task 5: SummaryService](#task-5-summaryservice)
8. [Task 6: SummarizerService Refactor](#task-6-summarizerservice-refactor)
9. [Task 7: SectionEditService](#task-7-sectioneditservice)
10. [Task 8: EvalService, BookService, ExportService & deps.py](#task-8-evalservice-bookservice-exportservice--depspy)
11. [Task 9: Preset & Summary CLI Commands](#task-9-preset--summary-cli-commands)
12. [Task 10: Summarize & Eval CLI Updates](#task-10-summarize--eval-cli-updates)
13. [Task 11: Show, Add & Edit Sections CLI](#task-11-show-add--edit-sections-cli)
14. [Task 12: Integration Tests](#task-12-integration-tests)
15. [Task 13: E2E Tests & Final Verification](#task-13-e2e-tests--final-verification)

---

## Decision Log

| # | Decision | Options Considered | Choice | Rationale |
|---|----------|--------------------|--------|-----------|
| D1 | `summary` CLI as Typer sub-app vs top-level command | (A) Sub-app with `invoke_without_command=True` callback (B) Separate `summary-list`, `summary-compare` commands (C) Sub-app only, no shorthand | **A** | Typer's `invoke_without_command=True` lets `summary <book_id>` work as shorthand while `summary list`, `summary compare` etc. are sub-commands. Matches spec's CLI reference exactly. |
| D2 | Section edit REPL implementation | (A) Raw `input()` loop (B) `prompt_toolkit` (C) Typer `prompt()` | **A — Raw `input()` loop** | Minimal dependency. The REPL is simple (6 commands). `prompt_toolkit` adds 3MB for tab completion we don't need. Wrap in a `SectionREPL` class for testability (inject stdin). |
| D3 | Quality check storage | (A) Persist to DB (B) In-memory only, recompute on demand | **B — In-memory** | Quality checks are fast deterministic heuristics (~ms). No benefit to persisting. Recompute during `add`, `show`, and `summarize`. |
| D4 | Fragment file content authoring | (A) Write fragments during plan implementation (B) Placeholder text, iterate later | **A — Write real fragments** | Fragments are 2-4 sentences each. Spec says prompt quality optimization is out of scope, but we need functional fragments for testing and the pipeline to work end-to-end. |
| D5 | `summary` sub-app registration | Register as `app.add_typer(summary_app, name="summary")` and remove old `app.command("summary")` | **Replace** | The old `summary` command becomes the callback of the sub-app. No backward compat needed — V1.1 is a clean break. |
| D6 | Migration: data migration for existing summaries | (A) Migrate existing `summary_md` into `summaries` table (B) Drop and re-summarize | **B — Drop** | Spec section 10.3 explicitly says "All existing summaries are deleted — re-summarize using new presets." Simpler migration, no data transformation. |
| D7 | Test approach for REPL commands | (A) Monkeypatch stdin (B) Extract parsing logic into testable functions, test REPL integration separately | **B — Separate parsing from I/O** | Parse functions (`parse_merge`, `parse_split`, etc.) are pure and testable. REPL loop tested via e2e with stdin piping. |
| D8 | Concept diff algorithm | (A) LLM-based extraction (B) Deterministic regex per spec | **B — Regex** | Spec section 8.2 defines exact regex patterns. No LLM call needed. Fast, reproducible. |
| D9 | Pre-save vs post-save edit code reuse | (A) Shared base class (B) Separate in-memory and DB-backed implementations (C) Single service with mode flag | **C — Single service, mode flag** | Both use the same REPL commands. In-memory mode mutates a list; DB mode wraps each operation in a transaction. `SectionEditService(mode="memory"|"db")`. |
| D10 | Existing `edit summary` command handling | (A) Remove (B) Adapt to work with `summaries` table (C) Keep as-is, deprecated | **B — Adapt** | Update `edit summary` to edit the default summary's `summary_md` in the `summaries` table. No `user_edited` flag on summaries (spec doesn't mention it). |

---

## File Structure

```
backend/
├── alembic/versions/
│   └── XXXX_v1_1_enhancements.py              # NEW: V1.1 migration
├── app/
│   ├── config.py                                # MODIFY: Remove old, add default_preset
│   ├── exceptions.py                            # MODIFY: Add PresetError, SectionEditError
│   ├── db/
│   │   ├── models.py                            # MODIFY: Summary model, SummaryContentType enum,
│   │   │                                        #   Book.default_summary_id, BookSection changes,
│   │   │                                        #   EvalTrace.summary_id, drop SummaryStatus
│   │   └── repositories/
│   │       ├── book_repo.py                     # MODIFY: default_summary_id updates
│   │       ├── section_repo.py                  # MODIFY: derived_from, default_summary_id,
│   │       │                                    #   bulk delete, reindex_order
│   │       ├── eval_repo.py                     # MODIFY: summary_id on creates
│   │       └── summary_repo.py                  # NEW: Summary CRUD + queries
│   ├── services/
│   │   ├── preset_service.py                    # NEW: Load/validate/create/delete presets
│   │   ├── quality_service.py                   # NEW: 10 deterministic quality checks
│   │   ├── summary_service.py                   # NEW: List, compare, set-default, concept diff
│   │   ├── section_edit_service.py              # NEW: Merge/split/reorder/delete (memory + DB)
│   │   ├── book_service.py                      # MODIFY: Status derivation, remove old summary writes
│   │   ├── export_service.py                    # MODIFY: Read from summaries table
│   │   └── summarizer/
│   │       ├── summarizer_service.py            # MODIFY: Faceted composition, append to summaries,
│   │       │                                    #   idempotent skip, progress callbacks
│   │       ├── evaluator.py                     # MODIFY: Facet-sensitive assertions, summary_id FK
│   │       └── prompts/
│   │           ├── base/
│   │           │   ├── summarize_section.txt    # NEW: Faceted base template
│   │           │   └── summarize_book.txt       # NEW: Faceted book template
│   │           ├── fragments/
│   │           │   ├── style/
│   │           │   │   ├── bullet_points.txt    # NEW (6 style fragments)
│   │           │   │   ├── narrative.txt
│   │           │   │   ├── podcast_dialogue.txt
│   │           │   │   ├── cornell_notes.txt
│   │           │   │   ├── mind_map_outline.txt
│   │           │   │   └── tweet_thread.txt
│   │           │   ├── audience/
│   │           │   │   ├── practitioner.txt     # NEW (3 audience fragments)
│   │           │   │   ├── academic.txt
│   │           │   │   └── executive.txt
│   │           │   ├── compression/
│   │           │   │   ├── brief.txt            # NEW (3 compression fragments)
│   │           │   │   ├── standard.txt
│   │           │   │   └── detailed.txt
│   │           │   └── content_focus/
│   │           │       ├── key_concepts.txt     # NEW (3 focus fragments)
│   │           │       ├── frameworks_examples.txt
│   │           │       └── full_coverage.txt
│   │           └── presets/
│   │               ├── practitioner_bullets.yaml # NEW (5 system presets)
│   │               ├── academic_detailed.yaml
│   │               ├── executive_brief.yaml
│   │               ├── study_guide.yaml
│   │               └── tweet_thread.yaml
│   └── cli/
│       ├── main.py                              # MODIFY: Register new sub-apps, remove old summary
│       ├── deps.py                              # MODIFY: Wire 4 new services
│       └── commands/
│           ├── books.py                         # MODIFY: add (quality+REPL), show (new columns)
│           ├── summarize_cmd.py                 # MODIFY: Preset flags, progress display, idempotency
│           ├── eval_cmd.py                      # MODIFY: --summary-id flag
│           ├── edit_cmd.py                      # MODIFY: Add edit sections subcommand
│           ├── preset_cmd.py                    # NEW: preset list/show/create/delete
│           ├── summary_cmds.py                  # NEW: summary list/compare/set-default/show/read
│           └── read_cmd.py                      # NEW: read <book_id> <section_id> [--with-summary]
├── tests/
│   ├── unit/
│   │   ├── test_prompt_fragments.py             # NEW: Fragment rendering, preset validation
│   │   ├── test_preset_service.py               # NEW: Preset CRUD, facet override
│   │   ├── test_quality_service.py              # NEW: 10 quality checks
│   │   ├── test_summary_service.py              # NEW: Concept diff, status derivation
│   │   ├── test_section_edit.py                 # NEW: Merge/split/reorder/delete in-memory
│   │   ├── test_repl_parsing.py                 # NEW: REPL command parsing
│   │   ├── test_eval_adaptations.py             # NEW: Facet-sensitive assertion thresholds
│   │   └── test_summarizer.py                   # MODIFY: Update for new interface
│   ├── integration/
│   │   ├── test_summary_crud.py                 # NEW: Summary append, cascade, set-default
│   │   └── test_section_edit_db.py              # NEW: Post-save merge/split with DB
│   └── e2e/
│       └── test_v1_1_flows.py                   # NEW: Full pipeline, preset mgmt, section editing
```

---

## Task 1: Models, Enums, Migration & Config

**Goal:** Create the `Summary` model, `SummaryContentType` enum, modify `Book`, `BookSection`, `EvalTrace` models, update config, and generate the Alembic migration.

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/exceptions.py`
- Create: `backend/alembic/versions/XXXX_v1_1_enhancements.py`
- Modify: `backend/tests/unit/test_models.py`
- Modify: `backend/tests/unit/test_config.py`

### Step-by-step

- [ ] **Step 1: Add `SummaryContentType` enum and `Summary` model to `models.py`**

Add after the existing `AnnotationType` enum (line 92):

```python
class SummaryContentType(str, enum.Enum):
    SECTION = "section"
    BOOK = "book"
    CONCEPT = "concept"        # Reserved for Phase 2
    ANNOTATION = "annotation"  # Reserved for Phase 2
```

Add the `Summary` model after `EvalTrace` (before Phase 2 models, line 331):

```python
class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content_type: Mapped[SummaryContentType] = mapped_column(
        Enum(SummaryContentType), nullable=False
    )
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    preset_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    facets_used: Mapped[dict] = mapped_column(JSON, nullable=False)
    prompt_text_sent: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_md: Mapped[str] = mapped_column(Text, nullable=False)
    eval_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_summaries_content", "content_type", "content_id"),
        Index("ix_summaries_book_id", "book_id"),
        Index("ix_summaries_created_at", "created_at"),
    )
```

- [ ] **Step 2: Modify `Book` model — add `default_summary_id`, keep `quick_summary`, mark `overall_summary` and `overall_summary_eval` for removal**

In the `Book` class, add `default_summary_id` and remove `overall_summary` + `overall_summary_eval`:

```python
# Add after cover_image (line 122):
default_summary_id: Mapped[int | None] = mapped_column(
    BigInteger,
    ForeignKey("summaries.id", ondelete="SET NULL", use_alter=True),
    nullable=True,
)

# Remove these two lines (127-128):
# overall_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
# overall_summary_eval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Note: `use_alter=True` is needed because `summaries` table has FK back to `books`, creating a circular dependency. SQLAlchemy handles this with ALTER TABLE.

- [ ] **Step 3: Modify `BookSection` model — add `default_summary_id`, `derived_from`, remove summary columns**

Replace the summary-related fields on `BookSection` (lines 188-195):

```python
# Remove these fields:
#   summary_md, summary_status, summary_version, summary_eval, summary_model, user_edited

# Add these fields (after content_token_count):
default_summary_id: Mapped[int | None] = mapped_column(
    BigInteger,
    ForeignKey("summaries.id", ondelete="SET NULL", use_alter=True),
    nullable=True,
)
derived_from: Mapped[list | None] = mapped_column(JSON, nullable=True)
```

Update `__table_args__` — remove the `ix_book_sections_summary_status` index:

```python
__table_args__ = (
    Index("ix_book_sections_book_id_order", "book_id", "order_index"),
)
```

- [ ] **Step 4: Delete the `SummaryStatus` enum class**

Remove the `SummaryStatus` class (lines 42-47). This enum is dropped from both Python and DB.

- [ ] **Step 5: Modify `EvalTrace` — add `summary_id` FK**

Add after `section_id` field (line 308):

```python
summary_id: Mapped[int | None] = mapped_column(
    BigInteger,
    ForeignKey("summaries.id", ondelete="SET NULL"),
    nullable=True,
)
```

- [ ] **Step 6: Update `config.py` — replace old summarization settings**

Replace `SummarizationConfig` (lines 27-30):

```python
class SummarizationConfig(BaseModel):
    default_preset: str = "practitioner_bullets"
    eval_prompt_version: str = "v1"
```

The `default_detail_level` and `prompt_version` fields are removed. The `model_post_init` in `Settings` already handles unknown YAML keys gracefully (it checks `hasattr`), so old config files won't crash.

- [ ] **Step 7: Add new exceptions to `exceptions.py`**

```python
class PresetError(BookCompanionError):
    """Preset-related errors (not found, validation, protected)."""

class SectionEditError(BookCompanionError):
    """Section editing errors (merge, split, reorder, delete)."""

class SummaryError(BookCompanionError):
    """Summary-related errors (not found, set-default)."""
```

- [ ] **Step 8: Write the Alembic migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "v1.1 enhancements"
```

Then manually edit the generated file to match this structure:

```python
"""v1.1 enhancements — summaries table, faceted presets, section editing.

No downgrade path — dropping columns with data is irreversible.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "XXXX"
down_revision = "bb35febd1383"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create SummaryContentType enum
    summary_content_type = postgresql.ENUM(
        "section", "book", "concept", "annotation",
        name="summarycontenttype", create_type=True
    )
    summary_content_type.create(op.get_bind(), checkfirst=True)

    # 2. Create summaries table
    op.create_table(
        "summaries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("content_type", summary_content_type, nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("book_id", sa.BigInteger(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preset_name", sa.String(200), nullable=True),
        sa.Column("facets_used", sa.JSON(), nullable=False),
        sa.Column("prompt_text_sent", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("input_char_count", sa.Integer(), nullable=False),
        sa.Column("summary_char_count", sa.Integer(), nullable=False),
        sa.Column("summary_md", sa.Text(), nullable=False),
        sa.Column("eval_json", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_summaries_content", "summaries", ["content_type", "content_id"])
    op.create_index("ix_summaries_book_id", "summaries", ["book_id"])
    op.create_index("ix_summaries_created_at", "summaries", ["created_at"])

    # 3. Add default_summary_id to books
    op.add_column("books", sa.Column("default_summary_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_books_default_summary", "books", "summaries",
        ["default_summary_id"], ["id"], ondelete="SET NULL"
    )

    # 4. Add default_summary_id and derived_from to book_sections
    op.add_column("book_sections", sa.Column("default_summary_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_sections_default_summary", "book_sections", "summaries",
        ["default_summary_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column("book_sections", sa.Column("derived_from", sa.JSON(), nullable=True))

    # 5. Drop summary_status index BEFORE dropping the column
    op.drop_index("ix_book_sections_summary_status", table_name="book_sections")

    # 6. Drop columns from book_sections
    op.drop_column("book_sections", "summary_md")
    op.drop_column("book_sections", "summary_status")
    op.drop_column("book_sections", "summary_version")
    op.drop_column("book_sections", "summary_model")
    op.drop_column("book_sections", "summary_eval")
    op.drop_column("book_sections", "user_edited")

    # 7. Drop columns from books
    op.drop_column("books", "overall_summary")
    op.drop_column("books", "overall_summary_eval")

    # 8. Drop SummaryStatus enum type
    sa.Enum(name="summarystatus").drop(op.get_bind(), checkfirst=True)

    # 9. Add summary_id to eval_traces
    op.add_column("eval_traces", sa.Column("summary_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_eval_traces_summary", "eval_traces", "summaries",
        ["summary_id"], ["id"], ondelete="SET NULL"
    )

    # 10. Truncate eval_traces (old traces reference dropped columns)
    op.execute("TRUNCATE TABLE eval_traces")


def downgrade() -> None:
    raise NotImplementedError("V1.1 migration is not reversible")
```

- [ ] **Step 9: Run migration on dev and test databases**

```bash
cd backend
uv run alembic upgrade head
BOOKCOMPANION_DATABASE__URL=postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test uv run alembic upgrade head
```

- [ ] **Step 10: Fix imports across codebase that reference `SummaryStatus`**

Grep for `SummaryStatus` and update all imports. Key files:
- `app/services/summarizer/summarizer_service.py`: Remove `SummaryStatus` import, update logic
- `app/db/repositories/section_repo.py`: Remove `SummaryStatus` import, remove `update_summary()` and `get_pending_sections()`
- `app/cli/commands/summarize_cmd.py`: Remove `summary_status` checks
- `app/cli/commands/eval_cmd.py`: Remove `summary_eval` references
- `app/cli/commands/edit_cmd.py`: Update `edit summary` to use `summaries` table

- [ ] **Step 11: Write unit tests for new models and config**

In `tests/unit/test_models.py`, add:

```python
def test_summary_content_type_enum():
    from app.db.models import SummaryContentType
    assert SummaryContentType.SECTION.value == "section"
    assert SummaryContentType.BOOK.value == "book"
    assert SummaryContentType.CONCEPT.value == "concept"
    assert SummaryContentType.ANNOTATION.value == "annotation"


def test_summary_model_instantiation():
    from app.db.models import Summary, SummaryContentType
    s = Summary(
        content_type=SummaryContentType.SECTION,
        content_id=1,
        book_id=1,
        facets_used={"style": "bullet_points", "audience": "practitioner",
                     "compression": "standard", "content_focus": "frameworks_examples"},
        prompt_text_sent="test prompt",
        model_used="sonnet",
        input_char_count=1000,
        summary_char_count=200,
        summary_md="# Test summary",
    )
    assert s.content_type == SummaryContentType.SECTION
    assert s.preset_name is None


def test_summary_status_enum_removed():
    """SummaryStatus should no longer exist in models."""
    import app.db.models as models
    assert not hasattr(models, "SummaryStatus")
```

In `tests/unit/test_config.py`, add:

```python
def test_summarization_default_preset(clean_env):
    from app.config import Settings
    s = Settings()
    assert s.summarization.default_preset == "practitioner_bullets"
    assert not hasattr(s.summarization, "default_detail_level")
    assert not hasattr(s.summarization, "prompt_version")


def test_old_config_keys_ignored(clean_env, tmp_path):
    """Old YAML config with removed keys should not crash."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("summarization:\\n  default_detail_level: brief\\n  prompt_version: v2\\n")
    import os
    os.environ["BOOKCOMPANION_CONFIG"] = str(config_file)
    from app.config import Settings
    s = Settings()
    assert s.summarization.default_preset == "practitioner_bullets"
```

- [ ] **Step 12: Run tests and verify**

```bash
cd backend && uv run python -m pytest tests/unit/test_models.py tests/unit/test_config.py -v
```

- [ ] **Step 13: Commit**

```bash
git add backend/app/db/models.py backend/app/config.py backend/app/exceptions.py \
  backend/alembic/versions/ backend/tests/unit/test_models.py backend/tests/unit/test_config.py
git commit -m "feat: V1.1 schema — Summary model, SummaryContentType enum, migration, config updates"
```

---

## Task 2: Prompt Fragment System & Preset Files

**Goal:** Create the faceted Jinja2 fragment files, base templates, and 5 system preset YAMLs. Delete V1 monolithic templates.

**Files:**
- Create: `backend/app/services/summarizer/prompts/base/summarize_section.txt`
- Create: `backend/app/services/summarizer/prompts/base/summarize_book.txt`
- Create: 15 fragment files under `prompts/fragments/`
- Create: 5 preset YAMLs under `prompts/presets/`
- Delete: `backend/app/services/summarizer/prompts/summarize_section_v1.txt`
- Delete: `backend/app/services/summarizer/prompts/summarize_book_v1.txt`
- Create: `backend/tests/unit/test_prompt_fragments.py`

### Step-by-step

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p backend/app/services/summarizer/prompts/{base,fragments/{style,audience,compression,content_focus},presets}
```

- [ ] **Step 2: Create base section template**

File: `backend/app/services/summarizer/prompts/base/summarize_section.txt`

```jinja
You are summarizing "{{ book_title }}" by {{ author }}.
Section: "{{ section_title }}"

{% include "fragments/audience/" + audience + ".txt" %}
{% include "fragments/content_focus/" + content_focus + ".txt" %}
{% include "fragments/style/" + style + ".txt" %}
{% include "fragments/compression/" + compression + ".txt" %}

{% if cumulative_context %}
## Context from prior sections
{{ cumulative_context }}
{% endif %}

{% if image_captions %}
## Visual Content
The section contains the following images/diagrams. Integrate key images into your summary. When referencing an image, use: ![brief description](image:ID).

{% for img in image_captions %}
- [{{ img.relevance }}] (image:{{ img.image_id }}) {{ img.caption }}
{% endfor %}
{% endif %}

## Source content
{{ section_content }}

Output as JSON matching the provided schema.
```

- [ ] **Step 3: Create base book template**

File: `backend/app/services/summarizer/prompts/base/summarize_book.txt`

```jinja
You are creating a book-level summary of "{{ book_title }}" by {{ author }}.
This summary synthesizes {{ section_count }} section summaries below.

{% include "fragments/audience/" + audience + ".txt" %}
{% include "fragments/content_focus/" + content_focus + ".txt" %}
{% include "fragments/style/" + style + ".txt" %}
{% include "fragments/compression/" + compression + ".txt" %}

## Section summaries
{% for section in sections %}
### {{ section.title }}
{{ section.summary }}
{% endfor %}

Output as JSON matching the provided schema.
```

- [ ] **Step 4: Create style fragment files (6 files)**

`fragments/style/bullet_points.txt`:
```
## Output Format
Structure your summary as a bulleted list. Use top-level bullets for major points and nested bullets for supporting details. Each bullet should be a complete thought, scannable without reading surrounding context.
```

`fragments/style/narrative.txt`:
```
## Output Format
Write the summary as flowing prose paragraphs. Use clear topic sentences and logical transitions between ideas. Aim for readability as a standalone essay — someone unfamiliar with the source should follow the argument.
```

`fragments/style/podcast_dialogue.txt`:
```
## Output Format
Write the summary as a dialogue between a Host and an Expert. The Host asks clarifying questions and highlights key takeaways. The Expert explains concepts, provides examples, and connects ideas. Use natural conversational tone.
```

`fragments/style/cornell_notes.txt`:
```
## Output Format
Structure the summary using the Cornell Notes method: a left column with cue questions or keywords and a right column with detailed notes answering each cue. End with a "Summary" section (2-3 sentences) synthesizing the main idea.
```

`fragments/style/mind_map_outline.txt`:
```
## Output Format
Structure the summary as an indented outline representing a mind map. The central topic is the section title. First-level items are major themes. Sub-levels are supporting details, examples, and connections. Use consistent indentation with dashes.
```

`fragments/style/tweet_thread.txt`:
```
## Output Format
Write the summary as a numbered tweet thread. Each tweet must be under 280 characters. Start with a hook tweet that captures the core idea. End with a takeaway tweet. Use plain language — no jargon unless it's the author's key term.
```

- [ ] **Step 5: Create audience fragment files (3 files)**

`fragments/audience/practitioner.txt`:
```
## Audience
Write for a working professional who wants to apply these ideas. Prioritize actionable frameworks, concrete examples, and implementation steps over theoretical background.
```

`fragments/audience/academic.txt`:
```
## Audience
Write for someone studying this topic rigorously. Prioritize precise definitions, theoretical foundations, relationships between concepts, and citations to specific claims in the source.
```

`fragments/audience/executive.txt`:
```
## Audience
Write for a decision-maker with limited time. Lead with conclusions and strategic implications. Provide just enough supporting evidence to justify claims. Skip implementation details.
```

- [ ] **Step 6: Create compression fragment files (3 files)**

`fragments/compression/brief.txt`:
```
## Length Target
Aim for approximately 10% of the source length. Include only the most essential points. Omit examples unless they are central to the argument.
```

`fragments/compression/standard.txt`:
```
## Length Target
Aim for approximately 20% of the source length. Cover all major points with representative examples. Balance completeness with conciseness.
```

`fragments/compression/detailed.txt`:
```
## Length Target
Aim for approximately 30% of the source length. Preserve nuance, include multiple examples per concept, and capture the author's reasoning chains.
```

- [ ] **Step 7: Create content_focus fragment files (3 files)**

`fragments/content_focus/key_concepts.txt`:
```
## Content Focus
Focus on 3-5 key concepts. For each, provide a clear definition, the author's argument, and one supporting example. Omit tangential points and secondary examples.
```

`fragments/content_focus/frameworks_examples.txt`:
```
## Content Focus
Prioritize named frameworks, models, and methodologies. For each framework, explain its components, how to apply it, and the specific examples the author uses to illustrate it.
```

`fragments/content_focus/full_coverage.txt`:
```
## Content Focus
Cover all major and minor points comprehensively. Include every framework, example, and supporting argument. Preserve the author's structure and logical progression.
```

- [ ] **Step 8: Create 5 system preset YAML files**

`presets/practitioner_bullets.yaml`:
```yaml
name: Practitioner Bullets
description: Actionable frameworks in scannable bullet format
system: true
facets:
  style: bullet_points
  audience: practitioner
  compression: standard
  content_focus: frameworks_examples
```

`presets/academic_detailed.yaml`:
```yaml
name: Academic Detailed
description: Comprehensive academic analysis with full coverage
system: true
facets:
  style: narrative
  audience: academic
  compression: detailed
  content_focus: full_coverage
```

`presets/executive_brief.yaml`:
```yaml
name: Executive Brief
description: Key decisions and bottom-line takeaways
system: true
facets:
  style: bullet_points
  audience: executive
  compression: brief
  content_focus: key_concepts
```

`presets/study_guide.yaml`:
```yaml
name: Study Guide
description: Cornell notes for active learning
system: true
facets:
  style: cornell_notes
  audience: practitioner
  compression: standard
  content_focus: full_coverage
```

`presets/tweet_thread.yaml`:
```yaml
name: Tweet Thread
description: 280-char tweet-sized takeaways
system: true
facets:
  style: tweet_thread
  audience: executive
  compression: brief
  content_focus: key_concepts
```

- [ ] **Step 9: Delete V1 monolithic templates**

```bash
rm backend/app/services/summarizer/prompts/summarize_section_v1.txt
rm backend/app/services/summarizer/prompts/summarize_book_v1.txt
```

Retain `quick_summary_v1.txt` (spec: "retained but unused by new code").

- [ ] **Step 10: Write fragment rendering tests**

File: `backend/tests/unit/test_prompt_fragments.py`

```python
"""Tests for faceted prompt fragment system."""

from pathlib import Path

import jinja2
import pytest
import yaml

PROMPTS_DIR = Path(__file__).parents[2] / "app" / "services" / "summarizer" / "prompts"
PRESETS_DIR = PROMPTS_DIR / "presets"

VALID_FACETS = {
    "style": ["bullet_points", "narrative", "podcast_dialogue", "cornell_notes", "mind_map_outline", "tweet_thread"],
    "audience": ["practitioner", "academic", "executive"],
    "compression": ["brief", "standard", "detailed"],
    "content_focus": ["key_concepts", "frameworks_examples", "full_coverage"],
}

SYSTEM_PRESETS = ["practitioner_bullets", "academic_detailed", "executive_brief", "study_guide", "tweet_thread"]


def _load_preset(name: str) -> dict:
    path = PRESETS_DIR / f"{name}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def _create_jinja_env() -> jinja2.Environment:
    return jinja2.Environment(loader=jinja2.FileSystemLoader(str(PROMPTS_DIR)))


@pytest.mark.parametrize("dimension,values", VALID_FACETS.items())
def test_all_fragment_files_exist(dimension, values):
    """Every declared facet value must have a corresponding fragment file."""
    for value in values:
        path = PROMPTS_DIR / "fragments" / dimension / f"{value}.txt"
        assert path.exists(), f"Missing fragment: {path}"
        content = path.read_text()
        assert len(content.strip()) > 0, f"Empty fragment: {path}"


@pytest.mark.parametrize("preset_name", SYSTEM_PRESETS)
def test_system_preset_has_valid_fields(preset_name):
    """System presets must have name, description, system=true, and valid facets."""
    preset = _load_preset(preset_name)
    assert "name" in preset
    assert "description" in preset
    assert preset.get("system") is True
    facets = preset["facets"]
    for dim, valid_values in VALID_FACETS.items():
        assert dim in facets, f"Preset {preset_name} missing facet: {dim}"
        assert facets[dim] in valid_values, f"Preset {preset_name} has invalid {dim}: {facets[dim]}"


@pytest.mark.parametrize("preset_name", SYSTEM_PRESETS)
def test_system_preset_renders(preset_name):
    """Load preset, resolve fragments, render template with mock data."""
    preset = _load_preset(preset_name)
    env = _create_jinja_env()
    template = env.get_template("base/summarize_section.txt")
    result = template.render(
        book_title="Test Book",
        author="Test Author",
        section_title="Test Section",
        section_content="Sample content for testing the template rendering.",
        cumulative_context="",
        image_captions=[],
        **preset["facets"],
    )
    assert len(result) > 0
    assert "{{" not in result, "Unrendered Jinja2 variable found"
    assert "Test Book" in result
    assert "Test Section" in result


@pytest.mark.parametrize("preset_name", SYSTEM_PRESETS)
def test_book_template_renders(preset_name):
    """Book template renders with preset facets."""
    preset = _load_preset(preset_name)
    env = _create_jinja_env()
    template = env.get_template("base/summarize_book.txt")
    result = template.render(
        book_title="Test Book",
        author="Test Author",
        section_count=3,
        sections=[
            {"title": "Ch 1", "summary": "Summary 1"},
            {"title": "Ch 2", "summary": "Summary 2"},
            {"title": "Ch 3", "summary": "Summary 3"},
        ],
        **preset["facets"],
    )
    assert len(result) > 0
    assert "{{" not in result


def test_invalid_fragment_raises():
    """Referencing a nonexistent fragment file raises TemplateNotFound."""
    env = _create_jinja_env()
    template = env.get_template("base/summarize_section.txt")
    with pytest.raises(jinja2.TemplateNotFound):
        template.render(
            book_title="Test", author="Author", section_title="S",
            section_content="C", cumulative_context="", image_captions=[],
            style="nonexistent_style", audience="practitioner",
            compression="standard", content_focus="key_concepts",
        )
```

- [ ] **Step 11: Run fragment tests**

```bash
cd backend && uv run python -m pytest tests/unit/test_prompt_fragments.py -v
```

- [ ] **Step 12: Commit**

```bash
git add backend/app/services/summarizer/prompts/ backend/tests/unit/test_prompt_fragments.py
git commit -m "feat: faceted prompt system — base templates, 15 fragments, 5 system presets"
```

---

## Task 3: Repositories

**Goal:** Create `SummaryRepository` and update `SectionRepository`, `BookRepository`, `EvalTraceRepository` for V1.1 schema.

**Files:**
- Create: `backend/app/db/repositories/summary_repo.py`
- Modify: `backend/app/db/repositories/section_repo.py`
- Modify: `backend/app/db/repositories/book_repo.py`
- Modify: `backend/app/db/repositories/eval_repo.py`

### Step-by-step

- [ ] **Step 1: Create `SummaryRepository`**

File: `backend/app/db/repositories/summary_repo.py`

```python
"""Summary repository — data access for append-only summary log."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Summary, SummaryContentType


class SummaryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, summary: Summary) -> Summary:
        self.session.add(summary)
        await self.session.flush()
        return summary

    async def get_by_id(self, summary_id: int) -> Summary | None:
        result = await self.session.execute(
            select(Summary).where(Summary.id == summary_id)
        )
        return result.scalar_one_or_none()

    async def list_by_book(self, book_id: int) -> list[Summary]:
        result = await self.session.execute(
            select(Summary)
            .where(Summary.book_id == book_id)
            .order_by(Summary.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_content(
        self, content_type: SummaryContentType, content_id: int
    ) -> list[Summary]:
        result = await self.session.execute(
            select(Summary)
            .where(
                Summary.content_type == content_type,
                Summary.content_id == content_id,
            )
            .order_by(Summary.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_book_level(self, book_id: int) -> list[Summary]:
        """List book-level summaries only."""
        result = await self.session.execute(
            select(Summary)
            .where(
                Summary.book_id == book_id,
                Summary.content_type == SummaryContentType.BOOK,
            )
            .order_by(Summary.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_latest_by_content_and_facets(
        self,
        content_type: SummaryContentType,
        content_id: int,
        facets: dict,
    ) -> Summary | None:
        """Find existing summary with same content + facets (for idempotent skip)."""
        result = await self.session.execute(
            select(Summary)
            .where(
                Summary.content_type == content_type,
                Summary.content_id == content_id,
                Summary.facets_used == facets,
            )
            .order_by(Summary.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_for_book(self, book_id: int) -> Summary | None:
        """Get the most recent summary for a book (any content type)."""
        result = await self.session.execute(
            select(Summary)
            .where(Summary.book_id == book_id)
            .order_by(Summary.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_by_content(
        self, content_type: SummaryContentType, content_id: int
    ) -> int:
        result = await self.session.execute(
            select(func.count(Summary.id))
            .where(
                Summary.content_type == content_type,
                Summary.content_id == content_id,
            )
        )
        return result.scalar_one()
```

- [ ] **Step 2: Update `SectionRepository`**

Replace the file content to remove `SummaryStatus` references and add new methods:

```python
"""BookSection repository — data access layer."""

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookSection


class SectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_bulk(self, sections: list[BookSection]) -> list[BookSection]:
        self.session.add_all(sections)
        await self.session.flush()
        return sections

    async def create(self, section: BookSection) -> BookSection:
        self.session.add(section)
        await self.session.flush()
        return section

    async def get_by_book_id(self, book_id: int) -> list[BookSection]:
        result = await self.session.execute(
            select(BookSection)
            .where(BookSection.book_id == book_id)
            .order_by(BookSection.order_index)
        )
        return list(result.scalars().all())

    async def get_by_id(self, section_id: int) -> BookSection | None:
        result = await self.session.execute(
            select(BookSection).where(BookSection.id == section_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ids(self, section_ids: list[int]) -> list[BookSection]:
        result = await self.session.execute(
            select(BookSection)
            .where(BookSection.id.in_(section_ids))
            .order_by(BookSection.order_index)
        )
        return list(result.scalars().all())

    async def delete_by_ids(self, section_ids: list[int]) -> int:
        """Hard delete sections. Returns count deleted."""
        result = await self.session.execute(
            delete(BookSection).where(BookSection.id.in_(section_ids))
        )
        await self.session.flush()
        return result.rowcount

    async def reindex_order(self, book_id: int) -> None:
        """Re-number order_index for all sections of a book (0-based)."""
        sections = await self.get_by_book_id(book_id)
        for i, section in enumerate(sections):
            section.order_index = i
        await self.session.flush()

    async def update_default_summary(
        self, section_id: int, summary_id: int | None
    ) -> None:
        section = await self.get_by_id(section_id)
        if section:
            section.default_summary_id = summary_id
            await self.session.flush()

    async def count_by_book(self, book_id: int) -> int:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count(BookSection.id))
            .where(BookSection.book_id == book_id)
        )
        return result.scalar_one()
```

- [ ] **Step 3: Update `BookRepository` — add `default_summary_id` method**

Add to `BookRepository` in `book_repo.py`:

```python
async def update_default_summary(self, book_id: int, summary_id: int | None) -> None:
    book = await self.get_by_id(book_id)
    if book:
        book.default_summary_id = summary_id
        await self.session.flush()
```

Remove any references to `overall_summary` or `overall_summary_eval` in existing methods.

- [ ] **Step 4: Update `EvalTraceRepository` — add `summary_id` to creates**

In `eval_repo.py`, the `create()` method already takes an `EvalTrace` object. No changes needed to the repo itself — the caller will set `summary_id` on the trace before calling `create()`. Verify the `get_by_section` method still works (it queries by `section_id` which is unchanged).

Add a new query method:

```python
async def get_by_summary(self, summary_id: int) -> list[EvalTrace]:
    result = await self.session.execute(
        select(EvalTrace)
        .where(EvalTrace.summary_id == summary_id)
        .order_by(EvalTrace.assertion_category, EvalTrace.assertion_name)
    )
    return list(result.scalars().all())
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/repositories/
git commit -m "feat: SummaryRepository + updated section/book/eval repos for V1.1"
```

---

## Task 4: PresetService & QualityService

**Goal:** Create services for preset management and extraction quality validation.

**Files:**
- Create: `backend/app/services/preset_service.py`
- Create: `backend/app/services/quality_service.py`
- Create: `backend/tests/unit/test_preset_service.py`
- Create: `backend/tests/unit/test_quality_service.py`

### Step-by-step

- [ ] **Step 1: Create `PresetService`**

File: `backend/app/services/preset_service.py`

```python
"""Preset management — load, validate, create, delete YAML preset files."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
import structlog

from app.exceptions import PresetError

logger = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent / "summarizer" / "prompts"
PRESETS_DIR = PROMPTS_DIR / "presets"
FRAGMENTS_DIR = PROMPTS_DIR / "fragments"

FACET_DIMENSIONS = {
    "style": ["bullet_points", "narrative", "podcast_dialogue", "cornell_notes", "mind_map_outline", "tweet_thread"],
    "audience": ["practitioner", "academic", "executive"],
    "compression": ["brief", "standard", "detailed"],
    "content_focus": ["key_concepts", "frameworks_examples", "full_coverage"],
}


@dataclass
class Preset:
    name: str
    description: str
    system: bool
    facets: dict[str, str]
    file_path: Path


class PresetService:
    def __init__(self, presets_dir: Path | None = None):
        self.presets_dir = presets_dir or PRESETS_DIR
        self.fragments_dir = FRAGMENTS_DIR

    def load(self, name: str) -> Preset:
        """Load a preset by name. Raises PresetError if not found."""
        path = self.presets_dir / f"{name}.yaml"
        if not path.exists():
            available = ", ".join(self.list_names())
            raise PresetError(
                f'Preset "{name}" not found. Available presets: {available}'
            )
        return self._parse_file(path)

    def list_all(self) -> list[Preset]:
        """List all presets sorted by system (first) then name."""
        presets = []
        for path in sorted(self.presets_dir.glob("*.yaml")):
            try:
                presets.append(self._parse_file(path))
            except Exception as e:
                logger.warning("preset_load_failed", path=str(path), error=str(e))
        presets.sort(key=lambda p: (not p.system, p.name))
        return presets

    def list_names(self) -> list[str]:
        return [p.stem for p in sorted(self.presets_dir.glob("*.yaml"))]

    def create(
        self, name: str, description: str, facets: dict[str, str]
    ) -> Preset:
        """Create a user preset. Raises PresetError on duplicate or invalid facets."""
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            raise PresetError(
                f'Invalid preset name "{name}". Use lowercase letters, numbers, and underscores.'
            )
        path = self.presets_dir / f"{name}.yaml"
        if path.exists():
            raise PresetError(
                f'Preset "{name}" already exists. Use a different name or delete it first '
                f"with: bookcompanion preset delete {name}"
            )
        self._validate_facets(facets)
        data = {
            "name": name.replace("_", " ").title(),
            "description": description,
            "system": False,
            "facets": facets,
        }
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
        return self._parse_file(path)

    def delete(self, name: str) -> None:
        """Delete a user preset. Raises PresetError if system or not found."""
        preset = self.load(name)
        if preset.system:
            raise PresetError(f'Cannot delete system preset "{name}".')
        preset.file_path.unlink()

    def resolve_facets(
        self,
        preset_name: str | None,
        overrides: dict[str, str | None],
        default_preset: str,
    ) -> tuple[str | None, dict[str, str]]:
        """Resolve final facets from preset + overrides + defaults.

        Returns (resolved_preset_name, facets_dict).
        """
        if preset_name:
            preset = self.load(preset_name)
            facets = dict(preset.facets)
        elif any(v is not None for v in overrides.values()):
            # Individual flags provided without preset — start from default
            preset = self.load(default_preset)
            preset_name = None  # Not using a named preset
            facets = dict(preset.facets)
        else:
            preset = self.load(default_preset)
            preset_name = default_preset
            facets = dict(preset.facets)

        # Apply overrides
        for key, value in overrides.items():
            if value is not None:
                facets[key] = value
                preset_name = None  # Overridden — no longer a pure preset

        self._validate_facets(facets)
        return preset_name, facets

    def _validate_facets(self, facets: dict[str, str]) -> None:
        for dim, valid_values in FACET_DIMENSIONS.items():
            if dim not in facets:
                raise PresetError(f"Missing facet: {dim}")
            if facets[dim] not in valid_values:
                # Find available values and the fragment path for the error message
                raise PresetError(
                    f"Fragment not found: fragments/{dim}/{facets[dim]}.txt. "
                    f"Available {dim}s: {', '.join(valid_values)}"
                )

    def _parse_file(self, path: Path) -> Preset:
        with open(path) as f:
            data = yaml.safe_load(f)
        if not data or "facets" not in data:
            raise PresetError(f"Invalid preset file: {path}")
        return Preset(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            system=data.get("system", False),
            facets=data["facets"],
            file_path=path,
        )
```

- [ ] **Step 2: Create `QualityService`**

File: `backend/app/services/quality_service.py`

```python
"""Extraction quality validation — deterministic heuristics, no LLM calls."""

import re
from dataclasses import dataclass


@dataclass
class QualityIssue:
    section_index: int
    section_title: str
    check: str
    severity: str  # "error", "warning", "info"
    message: str
    suggested_action: str


# Non-content title patterns (case-insensitive)
NON_CONTENT_PATTERN = re.compile(
    r"^(copyright|about the authors?|also by|acknowledgments?|dedication|"
    r"table of contents|index|bibliography)$",
    re.IGNORECASE,
)

# Page number artifact pattern
PAGE_NUMBER_PATTERN = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)


class QualityService:
    def check_sections(
        self, sections: list[dict]
    ) -> list[QualityIssue]:
        """Run all quality checks on a list of section dicts.

        Each dict must have: index, title, content, depth, char_count.
        Returns list of QualityIssue sorted by severity (errors first).
        """
        issues: list[QualityIssue] = []
        for i, s in enumerate(sections):
            issues.extend(self._check_section(s, sections))

        severity_order = {"error": 0, "warning": 1, "info": 2}
        issues.sort(key=lambda x: severity_order.get(x.severity, 3))
        return issues

    def suggested_actions(
        self, issues: list[QualityIssue]
    ) -> list[str]:
        """Generate human-readable suggested action lines."""
        actions = []
        # Group deletes
        delete_indices = [
            i.section_index for i in issues
            if i.suggested_action == "delete" and i.severity in ("error", "warning")
        ]
        if delete_indices:
            idx_str = ", ".join(str(i) for i in delete_indices)
            reasons = set(i.check for i in issues if i.section_index in delete_indices)
            actions.append(
                f"Delete sections {idx_str} — detected as {', '.join(reasons)}"
            )

        # Merge suggestions
        for issue in issues:
            if issue.suggested_action.startswith("merge") and issue.severity == "warning":
                actions.append(
                    f"Merge section {issue.section_index} into adjacent — "
                    f"{issue.message}"
                )
        return actions

    def _check_section(
        self, section: dict, all_sections: list[dict]
    ) -> list[QualityIssue]:
        issues = []
        idx = section["index"]
        title = section["title"]
        content = section.get("content", "")
        char_count = len(content)
        depth = section.get("depth", 0)

        # Empty section
        if char_count == 0:
            issues.append(QualityIssue(
                idx, title, "empty", "error",
                "0 characters", "delete",
            ))
            return issues  # Skip other checks for empty

        # Short section
        if char_count < 200:
            issues.append(QualityIssue(
                idx, title, "short", "warning",
                f"{char_count} chars — possibly truncated",
                "merge into adjacent section",
            ))

        # Non-content section
        if NON_CONTENT_PATTERN.match(title.strip()):
            issues.append(QualityIssue(
                idx, title, "non-content", "warning",
                f"Title matches non-content pattern",
                "delete",
            ))

        # Truncated (< 200 chars AND adjacent at same depth has 5x+ chars)
        if char_count < 200:
            for other in all_sections:
                if other["index"] != idx and other.get("depth") == depth:
                    if len(other.get("content", "")) >= char_count * 5:
                        issues.append(QualityIssue(
                            idx, title, "truncated", "warning",
                            f"{char_count} chars — adjacent section has {len(other['content'])} chars",
                            "merge into adjacent",
                        ))
                        break

        # Tiny fragment
        if char_count < 500 and depth > 0:
            issues.append(QualityIssue(
                idx, title, "tiny_fragment", "warning",
                f"{char_count} chars at depth {depth}",
                "merge into parent",
            ))

        # Oversized section
        if char_count > 100_000:
            issues.append(QualityIssue(
                idx, title, "oversized", "info",
                f"{char_count:,} chars — consider splitting",
                "split at detected sub-headings",
            ))

        # Encoding issues (> 1% replacement chars)
        replacement_count = content.count("\ufffd")
        if char_count > 0 and replacement_count / char_count > 0.01:
            issues.append(QualityIssue(
                idx, title, "encoding_issues", "warning",
                f"{replacement_count} replacement characters ({replacement_count/char_count:.1%})",
                "flag for review",
            ))

        # Repeated content (3-gram Jaccard > 0.8 with any other section)
        for other in all_sections:
            if other["index"] <= idx:
                continue
            similarity = self._trigram_jaccard(content, other.get("content", ""))
            if similarity > 0.8:
                shorter = idx if char_count <= len(other.get("content", "")) else other["index"]
                issues.append(QualityIssue(
                    shorter, title, "repeated_content", "warning",
                    f">{similarity:.0%} overlap with section {other['index']}",
                    "delete the shorter duplicate",
                ))

        # Image-heavy (image-to-text ratio > 3:1)
        image_count = section.get("image_count", 0)
        if image_count > 0 and char_count > 0:
            # Rough estimate: each image ~5000 "chars" of visual info
            if image_count * 5000 > char_count * 3:
                issues.append(QualityIssue(
                    idx, title, "image_heavy", "info",
                    f"{image_count} images for {char_count:,} chars of text",
                    "flag for review",
                ))

        # Page number artifacts
        page_matches = PAGE_NUMBER_PATTERN.findall(content)
        if len(page_matches) > 3:
            issues.append(QualityIssue(
                idx, title, "page_numbers", "info",
                f"{len(page_matches)} isolated page numbers detected",
                "flag for review",
            ))

        return issues

    @staticmethod
    def _trigram_jaccard(text_a: str, text_b: str) -> float:
        """Character 3-gram Jaccard similarity."""
        if len(text_a) < 3 or len(text_b) < 3:
            return 0.0
        trigrams_a = set(text_a[i:i+3] for i in range(len(text_a) - 2))
        trigrams_b = set(text_b[i:i+3] for i in range(len(text_b) - 2))
        intersection = trigrams_a & trigrams_b
        union = trigrams_a | trigrams_b
        return len(intersection) / len(union) if union else 0.0
```

- [ ] **Step 3: Write PresetService tests**

File: `backend/tests/unit/test_preset_service.py`

```python
"""Tests for PresetService."""

import pytest
import yaml
from pathlib import Path

from app.services.preset_service import PresetService, FACET_DIMENSIONS
from app.exceptions import PresetError


@pytest.fixture
def preset_dir(tmp_path):
    """Create a temp preset directory with one system preset."""
    d = tmp_path / "presets"
    d.mkdir()
    (d / "test_system.yaml").write_text(yaml.dump({
        "name": "Test System", "description": "A test preset",
        "system": True,
        "facets": {"style": "bullet_points", "audience": "practitioner",
                   "compression": "standard", "content_focus": "key_concepts"},
    }))
    return d


@pytest.fixture
def service(preset_dir):
    return PresetService(presets_dir=preset_dir)


def test_load_existing_preset(service):
    preset = service.load("test_system")
    assert preset.system is True
    assert preset.facets["style"] == "bullet_points"


def test_load_nonexistent_raises(service):
    with pytest.raises(PresetError, match="not found"):
        service.load("nonexistent")


def test_list_all(service):
    presets = service.list_all()
    assert len(presets) == 1
    assert presets[0].name == "Test System"


def test_create_user_preset(service, preset_dir):
    facets = {"style": "narrative", "audience": "academic",
              "compression": "detailed", "content_focus": "full_coverage"}
    preset = service.create("my_custom", "Custom preset", facets)
    assert preset.system is False
    assert (preset_dir / "my_custom.yaml").exists()


def test_create_duplicate_raises(service):
    with pytest.raises(PresetError, match="already exists"):
        service.create("test_system", "Dup", {
            "style": "narrative", "audience": "academic",
            "compression": "detailed", "content_focus": "full_coverage",
        })


def test_create_invalid_facet_raises(service):
    with pytest.raises(PresetError, match="Fragment not found"):
        service.create("bad", "Bad preset", {
            "style": "haiku", "audience": "academic",
            "compression": "detailed", "content_focus": "full_coverage",
        })


def test_delete_user_preset(service, preset_dir):
    facets = {"style": "narrative", "audience": "academic",
              "compression": "detailed", "content_focus": "full_coverage"}
    service.create("deletable", "To delete", facets)
    service.delete("deletable")
    assert not (preset_dir / "deletable.yaml").exists()


def test_delete_system_preset_raises(service):
    with pytest.raises(PresetError, match="Cannot delete system preset"):
        service.delete("test_system")


def test_resolve_facets_with_preset(service):
    name, facets = service.resolve_facets("test_system", {}, "test_system")
    assert name == "test_system"
    assert facets["style"] == "bullet_points"


def test_resolve_facets_with_overrides(service):
    overrides = {"style": "narrative", "audience": None, "compression": None, "content_focus": None}
    name, facets = service.resolve_facets("test_system", overrides, "test_system")
    assert name is None  # Overridden, no longer a pure preset
    assert facets["style"] == "narrative"
    assert facets["audience"] == "practitioner"  # From preset


def test_resolve_facets_default(service):
    name, facets = service.resolve_facets(
        None, {"style": None, "audience": None, "compression": None, "content_focus": None},
        "test_system"
    )
    assert name == "test_system"
```

- [ ] **Step 4: Write QualityService tests**

File: `backend/tests/unit/test_quality_service.py`

```python
"""Tests for QualityService quality checks."""

import pytest
from app.services.quality_service import QualityService


@pytest.fixture
def svc():
    return QualityService()


def _section(index, title, content="x" * 1000, depth=0, image_count=0):
    return {"index": index, "title": title, "content": content,
            "depth": depth, "char_count": len(content), "image_count": image_count}


def test_empty_section(svc):
    sections = [_section(1, "Empty", content="")]
    issues = svc.check_sections(sections)
    assert any(i.check == "empty" and i.severity == "error" for i in issues)


def test_short_section(svc):
    sections = [_section(1, "Short", content="x" * 100)]
    issues = svc.check_sections(sections)
    assert any(i.check == "short" for i in issues)


def test_non_content_section(svc):
    for title in ["Copyright", "About the Author", "Index", "Bibliography", "Acknowledgments"]:
        sections = [_section(1, title)]
        issues = svc.check_sections(sections)
        assert any(i.check == "non-content" for i in issues), f"Failed for: {title}"


def test_normal_title_not_flagged(svc):
    sections = [_section(1, "The Five Forces Framework")]
    issues = svc.check_sections(sections)
    assert not any(i.check == "non-content" for i in issues)


def test_oversized_section(svc):
    sections = [_section(1, "Big", content="x" * 150_000)]
    issues = svc.check_sections(sections)
    assert any(i.check == "oversized" for i in issues)


def test_encoding_issues(svc):
    content = "a" * 90 + "\ufffd" * 10 + "a" * 900
    sections = [_section(1, "Bad Encoding", content=content)]
    issues = svc.check_sections(sections)
    assert any(i.check == "encoding_issues" for i in issues)


def test_repeated_content(svc):
    text = "The quick brown fox jumps over the lazy dog. " * 50
    sections = [_section(1, "A", content=text), _section(2, "B", content=text)]
    issues = svc.check_sections(sections)
    assert any(i.check == "repeated_content" for i in issues)


def test_no_false_positive_on_different_content(svc):
    sections = [
        _section(1, "A", content="Alpha bravo charlie delta echo foxtrot " * 50),
        _section(2, "B", content="Golf hotel india juliet kilo lima " * 50),
    ]
    issues = svc.check_sections(sections)
    assert not any(i.check == "repeated_content" for i in issues)


def test_trigram_jaccard_identical():
    assert QualityService._trigram_jaccard("hello world", "hello world") == 1.0


def test_trigram_jaccard_different():
    assert QualityService._trigram_jaccard("abcdef", "uvwxyz") == 0.0


def test_suggested_actions_groups_deletes(svc):
    sections = [
        _section(1, "Copyright", content="x" * 500),
        _section(2, "Good Chapter"),
        _section(3, "Index", content="x" * 500),
    ]
    issues = svc.check_sections(sections)
    actions = svc.suggested_actions(issues)
    assert any("Delete" in a for a in actions)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run python -m pytest tests/unit/test_preset_service.py tests/unit/test_quality_service.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/preset_service.py backend/app/services/quality_service.py \
  backend/tests/unit/test_preset_service.py backend/tests/unit/test_quality_service.py
git commit -m "feat: PresetService (YAML CRUD + facet resolution) and QualityService (10 heuristics)"
```

---

## Task 5: SummaryService

**Goal:** Create the service for summary log queries: list, compare, set-default, concept diff extraction.

**Files:**
- Create: `backend/app/services/summary_service.py`
- Create: `backend/tests/unit/test_summary_service.py`

### Step-by-step

- [ ] **Step 1: Create `SummaryService`**

File: `backend/app/services/summary_service.py`

```python
"""Summary service — list, compare, set-default, concept diff."""

import re

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Book, BookSection, Summary, SummaryContentType
from app.db.repositories.book_repo import BookRepository
from app.db.repositories.section_repo import SectionRepository
from app.db.repositories.summary_repo import SummaryRepository
from app.exceptions import SummaryError

logger = structlog.get_logger()

# Concept extraction regex patterns (spec section 8.2)
BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
HEADER_PATTERN = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
NAMED_ENTITY_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")


class SummaryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.summary_repo = SummaryRepository(session)
        self.book_repo = BookRepository(session)
        self.section_repo = SectionRepository(session)

    async def get_by_id(self, summary_id: int) -> Summary:
        summary = await self.summary_repo.get_by_id(summary_id)
        if not summary:
            raise SummaryError(f"Summary #{summary_id} not found.")
        return summary

    async def list_for_book(self, book_id: int) -> list[Summary]:
        return await self.summary_repo.list_by_book(book_id)

    async def list_for_content(
        self, content_type: SummaryContentType, content_id: int
    ) -> list[Summary]:
        return await self.summary_repo.list_by_content(content_type, content_id)

    async def list_book_level(self, book_id: int) -> list[Summary]:
        return await self.summary_repo.list_book_level(book_id)

    async def set_default(self, summary_id: int) -> Summary:
        """Set a summary as the default for its section/book.

        Returns the summary. Raises SummaryError if summary or target not found.
        """
        summary = await self.get_by_id(summary_id)

        if summary.content_type == SummaryContentType.SECTION:
            section = await self.section_repo.get_by_id(summary.content_id)
            if not section:
                raise SummaryError(
                    f"Section #{summary.content_id} not found "
                    f"(summary references a deleted section)."
                )
            await self.section_repo.update_default_summary(section.id, summary_id)
        elif summary.content_type == SummaryContentType.BOOK:
            book = await self.book_repo.get_by_id(summary.content_id)
            if not book:
                raise SummaryError(
                    f"Book #{summary.content_id} not found."
                )
            await self.book_repo.update_default_summary(book.id, summary_id)
        else:
            raise SummaryError(
                f"Cannot set default for content_type={summary.content_type.value}"
            )

        return summary

    def extract_concepts(self, text: str) -> set[str]:
        """Extract concepts from summary text using deterministic regex."""
        concepts = set()
        concepts.update(BOLD_PATTERN.findall(text))
        concepts.update(HEADER_PATTERN.findall(text))
        concepts.update(NAMED_ENTITY_PATTERN.findall(text))
        return concepts

    def concept_diff(
        self, summary_a: Summary, summary_b: Summary
    ) -> dict[str, set[str]]:
        """Compare two summaries and return concepts unique to each."""
        concepts_a = self.extract_concepts(summary_a.summary_md)
        concepts_b = self.extract_concepts(summary_b.summary_md)
        return {
            "only_in_a": concepts_a - concepts_b,
            "only_in_b": concepts_b - concepts_a,
            "shared": concepts_a & concepts_b,
        }

    async def get_last_used_preset(self, book_id: int) -> str | None:
        """Get the preset name from the most recent summary for a book."""
        latest = await self.summary_repo.get_latest_for_book(book_id)
        return latest.preset_name if latest else None
```

- [ ] **Step 2: Write tests**

File: `backend/tests/unit/test_summary_service.py`

```python
"""Tests for SummaryService concept diff and extraction."""

import pytest
from app.services.summary_service import SummaryService, BOLD_PATTERN, HEADER_PATTERN, NAMED_ENTITY_PATTERN


class TestConceptExtraction:
    def setup_method(self):
        # SummaryService needs a session but concept methods don't use it
        self.svc = SummaryService.__new__(SummaryService)

    def test_extracts_bold_terms(self):
        text = "The **Five Forces** framework and **Value Chain** analysis"
        concepts = self.svc.extract_concepts(text)
        assert "Five Forces" in concepts
        assert "Value Chain" in concepts

    def test_extracts_headers(self):
        text = "## Strategic Positioning\nContent here\n### Cost Leadership"
        concepts = self.svc.extract_concepts(text)
        assert "Strategic Positioning" in concepts
        assert "Cost Leadership" in concepts

    def test_extracts_named_entities(self):
        text = "Michael Porter argues that Competitive Advantage is key"
        concepts = self.svc.extract_concepts(text)
        assert "Michael Porter" in concepts
        assert "Competitive Advantage" in concepts

    def test_concept_diff(self):
        from unittest.mock import MagicMock
        a = MagicMock()
        a.summary_md = "The **Five Forces** drive **Competitive Advantage**"
        b = MagicMock()
        b.summary_md = "The **Five Forces** and **Value Chain** are central"

        diff = self.svc.concept_diff(a, b)
        assert "Competitive Advantage" in diff["only_in_a"]
        assert "Value Chain" in diff["only_in_b"]
        assert "Five Forces" in diff["shared"]

    def test_empty_text(self):
        concepts = self.svc.extract_concepts("")
        assert concepts == set()
```

- [ ] **Step 3: Run tests and commit**

```bash
cd backend && uv run python -m pytest tests/unit/test_summary_service.py -v
git add backend/app/services/summary_service.py backend/tests/unit/test_summary_service.py
git commit -m "feat: SummaryService — list, set-default, concept diff extraction"
```

---

## Task 6: SummarizerService Refactor

**Goal:** Refactor `SummarizerService` to use faceted fragment composition, write to the `summaries` table, implement idempotent skip logic, and accept preset/facets parameters. Support progress callbacks for CLI display.

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py`
- Modify: `backend/tests/unit/test_summarizer.py`

### Step-by-step

- [ ] **Step 1: Refactor `SummarizerService.__init__` and template loading**

Update the Jinja2 environment to use `PROMPTS_DIR` (same base directory), which now resolves `base/` templates and `fragments/` includes:

```python
# The __init__ stays mostly the same — the FileSystemLoader already points to PROMPTS_DIR.
# The key change is loading base templates instead of v1 templates.

def __init__(self, db: AsyncSession, llm: LLMProvider, config, captioner=None):
    self.db = db
    self.llm = llm
    self.config = config
    self.captioner = captioner
    self._jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(PROMPTS_DIR))
    )
    self._summary_repo = SummaryRepository(db)
    self._section_repo = SectionRepository(db)
    self._book_repo = BookRepository(db)
```

- [ ] **Step 2: Rewrite `summarize_book()` method**

The new signature accepts preset/facets instead of `detail_level`:

```python
async def summarize_book(
    self,
    book_id: int,
    preset_name: str | None = None,
    facets: dict[str, str] | None = None,
    force: bool = False,
    model: str | None = None,
    skip_eval: bool = False,
    on_section_complete: Callable | None = None,
    on_section_skip: Callable | None = None,
    on_section_fail: Callable | None = None,
) -> dict:
    """Orchestrate full book summarization with faceted prompts.

    Returns: {"completed": int, "skipped": int, "failed": list[int]}
    """
```

Key logic changes:
- Load sections via `_section_repo.get_by_book_id(book_id)`
- For each section, check idempotency via `_summary_repo.get_latest_by_content_and_facets(SECTION, section.id, facets)` — skip if exists and not `force`
- Build prompt using `base/summarize_section.txt` with facets as template variables
- Create `Summary` row (not write to `section.summary_md`)
- Set `section.default_summary_id` to the new summary ID
- Track timing in `latency_ms`
- After all sections, call `_generate_book_summary()` with same facets
- Return stats dict

- [ ] **Step 3: Rewrite `_summarize_single_section()` to return `Summary` object**

```python
async def _summarize_single_section(
    self,
    book_id: int,
    section: BookSection,
    facets: dict[str, str],
    preset_name: str | None,
    model: str | None,
    cumulative_context: str,
) -> Summary:
    """Summarize one section. Returns a Summary model (not yet committed)."""
    import time

    book = await self._book_repo.get_by_id(book_id)
    author = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"

    image_captions = await self._get_image_captions(section) if self.captioner else []

    template = self._jinja_env.get_template("base/summarize_section.txt")
    prompt = template.render(
        book_title=book.title,
        author=author,
        section_title=section.title,
        section_content=section.content_md or "",
        cumulative_context=cumulative_context,
        image_captions=image_captions,
        **facets,
    )

    effective_model = model or self.config.llm.model
    start = time.monotonic()
    response = await self.llm.generate(prompt, model=effective_model)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    summary_text = self._extract_summary_text(response)

    summary = Summary(
        content_type=SummaryContentType.SECTION,
        content_id=section.id,
        book_id=book_id,
        preset_name=preset_name,
        facets_used=facets,
        prompt_text_sent=prompt,
        model_used=effective_model,
        input_tokens=getattr(response, "input_tokens", None),
        output_tokens=getattr(response, "output_tokens", None),
        input_char_count=len(section.content_md or ""),
        summary_char_count=len(summary_text),
        summary_md=summary_text,
        latency_ms=elapsed_ms,
    )
    return await self._summary_repo.create(summary)
```

- [ ] **Step 4: Rewrite `_generate_book_summary()` to use facets and return Summary**

```python
async def _generate_book_summary(
    self,
    book_id: int,
    facets: dict[str, str],
    preset_name: str | None,
    model: str | None,
) -> Summary:
    """Generate book-level summary from section summaries."""
    import time

    book = await self._book_repo.get_by_id(book_id)
    sections = await self._section_repo.get_by_book_id(book_id)
    author = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"

    # Collect default summaries for each section
    section_data = []
    for s in sections:
        if s.default_summary_id:
            summary = await self._summary_repo.get_by_id(s.default_summary_id)
            if summary:
                section_data.append({"title": s.title, "summary": summary.summary_md})

    template = self._jinja_env.get_template("base/summarize_book.txt")
    prompt = template.render(
        book_title=book.title,
        author=author,
        section_count=len(section_data),
        sections=section_data,
        **facets,
    )

    effective_model = model or self.config.llm.model
    start = time.monotonic()
    response = await self.llm.generate(prompt, model=effective_model)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    summary_text = self._extract_summary_text(response)
    combined_input = "\n".join(s["summary"] for s in section_data)

    summary = Summary(
        content_type=SummaryContentType.BOOK,
        content_id=book_id,
        book_id=book_id,
        preset_name=preset_name,
        facets_used=facets,
        prompt_text_sent=prompt,
        model_used=effective_model,
        input_tokens=getattr(response, "input_tokens", None),
        output_tokens=getattr(response, "output_tokens", None),
        input_char_count=len(combined_input),
        summary_char_count=len(summary_text),
        summary_md=summary_text,
        latency_ms=elapsed_ms,
    )
    saved = await self._summary_repo.create(summary)
    await self._book_repo.update_default_summary(book_id, saved.id)
    return saved
```

- [ ] **Step 5: Remove `quick_summary()` method body, make it alias**

```python
async def quick_summary(self, book_id: int) -> None:
    """Deprecated: runs summarize with executive_brief preset."""
    await self.summarize_book(
        book_id=book_id,
        preset_name="executive_brief",
        facets={"style": "bullet_points", "audience": "executive",
                "compression": "brief", "content_focus": "key_concepts"},
    )
```

- [ ] **Step 6: Update test_summarizer.py for new interface**

Update existing tests to use the new `preset_name`/`facets` parameters instead of `detail_level`. Verify that:
- `summarize_book()` accepts facets dict
- Idempotent skip works (mock `get_latest_by_content_and_facets` to return existing summary)
- `force=True` bypasses skip
- Summary objects are created (not written to section.summary_md)

- [ ] **Step 7: Run tests and commit**

```bash
cd backend && uv run python -m pytest tests/unit/test_summarizer.py -v
git add backend/app/services/summarizer/summarizer_service.py backend/tests/unit/test_summarizer.py
git commit -m "refactor: SummarizerService — faceted prompts, append-only summary log, idempotent skip"
```

---

## Task 7: SectionEditService

**Goal:** Create the section editing service supporting merge, split, reorder, delete — both in-memory (pre-save) and DB-backed (post-save).

**Files:**
- Create: `backend/app/services/section_edit_service.py`
- Create: `backend/tests/unit/test_section_edit.py`
- Create: `backend/tests/unit/test_repl_parsing.py`

### Step-by-step

- [ ] **Step 1: Create REPL command parser**

Put parsing functions at the top of `section_edit_service.py`:

```python
"""Section editing — merge, split, reorder, delete (in-memory and DB-backed)."""

import re
from dataclasses import dataclass, field

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookSection
from app.db.repositories.section_repo import SectionRepository
from app.exceptions import SectionEditError

logger = structlog.get_logger()


@dataclass
class EditCommand:
    action: str  # merge, split, move, delete, undo, show, done
    indices: list[int] = field(default_factory=list)
    title: str | None = None
    split_mode: str | None = None  # "heading", "char", "paragraph"
    split_value: int | None = None
    target_after: int | None = None


def parse_command(raw: str) -> EditCommand:
    """Parse a REPL command string into an EditCommand."""
    raw = raw.strip()
    if not raw:
        raise SectionEditError("Empty command.")

    parts = raw.split(None, 1)
    action = parts[0].lower()

    if action == "done":
        return EditCommand(action="done")
    if action == "show":
        return EditCommand(action="show")
    if action == "undo":
        return EditCommand(action="undo")

    if action == "merge":
        # merge 3,4,5 "Combined Title"
        rest = parts[1] if len(parts) > 1 else ""
        match = re.match(r'([\d,\s]+)\s*(?:"([^"]+)")?', rest)
        if not match:
            raise SectionEditError('Usage: merge 3,4,5 "New Title"')
        indices = [int(x.strip()) for x in match.group(1).split(",") if x.strip()]
        title = match.group(2)
        if len(indices) < 2:
            raise SectionEditError("Merge requires at least 2 section indices.")
        return EditCommand(action="merge", indices=indices, title=title)

    if action == "split":
        # split 3 --at-heading | --at-char 5000 | --at-paragraph 5000
        rest = parts[1] if len(parts) > 1 else ""
        idx_match = re.match(r"(\d+)\s+(.*)", rest)
        if not idx_match:
            raise SectionEditError("Usage: split <index> --at-heading|--at-char N|--at-paragraph N")
        idx = int(idx_match.group(1))
        flags = idx_match.group(2)
        if "--at-heading" in flags:
            return EditCommand(action="split", indices=[idx], split_mode="heading")
        char_match = re.search(r"--at-char\s+(\d+)", flags)
        if char_match:
            return EditCommand(action="split", indices=[idx], split_mode="char", split_value=int(char_match.group(1)))
        para_match = re.search(r"--at-paragraph\s+(\d+)", flags)
        if para_match:
            return EditCommand(action="split", indices=[idx], split_mode="paragraph", split_value=int(para_match.group(1)))
        raise SectionEditError("Split requires --at-heading, --at-char N, or --at-paragraph N")

    if action == "move":
        # move 5 --after 2
        rest = parts[1] if len(parts) > 1 else ""
        match = re.match(r"(\d+)\s+--after\s+(\d+)", rest)
        if not match:
            raise SectionEditError("Usage: move <index> --after <index>")
        return EditCommand(action="move", indices=[int(match.group(1))], target_after=int(match.group(2)))

    if action == "delete":
        # delete 7,8
        rest = parts[1] if len(parts) > 1 else ""
        indices = [int(x.strip()) for x in rest.split(",") if x.strip().isdigit()]
        if not indices:
            raise SectionEditError("Usage: delete 7,8")
        return EditCommand(action="delete", indices=indices)

    raise SectionEditError(f'Unknown command: "{action}". Available: merge, split, move, delete, undo, show, done')
```

- [ ] **Step 2: Create `SectionEditService` class**

```python
@dataclass
class SectionItem:
    """In-memory representation of a section for editing."""
    index: int
    id: int | None  # DB id (None for newly created during editing)
    title: str
    content: str
    depth: int
    char_count: int
    derived_from: list[int] | None = None


class SectionEditService:
    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self._section_repo = SectionRepository(session) if session else None
        self._undo_stack: list[list[SectionItem]] | None = None

    # --- In-Memory Operations (pre-save during add) ---

    def init_memory_mode(self, sections: list[SectionItem]) -> None:
        """Initialize for in-memory editing with undo support."""
        self._sections = list(sections)
        self._undo_stack = [self._snapshot()]

    def get_sections(self) -> list[SectionItem]:
        return list(self._sections)

    def merge(self, indices: list[int], title: str | None = None) -> SectionItem:
        """Merge sections at given 1-based indices."""
        items = [s for s in self._sections if s.index in indices]
        if len(items) != len(indices):
            missing = set(indices) - {s.index for s in self._sections}
            raise SectionEditError(f"Section(s) not found: {missing}")

        items.sort(key=lambda s: s.index)
        merged_content = "\n\n".join(s.content for s in items)
        merged_title = title or " + ".join(s.title for s in items)
        derived = [s.id for s in items if s.id is not None]

        self._save_undo()
        new_item = SectionItem(
            index=items[0].index,
            id=None,
            title=merged_title,
            content=merged_content,
            depth=items[0].depth,
            char_count=len(merged_content),
            derived_from=derived or None,
        )
        # Remove merged items, insert new one
        self._sections = [s for s in self._sections if s.index not in indices]
        self._sections.append(new_item)
        self._reindex()
        return new_item

    def split_at_char(self, index: int, position: int) -> list[SectionItem]:
        """Split section at exact character position."""
        item = self._get_by_index(index)
        self._save_undo()

        part1_content = item.content[:position]
        part2_content = item.content[position:]

        new_items = [
            SectionItem(index=0, id=None, title=f"{item.title} (Part 1)",
                        content=part1_content, depth=item.depth,
                        char_count=len(part1_content),
                        derived_from=[item.id] if item.id else None),
            SectionItem(index=0, id=None, title=f"{item.title} (Part 2)",
                        content=part2_content, depth=item.depth,
                        char_count=len(part2_content),
                        derived_from=[item.id] if item.id else None),
        ]
        self._sections = [s for s in self._sections if s.index != index]
        insert_pos = next((i for i, s in enumerate(self._sections) if s.index > index), len(self._sections))
        for ni in reversed(new_items):
            self._sections.insert(insert_pos, ni)
        self._reindex()
        return new_items

    def split_at_paragraph(self, index: int, target_pos: int) -> list[SectionItem]:
        """Split at nearest paragraph boundary (\\n\\n) to target position."""
        item = self._get_by_index(index)
        content = item.content

        # Find nearest \n\n to target position
        best_pos = None
        best_dist = float("inf")
        for match in re.finditer(r"\n\n", content):
            dist = abs(match.start() - target_pos)
            if dist < best_dist:
                best_dist = dist
                best_pos = match.end()

        if best_pos is None or best_dist > 500:
            logger.warning("no_paragraph_boundary", target=target_pos)
            return self.split_at_char(index, target_pos)

        return self.split_at_char(index, best_pos)

    def detect_headings(self, index: int) -> list[tuple[str, int]]:
        """Detect sub-headings in a section. Returns [(heading_text, char_position)]."""
        item = self._get_by_index(index)
        headings = []
        for match in re.finditer(r"^#{2,6}\s+(.+)$", item.content, re.MULTILINE):
            headings.append((match.group(1), match.start()))
        return headings

    def split_at_headings(self, index: int, heading_positions: list[int] | None = None) -> list[SectionItem]:
        """Split section at heading positions."""
        item = self._get_by_index(index)
        all_headings = self.detect_headings(index)
        if not all_headings:
            raise SectionEditError(
                f"No sub-headings detected in section {index}. "
                "Use --at-char <position> or --at-paragraph <position> to split manually."
            )

        if heading_positions:
            all_headings = [(h, p) for h, p in all_headings if p in heading_positions]

        self._save_undo()
        positions = [p for _, p in all_headings]
        positions.insert(0, 0)

        new_items = []
        for i, start in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(item.content)
            sub_content = item.content[start:end].strip()
            sub_title = all_headings[i][0] if i < len(all_headings) else f"{item.title} (Intro)"
            if i == 0 and start == 0 and len(positions) > 1:
                sub_title = f"{item.title} (Intro)"
            new_items.append(SectionItem(
                index=0, id=None, title=sub_title, content=sub_content,
                depth=item.depth, char_count=len(sub_content),
                derived_from=[item.id] if item.id else None,
            ))

        self._sections = [s for s in self._sections if s.index != index]
        insert_pos = next((i for i, s in enumerate(self._sections) if s.index > index), len(self._sections))
        for ni in reversed(new_items):
            self._sections.insert(insert_pos, ni)
        self._reindex()
        return new_items

    def move(self, index: int, after: int) -> None:
        """Move section to after another section."""
        item = self._get_by_index(index)
        if after != 0 and not any(s.index == after for s in self._sections):
            raise SectionEditError(f"Target section {after} not found.")
        self._save_undo()
        self._sections.remove(item)
        if after == 0:
            self._sections.insert(0, item)
        else:
            target_pos = next(i for i, s in enumerate(self._sections) if s.index == after)
            self._sections.insert(target_pos + 1, item)
        self._reindex()

    def delete(self, indices: list[int]) -> int:
        """Delete sections by index. Returns count deleted."""
        remaining = len(self._sections) - len(indices)
        if remaining < 1:
            raise SectionEditError("Cannot delete all sections. At least 1 section must remain.")
        self._save_undo()
        before = len(self._sections)
        self._sections = [s for s in self._sections if s.index not in indices]
        self._reindex()
        return before - len(self._sections)

    def undo(self) -> bool:
        """Revert last operation. Returns True if undo succeeded."""
        if not self._undo_stack or len(self._undo_stack) < 2:
            return False
        self._undo_stack.pop()  # Remove current state
        self._sections = self._undo_stack[-1]
        return True

    # --- DB-Backed Operations (post-save) ---

    async def db_merge(self, book_id: int, section_ids: list[int], title: str | None = None) -> BookSection:
        """Merge sections in DB. Atomic transaction."""
        sections = await self._section_repo.get_by_ids(section_ids)
        if len(sections) != len(section_ids):
            raise SectionEditError("One or more sections not found.")

        sections.sort(key=lambda s: s.order_index)
        merged_content = "\n\n".join(s.content_md or "" for s in sections)
        merged_title = title or " + ".join(s.title for s in sections)
        derived = [s.id for s in sections]

        new_section = BookSection(
            book_id=book_id,
            title=merged_title,
            order_index=sections[0].order_index,
            depth=sections[0].depth,
            content_md=merged_content,
            content_token_count=len(merged_content) // 4,
            derived_from=derived,
        )
        await self._section_repo.create(new_section)
        await self._section_repo.delete_by_ids(section_ids)
        await self._section_repo.reindex_order(book_id)

        # Clear book-level default summary
        from app.db.repositories.book_repo import BookRepository
        book_repo = BookRepository(self.session)
        await book_repo.update_default_summary(book_id, None)

        await self.session.flush()
        return new_section

    async def db_split_at_char(self, book_id: int, section_id: int, position: int) -> list[BookSection]:
        """Split section at character position in DB. Atomic transaction."""
        section = await self._section_repo.get_by_id(section_id)
        if not section:
            raise SectionEditError(f"Section {section_id} not found.")

        content = section.content_md or ""
        new_sections = []
        for i, (start, end) in enumerate([(0, position), (position, len(content))]):
            sub_content = content[start:end].strip()
            ns = BookSection(
                book_id=book_id,
                title=f"{section.title} (Part {i+1})",
                order_index=section.order_index + i,
                depth=section.depth,
                content_md=sub_content,
                content_token_count=len(sub_content) // 4,
                derived_from=[section.id],
            )
            new_sections.append(await self._section_repo.create(ns))

        await self._section_repo.delete_by_ids([section_id])
        await self._section_repo.reindex_order(book_id)

        from app.db.repositories.book_repo import BookRepository
        book_repo = BookRepository(self.session)
        await book_repo.update_default_summary(book_id, None)

        await self.session.flush()
        return new_sections

    async def db_delete(self, book_id: int, section_ids: list[int]) -> int:
        """Delete sections from DB. Validates at least 1 remains."""
        total = await self._section_repo.count_by_book(book_id)
        if total - len(section_ids) < 1:
            raise SectionEditError("Cannot delete all sections. At least 1 section must remain.")
        count = await self._section_repo.delete_by_ids(section_ids)
        await self._section_repo.reindex_order(book_id)
        await self.session.flush()
        return count

    async def db_move(self, book_id: int, section_id: int, after_id: int) -> None:
        """Move a section after another in DB."""
        section = await self._section_repo.get_by_id(section_id)
        target = await self._section_repo.get_by_id(after_id) if after_id else None
        if not section:
            raise SectionEditError(f"Section {section_id} not found.")
        if after_id and not target:
            raise SectionEditError(f"Target section {after_id} not found.")

        new_order = (target.order_index + 1) if target else 0
        section.order_index = new_order
        await self._section_repo.reindex_order(book_id)
        await self.session.flush()

    # --- Helpers ---

    def _get_by_index(self, index: int) -> SectionItem:
        for s in self._sections:
            if s.index == index:
                return s
        raise SectionEditError(f"Section {index} not found.")

    def _reindex(self) -> None:
        self._sections.sort(key=lambda s: s.index)
        for i, s in enumerate(self._sections):
            s.index = i + 1

    def _save_undo(self) -> None:
        if self._undo_stack is not None:
            self._undo_stack.append(self._snapshot())

    def _snapshot(self) -> list[SectionItem]:
        return [SectionItem(s.index, s.id, s.title, s.content, s.depth, s.char_count, s.derived_from) for s in self._sections]
```

- [ ] **Step 3: Write REPL parsing tests**

File: `backend/tests/unit/test_repl_parsing.py`

```python
"""Tests for section editing REPL command parser."""

import pytest
from app.services.section_edit_service import parse_command, EditCommand
from app.exceptions import SectionEditError


def test_parse_merge():
    cmd = parse_command('merge 3,4,5 "Combined Title"')
    assert cmd.action == "merge"
    assert cmd.indices == [3, 4, 5]
    assert cmd.title == "Combined Title"


def test_parse_merge_no_title():
    cmd = parse_command("merge 1,2")
    assert cmd.indices == [1, 2]
    assert cmd.title is None


def test_parse_split_heading():
    cmd = parse_command("split 3 --at-heading")
    assert cmd.action == "split"
    assert cmd.indices == [3]
    assert cmd.split_mode == "heading"


def test_parse_split_char():
    cmd = parse_command("split 3 --at-char 5000")
    assert cmd.split_mode == "char"
    assert cmd.split_value == 5000


def test_parse_split_paragraph():
    cmd = parse_command("split 3 --at-paragraph 5000")
    assert cmd.split_mode == "paragraph"
    assert cmd.split_value == 5000


def test_parse_move():
    cmd = parse_command("move 5 --after 2")
    assert cmd.action == "move"
    assert cmd.indices == [5]
    assert cmd.target_after == 2


def test_parse_delete():
    cmd = parse_command("delete 7,8")
    assert cmd.action == "delete"
    assert cmd.indices == [7, 8]


def test_parse_done():
    assert parse_command("done").action == "done"


def test_parse_show():
    assert parse_command("show").action == "show"


def test_parse_undo():
    assert parse_command("undo").action == "undo"


def test_parse_unknown_raises():
    with pytest.raises(SectionEditError, match="Unknown command"):
        parse_command("invalid_cmd")


def test_parse_empty_raises():
    with pytest.raises(SectionEditError):
        parse_command("")


def test_parse_merge_single_index_raises():
    with pytest.raises(SectionEditError, match="at least 2"):
        parse_command("merge 3")
```

- [ ] **Step 4: Write section edit service tests**

File: `backend/tests/unit/test_section_edit.py`

```python
"""Tests for SectionEditService in-memory operations."""

import pytest
from app.services.section_edit_service import SectionEditService, SectionItem
from app.exceptions import SectionEditError


def _make_sections(count=5):
    return [SectionItem(i+1, i+100, f"Section {i+1}", f"Content {i+1} " * 200, 0, 2000) for i in range(count)]


@pytest.fixture
def svc():
    s = SectionEditService()
    s.init_memory_mode(_make_sections())
    return s


def test_merge(svc):
    result = svc.merge([2, 3], "Merged")
    sections = svc.get_sections()
    assert len(sections) == 4
    assert result.title == "Merged"
    assert result.derived_from == [101, 102]
    assert "Content 2" in result.content
    assert "Content 3" in result.content


def test_split_at_char(svc):
    result = svc.split_at_char(1, 500)
    sections = svc.get_sections()
    assert len(sections) == 6
    assert result[0].title == "Section 1 (Part 1)"


def test_split_at_paragraph(svc):
    # Create a section with paragraph breaks
    svc._sections[0].content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    result = svc.split_at_paragraph(1, 20)
    assert len(result) == 2


def test_move(svc):
    svc.move(1, 3)
    sections = svc.get_sections()
    titles = [s.title for s in sections]
    assert titles.index("Section 1") > titles.index("Section 3")


def test_delete(svc):
    count = svc.delete([4, 5])
    assert count == 2
    assert len(svc.get_sections()) == 3


def test_delete_all_raises(svc):
    with pytest.raises(SectionEditError, match="Cannot delete all"):
        svc.delete([1, 2, 3, 4, 5])


def test_undo(svc):
    svc.delete([5])
    assert len(svc.get_sections()) == 4
    assert svc.undo()
    assert len(svc.get_sections()) == 5


def test_undo_no_history(svc):
    assert not svc.undo()  # Only initial state, nothing to undo


def test_reindex_after_operations(svc):
    svc.delete([3])
    sections = svc.get_sections()
    indices = [s.index for s in sections]
    assert indices == [1, 2, 3, 4]  # Reindexed


def test_detect_headings(svc):
    svc._sections[0].content = "Intro text\n\n## Heading One\nContent\n\n## Heading Two\nMore"
    headings = svc.detect_headings(1)
    assert len(headings) == 2
    assert headings[0][0] == "Heading One"
```

- [ ] **Step 5: Run tests and commit**

```bash
cd backend && uv run python -m pytest tests/unit/test_repl_parsing.py tests/unit/test_section_edit.py -v
git add backend/app/services/section_edit_service.py \
  backend/tests/unit/test_repl_parsing.py backend/tests/unit/test_section_edit.py
git commit -m "feat: SectionEditService — merge/split/reorder/delete with REPL parser and undo"
```

---

## Task 8: EvalService, BookService, ExportService & deps.py

**Goal:** Adapt EvalService for facet-sensitive assertions, update BookService for new status derivation, update ExportService to read from `summaries` table, and wire all new services in `deps.py`.

**Files:**
- Modify: `backend/app/services/summarizer/evaluator.py`
- Modify: `backend/app/services/book_service.py`
- Modify: `backend/app/services/export_service.py`
- Modify: `backend/app/cli/deps.py`
- Create: `backend/tests/unit/test_eval_adaptations.py`

### Step-by-step

- [ ] **Step 1: Update `EvalService` for facet-sensitive assertions**

Key changes to `evaluator.py`:

1. `evaluate_summary()` now accepts `facets_used: dict` and `summary_id: int | None` parameters
2. Pass `facets_used` to each assertion runner
3. Assertions that need adaptation (`reasonable_length`, `has_key_concepts`, `covers_main_themes`, `appropriate_detail_level`, `well_structured`) read from `facets_used`
4. `EvalTrace` creation includes `summary_id` FK

Add a facet-aware threshold method:

```python
def _get_compression_range(self, facets: dict) -> tuple[float, float]:
    """Get acceptable compression range based on facets."""
    compression = facets.get("compression", "standard")
    style = facets.get("style", "narrative")

    # Tweet thread overrides compression
    if style == "tweet_thread":
        return (2.0, 8.0)

    ranges = {
        "brief": (5.0, 15.0),
        "standard": (15.0, 25.0),
        "detailed": (25.0, 40.0),
    }
    return ranges.get(compression, (15.0, 25.0))
```

Update trace creation to include `summary_id`:

```python
trace = EvalTrace(
    section_id=section_id,
    summary_id=summary_id,  # NEW
    assertion_name=name,
    assertion_category=meta["category"],
    passed=result["passed"],
    prompt_sent=prompt,
    prompt_version=self.config.summarization.eval_prompt_version,
    llm_response=str(response.content),
    reasoning=result.get("reasoning"),
    model_used=response.model or self.config.llm.model,
    input_tokens=response.input_tokens,
    output_tokens=response.output_tokens,
    latency_ms=response.latency_ms,
)
```

- [ ] **Step 2: Write eval adaptation tests**

File: `backend/tests/unit/test_eval_adaptations.py`

```python
"""Tests for facet-sensitive eval assertion thresholds."""

import pytest


def test_compression_range_brief():
    from app.services.summarizer.evaluator import EvalService
    svc = EvalService.__new__(EvalService)
    low, high = svc._get_compression_range({"compression": "brief", "style": "narrative"})
    assert low == 5.0
    assert high == 15.0


def test_compression_range_tweet_thread_overrides():
    from app.services.summarizer.evaluator import EvalService
    svc = EvalService.__new__(EvalService)
    low, high = svc._get_compression_range({"compression": "detailed", "style": "tweet_thread"})
    assert low == 2.0
    assert high == 8.0


def test_compression_range_standard():
    from app.services.summarizer.evaluator import EvalService
    svc = EvalService.__new__(EvalService)
    low, high = svc._get_compression_range({"compression": "standard", "style": "bullet_points"})
    assert low == 15.0
    assert high == 25.0
```

- [ ] **Step 3: Update `BookService` — status derivation**

In `book_service.py`, update any method that checks or sets `BookStatus.COMPLETED`:

```python
async def update_book_status(self, book_id: int) -> None:
    """Derive status from default_summary_id state."""
    book = await self.book_repo.get_by_id(book_id)
    sections = book.sections or []

    all_summarized = all(s.default_summary_id is not None for s in sections)
    book_summarized = book.default_summary_id is not None

    if all_summarized and book_summarized:
        book.status = BookStatus.COMPLETED
    elif book.status not in (BookStatus.PARSING, BookStatus.PARSE_FAILED, BookStatus.UPLOADING):
        book.status = BookStatus.PARSED
    await self.db.flush()
```

Remove any writes to `book.overall_summary` or `book.overall_summary_eval`.

- [ ] **Step 4: Update `ExportService` — read from `summaries` table**

In `export_service.py`, change `_collect_book_data()` to read summaries from the `summaries` table:

```python
# Replace section summary_md references:
# Old: section.summary_md
# New: fetch via summary_repo or join

# For each section in book data:
section_data = {
    "id": section.id,
    "title": section.title,
    "order_index": section.order_index,
    "depth": section.depth,
    "summary_md": None,  # Will be populated below
    "default_summary_id": section.default_summary_id,
}

# If section has a default summary, fetch it
if section.default_summary_id:
    summary = await self.summary_repo.get_by_id(section.default_summary_id)
    if summary:
        section_data["summary_md"] = summary.summary_md

# For book-level summary:
# Old: book.overall_summary or book.quick_summary
# New: fetch via Book.default_summary_id
book_summary = None
if book.default_summary_id:
    summary = await self.summary_repo.get_by_id(book.default_summary_id)
    if summary:
        book_summary = summary.summary_md
elif book.quick_summary:
    book_summary = book.quick_summary  # Legacy fallback
```

- [ ] **Step 5: Update `deps.py` — wire new services**

Add to `get_services()`:

```python
# After existing service wiring, add:
try:
    from app.services.preset_service import PresetService
    services["preset"] = PresetService()
except ImportError:
    pass

try:
    from app.services.quality_service import QualityService
    services["quality"] = QualityService()
except ImportError:
    pass

try:
    from app.services.summary_service import SummaryService
    services["summary_service"] = SummaryService(session)
except ImportError:
    pass

try:
    from app.services.section_edit_service import SectionEditService
    services["section_edit"] = SectionEditService(session)
except ImportError:
    pass
```

- [ ] **Step 6: Update `edit_cmd.py` — adapt `edit summary` for summaries table**

Update `edit_summary()` to read/write from the `summaries` table instead of `section.summary_md`:

```python
if section_id:
    section = ...  # fetch section
    if not section.default_summary_id:
        print_error(f"No summary for section {section_id}. Run: bookcompanion summarize {book_id}")
        raise typer.Exit(1)
    from app.db.repositories.summary_repo import SummaryRepository
    summary_repo = SummaryRepository(session)
    summary = await summary_repo.get_by_id(section.default_summary_id)
    edited = edit_in_editor(summary.summary_md, suffix=".md")
    if edited.strip() != summary.summary_md.strip():
        summary.summary_md = edited
        await session.flush()
        print_success(f"Summary #{summary.id} updated.")
```

- [ ] **Step 7: Run tests and commit**

```bash
cd backend && uv run python -m pytest tests/unit/test_eval_adaptations.py -v
git add backend/app/services/summarizer/evaluator.py backend/app/services/book_service.py \
  backend/app/services/export_service.py backend/app/cli/deps.py \
  backend/app/cli/commands/edit_cmd.py backend/tests/unit/test_eval_adaptations.py
git commit -m "feat: eval facet adaptations, BookService status derivation, ExportService + deps.py updates"
```

---

## Task 9: Preset & Summary CLI Commands

**Goal:** Create the `preset` and `summary` Typer sub-apps with all subcommands. Create the `read` command.

**Files:**
- Create: `backend/app/cli/commands/preset_cmd.py`
- Create: `backend/app/cli/commands/summary_cmds.py`
- Create: `backend/app/cli/commands/read_cmd.py`
- Modify: `backend/app/cli/main.py`

### Step-by-step

- [ ] **Step 1: Create `preset_cmd.py`**

```python
"""bookcompanion preset — manage summarization presets."""

import typer
from rich.console import Console
from rich.table import Table

from app.cli.deps import get_services
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
            "[green]\\u2713[/green]" if p.system else "",
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
        raise typer.Exit(1)

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
    from app.services.preset_service import PresetService, FACET_DIMENSIONS
    svc = PresetService()

    # Interactive mode if not all facets provided
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

    facets = {"style": style, "audience": audience,
              "compression": compression, "content_focus": content_focus}

    try:
        preset = svc.create(name, description, facets)
        print_success(f'Preset "{name}" created at {preset.file_path}')
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


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
        raise typer.Exit(1)
```

- [ ] **Step 2: Create `summary_cmds.py`**

```python
"""bookcompanion summary — summary log commands."""

import typer
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_empty_state, print_error, print_markdown, print_success
from app.db.models import SummaryContentType

summary_app = typer.Typer(help="Summary management commands.")
console = Console()


@summary_app.callback(invoke_without_command=True)
@async_command
async def summary_default(
    ctx: typer.Context,
    book_id: int = typer.Argument(None, help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID (optional)."),
):
    """Read the default summary for a book or section."""
    if ctx.invoked_subcommand is not None:
        return
    if book_id is None:
        console.print("Usage: bookcompanion summary <book_id> [section_id]")
        console.print("       bookcompanion summary list|compare|set-default|show")
        raise typer.Exit(0)

    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        summary_service = svc.get("summary_service")
        if not summary_service:
            print_error("Summary service not available.")
            raise typer.Exit(1)

        if section_id is not None:
            section = next((s for s in (book.sections or []) if s.id == section_id), None)
            if not section:
                print_error(f"Section {section_id} not found.")
                raise typer.Exit(1)
            if not section.default_summary_id:
                preset = svc["settings"].summarization.default_preset
                print_empty_state(
                    f'No summary for section #{section_id} "{section.title}".\n'
                    f"Run: bookcompanion summarize {book_id} --preset {preset}"
                )
                return
            summary = await summary_service.get_by_id(section.default_summary_id)
            content = f"## {section.title}\n\n{summary.summary_md}"
        else:
            if not book.default_summary_id:
                preset = svc["settings"].summarization.default_preset
                print_empty_state(
                    f'No summary for "{book.title}".\n'
                    f"Run: bookcompanion summarize {book_id} --preset {preset}"
                )
                return
            summary = await summary_service.get_by_id(book.default_summary_id)
            content = f"# {book.title}\n\n{summary.summary_md}"

        print_markdown(content, use_pager=True)


@summary_app.command("list")
@async_command
async def summary_list(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID for detailed list."),
    book_level: bool = typer.Option(False, "--book-level", help="Show book-level summaries only."),
):
    """List summaries for a book or section."""
    async with get_services() as svc:
        summary_service = svc.get("summary_service")
        book_service = svc.get("book_service")
        if not summary_service or not book_service:
            print_error("Required services not available.")
            raise typer.Exit(1)

        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        if book_level:
            summaries = await summary_service.list_book_level(book_id)
            table = Table(title=f'Book-level summaries — "{book.title}"')
            table.add_column("ID")
            table.add_column("Preset")
            table.add_column("Model")
            table.add_column("Compression")
            table.add_column("Chars")
            table.add_column("Eval")
            table.add_column("Created")
            for s in summaries:
                comp = f"{s.summary_char_count / s.input_char_count * 100:.1f}%" if s.input_char_count else "—"
                eval_str = _format_eval(s.eval_json)
                default_marker = " [green]\\u2605[/green]" if book.default_summary_id == s.id else ""
                table.add_row(
                    str(s.id) + default_marker, s.preset_name or "—",
                    s.model_used, comp, f"{s.summary_char_count:,}",
                    eval_str, str(s.created_at.strftime("%Y-%m-%d %H:%M")),
                )
            console.print(table)
            return

        if section_id is not None:
            summaries = await summary_service.list_for_content(
                SummaryContentType.SECTION, section_id
            )
            section = next((s for s in (book.sections or []) if s.id == section_id), None)
            title = section.title if section else f"Section {section_id}"

            table = Table(title=f'Section "{title}" — {len(summaries)} summaries')
            table.add_column("ID")
            table.add_column("Preset")
            table.add_column("Model")
            table.add_column("Compression")
            table.add_column("Chars")
            table.add_column("Eval")
            table.add_column("Created")

            for s in summaries:
                comp = f"{s.summary_char_count / s.input_char_count * 100:.1f}%" if s.input_char_count else "—"
                eval_str = _format_eval(s.eval_json)
                default_marker = " [green]\\u2605[/green]" if section and section.default_summary_id == s.id else ""
                table.add_row(
                    str(s.id) + default_marker, s.preset_name or "—",
                    s.model_used, comp, f"{s.summary_char_count:,}",
                    eval_str, str(s.created_at.strftime("%Y-%m-%d %H:%M")),
                )
            console.print(table)
        else:
            # Per-section overview
            sections = book.sections or []
            all_summaries = await summary_service.list_for_book(book_id)

            # Count summaries per section
            section_counts: dict[int, int] = {}
            for s in all_summaries:
                if s.content_type == SummaryContentType.SECTION:
                    section_counts[s.content_id] = section_counts.get(s.content_id, 0) + 1

            book_summaries = [s for s in all_summaries if s.content_type == SummaryContentType.BOOK]
            total_count = sum(section_counts.values())

            console.print(f'Book: "{book.title}" — {total_count} summaries across {len(sections)} sections\n')
            table = Table()
            table.add_column("#")
            table.add_column("ID")
            table.add_column("Title")
            table.add_column("Summaries")
            table.add_column("Default Preset")

            for i, section in enumerate(sections, 1):
                count = section_counts.get(section.id, 0)
                # Find default summary's preset
                default_preset = "—"
                if section.default_summary_id:
                    for s in all_summaries:
                        if s.id == section.default_summary_id:
                            default_preset = s.preset_name or "—"
                            break
                indent = "  " * section.depth
                table.add_row(str(i), str(section.id), f"{indent}{section.title}", str(count), default_preset)

            console.print(table)

            if book_summaries:
                default_id = book.default_summary_id
                default_preset = "—"
                for s in book_summaries:
                    if s.id == default_id:
                        default_preset = s.preset_name or "—"
                console.print(
                    f"\n  Book-level summaries: {len(book_summaries)} "
                    f"(default: #{default_id}, {default_preset})"
                )


@summary_app.command("compare")
@async_command
async def summary_compare(
    id1: int = typer.Argument(..., help="First summary ID."),
    id2: int = typer.Argument(..., help="Second summary ID."),
):
    """Compare two summaries side-by-side with concept diff."""
    async with get_services() as svc:
        summary_service = svc.get("summary_service")
        if not summary_service:
            print_error("Summary service not available.")
            raise typer.Exit(1)

        try:
            a = await summary_service.get_by_id(id1)
            b = await summary_service.get_by_id(id2)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

        # Metadata header
        width = console.width
        if width >= 120:
            cols = Columns([
                Panel(
                    f"Preset: {a.preset_name or '—'}\nModel: {a.model_used}\n"
                    f"Compression: {a.summary_char_count/a.input_char_count*100:.1f}%\n"
                    f"Eval: {_format_eval(a.eval_json)}\n\n{a.summary_md}",
                    title=f"Summary #{a.id}",
                ),
                Panel(
                    f"Preset: {b.preset_name or '—'}\nModel: {b.model_used}\n"
                    f"Compression: {b.summary_char_count/b.input_char_count*100:.1f}%\n"
                    f"Eval: {_format_eval(b.eval_json)}\n\n{b.summary_md}",
                    title=f"Summary #{b.id}",
                ),
            ], equal=True)
            console.print(cols)
        else:
            console.print(Panel(a.summary_md, title=f"Summary #{a.id} ({a.preset_name or '—'})"))
            console.print(Panel(b.summary_md, title=f"Summary #{b.id} ({b.preset_name or '—'})"))

        # Concept diff
        diff = summary_service.concept_diff(a, b)
        if diff["only_in_a"] or diff["only_in_b"]:
            console.print("\n[bold]Concept Diff[/bold]")
            if diff["only_in_a"]:
                console.print(f"  Only in #{a.id}: {', '.join(sorted(diff['only_in_a']))}")
            if diff["only_in_b"]:
                console.print(f"  Only in #{b.id}: {', '.join(sorted(diff['only_in_b']))}")


@summary_app.command("set-default")
@async_command
async def summary_set_default(
    summary_id: int = typer.Argument(..., help="Summary ID to set as default."),
):
    """Set a summary as the default for its section or book."""
    async with get_services() as svc:
        summary_service = svc.get("summary_service")
        if not summary_service:
            print_error("Summary service not available.")
            raise typer.Exit(1)

        try:
            summary = await summary_service.set_default(summary_id)
            target = "section" if summary.content_type == SummaryContentType.SECTION else "book"
            print_success(f"Default summary for {target} #{summary.content_id} updated to #{summary_id}.")
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

        # Trigger re-embedding for section summaries
        if summary.content_type == SummaryContentType.SECTION:
            embedding = svc.get("embedding")
            search = svc.get("search")
            if embedding and search:
                try:
                    from app.db.models import SourceType
                    await search.reindex_summary(summary.content_id, summary.summary_md, summary.book_id)
                    print_success("Search index re-embedded.")
                except Exception:
                    pass  # Non-blocking


@summary_app.command("show")
@async_command
async def summary_show(
    summary_id: int = typer.Argument(..., help="Summary ID."),
):
    """Show a summary with full provenance metadata."""
    async with get_services() as svc:
        summary_service = svc.get("summary_service")
        if not summary_service:
            print_error("Summary service not available.")
            raise typer.Exit(1)

        try:
            s = await summary_service.get_by_id(summary_id)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

        comp = f"{s.summary_char_count / s.input_char_count * 100:.1f}%" if s.input_char_count else "—"
        console.print(f"[bold]Summary #{s.id}[/bold]")
        console.print(f"Content type: {s.content_type.value}")
        console.print(f"Content ID: {s.content_id}")
        console.print(f"Book ID: {s.book_id}")
        console.print(f"Preset: {s.preset_name or '—'}")
        console.print(f"Facets: {s.facets_used}")
        console.print(f"Model: {s.model_used}")
        console.print(f"Input tokens: {s.input_tokens or '—'}")
        console.print(f"Output tokens: {s.output_tokens or '—'}")
        console.print(f"Input chars: {s.input_char_count:,}")
        console.print(f"Summary chars: {s.summary_char_count:,}")
        console.print(f"Compression: {comp}")
        console.print(f"Latency: {s.latency_ms or '—'}ms")
        console.print(f"Eval: {_format_eval(s.eval_json)}")
        console.print(f"Created: {s.created_at}")
        console.print(f"\n{'─' * 40}\n")
        print_markdown(s.summary_md, use_pager=True)


def _format_eval(eval_json: dict | None) -> str:
    if not eval_json or not isinstance(eval_json, dict):
        return "—"
    passed = eval_json.get("passed", 0)
    total = eval_json.get("total", 0)
    return f"{passed}/{total}"
```

- [ ] **Step 3: Create `read_cmd.py`**

```python
"""bookcompanion read — display original section content."""

import typer
from rich.console import Console

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_empty_state, print_error, print_markdown

console = Console()


@async_command
async def read(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(..., help="Section ID."),
    with_summary: bool = typer.Option(False, "--with-summary", help="Show default summary below content."),
):
    """Read original section content, optionally with its default summary."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        section = next((s for s in (book.sections or []) if s.id == section_id), None)
        if not section:
            print_error(f"Section {section_id} not found.")
            raise typer.Exit(1)

        content = f"## {section.title}\n\n{section.content_md or '(no content)'}"

        if with_summary and section.default_summary_id:
            summary_service = svc.get("summary_service")
            if summary_service:
                summary = await summary_service.get_by_id(section.default_summary_id)
                content += f"\n\n{'─' * 40}\n\n## Summary\n\n{summary.summary_md}"
        elif with_summary:
            content += "\n\n(no summary available)"

        print_markdown(content, use_pager=True)
```

- [ ] **Step 4: Update `main.py` — register new commands**

```python
# Replace the old summary command registration:
# OLD: app.command("summary")(summarize_cmd.summary)
# NEW:
from app.cli.commands.summary_cmds import summary_app
from app.cli.commands.preset_cmd import preset_app
from app.cli.commands.read_cmd import read

app.add_typer(summary_app, name="summary")
app.add_typer(preset_app, name="preset", help="Manage summarization presets.")
app.command("read")(read)

# Keep existing: app.command("summarize")(summarize_cmd.summarize)
# Remove: app.command("summary")(summarize_cmd.summary)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/commands/preset_cmd.py backend/app/cli/commands/summary_cmds.py \
  backend/app/cli/commands/read_cmd.py backend/app/cli/main.py
git commit -m "feat: preset, summary, read CLI commands — list/show/create/delete/compare/set-default"
```

---

## Task 10: Summarize & Eval CLI Updates

**Goal:** Update `summarize` command for preset flags, idempotent skip, new progress display. Update `eval` for `--summary-id` flag.

**Files:**
- Modify: `backend/app/cli/commands/summarize_cmd.py`
- Modify: `backend/app/cli/commands/eval_cmd.py`

### Step-by-step

- [ ] **Step 1: Rewrite `summarize` command**

Replace the `summarize` function in `summarize_cmd.py`:

```python
@async_command
async def summarize(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID. If omitted, processes all sections."),
    preset: str = typer.Option(None, "--preset", help="Preset name (e.g., practitioner_bullets)."),
    style: str = typer.Option(None, "--style", help="Override style facet."),
    audience: str = typer.Option(None, "--audience", help="Override audience facet."),
    compression: str = typer.Option(None, "--compression", help="Override compression facet."),
    content_focus: str = typer.Option(None, "--content-focus", help="Override content focus facet."),
    model: str = typer.Option(None, "--model", help="Override LLM model."),
    force: bool = typer.Option(False, "--force", help="Re-summarize all sections, ignoring existing."),
    skip_eval: bool = typer.Option(False, "--skip-eval", help="Skip eval assertions."),
    skip_images: bool = typer.Option(False, "--skip-images", help="Skip image captioning."),
):
    """Generate summaries using faceted presets."""
    async with get_services() as svc:
        summarizer = svc.get("summarizer")
        preset_svc = svc.get("preset")
        if not summarizer or not preset_svc:
            print_error("Summarizer or preset service not available.")
            raise typer.Exit(1)

        # Resolve facets
        settings = svc["settings"]
        overrides = {"style": style, "audience": audience,
                     "compression": compression, "content_focus": content_focus}
        try:
            resolved_preset, facets = preset_svc.resolve_facets(
                preset, overrides, settings.summarization.default_preset
            )
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

        # Validate book exists
        book_service = svc.get("book_service")
        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        # Check for concurrent runs
        from app.db.models import ProcessingJobStatus, ProcessingStep
        from sqlalchemy import select
        from app.db.models import ProcessingJob
        session = svc["session"]
        active_jobs = await session.execute(
            select(ProcessingJob).where(
                ProcessingJob.book_id == book_id,
                ProcessingJob.step == ProcessingStep.SUMMARIZE,
                ProcessingJob.status == ProcessingJobStatus.RUNNING,
            )
        )
        active = active_jobs.scalar_one_or_none()
        if active:
            if not typer.confirm(
                f"A summarization is already running for this book (PID: {active.pid}). Run anyway?",
                default=False
            ):
                raise typer.Exit(0)

        if skip_images:
            summarizer.captioner = None

        preset_label = resolved_preset or "custom facets"

        # Single section mode
        if section_id is not None:
            console.print(f'Summarizing section {section_id} with preset "{preset_label}"...')
            # ... delegate to summarizer with facets
            return

        # Full book mode with spec-compliant progress display
        sections = book.sections or []
        console.print(f'Summarizing {len(sections)} sections with preset "{preset_label}"...')

        stats = await summarizer.summarize_book(
            book_id=book_id,
            preset_name=resolved_preset,
            facets=facets,
            force=force,
            model=model,
            skip_eval=skip_eval,
            # Progress callbacks print spec-format lines
            on_section_complete=lambda i, total, title, elapsed, comp:
                console.print(f"  [{i}/{total}] {title:<35} [green]\\u2713[/green]  ({elapsed}s, {comp:.1f}%)"),
            on_section_skip=lambda i, total, title:
                console.print(f"  [{i}/{total}] {title:<35} [dim]\\u2298  skipped (already summarized)[/dim]"),
            on_section_fail=lambda i, total, title, err:
                console.print(f"  [{i}/{total}] {title:<35} [red]\\u2717[/red]  ({err})"),
        )

        # Book-level summary
        console.print("Generating book-level summary...     ", end="")
        try:
            await summarizer._generate_book_summary(book_id, facets, resolved_preset, model)
            console.print("[green]\\u2713[/green]")
        except Exception as e:
            console.print(f"[red]\\u2717[/red] ({e})")

        # Final report
        completed = stats.get("completed", 0)
        skipped = stats.get("skipped", 0)
        failed = stats.get("failed", [])
        parts = [f"{completed} section summaries"]
        if not failed:
            parts.append("1 book summary generated")
        if skipped:
            parts.append(f"{skipped} skipped")
        if failed:
            parts.append(f"{len(failed)} failed (sections {', '.join(f'#{f}' for f in failed)})")

        print_success(f"Done. {'. '.join(parts)}.")
```

- [ ] **Step 2: Update `eval` command**

Add `--summary-id` flag:

```python
@async_command
async def eval_cmd(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID for detailed results."),
    summary_id: int = typer.Option(None, "--summary-id", help="Evaluate a specific summary."),
):
    """Show or run evaluation results."""
    async with get_services() as svc:
        # ... existing book validation ...

        if summary_id:
            # Evaluate a specific summary
            summary_service = svc.get("summary_service")
            summary = await summary_service.get_by_id(summary_id)

            eval_service = svc.get("eval")
            if not eval_service:
                print_error("Eval service not available.")
                raise typer.Exit(1)

            # Get source text
            if summary.content_type == SummaryContentType.SECTION:
                section = await svc["session"].get(BookSection, summary.content_id)
                source_text = section.content_md or ""
            else:
                source_text = ""  # Book-level: source is section summaries

            results = await eval_service.evaluate_summary(
                section_id=summary.content_id,
                source_text=source_text,
                summary_text=summary.summary_md,
                facets_used=summary.facets_used,
                summary_id=summary.id,
            )

            # Write inline eval to summary
            passed = sum(1 for r in results.values() if r.get("passed"))
            summary.eval_json = {"passed": passed, "total": len(results), "results": results}
            await svc["session"].flush()

            # Display results table
            # ... same table display as existing code ...
```

- [ ] **Step 3: Remove old `summary` function from `summarize_cmd.py`**

Delete the `summary()` function — it's now handled by `summary_cmds.py`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/cli/commands/summarize_cmd.py backend/app/cli/commands/eval_cmd.py
git commit -m "feat: summarize command with preset flags + eval with --summary-id"
```

---

## Task 11: Show, Add & Edit Sections CLI

**Goal:** Update `show` with new columns, `add` with quality checks and editing REPL, add `edit sections` subcommand.

**Files:**
- Modify: `backend/app/cli/commands/books.py`
- Modify: `backend/app/cli/commands/edit_cmd.py`

### Step-by-step

- [ ] **Step 1: Update `show` command**

Rewrite the `show` function in `books.py` to display per spec section 6.1:

```python
@async_command
async def show(
    book_id: int = typer.Argument(..., help="Book ID."),
):
    """Show book details and section structure."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        sections = book.sections or []
        quality_svc = svc.get("quality")

        # Quality summary
        if quality_svc:
            section_dicts = [
                {"index": i+1, "title": s.title, "content": s.content_md or "",
                 "depth": s.depth, "image_count": len(s.images) if hasattr(s, 'images') and s.images else 0}
                for i, s in enumerate(sections)
            ]
            issues = quality_svc.check_sections(section_dicts)
            warnings = [i for i in issues if i.severity in ("warning", "error")]
            ok_count = len(sections) - len(set(i.section_index for i in warnings))
            if warnings:
                console.print(f"Quality: {ok_count}/{len(sections)} sections OK. "
                              f"{len(warnings)} warning(s)")
            else:
                console.print(f"Quality: {len(sections)}/{len(sections)} sections OK")

        # Adaptive columns based on terminal width
        width = console.width
        table = Table(title=f"{book.title}")
        table.add_column("#", width=4)
        table.add_column("ID", width=5)
        table.add_column("Title")
        table.add_column("Status", width=10)
        table.add_column("Chars", justify="right", width=8)

        show_compression = width >= 100
        show_eval = width >= 100
        show_images = width >= 120

        if show_compression:
            table.add_column("Compression", justify="right", width=12)
        if show_eval:
            table.add_column("Eval", width=7)
        if show_images:
            table.add_column("Images", width=7)

        summary_service = svc.get("summary_service")

        for i, section in enumerate(sections, 1):
            indent = "  " * section.depth
            status = "Completed" if section.default_summary_id else "Pending"
            chars = f"{len(section.content_md or ''):,}"

            row = [str(i), str(section.id), f"{indent}{section.title}", status, chars]

            if show_compression:
                if section.default_summary_id and summary_service:
                    try:
                        s = await summary_service.get_by_id(section.default_summary_id)
                        comp = f"{s.summary_char_count / s.input_char_count * 100:.1f}%" if s.input_char_count else "—"
                    except Exception:
                        comp = "—"
                else:
                    comp = "—"
                row.append(comp)

            if show_eval:
                if section.default_summary_id and summary_service:
                    try:
                        s = await summary_service.get_by_id(section.default_summary_id)
                        eval_str = _format_eval_inline(s.eval_json)
                    except Exception:
                        eval_str = "—"
                else:
                    eval_str = "—"
                row.append(eval_str)

            if show_images:
                images = getattr(section, 'images', None) or []
                if images:
                    captioned = sum(1 for img in images if img.caption)
                    row.append(f"{captioned}/{len(images)}")
                else:
                    row.append("—")

            table.add_row(*row)
        console.print(table)


def _format_eval_inline(eval_json):
    if not eval_json or not isinstance(eval_json, dict):
        return "—"
    return f"{eval_json.get('passed', 0)}/{eval_json.get('total', 0)}"
```

- [ ] **Step 2: Update `add` command — quality checks and editing REPL**

Add quality validation and interactive editing after structure detection:

```python
@async_command
async def add(
    file_path: Path = typer.Argument(..., help="Path to the book file."),
    quick: bool = typer.Option(False, "--quick", help="Parse + summarize with executive_brief preset."),
    async_mode: bool = typer.Option(False, "--async", help="Parse + summarize in background."),
    force: bool = typer.Option(False, "--force", help="Re-import or retry failed parse."),
):
    """Upload and parse a book file."""
    # ... existing validation ...

    async with get_services() as svc:
        book_service = svc.get("book_service")
        # ... existing parse logic ...

        book = await book_service.add_book(str(file_path), force=force)
        book = await book_service.get_book(book.id)

        # Display structure with quality info
        sections = book.sections or []
        console.print(f"\nDetected structure ({len(sections)} sections):")

        quality_svc = svc.get("quality")
        section_dicts = []
        for i, s in enumerate(sections):
            chars = len(s.content_md or "")
            tokens = int(chars / 4.5)
            indent = "  " * (s.depth + 1)

            # Quality flags
            flags = ""
            if quality_svc:
                section_dicts.append({
                    "index": i+1, "title": s.title,
                    "content": s.content_md or "", "depth": s.depth,
                    "image_count": len(s.images) if hasattr(s, 'images') and s.images else 0,
                })

            console.print(f"{indent}{i+1}. {s.title:<35} {chars:>6,} chars  ~{tokens:,} tokens")

        # Quality checks
        if quality_svc and section_dicts:
            issues = quality_svc.check_sections(section_dicts)
            if issues:
                actions = quality_svc.suggested_actions(issues)
                if actions:
                    console.print("\nSuggested actions:")
                    for action in actions:
                        console.print(f"  * {action}")

                    choice = typer.prompt(
                        "\nApply suggested actions? [Y/n/customize]",
                        default="Y"
                    ).strip().lower()

                    if choice in ("y", "yes", ""):
                        # Apply suggestions (delete non-content, merge short)
                        # ... apply logic using SectionEditService in memory mode ...
                        pass
                    elif choice == "customize":
                        # Enter REPL
                        _run_editing_repl(sections, svc)

        # ... rest of add logic (save, quick summary alias) ...

        if quick and svc.get("summarizer"):
            console.print("Generating quick summary (executive_brief preset)...")
            try:
                from app.services.preset_service import PresetService
                ps = PresetService()
                preset = ps.load("executive_brief")
                await svc["summarizer"].summarize_book(
                    book.id, preset_name="executive_brief", facets=preset.facets
                )
                print_success("Summary generated with executive_brief preset.")
            except Exception as e:
                print_error(f"Summary failed: {e}")
```

- [ ] **Step 3: Add `edit sections` subcommand to `edit_cmd.py`**

```python
@edit_app.command("sections")
@async_command
async def edit_sections(
    book_id: int = typer.Argument(..., help="Book ID."),
):
    """Interactive section merge/split/reorder/delete (post-save)."""
    async with get_services() as svc:
        section_edit = svc.get("section_edit")
        book_service = svc.get("book_service")
        if not section_edit or not book_service:
            print_error("Required services not available.")
            raise typer.Exit(1)

        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        sections = book.sections or []
        if not sections:
            print_error(f"Book has no sections. Re-parse with: bookcompanion add <path>")
            raise typer.Exit(1)

        # Display current structure
        _display_sections(sections, svc)

        # REPL loop
        modified_count = 0
        while True:
            try:
                raw = input("\nEdit sections> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not raw:
                continue

            from app.services.section_edit_service import parse_command
            try:
                cmd = parse_command(raw)
            except Exception as e:
                print_error(str(e))
                continue

            if cmd.action == "done":
                break
            if cmd.action == "show":
                book = await book_service.get_book(book_id)
                _display_sections(book.sections or [], svc)
                continue

            # Execute DB-backed operations with confirmation
            try:
                if cmd.action == "merge":
                    if not typer.confirm(f"Merge sections {cmd.indices}?", default=True):
                        continue
                    result = await section_edit.db_merge(book_id, cmd.indices, cmd.title)
                    await svc["session"].commit()
                    print_success(f'Merged into "{result.title}" (ID: {result.id})')
                    modified_count += 1

                elif cmd.action == "split":
                    section_id = cmd.indices[0]
                    # Resolve section_id from display index
                    sections = await svc["session"].execute(
                        select(BookSection).where(BookSection.book_id == book_id)
                        .order_by(BookSection.order_index)
                    )
                    section_list = list(sections.scalars().all())
                    if cmd.indices[0] > len(section_list):
                        print_error(f"Section index {cmd.indices[0]} out of range.")
                        continue
                    target_section = section_list[cmd.indices[0] - 1]

                    if cmd.split_mode == "heading":
                        headings = section_edit.detect_headings_from_content(target_section.content_md or "")
                        if not headings:
                            print_error("No sub-headings detected. Use --at-char or --at-paragraph.")
                            continue
                        # Display headings for selection
                        console.print(f"Detected sub-headings:")
                        for j, (h, pos) in enumerate(headings, 1):
                            console.print(f"  {j}. \"{h}\" (at char {pos:,})")
                        # ... heading selection ...
                    elif cmd.split_mode == "char":
                        results = await section_edit.db_split_at_char(book_id, target_section.id, cmd.split_value)
                        await svc["session"].commit()
                        print_success(f"Split into {len(results)} sections.")
                        modified_count += 1
                    elif cmd.split_mode == "paragraph":
                        # Find nearest paragraph boundary
                        # ... paragraph split logic ...
                        pass

                elif cmd.action == "delete":
                    if not typer.confirm(f"Delete sections {cmd.indices}?", default=True):
                        continue
                    # Resolve indices to IDs
                    sections = await section_edit._section_repo.get_by_book_id(book_id)
                    ids = [sections[i-1].id for i in cmd.indices if i <= len(sections)]
                    count = await section_edit.db_delete(book_id, ids)
                    await svc["session"].commit()
                    print_success(f"Deleted {count} section(s).")
                    modified_count += 1

                elif cmd.action == "move":
                    sections = await section_edit._section_repo.get_by_book_id(book_id)
                    src_id = sections[cmd.indices[0]-1].id
                    tgt_id = sections[cmd.target_after-1].id if cmd.target_after else 0
                    await section_edit.db_move(book_id, src_id, tgt_id)
                    await svc["session"].commit()
                    print_success("Section moved.")
                    modified_count += 1

            except Exception as e:
                print_error(str(e))
                await svc["session"].rollback()

        # Post-edit prompt
        if modified_count > 0:
            if typer.confirm(
                f"\n{modified_count} section(s) modified. Resummarize affected sections now?",
                default=True
            ):
                # Get last-used preset
                summary_service = svc.get("summary_service")
                last_preset = None
                if summary_service:
                    last_preset = await summary_service.get_last_used_preset(book_id)

                preset_name = last_preset or svc["settings"].summarization.default_preset
                from app.services.preset_service import PresetService
                ps = PresetService()
                preset = ps.load(preset_name)

                summarizer = svc.get("summarizer")
                if summarizer:
                    await summarizer.summarize_book(
                        book_id, preset_name=preset_name, facets=preset.facets
                    )
                    print_success("Re-summarization complete.")


def _display_sections(sections, svc):
    """Display section structure table."""
    table = Table()
    table.add_column("#", width=4)
    table.add_column("ID", width=5)
    table.add_column("Title")
    table.add_column("Chars", justify="right")
    table.add_column("Summary", width=25)

    for i, s in enumerate(sections, 1):
        indent = "  " * s.depth
        chars = f"{len(s.content_md or ''):,}"
        summary_status = "—"
        if s.default_summary_id:
            summary_status = f"\\u2713 summarized"
        table.add_row(str(i), str(s.id), f"{indent}{s.title}", chars, summary_status)
    console.print(table)
```

- [ ] **Step 4: Update help text**

Add Common Workflows section to `main.py` app help:

```python
app = typer.Typer(
    name="bookcompanion",
    help="""Book Companion - Personal book summarization and knowledge extraction tool.

Common Workflows:
  Read a section summary      bookcompanion summary <book_id> <section_id>
  Compare with original       bookcompanion read <book_id> <section_id> --with-summary
  Search across library       bookcompanion search "competitive advantage"
  Re-summarize with preset    bookcompanion summarize <book_id> --preset academic_detailed
  Compare two summaries       bookcompanion summary compare <id1> <id2>
  Export book summary         bookcompanion export book <book_id> --format markdown
  Edit section structure      bookcompanion edit sections <book_id>""",
    no_args_is_help=True,
)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/commands/books.py backend/app/cli/commands/edit_cmd.py \
  backend/app/cli/main.py
git commit -m "feat: show/add/edit CLI updates — quality checks, editing REPL, adaptive columns"
```

---

## Task 12: Integration Tests

**Goal:** Test database operations end-to-end: summary CRUD, cascade delete, set-default with re-embedding, post-save merge/split, migration validation.

**Files:**
- Create: `backend/tests/integration/test_summary_crud.py`
- Create: `backend/tests/integration/test_section_edit_db.py`

### Step-by-step

- [ ] **Step 1: Write summary CRUD integration tests**

File: `backend/tests/integration/test_summary_crud.py`

```python
"""Integration tests for summary CRUD operations."""

import pytest
import pytest_asyncio
from app.db.models import Book, BookSection, BookStatus, Summary, SummaryContentType
from app.db.repositories.summary_repo import SummaryRepository
from app.db.repositories.section_repo import SectionRepository
from app.db.repositories.book_repo import BookRepository


@pytest_asyncio.fixture
async def book_with_sections(db_session):
    """Create a book with 3 sections."""
    book = Book(
        title="Test Book", file_data=b"test", file_hash="test_hash_summary",
        file_format="epub", file_size_bytes=100, status=BookStatus.PARSED,
    )
    db_session.add(book)
    await db_session.flush()

    sections = []
    for i in range(3):
        s = BookSection(
            book_id=book.id, title=f"Section {i+1}",
            order_index=i, depth=0, content_md=f"Content {i+1} " * 200,
        )
        db_session.add(s)
        sections.append(s)
    await db_session.flush()
    return book, sections


@pytest.mark.asyncio
async def test_summary_append(db_session, book_with_sections):
    book, sections = book_with_sections
    repo = SummaryRepository(db_session)

    s1 = Summary(
        content_type=SummaryContentType.SECTION, content_id=sections[0].id,
        book_id=book.id, facets_used={"style": "bullet_points", "audience": "practitioner",
                                       "compression": "standard", "content_focus": "key_concepts"},
        prompt_text_sent="test", model_used="sonnet",
        input_char_count=1000, summary_char_count=200, summary_md="Summary 1",
    )
    await repo.create(s1)

    s2 = Summary(
        content_type=SummaryContentType.SECTION, content_id=sections[0].id,
        book_id=book.id, facets_used={"style": "narrative", "audience": "academic",
                                       "compression": "detailed", "content_focus": "full_coverage"},
        prompt_text_sent="test2", model_used="opus",
        input_char_count=1000, summary_char_count=300, summary_md="Summary 2",
    )
    await repo.create(s2)

    all_summaries = await repo.list_by_content(SummaryContentType.SECTION, sections[0].id)
    assert len(all_summaries) == 2


@pytest.mark.asyncio
async def test_summary_cascade_delete(db_session, book_with_sections):
    """Deleting book cascades to summaries."""
    book, sections = book_with_sections
    repo = SummaryRepository(db_session)

    await repo.create(Summary(
        content_type=SummaryContentType.SECTION, content_id=sections[0].id,
        book_id=book.id, facets_used={}, prompt_text_sent="t", model_used="s",
        input_char_count=100, summary_char_count=20, summary_md="S",
    ))

    await db_session.delete(book)
    await db_session.flush()

    all_summaries = await repo.list_by_book(book.id)
    assert len(all_summaries) == 0


@pytest.mark.asyncio
async def test_set_default_summary(db_session, book_with_sections):
    book, sections = book_with_sections
    summary_repo = SummaryRepository(db_session)
    section_repo = SectionRepository(db_session)

    s = await summary_repo.create(Summary(
        content_type=SummaryContentType.SECTION, content_id=sections[0].id,
        book_id=book.id, facets_used={}, prompt_text_sent="t", model_used="s",
        input_char_count=100, summary_char_count=20, summary_md="S",
    ))

    await section_repo.update_default_summary(sections[0].id, s.id)
    updated = await section_repo.get_by_id(sections[0].id)
    assert updated.default_summary_id == s.id


@pytest.mark.asyncio
async def test_idempotent_skip(db_session, book_with_sections):
    book, sections = book_with_sections
    repo = SummaryRepository(db_session)

    facets = {"style": "bullet_points", "audience": "practitioner",
              "compression": "standard", "content_focus": "key_concepts"}

    await repo.create(Summary(
        content_type=SummaryContentType.SECTION, content_id=sections[0].id,
        book_id=book.id, facets_used=facets, preset_name="practitioner_bullets",
        prompt_text_sent="t", model_used="s",
        input_char_count=100, summary_char_count=20, summary_md="S",
    ))

    existing = await repo.get_latest_by_content_and_facets(
        SummaryContentType.SECTION, sections[0].id, facets
    )
    assert existing is not None
```

- [ ] **Step 2: Write section edit DB integration tests**

File: `backend/tests/integration/test_section_edit_db.py`

```python
"""Integration tests for post-save section editing."""

import pytest
import pytest_asyncio
from app.db.models import Book, BookSection, BookStatus
from app.services.section_edit_service import SectionEditService


@pytest_asyncio.fixture
async def book_with_sections(db_session):
    book = Book(
        title="Edit Test", file_data=b"test", file_hash="edit_test_hash",
        file_format="epub", file_size_bytes=100, status=BookStatus.PARSED,
    )
    db_session.add(book)
    await db_session.flush()

    for i in range(5):
        s = BookSection(
            book_id=book.id, title=f"Section {i+1}",
            order_index=i, depth=0, content_md=f"Content for section {i+1}. " * 100,
        )
        db_session.add(s)
    await db_session.flush()
    return book


@pytest.mark.asyncio
async def test_db_merge(db_session, book_with_sections):
    book = book_with_sections
    svc = SectionEditService(db_session)
    sections = await svc._section_repo.get_by_book_id(book.id)
    ids = [sections[1].id, sections[2].id]

    result = await svc.db_merge(book.id, ids, "Merged 2+3")
    await db_session.flush()

    updated = await svc._section_repo.get_by_book_id(book.id)
    assert len(updated) == 4
    merged = next(s for s in updated if s.title == "Merged 2+3")
    assert merged.derived_from == ids


@pytest.mark.asyncio
async def test_db_split(db_session, book_with_sections):
    book = book_with_sections
    svc = SectionEditService(db_session)
    sections = await svc._section_repo.get_by_book_id(book.id)

    results = await svc.db_split_at_char(book.id, sections[0].id, 500)
    await db_session.flush()

    updated = await svc._section_repo.get_by_book_id(book.id)
    assert len(updated) == 6  # 5 - 1 + 2


@pytest.mark.asyncio
async def test_db_delete_validates_minimum(db_session, book_with_sections):
    book = book_with_sections
    svc = SectionEditService(db_session)
    sections = await svc._section_repo.get_by_book_id(book.id)
    all_ids = [s.id for s in sections]

    from app.exceptions import SectionEditError
    with pytest.raises(SectionEditError, match="Cannot delete all"):
        await svc.db_delete(book.id, all_ids)
```

- [ ] **Step 3: Run integration tests**

```bash
cd backend && uv run python -m pytest tests/integration/test_summary_crud.py tests/integration/test_section_edit_db.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_summary_crud.py backend/tests/integration/test_section_edit_db.py
git commit -m "test: integration tests for summary CRUD, cascade, set-default, section editing"
```

---

## Task 13: E2E Tests & Final Verification

**Goal:** Run the full pipeline end-to-end via CLI, verify lint/format, run all tests, deploy migration, and manually verify all CLI commands work as specified.

**Files:**
- Create: `backend/tests/e2e/test_v1_1_flows.py`
- Modify: `CLAUDE.md` (update docs)

### Step-by-step

- [ ] **Step 1: Write E2E test file**

File: `backend/tests/e2e/test_v1_1_flows.py`

```python
"""E2E tests for V1.1 features — runs actual CLI commands."""

import subprocess
import pytest

CLI = ["uv", "run", "bookcompanion"]


def run_cli(*args, input_text=None):
    result = subprocess.run(
        [*CLI, *args],
        capture_output=True, text=True, timeout=60,
        input=input_text, cwd=".",
    )
    return result


class TestPresetManagement:
    def test_preset_list(self):
        result = run_cli("preset", "list")
        assert result.returncode == 0
        assert "practitioner_bullets" in result.stdout

    def test_preset_show(self):
        result = run_cli("preset", "show", "practitioner_bullets")
        assert result.returncode == 0
        assert "bullet_points" in result.stdout

    def test_preset_create_and_delete(self):
        result = run_cli(
            "preset", "create", "test_e2e",
            "--description", "E2E test preset",
            "--style", "narrative",
            "--audience", "academic",
            "--compression", "detailed",
            "--content-focus", "full_coverage",
        )
        assert result.returncode == 0

        result = run_cli("preset", "delete", "test_e2e")
        assert result.returncode == 0

    def test_preset_delete_system_fails(self):
        result = run_cli("preset", "delete", "practitioner_bullets")
        assert result.returncode != 0
        assert "Cannot delete system preset" in result.stderr or "Cannot delete system preset" in result.stdout


class TestSummaryCommands:
    def test_summary_list_no_book(self):
        result = run_cli("summary", "list", "99999")
        assert result.returncode != 0


class TestHelpText:
    def test_main_help_has_workflows(self):
        result = run_cli("--help")
        assert "Common Workflows" in result.stdout

    def test_summarize_help_has_preset(self):
        result = run_cli("summarize", "--help")
        assert "--preset" in result.stdout


class TestReadCommand:
    def test_read_nonexistent_book(self):
        result = run_cli("read", "99999", "1")
        assert result.returncode != 0
```

- [ ] **Step 2: Run linting and format checks**

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
```

Fix any issues found.

- [ ] **Step 3: Run the full test suite**

```bash
cd backend && uv run python -m pytest tests/ -v --tb=short
```

Fix any failures. Expected test count: ~90+ tests (78 existing + new).

- [ ] **Step 4: Deploy migration to development database**

```bash
# Ensure Docker is running
docker compose up -d

# Run migration on dev DB
cd backend && uv run alembic upgrade head

# Run migration on test DB
BOOKCOMPANION_DATABASE__URL=postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test \
  uv run alembic upgrade head
```

Verify migration applied:

```bash
docker exec bookcompanion-db psql -U bookcompanion -c "\dt" | grep summaries
docker exec bookcompanion-db psql -U bookcompanion -c "\d summaries"
docker exec bookcompanion-db psql -U bookcompanion -c "\d book_sections" | grep default_summary_id
```

- [ ] **Step 5: Manual CLI verification**

Run through the end-to-end user journey from spec section 14:

```bash
# Verify preset commands
uv run bookcompanion preset list
uv run bookcompanion preset show practitioner_bullets

# Verify show command (with existing book, if any)
uv run bookcompanion list
uv run bookcompanion show <book_id>  # Check new columns

# Verify summary commands
uv run bookcompanion summary list <book_id>

# Verify help text
uv run bookcompanion --help
uv run bookcompanion summarize --help
uv run bookcompanion summary --help
uv run bookcompanion preset --help

# Verify read command
uv run bookcompanion read <book_id> <section_id>
```

If a test book is available:

```bash
# Full pipeline
uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub
uv run bookcompanion summarize <book_id> --preset practitioner_bullets
uv run bookcompanion summary list <book_id>
uv run bookcompanion summary <book_id>
uv run bookcompanion eval <book_id>
```

- [ ] **Step 6: Update `CLAUDE.md`**

Update the following sections:
- **Commands**: Add `preset`, `summary` sub-apps, `read`, `edit sections`
- **Architecture**: Update service list to include PresetService, QualityService, SummaryService, SectionEditService
- **Domain Terms**: Add Preset, Facet, Fragment, Summary Log, Default Summary
- **Key Patterns**: Update prompt versioning to faceted fragments
- **Gotchas**: Add note about `SummaryStatus` removal and `default_summary_id` pattern
- **Workflows**: Update "Running a book through the full pipeline" with preset flag

- [ ] **Step 7: Run full test suite one final time**

```bash
cd backend && uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

All tests should pass.

- [ ] **Step 8: Final commit**

```bash
git add backend/tests/e2e/test_v1_1_flows.py CLAUDE.md
git commit -m "feat: V1.1 E2E tests, CLAUDE.md updates, final verification"
```

---

## Summary of Changes

| Area | Files Created | Files Modified |
|------|--------------|----------------|
| Models & Schema | 1 migration | `models.py`, `config.py`, `exceptions.py` |
| Prompts | 21 files (2 base + 15 fragments + 4 presets + 1 preset) | Delete 2 V1 templates |
| Repositories | `summary_repo.py` | `section_repo.py`, `book_repo.py`, `eval_repo.py` |
| Services | 4 new (`preset`, `quality`, `summary`, `section_edit`) | `summarizer_service.py`, `evaluator.py`, `book_service.py`, `export_service.py` |
| CLI | 3 new (`preset_cmd`, `summary_cmds`, `read_cmd`) | `main.py`, `deps.py`, `books.py`, `summarize_cmd.py`, `eval_cmd.py`, `edit_cmd.py` |
| Tests | 9 new test files | `test_models.py`, `test_config.py`, `test_summarizer.py` |
| Docs | — | `CLAUDE.md` |
