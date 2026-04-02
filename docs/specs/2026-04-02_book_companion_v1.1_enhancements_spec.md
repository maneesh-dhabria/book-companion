# Book Companion V1.1 — Enhancements Spec

**Date:** 2026-04-02
**Status:** Draft
**Relationship:** Implements [V1.1 Enhancement Requirements](../requirements/2026-04-02_book_companion_v1.1_enhancements.md). Addendum to [V1 Spec](2026-04-01_book_companion_v1_spec.md).

---

## Table of Contents

1. [Glossary](#1-glossary)
2. [Not in Scope](#2-not-in-scope)
3. [Summary Presets & Faceted Prompt Composition](#3-summary-presets--faceted-prompt-composition)
4. [Summary Log (Append-Only)](#4-summary-log-append-only)
5. [Section Merge, Split & Reorder](#5-section-merge-split--reorder)
6. [Enhanced CLI Display & Help](#6-enhanced-cli-display--help)
7. [Extraction Quality Validation](#7-extraction-quality-validation)
8. [Summary Comparison & Quality Visibility](#8-summary-comparison--quality-visibility)
9. [Quick Summary Deprecation](#9-quick-summary-deprecation)
10. [Clean Migration from V1](#10-clean-migration-from-v1)
11. [Database Schema](#11-database-schema)
12. [Eval Assertion Adaptations](#12-eval-assertion-adaptations)
13. [CLI Command Reference](#13-cli-command-reference)
14. [End-to-End User Journey](#14-end-to-end-user-journey)
15. [Verification & Testing Plan](#15-verification--testing-plan)
16. [Industry Research & Recommendations](#16-industry-research--recommendations)
17. [Decision Log](#17-decision-log)
18. [Sources Consulted](#18-sources-consulted)

---

## 1. Glossary

| Term | Definition |
|------|-----------|
| **Preset** | A named YAML file storing a combination of facet values. Analogous to Handbrake encoding presets. Applies to the `summarize` command. |
| **Facet** | One independent dimension of summarization config. V1.1 defines four: output style, compression, audience, content focus. Each backed by a Jinja2 fragment file. |
| **Fragment** | A short (2-4 sentence) Jinja2 template file providing instructions for one facet value. Composed into a full prompt by the base template via `{% include %}`. |
| **Summary log** | The append-only `summary` database table. Every generated summary is a row; rows are never overwritten or deleted (except on book deletion). |
| **Default summary** | The active summary for a section or book, pointed to by `default_summary_id` FK. Changeable via `summary set-default`. |
| **Content type** | Enum (`section`, `book`, `concept`, `annotation`) identifying what a summary row describes. Used with `content_id` for polymorphic association. All 4 values defined upfront; `concept` and `annotation` are reserved for Phase 2. |
| **Derived from** | JSON field on `BookSection` storing IDs of original sections that were merged/split to create it. |

---

## 2. Not in Scope

- **Prompt quality optimization** — separate workstream; this doc provides structural foundation only
- **Web UI / REST API** — V1.1 is CLI-only
- **New eval assertions** — existing 16-assertion battery retained; adaptations for facets specified in [section 12](#12-eval-assertion-adaptations)
- **Multi-language, auth, multi-user** — unchanged from V1
- **Annotation or tagging changes** — unaffected
- **Export format changes** — reads from `default_summary_id` instead of `summary_md`; output formats unchanged

---

## 3. Summary Presets & Faceted Prompt Composition

### 3.1 Facet Dimensions

| Dimension | Values | Controls |
|-----------|--------|----------|
| **style** | `bullet_points`, `narrative`, `podcast_dialogue`, `cornell_notes`, `mind_map_outline`, `tweet_thread` | Output format and structure |
| **compression** | `brief` (10%), `standard` (20%), `detailed` (30%) | Target summary length relative to source |
| **audience** | `practitioner`, `academic`, `executive` | Content prioritization and framing |
| **content_focus** | `key_concepts`, `frameworks_examples`, `full_coverage` | Depth and breadth of coverage |

### 3.2 File System Layout

```
backend/app/services/summarizer/prompts/
  base/
    summarize_section.txt       # Skeleton, assembles fragments via {% include %}
    summarize_book.txt          # Book-level summary template
  fragments/
    style/
      bullet_points.txt
      narrative.txt
      podcast_dialogue.txt
      cornell_notes.txt
      mind_map_outline.txt
      tweet_thread.txt
    audience/
      practitioner.txt
      academic.txt
      executive.txt
    compression/
      brief.txt
      standard.txt
      detailed.txt
    content_focus/
      key_concepts.txt
      frameworks_examples.txt
      full_coverage.txt
  presets/
    practitioner_bullets.yaml   # system: true
    academic_detailed.yaml      # system: true
    executive_brief.yaml        # system: true
    study_guide.yaml            # system: true
    tweet_thread.yaml           # system: true
```

V1 monolithic templates (`summarize_section_v1.txt`, `summarize_book_v1.txt`) are deleted during migration.

### 3.3 Preset YAML Format

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

- `system: true` presets ship with the project and are protected from deletion.
- User presets are stored in the same `presets/` directory with `system: false` or omitted.

### 3.4 Base Template Composition

Fragments are assembled in canonical order: **Role -> Audience -> Content Focus -> Style -> Compression**. This ordering follows research (arXiv 2504.02052) showing Role -> Directive -> Context -> Output Format -> Constraints produces the most consistent output.

```jinja
{# base/summarize_section.txt #}
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

## Source content
{{ section_content }}
```

Fragment loading uses native Jinja2 `{% include %}`. The `FileSystemLoader` search path is set to `backend/app/services/summarizer/prompts/` so fragment paths resolve naturally. A `TemplateNotFound` exception produces a clear error message.

### 3.5 Fragment Design Constraints

- Each fragment: **2-4 sentences**, self-contained, no references to other fragments.
- Fragments must not contradict each other (tested via system preset validation).
- The 5 system presets are tested as known-good combinations. Arbitrary facet combinations are supported but not guaranteed tested.

### 3.6 Preset Validation & Error Handling

On `summarize`:
1. Load preset YAML (or resolve individual facet flags).
2. For each facet value, check that the corresponding fragment file exists. If missing: `Error: Fragment not found: fragments/style/haiku.txt. Available styles: bullet_points, narrative, ...`
3. If `--preset` names a nonexistent preset: `Error: Preset "foo" not found. Run "bookcompanion preset list" to see available presets.`
4. If both `--preset` and individual facet flags are provided, explicit flags override preset values.
5. If neither `--preset` nor any facet flags are provided, use `summarization.default_preset` from config.

### 3.7 Summarize Idempotency

Default behavior: **skip sections that already have a summary with the same preset + facet combination**. This avoids wasted LLM cost. Use `--force` to re-summarize all sections (and the book-level summary) regardless.

`--force` appends new summary rows and updates `default_summary_id` for all sections and the book.

### 3.8 Book-Level Summary Template

The `base/summarize_book.txt` template receives all section summaries (not original content) and produces a book-level summary. It uses the same facet fragments as the section template.

```jinja
{# base/summarize_book.txt #}
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
```

### 3.9 Summarize Error Handling

If an individual section summarization fails (LLM timeout, parsing error):
1. Log the error with section details
2. Mark the section as failed in progress display: `[3/8] Five Forces Framework ✗ (timeout after 300s)`
3. **Continue** to the next section (do not abort the entire run)
4. At the end, report: `✓ Done. 6 section summaries generated. 2 failed (sections #3, #7).`
5. Failed sections retain their previous `default_summary_id` (unchanged)
6. Book-level summary is still generated using available section summaries, with a note about missing sections

### 3.10 Model Selection

The LLM model is determined in this priority order:
1. `--model` flag on `summarize` command (e.g., `--model opus`)
2. `llm.model` from config (default: `"sonnet"`)

The selected model is stored in `summary.model_used` for provenance.

### 3.11 Eval Integration

- `eval_json` on the summary row is populated when the `eval` command is run, **not** automatically after summarization.
- The `eval` command in V1.1 takes a `--summary-id` flag to evaluate a specific summary: `bookcompanion eval <book_id> [--summary-id <id>]`
- Without `--summary-id`, it evaluates the default summary for each section.
- Eval results are written to both `summary.eval_json` (inline) and `eval_traces` table (detailed per-assertion audit trail with `summary_id` FK).

### 3.12 Summarize Progress Display

```
Summarizing 8 sections with preset "practitioner_bullets"...
  [1/8] Introduction                  ✓  (12s, 18.2%)
  [2/8] What Is Competition?          ✓  (28s, 21.5%)
  [3/8] What Is Strategy?             ⊘  skipped (already summarized)
  ...
  [8/8] Continuity                    ✓  (8s, 19.1%)
Generating book-level summary...     ✓  (15s)
✓ Done. 7 section summaries + 1 book summary generated. 1 skipped.
```

Each line shows: index, section title, status (✓/✗/⊘), elapsed time, and compression ratio. Skipped sections (idempotent) show `⊘ skipped`.

### 3.8 Config Changes

| Setting | V1 | V1.1 |
|---------|-----|------|
| `summarization.default_detail_level` | `"standard"` | **Removed.** Replaced by `compression` facet. |
| `summarization.prompt_version` | `"v1"` | **Removed.** Versioning is per-fragment file. |
| `summarization.default_preset` | — | **New.** Default preset name (e.g., `"practitioner_bullets"`). |

### 3.9 Quick Summary Independence

The `quick_summary` code path is **deprecated** in V1.1. The `--quick` flag on `add` becomes an alias that runs `add` followed by `summarize` with the `executive_brief` preset. The `quick_summary` column on `Book` is retained but no longer written to by new code. The `QUICK_SUMMARY` processing step enum value is retained for backward compatibility.

---

## 4. Summary Log (Append-Only)

### 4.1 Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | BigInteger, PK | Auto-increment |
| `content_type` | Enum: `section`, `book`, `concept`, `annotation` | What was summarized. `concept` and `annotation` are reserved for Phase 2. |
| `content_id` | BigInteger | ID of the summarized entity |
| `book_id` | BigInteger, FK -> `Book.id` (CASCADE) | Parent book for efficient per-book queries |
| `preset_name` | String, nullable | Preset used (string reference, not FK) |
| `facets_used` | JSON | `{style, audience, compression, content_focus}` — exact values |
| `prompt_text_sent` | Text | Fully rendered prompt (frozen snapshot, 50-100KB typical) |
| `model_used` | String | e.g., `"opus"`, `"sonnet"` |
| `input_tokens` | Integer, nullable | LLM input token count |
| `output_tokens` | Integer, nullable | LLM output token count |
| `input_char_count` | Integer | Character count of source content |
| `summary_char_count` | Integer | Character count of generated summary |
| `summary_md` | Text | Generated summary markdown |
| `eval_json` | JSON, nullable | Inline evaluation results |
| `latency_ms` | Integer, nullable | Generation time in milliseconds |
| `created_at` | DateTime with TZ | Immutable timestamp |

### 4.2 Relationships

- `Book.default_summary_id` -> FK to `summary.id` (nullable, SET NULL on delete)
- `BookSection.default_summary_id` -> FK to `summary.id` (nullable, SET NULL on delete)
- `summary.book_id` -> FK to `Book.id` (CASCADE). Book deletion cascades to all summary rows.
- `preset_name` is a string, not a FK — the log is self-contained regardless of whether the preset still exists.

### 4.3 Behavior

- Every summarization **appends** rows. No overwrites, no deletes (except cascade from book deletion).
- The most recent summary is auto-set as default unless the user has manually overridden via `set-default`.
- **No delete command** for individual summaries. The append-only log is absolute.
- Self-contained provenance: `prompt_text_sent` + `facets_used` + `model_used` fully capture what produced the summary.

### 4.4 Concurrent Runs

When a second `summarize` starts while one is in progress, the CLI checks for active `ProcessingJob` rows and warns: `A summarization is already running for this book (PID: 1234). Run anyway? [y/N]`. Both runs append independently; the last to complete sets `default_summary_id`.

### 4.5 Orphaned Summary Rows

When sections are deleted via post-save editing, their summary log entries **retain** the original `content_id`. The section row no longer exists, but the summary rows remain as historical records. No NULL-ing of `content_id`.

### 4.6 Indexes

- `(content_type, content_id)` — query all summaries for a given section/book
- `book_id` — query all summaries across a book
- `created_at` — chronological ordering

### 4.7 Storage Estimate

~100 books x 20 sections x 3 summaries = 6,000 rows x ~75KB avg = ~450MB. Acceptable for personal PostgreSQL.

---

## 5. Section Merge, Split & Reorder

### 5.1 Pre-Save Editing (During `add`)

After structure detection and quality analysis, before accepting, the user enters an interactive editing loop. All operations modify an in-memory section list — no DB impact.

**REPL commands:**
- `merge 3,4,5 "Combined Title"` — concatenate content in order
- `split 3 --at-heading` — auto-detect sub-headings, present choices (see [5.3](#53-split-heading-ux))
- `split 3 --at-char 5000` — manual split at character position
- `split 3 --at-paragraph 5000` — split at nearest paragraph boundary to given character position
- `move 5 --after 2` — reorder
- `delete 7,8` — remove unwanted sections
- `undo` — revert the last operation (one level only)
- `show` — redisplay structure
- `done` — accept and save

**Flow:**
1. Display structure with quality metrics and suggested actions (see [section 7](#7-extraction-quality-validation))
2. Prompt: `Apply suggested actions? [Y/n/customize]`
3. Enter interactive REPL loop
4. `done` or `Ctrl+C` exits

### 5.2 Post-Save Editing

```bash
bookcompanion edit sections <book_id>
```

Same REPL commands as pre-save, **except**: no `undo` (operations commit to DB immediately). Each operation is wrapped in a **transaction** — if it fails mid-way, the entire operation rolls back.

> **Deviation from requirements:** Requirements list `undo` for both pre-save and post-save. Per clarification, undo is pre-save only — post-save operations commit immediately, and implementing undo would require deferred DB writes for marginal benefit. Users get a confirmation prompt before each destructive action instead.

**Initial display on entry:**
```
Current structure (8 sections):
  #  ID  Title                        Chars    Summary
  1  20  Introduction                 14,500   ✓ practitioner_bullets
  2  21    What Is Competition?       36,200   ✓ practitioner_bullets
  3  22    Five Forces Framework      24,100   ✓ academic_detailed
  4  23  What Is Strategy?            28,900   ✓ practitioner_bullets
  ...

Edit sections> 
```

**Downstream effects:**
- Merged/split sections are new rows with `default_summary_id = NULL`
- New sections store `derived_from` JSON (e.g., `[3, 4, 5]`) for provenance
- Original sections are **hard deleted**. Summary log entries for deleted sections remain (orphaned `content_id`).
- All sections get `order_index` re-indexed
- Book-level `default_summary_id` is cleared (set to NULL)

**Post-edit prompt:**
```
2 sections modified. Would you like to resummarize affected sections now? [Y/n]
```
- **Yes (default):** Summarize new sections with the book's last-used preset, then regenerate book summary. The "last-used preset" is determined by querying the most recent summary row for this book (`ORDER BY created_at DESC LIMIT 1`) and reading its `preset_name`. Falls back to `summarization.default_preset` from config if no prior summaries exist.
- **No:** Sections stay with `default_summary_id = NULL`, displayed as "Pending" in `show`.

### 5.3 Split Heading UX

When `split 3 --at-heading` is used and multiple sub-headings are detected:

```
Detected sub-headings in section #3 "Five Forces Framework":
  1. "Threat of New Entrants" (at char 1,200)
  2. "Bargaining Power of Suppliers" (at char 4,800)
  3. "Bargaining Power of Buyers" (at char 8,100)
  4. "Threat of Substitutes" (at char 11,400)
  5. "Rivalry Among Existing Competitors" (at char 14,900)

Split at all headings? [Y/n] or enter heading numbers (e.g., 1,3): 
```

If no sub-headings detected: `No sub-headings detected in section 3. Use --at-char <position> or --at-paragraph <position> to split manually.`

### 5.4 Paragraph Boundary Split

`split 3 --at-paragraph 5000` finds the nearest double-newline (`\n\n`) to character position 5000 and splits there. If the nearest paragraph boundary is within 500 chars of the target, use it. Otherwise, fall back to exact character split with a warning: `No paragraph boundary near position 5000. Splitting at exact position.`

### 5.5 Edge Case: Zero Sections

If all sections are deleted, the user must re-parse: `Error: Book has no sections. Re-parse with: bookcompanion add <path>`

Section editing must leave at least 1 section — the `delete` command validates this and errors: `Error: Cannot delete all sections. At least 1 section must remain.`

---

## 6. Enhanced CLI Display & Help

### 6.1 `show` Command

```
#   ID   Title                        Status     Chars    Compression   Eval    Images
1   12   Introduction                 Completed  14,500   18.2%         15/16   —
2   13     What Is Strategy?          Completed  36,200   21.5%         14/16   2/3
3   14     Five Forces Framework      Completed  24,100   19.8%         16/16   1/2
4   15     Strategic Positioning       Pending    27,300   —             —       3/4
5   16   Trade-offs                   Completed  33,800   22.1%         —       —
```

- **`#`**: Flat sequential index (1, 2, 3...)
- **`ID`**: Database section ID for use in CLI commands
- **`Title`**: Indented by `depth * 2 spaces` for hierarchy
- **`Status`**: Derived. `Completed` = `default_summary_id` non-null. `Pending` = NULL. `Running`/`Failed` from active `ProcessingJob`.
- **`Chars`**: Content character count, comma-formatted
- **`Compression`**: `summary_char_count / input_char_count * 100`. Dash when no summary.
- **`Eval`**: Pass/total (e.g., `14/16`). Dash when no eval.
- **`Images`**: `captioned/total` from existing V1 image data. Dash when no images.

**Quality summary line** above the table:
```
Quality: 7/8 sections OK. 1 warning (section #3: possibly truncated)
```

**Adaptive column hiding**: Detect terminal width. At < 120 columns, hide `Images`. At < 100 columns, also hide `Eval`. At < 80 columns, also hide `Compression`.

### 6.2 `add` Command — Structure Detection Display

```
Detected structure (8 sections):
  1. Introduction                    14,500 chars  ~3,200 tokens
  2. What Is Strategy?               36,200 chars  ~8,100 tokens
  3.   Five Forces Framework         24,100 chars  ~5,400 tokens
  4. Trade-offs                         120 chars   ~30 tokens   ⚠ possibly truncated
  5. Copyright Notice                    0 chars    ~0 tokens    ✗ empty section
  6. About the Author                  450 chars   ~100 tokens   ⚠ non-content
```

Token estimation: `chars / 4.5` (approximate for English text).

### 6.3 Help Text

`bookcompanion --help` includes a "Common Workflows" section:

```
Common Workflows:
  Read a section summary      bookcompanion summary <book_id> <section_id>
  Compare with original       bookcompanion read <book_id> <section_id> --with-summary
  Search across library       bookcompanion search "competitive advantage"
  Re-summarize with preset    bookcompanion summarize <book_id> --preset academic_detailed
  Compare two summaries       bookcompanion summary compare <id1> <id2>
  Export book summary         bookcompanion export book <book_id> --format markdown
  Edit section structure      bookcompanion edit sections <book_id>
```

Each subcommand `--help` includes 2-3 example invocations.

### 6.4 Empty State: No Summary

When `bookcompanion summary <book_id> <section_id>` is called but `default_summary_id` is NULL:

```
No summary for section #3 "Five Forces Framework".
Run: bookcompanion summarize 3 14 --preset practitioner_bullets
```

---

## 7. Extraction Quality Validation

Deterministic heuristics (no LLM calls) run automatically during parsing. Surface warnings during `add` and `show`. Act as a soft gate before `summarize`.

### 7.1 Quality Checks

| Check | Detection Rule | Severity | Suggested Action |
|-------|---------------|----------|-----------------|
| Empty section | 0 characters | Error | Delete |
| Short section | < 200 characters | Warning | Merge into adjacent section |
| Non-content section | Title matches regex: `copyright\|about the author\|also by\|acknowledgments?\|dedication\|table of contents\|index\|bibliography` (case-insensitive) | Warning | Delete |
| Truncated section | < 200 chars AND adjacent section at same depth has 5x+ chars | Warning | Merge into adjacent |
| Tiny fragment | < 500 chars AND depth > 0 | Warning | Merge into parent |
| Oversized section | > 100,000 chars | Info | Suggest split at detected sub-headings |
| Encoding issues | > 1% of characters are U+FFFD replacement chars | Warning | Flag for review |
| Repeated content | > 80% text overlap via character 3-gram Jaccard similarity | Warning | Delete the shorter duplicate |
| Image-heavy | Image-to-text ratio > 3:1 | Info | Flag for review |
| Page number artifacts | Isolated page numbers between paragraphs (regex: `^\s*\d{1,4}\s*$` on its own line) | Info | Flag for review |

### 7.2 Suggested Actions Flow (During `add`)

```
Suggested actions:
  * Delete sections 4, 5, 6 — detected as non-content
  * Merge section 3 into section 2 — section 3 appears truncated (85 chars)

Apply suggested actions? [Y/n/customize]
```

- **Y (default):** Apply all suggestions
- **N:** Skip, accept structure as-is
- **Customize:** Enter the interactive editing REPL with suggestions pre-populated

### 7.3 Soft Gate on Summarization

When `summarize` runs, sections with unresolved warnings are flagged:

```
⚠ Section #3 "Appendix A" has quality warnings (85 chars — possibly truncated).
Skip this section? [Y/n/force-all]
```

- `--force` flag bypasses all quality gates
- `force-all` response in the interactive prompt skips warnings for all remaining sections in this run
- Sections with errors (empty, 0 chars) are auto-skipped with a message

---

## 8. Summary Comparison & Quality Visibility

### 8.1 `summary list <book_id> [section_id]`

**Without `section_id`** — per-section overview:
```
Book: "Understanding Michael Porter" — 12 summaries across 5 sections

  #   ID   Title                        Summaries   Default Preset
  1   12   Introduction                 2           practitioner_bullets
  2   13     What Is Strategy?          3           practitioner_bullets
  3   14     Five Forces Framework      2           academic_detailed
  4   15     Strategic Positioning       0           —
  5   16   Trade-offs                   2           practitioner_bullets

  Book-level summaries: 3 (default: #78, practitioner_bullets)
```

**With `section_id`** — detailed list:
```
Section #3 "Five Forces Framework" — 2 summaries:

  ID   Preset                  Model    Compression   Chars    Eval     Created
  42   practitioner_bullets    opus     21.5%         7,800    14/16    2026-04-01 10:30
  58   academic_detailed       sonnet   31.2%         11,300   12/16    2026-04-01 14:15

  ★ Default: #42
```

### 8.2 `summary compare <id1> <id2>`

- Metadata header for each summary (preset, model, compression, eval score)
- Side-by-side display if terminal >= 120 columns; sequential otherwise
- **Concept diff**: deterministic extraction via regex:
  - Bold terms: `\*\*([^*]+)\*\*`
  - Header terms: `^#{1,6}\s+(.+)$`
  - Capitalized multi-word phrases (likely named entities): `\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b`
  - Shows terms present in one but missing from the other as "Only in #42" / "Only in #58" lists.
- **Cross-section comparison**: Allowed. No validation that both summaries are for the same section — useful for comparing summaries across different sections or books.
- **Book-level summaries**: `summary list <book_id> --book-level` shows detailed list of book-level summaries only (same format as section-level detailed list).

### 8.3 `summary set-default <summary_id>`

- Looks up the summary row by ID. Reads `content_type` to determine if it's a section or book summary.
- For `content_type=section`: sets `BookSection.default_summary_id` where `BookSection.id == summary.content_id`
- For `content_type=book`: sets `Book.default_summary_id` where `Book.id == summary.content_id`
- Validates the target entity exists: `Error: Section #999 not found (summary references a deleted section).`
- **Triggers synchronous re-embedding** for `source_type=SECTION_SUMMARY` search index entries (< 2s with local Ollama)
- Validates the summary_id exists: `Error: Summary #999 not found.`

### 8.4 `summary <book_id> [section_id]` (Read Default)

Reads and displays the default summary for a book or section.

- **`summary <book_id>`**: Shows the book-level default summary (from `Book.default_summary_id`).
- **`summary <book_id> <section_id>`**: Shows the section's default summary (from `BookSection.default_summary_id`).
- **No summary exists**: Display helpful error: `No summary for section #3 "Five Forces Framework". Run: bookcompanion summarize 3 14 --preset practitioner_bullets`

### 8.5 `summary show <summary_id>`

Displays a specific summary (by summary table ID) with full provenance: preset, facets used, model, input/output tokens, character counts, compression ratio, eval results, timestamp.

### 8.6 `read <book_id> <section_id> [--with-summary]`

Displays the original section content. With `--with-summary`, appends the default summary below a separator for side-by-side reading.

---

## 9. Quick Summary Deprecation

> **Deviation from requirements:** Requirements state quick_summary "remains independent." This spec deprecates it per clarification with the product owner — the preset system (`--preset executive_brief`) provides the same fast-summary workflow with better provenance tracking.

- The `quick_summary` single-pass code path is deprecated.
- `--quick` flag on `add` becomes an alias: runs `add` then `summarize --preset executive_brief`.
- `Book.quick_summary` column is retained (not dropped in migration) but no longer written to.
- `ProcessingStep.QUICK_SUMMARY` enum value retained for backward compatibility.
- The `quick_summary_v1.txt` prompt template file is retained but unused by new code.

---

## 10. Clean Migration from V1

Single Alembic migration file. No backward compatibility layer.

### 10.1 Migration Steps

1. **Create** `summaries` table (schema per [section 4](#4-summary-log-append-only))
2. **Add** `default_summary_id` FK column to `books` (nullable, FK -> `summary.id`, SET NULL on delete)
3. **Add** `default_summary_id` FK column to `book_sections` (nullable, FK -> `summary.id`, SET NULL on delete)
4. **Add** `derived_from` JSON column to `book_sections` (nullable)
5. **Drop** index `ix_book_sections_summary_status` (depends on `summary_status` column)
6. **Drop** columns from `book_sections`: `summary_md`, `summary_status`, `summary_version`, `summary_model`, `summary_eval`, `user_edited`
7. **Drop** columns from `books`: `overall_summary`, `overall_summary_eval`
8. **Drop** `SummaryStatus` enum type from database
9. **Add** `summary_id` FK column to `eval_traces` (nullable, FK -> `summary.id`, SET NULL on delete)
10. **Truncate** `eval_traces` table
11. Create indexes on `summaries` table per [section 4.6](#46-indexes)

### 10.2 Prompt System Migration

- Delete V1 templates: `summarize_section_v1.txt`, `summarize_book_v1.txt`
- Create faceted base templates + fragment files per [section 3.2](#32-file-system-layout)
- Create 5 system preset YAML files

### 10.3 User Impact

- All existing books retain parsed structure, sections, and content
- All existing summaries are deleted — re-summarize using new presets
- Eval traces are cleared — re-run evals after re-summarization

### 10.4 Downstream Model Updates

- **`BookStatus` enum**: `SUMMARIZING` and `COMPLETED` meanings update. `COMPLETED` = all sections have non-null `default_summary_id` AND book has non-null `default_summary_id`. `SUMMARIZING` = at least one section is currently being processed.
- **`SummaryStatus` enum**: Dropped from both Python code and database. Section status derived from `default_summary_id`.
- **`SearchIndex`**: When a section's default summary changes, re-embed `source_type=SECTION_SUMMARY` entries synchronously.
- **`EvalTrace`**: New `summary_id` FK links eval runs to specific summary rows. Existing traces truncated.
- **`ProcessingJob`**: No schema changes. Existing PID-based orphan detection reused as-is.
- **`ContentType` enum** (existing in models.py): The new `SummaryContentType` enum (`section`, `book`, `concept`, `annotation`) is separate from the existing `ContentType` enum used by `Annotation`. Name the new enum `SummaryContentType` to avoid collision.

---

## 11. Database Schema

### 11.1 New Table: `summary`

```python
class SummaryContentType(str, enum.Enum):
    SECTION = "section"
    BOOK = "book"
    CONCEPT = "concept"       # Reserved for Phase 2
    ANNOTATION = "annotation"  # Reserved for Phase 2


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

### 11.2 Modified: `Book`

| Change | Field | Type |
|--------|-------|------|
| Add | `default_summary_id` | BigInteger, FK -> `summaries.id`, nullable, SET NULL |
| Drop | `overall_summary` | — |
| Drop | `overall_summary_eval` | — |

`Book.quick_summary` column retained (not dropped).

### 11.3 Modified: `BookSection`

| Change | Field | Type |
|--------|-------|------|
| Add | `default_summary_id` | BigInteger, FK -> `summaries.id`, nullable, SET NULL |
| Add | `derived_from` | JSON, nullable |
| Drop | `summary_md` | — |
| Drop | `summary_status` | — |
| Drop | `summary_version` | — |
| Drop | `summary_model` | — |
| Drop | `summary_eval` | — |
| Drop | `user_edited` | — |

### 11.4 Modified: `EvalTrace`

| Change | Field | Type |
|--------|-------|------|
| Add | `summary_id` | BigInteger, FK -> `summaries.id`, nullable, SET NULL |

### 11.5 ER Diagram

```
summary_preset (YAML files, not a DB table)
  - name, description, system flag
  - facets: {style, audience, compression, content_focus}

summaries (DB table, append-only)
+---------------------------------+
| id (PK, BigInteger)             |
| content_type (SummaryContentType)|
| content_id (BigInt)             |
| book_id (FK -> books.id)        |
| preset_name (String, nullable)  |
| facets_used (JSON)              |
| prompt_text_sent (Text)         |
| model_used (String)             |
| input_tokens (Int, nullable)    |
| output_tokens (Int, nullable)   |
| input_char_count (Int)          |
| summary_char_count (Int)        |
| summary_md (Text)               |
| eval_json (JSON, nullable)      |
| latency_ms (Int, nullable)      |
| created_at (DateTime TZ)        |
+---------------------------------+
        ^              ^
        |              |
  default_summary_id   default_summary_id
        |              |
 +----------+   +----------------+
 |   books  |   | book_sections  |
 |          |   | + derived_from |
 +----------+   +----------------+

eval_traces (modified)
+---------------------------------+
| ...existing fields...           |
| + summary_id (FK, nullable)     |
+---------------------------------+
```

### 11.6 Service Layer Changes

| Service | Change |
|---------|--------|
| **SummarizerService** | Replace monolithic template loading with faceted fragment composition. Accept preset/facets parameters. Write to `summaries` table instead of `BookSection.summary_md`. Implement idempotent skip logic. |
| **PresetService** (new) | Load, validate, create, delete preset YAML files. Resolve facet overrides. Validate fragment file existence. |
| **SectionEditService** (new) | In-memory merge/split/reorder/delete for pre-save. DB-backed operations for post-save with per-operation transactions. |
| **QualityService** (new) | Run deterministic quality checks on parsed sections. Generate suggested actions. |
| **SummaryService** (new) | CRUD for summary log queries (list, compare, set-default, show). Concept diff extraction. |
| **EvalService** | Read `facets_used` from summary row to adapt assertion thresholds. Link eval traces to `summary_id`. |
| **EmbeddingService** | Re-embed on `set-default` changes (synchronous, called by SummaryService). |
| **BookService** | Update status derivation. Remove `overall_summary`/`overall_summary_eval` writes. |

### 11.7 Repository Layer Changes

| Repository | Change |
|------------|--------|
| **SummaryRepository** (new) | `create()`, `get_by_id()`, `list_by_book()`, `list_by_content()`, `get_latest_by_content_and_facets()` (for idempotent skip). Use `selectinload()` as needed. |
| **BookRepository** | Add `default_summary_id` to updates. Remove `overall_summary` writes. |
| **SectionRepository** | Add `default_summary_id`, `derived_from`. Remove summary-related field writes. Add bulk `delete_by_ids()`, `reindex_order()`. |
| **EvalTraceRepository** | Add `summary_id` to creates. |

---

## 12. Eval Assertion Adaptations

The existing 16-assertion battery is retained. Assertions that depend on output format must adapt based on `facets_used` from the summary row.

### 12.1 Facet-Sensitive Assertions

| Assertion | Category | Adaptation |
|-----------|----------|------------|
| `reasonable_length` | Completeness | Read target compression from `facets_used.compression`. `brief`=5-15%, `standard`=15-25%, `detailed`=25-40%. `tweet_thread` style overrides to 2-8% regardless of compression. |
| `has_key_concepts` | Completeness | `key_concepts` focus: expect 3-5 focused concepts. `full_coverage`: expect 8+ concepts. `frameworks_examples`: expect named frameworks. |
| `covers_main_themes` | Completeness | `key_concepts` focus: relax threshold (top 2-3 themes). `full_coverage`: strict threshold (all major themes). |
| `appropriate_detail_level` | Completeness | Map directly to `facets_used.compression` value instead of the old `detail_level` config. |
| `well_structured` | Format | `bullet_points`: expect bullet markdown. `narrative`: expect paragraphs. `cornell_notes`: expect Q&A format. `tweet_thread`: expect numbered items < 280 chars. `mind_map_outline`: expect indented outline. |

### 12.2 Universally Applied Assertions (No Adaptation)

These apply identically regardless of facets:

| Assertion | Category |
|-----------|----------|
| `no_hallucinated_facts` | Faithfulness |
| `faithful_to_source` | Faithfulness |
| `no_unsupported_claims` | Faithfulness |
| `coherent_flow` | Coherence |
| `logical_progression` | Coherence |
| `consistent_terminology` | Coherence |
| `no_redundancy` | Coherence |
| `specific_not_vague` | Specificity |
| `uses_concrete_examples` | Specificity |
| `avoids_generic_phrases` | Specificity |
| `captures_nuance` | Depth |

---

## 13. CLI Command Reference

### 13.1 New Commands

| Command | Description |
|---------|-------------|
| `preset list` | List presets with name, description, system flag, and all 4 facet values |
| `preset show <name>` | Show facet values for a preset |
| `preset create <name>` | Create preset. Interactive by default; supports `--style`, `--audience`, `--compression`, `--content-focus`, `--description` flags for non-interactive mode |
| `preset delete <name>` | Delete user preset. System presets protected: `Error: Cannot delete system preset "practitioner_bullets".` |
| `summary list <book_id> [section_id]` | List summaries for book or section |
| `summary compare <id1> <id2>` | Side-by-side comparison with concept diff |
| `summary set-default <summary_id>` | Set active default summary; triggers sync re-embedding |
| `summary show <summary_id>` | Show summary with full provenance metadata |
| `summary <book_id> [section_id]` | Read the default summary for a book or section |
| `read <book_id> <section_id> [--with-summary]` | Read original section content, optionally with default summary |
| `edit sections <book_id>` | Interactive section merge/split/reorder/delete (post-save) |

**Typer registration:** `preset` and `summary` are registered as Typer sub-apps via `app.add_typer()` in `backend/app/cli/main.py`. New command files: `cli/commands/preset.py`, `cli/commands/summary_cmds.py`, `cli/commands/edit.py`, `cli/commands/read.py`.

**deps.py wiring:** New services (PresetService, SectionEditService, QualityService, SummaryService) are added to `get_services()` with try/except for graceful degradation.

### 13.2 Modified Commands

| Command | Changes |
|---------|---------|
| `summarize` | New flags: `--preset`, `--style`, `--audience`, `--compression`, `--content-focus`, `--model` (override LLM model). Removes `--detail`. Skips already-summarized sections by default. `--force` re-summarizes all. Warns on concurrent runs. |
| `summary <book_id> [section_id]` | Reads from `summaries` table via `default_summary_id`. Shows helpful error when no summary exists. |
| `show` | New columns: ID, Chars, Compression, Eval, Images. Quality summary line. Adaptive column hiding. |
| `add` | Structure detection shows chars + tokens per section, quality warnings, suggested actions, interactive editing REPL. `--quick` aliased to add + summarize with `executive_brief` preset. |
| `eval` | New `--summary-id` flag to evaluate a specific summary. Without it, evaluates default summaries. Writes to both `summary.eval_json` and `eval_traces` with `summary_id` FK. |
| `--help` (all) | Common Workflows section on main help. 2-3 examples per subcommand. |

### 13.3 Preset Create — Detailed Behavior

**Interactive mode** (no facet flags):
```
$ bookcompanion preset create my_preset
Description: My custom preset for detailed academic work
Style [bullet_points/narrative/podcast_dialogue/cornell_notes/mind_map_outline/tweet_thread]: narrative
Audience [practitioner/academic/executive]: academic
Compression [brief/standard/detailed]: detailed
Content focus [key_concepts/frameworks_examples/full_coverage]: full_coverage

✓ Preset "my_preset" created at prompts/presets/my_preset.yaml
```

**Non-interactive mode** (all facets via flags):
```
$ bookcompanion preset create my_preset \
    --description "Detailed academic" \
    --style narrative --audience academic \
    --compression detailed --content-focus full_coverage
```

Missing facets in non-interactive mode default to the system default preset's values.

**Duplicate name handling:** If a preset with the same name already exists: `Error: Preset "my_preset" already exists. Use a different name or delete it first with: bookcompanion preset delete my_preset`

### 13.4 Preset List — Display Format

```
Available presets:

  Name                   Description                                    System   Style           Audience      Compression   Focus
  practitioner_bullets   Actionable frameworks in scannable bullet      ✓        bullet_points   practitioner  standard      frameworks_examples
  academic_detailed      Comprehensive academic analysis                ✓        narrative       academic      detailed      full_coverage
  executive_brief        Key decisions and bottom-line takeaways        ✓        bullet_points   executive     brief         key_concepts
  study_guide            Cornell notes for active learning              ✓        cornell_notes   practitioner  standard      full_coverage
  tweet_thread           280-char tweet-sized takeaways                 ✓        tweet_thread    executive     brief         key_concepts
  my_custom              Custom preset for Porter analysis                       narrative       academic      detailed      frameworks_examples
```

---

## 14. End-to-End User Journey

```bash
# 1. Add a new book — quality checks and section editing
$ bookcompanion add ~/books/understanding-michael-porter.epub

Parsing "understanding-michael-porter.epub"...
Title: Understanding Michael Porter
Author: Joan Magretta
Format: EPUB

Detected structure (12 sections):
  1.  Introduction                    14,500 chars  ~3,200 tokens
  2.  What Is Competition?            36,200 chars  ~8,100 tokens
  3.    The Five Forces Framework     24,100 chars  ~5,400 tokens
  4.  What Is Strategy?               28,900 chars  ~6,400 tokens
  5.    Creating Value                18,300 chars  ~4,100 tokens
  6.    Trade-offs                    22,700 chars  ~5,100 tokens
  7.    Fit                           19,800 chars  ~4,400 tokens
  8.  Continuity                       8,200 chars  ~1,800 tokens
  9.  Copyright Notice                     0 chars      ~0 tokens  ✗ empty
  10. About the Author                   450 chars    ~100 tokens  ⚠ non-content
  11. Also by Joan Magretta            1,200 chars    ~270 tokens  ⚠ non-content
  12. Index                           12,400 chars  ~2,800 tokens  ⚠ non-content

Suggested actions:
  * Delete sections 9, 10, 11, 12 — detected as non-content

Apply suggested actions? [Y/n/customize] Y
✓ Deleted 4 sections.

  [Updated structure: 8 sections]

Edit sections> done
✓ Structure accepted. Book saved (ID: 3). 8 sections parsed and stored.

# 2. Summarize with a preset
$ bookcompanion summarize 3 --preset practitioner_bullets

Summarizing 8 sections with preset "practitioner_bullets"...
  [1/8] Introduction                  ✓  (12s, 18.2%)
  [2/8] What Is Competition?          ✓  (28s, 21.5%)
  ...
  [8/8] Continuity                    ✓  (8s, 19.1%)
Generating book-level summary...     ✓  (15s)
✓ Done. 8 section summaries + 1 book summary generated.

# 3. Try a different preset for one section
$ bookcompanion summarize 3 22 --preset academic_detailed

Summarizing section #3 "The Five Forces Framework" with preset "academic_detailed"...
  ✓ (45s, 31.2%)

# 4. Compare the two summaries
$ bookcompanion summary compare 42 58

[Side-by-side comparison with concept diff]

# 5. Set preferred summary as default
$ bookcompanion summary set-default 58
✓ Default summary for section #3 updated to #58.
✓ Search index re-embedded.

# 6. Edit sections post-save
$ bookcompanion edit sections 3

Current structure (8 sections):
  #  ID  Title                        Chars
  1  20  Introduction                 14,500
  2  21    What Is Competition?       36,200
  ...

Edit sections> merge 5,6 "Creating Value & Trade-offs"
✓ Merged sections 5-6 into "Creating Value & Trade-offs" (ID: 30)

1 section modified. Would you like to resummarize affected sections now? [Y/n] Y
Summarizing 1 section with preset "practitioner_bullets"...
  ✓ (20s, 19.5%)
Regenerating book-level summary...  ✓ (15s)
```

---

## 15. Verification & Testing Plan

### 15.1 Unit Tests

| Area | Tests | Description |
|------|-------|-------------|
| **Fragment validation** | `test_all_system_presets_resolve` | Load each of 5 system presets, resolve all fragment paths, render template with mock data. Verify no Jinja2 errors, output is non-empty. |
| **Fragment file existence** | `test_all_fragment_files_exist` | For each dimension, verify all expected fragment files exist on disk. |
| **Preset YAML parsing** | `test_preset_loading` | Load each preset, validate required fields (name, description, facets), verify all facet values are valid. |
| **Preset validation** | `test_invalid_preset_errors` | Missing facet values, nonexistent fragment references, missing required fields. |
| **Facet override logic** | `test_preset_with_overrides` | Preset + explicit flags merge correctly. |
| **Quality checks** | `test_quality_heuristics` | Each of the 10 quality checks with positive and negative cases. Test 3-gram Jaccard similarity with known duplicates. |
| **Section merge logic** | `test_merge_sections` | In-memory merge: content concatenation, title assignment, order re-indexing. |
| **Section split logic** | `test_split_at_heading`, `test_split_at_char`, `test_split_at_paragraph` | Split produces correct sub-sections, content integrity preserved. |
| **Summary status derivation** | `test_status_from_default_summary_id` | NULL -> Pending, non-null -> Completed, active ProcessingJob -> Running. |
| **Adaptive display** | `test_column_hiding_thresholds` | Terminal width thresholds (120, 100, 80) hide correct columns. |
| **Eval adaptations** | `test_reasonable_length_by_compression` | `brief`/`standard`/`detailed` produce correct threshold ranges. Tweet thread override. |
| **Config migration** | `test_removed_config_keys_ignored` | Old config keys (`default_detail_level`, `prompt_version`) don't cause errors. |
| **Idempotent summarization** | `test_skip_already_summarized` | Section with matching preset+facets is skipped. `--force` overrides. |
| **REPL command parsing** | `test_parse_merge`, `test_parse_split`, `test_parse_delete`, `test_parse_move` | Parse REPL input strings into structured commands. Edge cases: quoted titles, comma-separated IDs, invalid input. |
| **Concept diff extraction** | `test_concept_diff` | Extract bold terms, headers, capitalized phrases from two summaries. Verify diff correctly shows unique terms in each. |
| **Paragraph boundary split** | `test_split_at_paragraph` | Given content and a target char position, find the nearest `\n\n` boundary and split there. Test edge cases: position at start, end, within paragraph. |
| **Book validation** | `test_invalid_book_id_errors` | Summary list, summarize, edit for nonexistent book_id returns clear error. |

### 15.2 Integration Tests

| Area | Tests | Description |
|------|-------|-------------|
| **Summary CRUD** | `test_summary_append`, `test_summary_cascade_delete` | Insert summary rows, verify append-only. Delete book, verify cascade. |
| **Default summary FK** | `test_set_default_summary` | Set default, verify FK on section. Delete summary, verify SET NULL. |
| **Section merge/split (DB)** | `test_post_save_merge`, `test_post_save_split` | Merge/split sections in DB. Verify `derived_from`, `order_index`, orphaned summary rows. Transaction rollback on failure. |
| **Migration** | `test_migration_up_down` | Run migration forward and backward on test DB. Verify table creation, column drops, index creation. |
| **Re-embedding** | `test_set_default_triggers_reembed` | After `set-default`, verify search index entries are updated. |
| **Concurrent run warning** | `test_concurrent_summarize_warning` | Create active ProcessingJob, verify warning message. |
| **Eval with facets** | `test_eval_reads_facets_from_summary` | Run eval on a summary with specific facets, verify adapted thresholds. |

### 15.3 E2E Tests

| Test | Description |
|------|-------------|
| **Full pipeline** | Add book -> edit sections (delete non-content) -> summarize with preset -> list summaries -> compare -> set-default -> search. Covers the complete user journey from [section 14](#14-end-to-end-user-journey). Uses a Gutenberg test book. |
| **Preset management** | Create preset -> list (verify appears) -> show -> use in summarize -> delete. |
| **Section editing** | Add book -> post-save merge -> verify derived_from -> resummarize -> verify new summary in log. |
| **Quality gate** | Add book with intentionally truncated section -> verify warning -> verify skip on summarize without --force -> verify pass with --force. |
| **Quick deprecation** | `add --quick` runs add + summarize with executive_brief preset. Verify summary in log with correct preset. |

### 15.4 Fragment Rendering Tests

Dedicated test file: `tests/unit/test_prompt_fragments.py`

```python
@pytest.mark.parametrize("preset_name", SYSTEM_PRESETS)
def test_system_preset_renders(preset_name):
    """Load preset, resolve fragments, render template with mock data."""
    preset = load_preset(preset_name)
    env = create_jinja_env()
    template = env.get_template("base/summarize_section.txt")
    result = template.render(
        book_title="Test Book",
        author="Test Author",
        section_title="Test Section",
        section_content="Sample content...",
        cumulative_context="",
        **preset.facets,
    )
    assert len(result) > 0
    assert "{{" not in result  # No unrendered variables
```

### 15.5 Linting & Static Analysis

- `ruff check .` — all new code passes existing lint rules
- `ruff format --check .` — formatting consistent
- Type annotations on all new public functions (services, repositories, CLI commands)
- No `# type: ignore` without justification

---

## 16. Industry Research & Recommendations

### 16.1 Summarization Architecture

| Pattern | Applicability | Status |
|---------|--------------|--------|
| **Map-Reduce with cumulative context** | Already in V1 | Retained |
| **Context-Aware Hierarchical Merging** (ACL 2025) | Augment book summary step with key source excerpts | Recommended for prompt optimization workstream |
| **Chain of Density** (Adams et al., 2023) | Optional post-processing for `brief` compression | Recommended for prompt optimization workstream |
| **Self-Critique Refinement** (SCRPO, 2025) | Single critique-refine pass | Deferred to prompt optimization workstream |

### 16.2 Composable Prompt Systems

| Pattern | Source | Adoption |
|---------|--------|----------|
| Faceted fragments + preset shortcuts | Handbrake/Lightroom model | **Adopted** as core architecture |
| Canonical fragment ordering | arXiv 2504.02052 | **Adopted**: Role -> Audience -> Content Focus -> Style -> Compression |
| Prompt interference mitigation | Microsoft ISE research | **Mitigated**: 2-4 sentence fragments, tested system presets |

### 16.3 Quality Metrics

| Framework | Recommendation |
|-----------|----------------|
| **DeepEval Summarization** | Consider as future complement to 16-assertion battery |
| **BooookScore** (ICLR 2024) | Useful taxonomy for future eval assertions |

---

## 17. Decision Log

| # | Decision | Options Considered | Choice | Rationale |
|---|----------|--------------------|--------|-----------|
| 1 | Summary storage model | (A) New `summaries` table with polymorphic content_type+content_id (B) JSON array in existing field (C) Event log | A | Clean relational model. Polymorphic pattern already used in Annotation. |
| 2 | Content type enum scope | (A) All 4 types now (B) Only section+book (C) Extensible string | A | Include concept+annotation as reserved values. Avoids future migration to alter enum. |
| 3 | Prompt storage | (A) Inline in summary table (B) Separate table (C) File reference | A | Simple, self-contained. ~450MB for 6K rows acceptable for personal PostgreSQL. |
| 4 | Preset storage | (A) YAML files in repo (B) DB table (C) ~/.config/ | A | Version controlled, visible, portable. DB adds complexity without benefit until web UI. |
| 5 | Prompt composition | (A) Monolithic templates (B) Composable Jinja2 fragments (C) DSPy programmatic | B | 4 dimensions x values = 135+ monolithic templates. Jinja2 matches existing infrastructure. |
| 6 | Fragment loading | (A) Native {% include %} (B) Custom load function (C) Pre-compose in Python | A | Standard Jinja2. TemplateNotFound is clear enough. |
| 7 | Preset FK in summary log | Nullable string + facets_used JSON + prompt_text_sent | String | Log must be self-contained regardless of preset changes. |
| 8 | Section merge/split timing | (A) During add only (B) Post-save only (C) Both | C | Pre-save is zero-cost. Post-save needed for corrections. |
| 9 | Section mutation strategy | (A) In-place with derived_from (B) Soft delete (C) Event sourcing | A | Hard delete originals, store derived_from. Soft deletes add query complexity. |
| 10 | Undo scope | (A) Both pre and post-save (B) Pre-save only (C) Both with multi-level | B | Post-save commits immediately with confirmation prompts. Undo in post-save requires deferred DB writes — complex for marginal benefit. |
| 11 | Orphaned summary handling | (A) Keep original content_id (B) Set to NULL (C) Cascade delete | A | Historical reference retained. Section won't exist on join but summary is self-contained. |
| 12 | Extraction quality gate | (A) Warn only (B) Soft gate with --force (C) Hard gate | B | Soft gate balances safety with flexibility. |
| 13 | Quality check approach | (A) LLM-based (B) Deterministic heuristics (C) Hybrid | B | Regex, char counts, 3-gram Jaccard are fast, free, reproducible. |
| 14 | Overlap algorithm | (A) Character 3-gram Jaccard (B) Sentence overlap (C) Unspecified | A | Simple, fast, well-understood. Jaccard >0.8 = duplicate. |
| 15 | V1 migration strategy | (A) Backward-compatible (B) Clean, drop old data | B | Simpler migration. Books retain structure; summaries cheap to regenerate. |
| 16 | Migration structure | (A) Single Alembic revision (B) Split 2-3 (C) One per feature | A | Atomic upgrade/downgrade. All changes are interdependent. |
| 17 | Summarize re-run behavior | (A) Skip already-summarized (B) Always append (C) Ask per section | A | Default skip saves LLM cost. --force overrides. |
| 18 | --force scope | Includes both sections and book-level summary | Both | Complete refresh. |
| 19 | Quick summary | (A) Keep independent (B) Store in log (C) Deprecate | C | Users can use --preset executive_brief. --quick aliased. |
| 20 | Empty state (no summary) | (A) Helpful error + suggestion (B) Offer to summarize (C) Just error | A | Shows exact command to run. Not overly aggressive. |
| 21 | Display adaptive columns | (A) Auto-adapt to width (B) Always show all (C) --compact flag | A | Progressive hiding: Images < 120, Eval < 100, Compression < 80. |
| 22 | Re-embedding on set-default | (A) Synchronous (B) Background (C) Manual | A | Single section < 2s with Ollama. Simple, predictable. |
| 23 | Summary delete | (A) No delete (B) With confirmation (C) Soft delete | A | Append-only is absolute. Only book deletion removes summaries. |
| 24 | Split options | --at-heading, --at-char, --at-paragraph | All 3 | --at-paragraph splits at nearest paragraph boundary. |
| 25 | Split heading UX | (A) Present headings, user chooses (B) Auto-split all (C) First only | A | Show headings, user picks. Avoids creating too many small sections. |
| 26 | ProcessingJob changes | (A) Extend with preset fields (B) Use as-is (C) Replace | B | Already tracks book_id + PID + status. Preset info in summary log. |
| 27 | Images column | Existing V1 display | V1 data | Image extraction already exists. Show command just displays counts. |
| 28 | Preset create modes | (A) Interactive only (B) Both interactive + flags (C) Non-interactive only | B | Interactive default, flags for scripting and testing. |
| 29 | Fragment validation test | (A) Dedicated test (B) Implicit via integration | A | Catches broken presets before runtime. Renders each preset with mock data. |
| 30 | Eval detail in spec | (A) Detail all adaptations (B) Flag + principles (C) Defer | A | Specified per-assertion in section 12. |
| 31 | Encoding threshold | >1% U+FFFD characters | 1% | Catches significant issues without false positives. |
| 32 | ID type for summary table | (A) Match existing (B) BigInteger (C) UUID | B | Append-only table could grow large. BigInteger is appropriate. |
| 33 | Preset list display | (A) Full table with facets (B) Name + description (C) Grouped | A | Complete at a glance. All 4 facet values shown. |
| 34 | Post-save transaction | (A) Per operation (B) Entire session (C) Default | A | Each merge/split/delete atomic. Failed operation rolls back cleanly. |
| 35 | Compare layout threshold | 120 columns for side-by-side | 120 | Each summary gets ~55 cols. Sequential below 120. |
| 36 | E2E test approach | Full pipeline E2E | One test | Covers complete user journey from add to search. |
| 37 | Health check command | (A) Extend init (B) New doctor (C) None | C | Fragment validation at summarize time. DB via alembic. No dedicated command. |
| 38 | Zero sections guard | Error with helpful message | Error | Prevent deletion of all sections + error if summarize called with 0 sections. |
| 39 | Summary enum naming | `SummaryContentType` | New enum | Avoids collision with existing `ContentType` used by Annotation. |
| 40 | Facet dimensions | (A) 4 dims (B) Fewer (C) More | A | Style, compression, audience, content_focus cover independent axes. Extensible by adding new fragment folders. |

---

## 18. Sources Consulted

### Existing Codebase

| Area | Files | Key Findings |
|------|-------|-------------|
| Models | `backend/app/db/models.py` | BigInteger PKs, existing enums (BookStatus, SummaryStatus, ContentType, SourceType), polymorphic pattern on Annotation |
| Config | `backend/app/config.py` | SummarizationConfig has `default_detail_level`, `prompt_version` — both removed in V1.1 |
| Summarizer | `backend/app/services/summarizer/summarizer_service.py` | Map-reduce flow, Jinja2 FileSystemLoader, cumulative context |
| Prompts | `backend/app/services/summarizer/prompts/*.txt` | 7 template files; section/book/quick/eval/image/structure/references |
| CLI | `backend/app/cli/commands/add.py`, `show.py`, `summarize.py` | Current display logic, async_command pattern, get_services() DI |
| Repositories | `backend/app/db/repositories/*.py` | selectinload() patterns, thin query builders |
| Tests | `backend/tests/` | pytest + pytest-asyncio, fixtures pattern, clean_db fixture |

### External Research

| Topic | Sources |
|-------|---------|
| Summarization architectures | NexusSum (ACL 2025), Context-Aware Hierarchical Merging (ACL 2025), BooookScore (ICLR 2024) |
| Chain of Density | Adams et al. (arXiv 2309.04269) |
| Self-critique | SCRPO (arXiv 2512.05387) |
| Quality evaluation | DeepEval Summarization, BooookScore, CMU SEI guide |
| Composable prompts | PromptLayer Jinja2, mdx-prompt, arXiv 2504.02052 |
| Prompt engineering | Microsoft ISE, Galileo strategies |
| Preset UX | HandBrake presets, Lightroom preset model |
| Chunking | Weaviate, Pinecone, Firecrawl (2026) |
