# Book Companion V1.1 — Enhancement Requirements

**Date:** 2026-04-02
**Status:** Draft
**Scope:** Enhancements to V1 based on usage observations — CLI UX, summarization flexibility, extraction quality, and data model improvements.
**Relationship:** Addendum to [V1 Requirements](2026-04-01_book_companion_v1_requirements.md). Prompt quality optimization (surface-level summaries, missing key concepts) is a separate workstream.

---

## Table of Contents

1. [Glossary](#1-glossary)
2. [Motivation](#2-motivation)
3. [Not in Scope](#3-not-in-scope)
4. [Feature Areas](#4-feature-areas)
   - [4.1 Summary Presets & Faceted Prompt Composition](#41-summary-presets--faceted-prompt-composition)
   - [4.2 Summary Log (Append-Only)](#42-summary-log-append-only)
   - [4.3 Section Merge, Split & Reorder](#43-section-merge-split--reorder)
   - [4.4 Enhanced CLI Display & Help](#44-enhanced-cli-display--help)
   - [4.5 Extraction Quality Validation](#45-extraction-quality-validation)
   - [4.6 Summary Comparison & Quality Visibility](#46-summary-comparison--quality-visibility)
   - [4.7 Clean Migration from V1](#47-clean-migration-from-v1)
5. [End-to-End User Journey](#5-end-to-end-user-journey)
6. [Data Model Changes](#6-data-model-changes)
7. [CLI Command Summary](#7-cli-command-summary)
8. [Industry Research & Recommendations](#8-industry-research--recommendations)
9. [Decision Log](#9-decision-log)
10. [Sources Consulted](#10-sources-consulted)

---

## 1. Glossary

Terms introduced in V1.1 that build on V1 concepts:

| Term | Definition |
|------|-----------|
| **Preset** | A named, saved combination of facet values (stored as a YAML file). Analogous to Handbrake encoding presets or Lightroom photo presets. Applies to the `summarize` command. |
| **Facet** | One independent dimension of summarization configuration. V1.1 defines four facets: output style, compression, audience, and content focus. Each facet has a set of allowed values, each backed by a Jinja2 fragment file. |
| **Fragment** | A short (2-4 sentence) Jinja2 template file that provides instructions for one facet value. Fragments are composed into a full prompt by the base template via `{% include %}`. |
| **Summary log** | The append-only `summary` database table. Every generated summary is a row; rows are never overwritten or deleted (except on book deletion). |
| **Default summary** | The active summary for a section or book, pointed to by `default_summary_id` FK. Users can change the default via `summary set-default`. |
| **Content type** | A polymorphic enum (`section`, `book`, `concept`, `annotation`) identifying what kind of content a summary row describes. Used with `content_id` to form a polymorphic association. |
| **Derived from** | A JSON field on `BookSection` storing the IDs of original sections that were merged or split to create it. Lightweight provenance without full event sourcing. |

---

## 2. Motivation

After using Book Companion V1 with several books (including "Understanding Michael Porter"), the following pain points emerged:

- **Surface-level summaries:** The book-level summary produced just 3-4 lines per chapter, missing key concepts like positioning maps (Chapter 4). Root cause analysis points to double-compression (book summary compresses already-compressed section summaries) and aggressive cumulative context truncation (500 chars/section). Prompt optimization is a separate workstream; this document focuses on the structural changes needed to support better summarization.
- **No summarization flexibility:** Single summary per section, single prompt template, no way to experiment with different styles or compare outputs.
- **Opaque extraction quality:** No visibility into whether parsed content is complete or truncated. No character counts, no quality warnings during structure detection.
- **Rigid section structure:** No way to merge small/truncated sections, split oversized ones, or remove non-content sections (copyright pages, indices) after parsing.
- **CLI display gaps:** `show` command missing section IDs (needed for CLI commands), no character counts, no compression ratios, flat ordering without hierarchy visualization.
- **Sparse help text:** No use-case examples showing common workflows like reading a section summary or re-summarizing with a different preset.

---

## 3. Not in Scope

The following are explicitly out of scope for V1.1:

- **Prompt quality optimization:** Fixing the surface-level summary issue (e.g., improving concept density, addressing the Understanding Michael Porter observations) is a separate workstream. This doc provides the structural foundation (presets, facets, summary log) that the prompt work will build on.
- **Web UI / REST API changes:** V1.1 is CLI-only. The web UI and API will be updated in a future phase to expose presets, summary comparison, and section editing.
- **New eval assertions:** The existing 16-assertion battery is retained. Adding new assertions (e.g., BooookScore coherence checks, DeepEval coverage metrics) is future work.
- **Multi-language support:** English-only, same as V1.
- **Authentication / multi-user:** Single-user, same as V1.
- **Annotation or tagging changes:** The annotation and tag systems are unaffected by V1.1.
- **Export format changes:** Existing export functionality is unaffected; it reads from `default_summary_id` instead of `summary_md` but output formats remain the same.

---

## 4. Feature Areas

### 4.1 Summary Presets & Faceted Prompt Composition

Replace the monolithic prompt template system with composable faceted fragments. Each summarization dimension is an independent Jinja2 fragment file. Presets are YAML files that name a tested combination of facet values.

#### Facet Dimensions

| Dimension | Values | What It Controls |
|-----------|--------|-----------------|
| **Output style** | `bullet_points`, `narrative`, `podcast_dialogue`, `cornell_notes`, `mind_map_outline`, `tweet_thread` | Format and structure of the output |
| **Compression** | `brief` (10%), `standard` (20%), `detailed` (30%) | Target summary length relative to source |
| **Audience** | `practitioner`, `academic`, `executive` | What content is prioritized and what is omitted |
| **Content focus** | `key_concepts`, `frameworks_examples`, `full_coverage` | Depth and breadth of concept coverage |

#### File System Layout

```
backend/app/services/summarizer/prompts/
  base/
    summarize_section.txt          # Skeleton template, assembles fragments via {% include %}
    summarize_book.txt
  fragments/
    style/
      bullet_points.txt
      narrative.txt
      podcast_dialogue.txt
      cornell_notes.txt
      mind_map_outline.txt
      tweet_thread.txt             # 280-char tweet-sized takeaways as a thread
    audience/
      practitioner.txt             # Actionable techniques, frameworks, how-to
      academic.txt                 # Evidence chains, methodology, counterarguments
      executive.txt                # Decisions, bottom-line, key takeaways
    compression/
      brief.txt                    # ~10% of source length
      standard.txt                 # ~20% of source length
      detailed.txt                 # ~30% of source length
    content_focus/
      key_concepts.txt             # Core thesis and 3-5 key claims only
      frameworks_examples.txt      # Named frameworks, models, supporting examples
      full_coverage.txt            # Comprehensive with quotes, evidence, nuance
  presets/
    practitioner_bullets.yaml      # system: true
    academic_detailed.yaml         # system: true
    executive_brief.yaml           # system: true
    study_guide.yaml               # system: true
    tweet_thread.yaml              # system: true
```

#### Preset YAML Format

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

- System presets are marked `system: true` and protected from deletion via CLI.
- User-created presets are stored in the same `presets/` directory with `system: false` (or omitted). Version controlled alongside the project.

#### Base Template Composition

The base template assembles fragments in a canonical order (Role → Audience → Content Focus → Style → Compression). This ordering is based on research showing it produces the most consistent output quality.

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

#### CLI Interface

```bash
# Use a named preset
bookcompanion summarize <book_id> --preset practitioner_bullets

# Override one facet from a preset
bookcompanion summarize <book_id> --preset practitioner_bullets --compression detailed

# Pick facets manually (no preset)
bookcompanion summarize <book_id> --style narrative --audience academic --compression detailed

# Single section with preset
bookcompanion summarize <book_id> <section_id> --preset tweet_thread

# Preset management
bookcompanion preset list                    # Show available presets with descriptions
bookcompanion preset show <name>             # Show facet values for a preset
bookcompanion preset create <name>           # Interactive creation of new preset
```

If no preset or facets specified, the system default preset is used (configurable via `bookcompanion config set summarization.default_preset <name>`).

#### Fragment Design Constraints

- Each fragment should be **2-4 sentences** — short and non-contradictory to minimize prompt interference (see [Microsoft ISE research](#8-industry-research--recommendations) on stacking constraints).
- Fragments must be self-contained — no references to other fragments.
- Test the shipped system presets (5 presets) as known-good combinations. Arbitrary facet combinations are supported but not guaranteed tested.

#### Preset Validation & Error Handling

- On `summarize`, preset YAML is loaded and each facet value is checked against existing fragment files. If a fragment file is missing (e.g., `style: haiku` but no `fragments/style/haiku.txt`), fail fast with: `Error: Fragment not found: fragments/style/haiku.txt. Available styles: bullet_points, narrative, ...`
- If `--preset` names a nonexistent preset: `Error: Preset "foo" not found. Run "bookcompanion preset list" to see available presets.`
- If both `--preset` and individual facet flags are provided, the explicit flags override the preset values for those facets.
- If neither `--preset` nor any facet flags are provided, use `summarization.default_preset` from config.

#### Quick Summary Interaction

The `quick_summary` code path (single-pass, `quick_summary_v1.txt`) remains **independent** of the preset system. It is a fundamentally different approach (full-book single pass vs. map-reduce per section). The `--quick` flag on `add` continues to work as in V1. Presets apply only to the `summarize` command's map-reduce pipeline.

#### Config Changes

| Setting | Old (V1) | New (V1.1) |
|---------|----------|------------|
| `summarization.default_detail_level` | `"standard"` | **Removed.** Replaced by `compression` facet in default preset. |
| `summarization.prompt_version` | `"v1"` | **Removed.** Prompt templates are now faceted fragments; versioning is per-fragment file. |
| `summarization.default_preset` | — | **New.** Name of the default preset (e.g., `"practitioner_bullets"`). |

---

### 4.2 Summary Log (Append-Only)

New `summary` table that stores every generated summary as an immutable log entry with full provenance. Replaces the current single `BookSection.summary_md` field.

#### Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | BigInteger, PK | Auto-increment |
| `content_type` | Enum: `section`, `book`, `concept`, `annotation` | What was summarized (extensible) |
| `content_id` | BigInteger | ID of the summarized content |
| `book_id` | BigInteger, FK → `Book.id` | Parent book — enables efficient "all summaries for this book" queries without joining through `BookSection` |
| `preset_name` | String, nullable | Which preset was used, if any |
| `facets_used` | JSON | `{style, audience, compression, content_focus}` — exact values |
| `prompt_text_sent` | Text | Fully rendered prompt (frozen snapshot) |
| `model_used` | String | e.g., `"opus"`, `"sonnet"` |
| `input_tokens` | Integer, nullable | LLM input token count |
| `output_tokens` | Integer, nullable | LLM output token count |
| `input_char_count` | Integer | Character count of source content |
| `summary_char_count` | Integer | Character count of generated summary |
| `summary_md` | Text | The generated summary markdown |
| `eval_json` | JSON, nullable | Evaluation assertion results |
| `latency_ms` | Integer, nullable | Generation time in milliseconds |
| `created_at` | DateTime with TZ | Immutable timestamp |

#### Relationships

- `Book.default_summary_id` → FK to `summary.id` (nullable, SET NULL on delete). The "active" book-level summary.
- `BookSection.default_summary_id` → FK to `summary.id` (nullable, SET NULL on delete). The "active" section summary.
- `summary.book_id` → FK to `Book.id` (CASCADE on delete). When a book is deleted, all its summary log entries are deleted.
- `summary.preset_name` is a string reference, not a FK — presets are YAML files, not DB rows. The log is self-contained regardless of whether the preset still exists.

#### Behavior

- Every summarization run **appends** rows. Never overwrites.
- The most recent summary is auto-set as default unless the user has manually overridden.
- The log is self-contained: `prompt_text_sent` + `facets_used` + `model_used` fully capture what produced the summary, independent of any preset file.
- **Concurrent runs:** If a user starts a second `summarize` run while one is in progress, the CLI checks for active `ProcessingJob` rows and warns: `A summarization is already running for this book (PID: 1234). Run anyway? [y/N]`. Both runs append independently to the log; the last to complete sets `default_summary_id`.
- **Storage:** `prompt_text_sent` can be 50-100KB+ per row. For a personal library of ~100 books × 20 sections × 3 summaries = ~6,000 rows × ~75KB = ~450MB. Acceptable for a personal PostgreSQL instance. No compression or truncation needed.

#### Eval Assertions and Presets

Eval assertions that depend on output format must adapt to the facets used:
- `reasonable_length`: Target compression range is read from `facets_used.compression`, not hardcoded. A `tweet_thread` summary at `brief` compression is expected to be much shorter than a `narrative` at `detailed`.
- `has_key_concepts`: For `content_focus=key_concepts`, expect fewer but more focused concepts. For `full_coverage`, expect comprehensive concept lists.
- Other assertions (faithfulness, coherence, specificity) apply universally regardless of facets.

#### Indexes

- `(content_type, content_id)` — query all summaries for a given section/book
- `book_id` — query all summaries across a book
- `created_at` — chronological ordering

---

### 4.3 Section Merge, Split & Reorder

Allow users to restructure book sections both during initial parsing (pre-save in the `add` flow) and after the book is stored (post-save editing).

#### During `add` (Pre-Save)

After structure detection and quality analysis (see [4.5](#45-extraction-quality-validation)), before accepting, the user enters an interactive editing loop:

**Operations:**
- **Merge:** `merge 3,4,5 "Combined Chapter Title"` — combine sections into one, concatenating content in order
- **Split:** `split 3 --at-heading` (auto-detect sub-headings) or `split 3 --at-char 5000` (manual split point). If `--at-heading` finds no sub-headings: `No sub-headings detected in section 3. Use --at-char <position> to split manually.`
- **Reorder:** `move 5 --after 2`
- **Delete:** `delete 7,8` — remove unwanted sections (copyright, indices, etc.)

**Flow:**
1. Display structure with quality metrics and suggested actions (see [4.5](#45-extraction-quality-validation))
2. Prompt: `Apply suggested actions? [Y/n/customize]`
3. After applying (or skipping) suggestions, enter interactive loop:
   ```
   Edit sections> merge 3,4 "Combined Chapter"
   ✓ Merged sections 3-4 into "Combined Chapter"

   [Updated structure displayed]

   Edit sections> done
   ✓ Structure accepted. 7 sections will be saved.
   ```
4. Commands available in the loop: `merge`, `split`, `move`, `delete`, `undo` (reverts the single last operation — one level only), `show` (redisplay structure), `done` (accept and exit)
5. `Ctrl+C` or `done` exits the loop

Since this is pre-save, no DB cleanup is needed — operations modify in-memory section list.

#### Post-Save Editing

```bash
bookcompanion edit sections <book_id>
```

Same operations as pre-save, but with downstream impact:

- Merged/split sections are **new sections** with `default_summary_id = NULL`
- New sections store `derived_from` JSON field with original section IDs for provenance (e.g., `[3, 4, 5]`)
- Original sections are **hard deleted**. Their entries in the `summary` log table remain (orphaned `content_id` but queryable for history).
- All sections get `order_index` re-indexed after the operation.
- Book-level `default_summary_id` is **cleared** (set to NULL) since it depends on section summaries.

**Post-edit prompt for re-summarization:**
```
2 sections modified. Would you like to resummarize affected sections now? [Y/n]
```
- **Yes (default):** Runs summarization on new/modified sections using the book's last-used preset (or system default). After section summaries complete, regenerates the book-level summary.
- **No:** Sections stay with `default_summary_id = NULL`. The `show` command displays these as "Pending summary" as a visual reminder.

---

### 4.4 Enhanced CLI Display & Help

#### `show` Command Improvements

Add Section ID, Characters, Compression ratio, and Eval columns. Title column uses depth-based indentation for hierarchy; all other columns are flat-aligned.

```
#   ID   Title                        Status     Chars    Compression   Eval    Images
1   12   Introduction                 Completed  14,500   18.2%         15/16   —
2   13     What Is Strategy?          Completed  36,200   21.5%         14/16   2/3
3   14     Five Forces Framework      Completed  24,100   19.8%         16/16   1/2
4   15     Strategic Positioning       Pending    27,300   —             —       3/4
5   16   Trade-offs                   Completed  33,800   22.1%         —       —
```

- **`#`**: Flat integer index (1, 2, 3...) — sequential, no hierarchical numbering
- **`ID`**: Database section ID — required for CLI commands (`summarize <book_id> <section_id>`)
- **`Title`**: Indented by `depth * 2 spaces` to show hierarchy
- **`Status`**: Derived, not stored. `Completed` = `default_summary_id` is non-null. `Pending` = `default_summary_id` is NULL. `Running` / `Failed` = read from active `ProcessingJob` for this section. The old `SummaryStatus` enum on `BookSection` is dropped in V1.1.
- **`Chars`**: Content character count, formatted with commas
- **`Compression`**: `summary_char_count / input_char_count * 100` as percentage. Shows `—` when no summary exists.
- **`Eval`**: Pass/total assertion count (e.g., `14/16`). Shows `—` when no eval run.
- **`Images`**: `captioned/total` or `—`

#### `add` Command — Structure Detection Display

Show character count and estimated token count per section. Inline quality warnings.

```
Detected structure (8 sections):
  1. Introduction                    14,500 chars  ~3,200 tokens
  2. What Is Strategy?               36,200 chars  ~8,100 tokens
  3.   Five Forces Framework         24,100 chars  ~5,400 tokens
  4. Trade-offs                         120 chars   ~30 tokens   ⚠ possibly truncated
  5. Copyright Notice                    0 chars    ~0 tokens    ✗ empty section
  6. About the Author                  450 chars   ~100 tokens   ⚠ non-content

Suggested actions:
  • Delete sections 5, 6 — detected as non-content (copyright, author bio)
  • Merge section 4 into section 2 — section 4 appears truncated (120 chars)

Apply suggested actions? [Y/n/customize]
```

Numbering is flat (1, 2, 3...) with title indentation showing hierarchy — consistent with the `show` command.

#### Help Text with Use-Case Examples

`bookcompanion --help` includes a "Common Workflows" section:

```
Common Workflows:
  Read a section summary      bookcompanion summary <book_id> <section_id>
  Compare with original       bookcompanion read <book_id> <section_id> --with-summary
  Search across library       bookcompanion search "competitive advantage"
  Re-summarize with preset    bookcompanion summarize <book_id> --preset academic_detailed
  Compare two summaries       bookcompanion summary compare <id1> <id2>
  Export book summary          bookcompanion export book <book_id> --format markdown
  Edit section structure      bookcompanion edit sections <book_id>
```

Each subcommand's `--help` output includes 2-3 example invocations showing common usage patterns.

---

### 4.5 Extraction Quality Validation

Deterministic heuristics (no LLM calls) to assess content extraction quality. Runs automatically during parsing. Surfaces warnings during `add` and `show`. Acts as a soft gate before summarization.

#### Quality Checks

| Check | Detection Rule | Severity | Suggested Action |
|-------|---------------|----------|-----------------|
| Empty section | 0 characters | Error | Delete |
| Short section | < 200 characters | Warning | Merge into adjacent section |
| Non-content section | Title matches regex: `copyright\|about the author\|also by\|acknowledgments?\|dedication\|table of contents\|index\|bibliography` | Warning | Delete |
| Truncated section | < 200 chars AND adjacent section at same depth has 5x+ more chars | Warning | Merge into adjacent section |
| Tiny fragment | < 500 chars AND depth > 0 (not top-level) | Warning | Merge into parent |
| Oversized section | > 100,000 chars (well above mean) | Info | Suggest split at detected sub-headings |
| Encoding issues | High ratio of U+FFFD replacement chars or unexpected non-ASCII sequences | Warning | Flag for review |
| Repeated content | > 80% text overlap with another section (character n-gram similarity) | Warning | Delete the shorter duplicate |
| Image-heavy | Image-to-text ratio exceeds 3:1 | Info | Flag for review |
| Page number artifacts | Isolated page numbers between paragraphs (regex) | Info | Flag for review |

#### Suggested Actions Flow (During `add`)

After quality checks run, the CLI presents suggested actions deterministically:

```
Suggested actions:
  • Delete sections 4, 5, 6 — detected as non-content (copyright, author bio, book list)
  • Merge section 3 into section 2 — section 3 appears truncated (85 chars)

Apply suggested actions? [Y/n/customize]
```

- **Yes (default):** Apply all suggestions automatically
- **No:** Skip suggestions, accept structure as-is
- **Customize:** Enter the interactive merge/split/delete loop (see [4.3](#43-section-merge-split--reorder)) with suggestions pre-populated as a starting point

#### Soft Gate on Summarization

When running `summarize`, sections with unresolved warnings are flagged:

```
⚠ Section #3 "Appendix A" has quality warnings (85 chars — possibly truncated).
Skip this section? [Y/n/force-all]
```

- `--force` flag bypasses all quality gates.
- Sections with errors (empty, 0 chars) are auto-skipped with a message.

#### Quality Summary in `show`

A one-line quality summary above the section table:

```
Quality: 7/8 sections OK. 1 warning (section #3: possibly truncated)
```

---

### 4.6 Summary Comparison & Quality Visibility

CLI commands for browsing, comparing, and managing multiple summaries per section.

#### Commands

**List summaries:**
```bash
bookcompanion summary list <book_id> [section_id]
```

Without `section_id`, shows a per-section summary count overview:
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

With `section_id`, shows detailed summary list for that section:
```
Section #2 "What Is Strategy?" — 3 summaries:

  ID   Preset                  Model    Compression   Chars    Eval     Created
  42   practitioner_bullets    opus     21.5%         7,800    14/16    2026-04-01 10:30
  58   academic_detailed       sonnet   31.2%         11,300   12/16    2026-04-01 14:15
  61   tweet_thread            sonnet   4.8%          1,740    —        2026-04-02 09:00

  ★ Default: #42
```

**Compare two summaries:**
```bash
bookcompanion summary compare <id1> <id2>
```
- Shows both summaries with metadata header (preset, model, compression, eval score)
- Concept diff is **deterministic**: extract bold/header terms and named entities via simple regex (not LLM-based), show terms present in one but missing from the other
- Uses terminal columns for side-by-side if width allows, sequential otherwise

**Set default summary:**
```bash
bookcompanion summary set-default <summary_id>
```
Changes which summary is the active default for a section or book. Validates that the summary's `content_type` + `content_id` matches the target section/book. Triggers search index re-embedding for `source_type=SECTION_SUMMARY` automatically.

**Show specific summary with provenance:**
```bash
bookcompanion summary show <summary_id>
```
Displays the summary markdown along with full metadata: preset, facets used, model, input/output tokens, character counts, eval results, timestamp.

---

### 4.7 Clean Migration from V1

No backward compatibility layer. Drop old columns, create new tables, re-summarize from scratch.

#### Database Migration Steps

1. **Create** `summary` table (schema per [4.2](#42-summary-log-append-only))
2. **Add** `default_summary_id` FK column to `Book` (nullable, FK → `summary.id`)
3. **Add** `default_summary_id` FK column to `BookSection` (nullable, FK → `summary.id`)
4. **Add** `derived_from` JSON column to `BookSection` (nullable, for merge/split provenance)
5. **Drop** columns from `BookSection`: `summary_md`, `summary_status`, `summary_version`, `summary_model`, `summary_eval`, `user_edited`
6. **Drop** columns from `Book`: `overall_summary`, `overall_summary_eval`
7. **Add** `summary_id` FK column to `EvalTrace` (nullable, FK → `summary.id`)
8. **Truncate** `eval_trace` table

#### Prompt System Migration

- Delete monolithic V1 templates (`summarize_section_v1.txt`, `summarize_book_v1.txt`)
- Create faceted base templates + fragment files (per [4.1](#41-summary-presets--faceted-prompt-composition))
- Create 5 system preset YAML files

#### User Impact

- All existing books retain their parsed structure, sections, and content
- All existing summaries are deleted — users re-summarize using the new preset system
- Eval traces are cleared — re-run evals after re-summarization

#### Downstream Model Updates

- **`BookStatus` enum:** The `SUMMARIZING` and `COMPLETED` states remain but their meaning updates. `COMPLETED` = all sections have a non-null `default_summary_id` AND book has a non-null `default_summary_id`. `SUMMARIZING` = at least one section is currently being processed.
- **`SummaryStatus` enum:** Dropped. Section status is derived from `default_summary_id` (NULL = pending, non-null = completed). Running/failed states are tracked via `ProcessingJob`.
- **`SearchIndex` impact:** When a section's default summary changes (via `set-default` or re-summarization), search embeddings for `source_type=SECTION_SUMMARY` must be regenerated for that section. The `summarize` command should trigger re-embedding automatically.
- **`EvalTrace` table:** Add `summary_id` FK column (nullable, FK → `summary.id`). New eval runs link to the specific summary row. Existing traces are truncated during migration. The `eval_json` on the `summary` log provides inline eval results; `EvalTrace` provides the detailed per-assertion audit trail.
- **`--force` flag with presets:** `--force` means "re-summarize all sections regardless of whether they already have a summary with this or any preset." It does not delete existing summary log entries — it appends new ones and updates `default_summary_id`.

---

## 5. End-to-End User Journey

A complete workflow showing how the V1.1 features compose, from adding a new book to choosing the best summary:

```
# 1. Add a new book — quality checks and section editing happen here
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
  • Delete sections 9, 10, 11, 12 — detected as non-content

Apply suggested actions? [Y/n/customize] Y
✓ Deleted 4 sections.

  [Updated structure: 8 sections]

Edit sections> done
✓ Structure accepted. Book saved (ID: 3). 8 sections parsed and stored.

# 2. Check the parsed book
$ bookcompanion show 3

  #  ID  Title                        Status   Chars    Compression  Eval   Images
  1  20  Introduction                 Pending  14,500   —            —      —
  2  21    What Is Competition?       Pending  36,200   —            —      2/3
  3  22    The Five Forces Framework  Pending  24,100   —            —      1/2
  4  23  What Is Strategy?            Pending  28,900   —            —      —
  5  24    Creating Value             Pending  18,300   —            —      —
  6  25    Trade-offs                 Pending  22,700   —            —      1/1
  7  26    Fit                        Pending  19,800   —            —      —
  8  27  Continuity                   Pending   8,200   —            —      —

# 3. Summarize with a preset
$ bookcompanion summarize 3 --preset practitioner_bullets

Summarizing 8 sections with preset "practitioner_bullets"...
  [1/8] Introduction                  ✓  (12s, 18.2%)
  [2/8] What Is Competition?          ✓  (28s, 21.5%)
  ...
  [8/8] Continuity                    ✓  (8s, 19.1%)
Generating book-level summary...     ✓  (15s)
✓ Done. 8 section summaries + 1 book summary generated.

# 4. Read a section summary
$ bookcompanion summary 3 22

[Displays the practitioner-focused bullet point summary of "The Five Forces Framework"]

# 5. Not satisfied — try a different preset for one section
$ bookcompanion summarize 3 22 --preset academic_detailed

Summarizing section #3 "The Five Forces Framework" with preset "academic_detailed"...
  ✓ (45s, 31.2%)

# 6. Compare the two summaries
$ bookcompanion summary list 3 22

Section #3 "The Five Forces Framework" — 2 summaries:

  ID  Preset                Model   Compression  Chars   Eval    Created
  42  practitioner_bullets  sonnet  21.5%        5,200   14/16   2026-04-02 10:30
  58  academic_detailed     opus    31.2%        7,500   15/16   2026-04-02 10:45

  ★ Default: #58

$ bookcompanion summary compare 42 58

[Side-by-side comparison with concept diff showing academic version
 includes "positioning maps", "activity systems" missing from practitioner version]

# 7. Set the academic version as default for this section
$ bookcompanion summary set-default 58
✓ Default summary for section #3 updated to #58.

# 8. Search across the library
$ bookcompanion search "five forces competitive advantage"

[Results grouped by book, searching across summaries and original content]
```

---

## 6. Data Model Changes

### New Table: `summary`

See [4.2](#42-summary-log-append-only) for full schema.

### Modified: `Book`

| Change | Field | Type |
|--------|-------|------|
| Add | `default_summary_id` | BigInteger, FK → `summary.id`, nullable |
| Drop | `overall_summary` | — |
| Drop | `overall_summary_eval` | — |

### Modified: `BookSection`

| Change | Field | Type |
|--------|-------|------|
| Add | `default_summary_id` | BigInteger, FK → `summary.id`, nullable |
| Add | `derived_from` | JSON, nullable |
| Drop | `summary_md` | — |
| Drop | `summary_status` | — |
| Drop | `summary_version` | — |
| Drop | `summary_model` | — |
| Drop | `summary_eval` | — |
| Drop | `user_edited` | — |

### Modified: `EvalTrace`

| Change | Field | Type |
|--------|-------|------|
| Add | `summary_id` | BigInteger, FK → `summary.id`, nullable |

### ER Diagram

```
summary_preset (YAML files, not a DB table)
  - name, description, system flag
  - facets: {style, audience, compression, content_focus}

summary (DB table, append-only)
┌────────────────────────────┐
│ id (PK)                    │
│ content_type (enum)        │
│ content_id (BigInt)        │
│ book_id (FK → Book.id)     │
│ preset_name (nullable)     │
│ facets_used (JSON)         │
│ prompt_text_sent (Text)    │
│ model_used (String)        │
│ input_tokens (Int)         │
│ output_tokens (Int)        │
│ input_char_count (Int)     │
│ summary_char_count (Int)   │
│ summary_md (Text)          │
│ eval_json (JSON)           │
│ latency_ms (Int)           │
│ created_at (DateTime)      │
└────────────────────────────┘
        ▲              ▲
        │              │
  default_summary_id   default_summary_id
        │              │
 ┌──────────┐   ┌──────────────┐
 │   Book   │   │ BookSection  │
 └──────────┘   │ + derived_from│
                └──────────────┘

eval_trace (modified)
┌────────────────────────────┐
│ ...existing fields...      │
│ + summary_id (FK, nullable)│
└────────────────────────────┘
```

---

## 7. CLI Command Summary

### New Commands

| Command | Description |
|---------|-------------|
| `bookcompanion preset list` | List available presets with descriptions |
| `bookcompanion preset show <name>` | Show facet values for a preset |
| `bookcompanion preset create <name>` | Interactive creation: prompts for description, then each facet with available values (e.g., `Style [bullet_points/narrative/...]:`) defaulting to system default. Saves YAML to `prompts/presets/<name>.yaml`. |
| `bookcompanion preset delete <name>` | Delete a user-created preset. System presets (`system: true`) are protected: `Error: Cannot delete system preset "practitioner_bullets".` |
| `bookcompanion summary list <book_id> [section_id]` | List all summaries for a book or section |
| `bookcompanion summary compare <id1> <id2>` | Side-by-side comparison of two summaries |
| `bookcompanion summary set-default <summary_id>` | Set the active default summary |
| `bookcompanion summary show <summary_id>` | Show a specific summary with full provenance |
| `bookcompanion edit sections <book_id>` | Interactive section merge/split/reorder/delete |

### Modified Commands

| Command | Changes |
|---------|---------|
| `bookcompanion summarize` | New flags: `--preset`, `--style`, `--audience`, `--compression`, `--content-focus`. Removes `--detail` (replaced by `--compression`). Warns on concurrent runs. |
| `bookcompanion summary <book_id> [section_id]` | Now reads from `summary` table via `default_summary_id` instead of `BookSection.summary_md`. |
| `bookcompanion show` | New columns: ID, Chars, Compression, Eval. Title indentation for hierarchy. Quality summary line. |
| `bookcompanion add` | Structure detection shows chars + tokens per section, inline quality warnings, suggested actions, interactive editing loop. |
| `bookcompanion --help` | Adds "Common Workflows" section with use-case examples. |
| All subcommands `--help` | Adds 2-3 example invocations. |

---

## 8. Industry Research & Recommendations

### Summarization Architecture

| Pattern | Description | Applicability |
|---------|-------------|--------------|
| **Map-Reduce with cumulative context** | Current approach. Summarize sections independently, then reduce to book summary. | Already implemented in V1. |
| **Context-Aware Hierarchical Merging** (ACL 2025) | Augment the reduce step with relevant source passages, not just section summaries. Reduces hallucination amplification. | Recommended for the book-level summary step. Pass key source excerpts alongside section summaries. |
| **Chain of Density** (Adams et al., 2023) | Iterative densification: generate summary, identify missing entities, rewrite at same length incorporating them. Repeat 2-3 times. | Recommended as optional post-processing, especially for brief compression where density matters most. |
| **Self-Critique Refinement** (SCRPO, 2025) | LLM critiques its own summary for faithfulness gaps, then refines. Single critique-refine pass significantly reduces surface-level output. | Recommended for the prompt optimization workstream (separate from this doc). |
| **NexusSum** (ACL 2025) | Multi-agent hierarchical pipeline, up to 30% BERTScore improvement on BookSum. | Aspirational. Current single-agent approach is simpler; adopt patterns selectively. |

### Summary Quality Metrics

| Framework | What It Measures | Recommendation |
|-----------|-----------------|----------------|
| **DeepEval Summarization Metric** | Coverage (can questions from source be answered by summary?) + Alignment (are summary claims supported by source?). Score = min(both). | Consider adopting as a complement to existing 16-assertion battery. |
| **BooookScore** (ICLR 2024) | Coherence errors in book-length summaries. 8 error types including causal omissions and salience errors. | Useful taxonomy for extending eval assertions. |

### Composable Prompt Systems

| Pattern | Source | Adoption |
|---------|--------|----------|
| **Faceted fragments + preset shortcuts** | Handbrake/Lightroom preset model, mdx-prompt, PromptLayer Jinja2 guidance | **Adopted** as the core architecture for [4.1](#41-summary-presets--faceted-prompt-composition). |
| **Canonical fragment ordering** | arXiv 2504.02052 — Role → Directive → Context → Examples → Output Format → Constraints | **Adopted** as: Role → Audience → Content Focus → Style → Compression. |
| **Prompt interference risk** | Microsoft ISE research on stacking constraints | **Mitigated** by keeping fragments short (2-4 sentences) and testing system presets. |

### Section Management

| Pattern | Source | Adoption |
|---------|--------|----------|
| **Dirty flags on mutation** | Standard DB pattern for cascading invalidation | **Adopted**: sections after merge/split have `default_summary_id = NULL`, prompting re-summarization. |
| **Lightweight provenance** | `derived_from` JSON field | **Adopted** on `BookSection` for merge/split traceability without full event sourcing overhead. |
| **Structure-aware chunking** | Jina AI, Pinecone, Weaviate RAG research | **Adopted**: use book's TOC/heading hierarchy as primary segmentation, semantic splitting only for oversized sections. |

---

## 9. Decision Log

| # | Decision | Options Considered | Choice | Rationale |
|---|----------|--------------------|--------|-----------|
| 1 | **Summary storage model** | (A) New `summary` table with polymorphic `content_type`+`content_id` (B) JSON array in existing `summary_md` field (C) Versioned append-only event log | A | Clean relational model. Polymorphic pattern already used in `Annotation` model. JSON array loses query power; event log is overkill for personal tool. |
| 2 | **Preset storage** | (A) YAML files in project repo (B) Database table (C) `~/.config/` directory | A | Version controlled with git, portable, visible alongside fragment files. DB table adds complexity without benefit until a web UI needs CRUD. `~/.config/` is machine-specific and invisible to version control. |
| 3 | **Prompt composition** | (A) Monolithic templates per combination (B) Composable Jinja2 fragments with presets (C) DSPy-style programmatic composition | B | 4 dimensions × multiple values = 135+ monolithic templates (unmaintainable). Jinja2 fragments match existing `FileSystemLoader` infrastructure. DSPy requires framework adoption. Handbrake/Lightroom "preset + override" pattern is proven UX. |
| 4 | **Preset FK in summary log** | (A) FK to preset DB table (B) Nullable string `preset_name` + self-contained `facets_used` JSON + `prompt_text_sent` | B | User explicitly doesn't want to maintain prompt version control. Summary log must be self-contained — the full rendered prompt is captured regardless of whether the preset still exists or has changed. |
| 5 | **Section merge/split timing** | (A) During `add` only (B) Post-save only (C) Both | C | Pre-save is zero-cost (no DB cleanup). Post-save is needed for corrections discovered after initial parsing. Both share the same interactive UI. |
| 6 | **Section mutation strategy** | (A) In-place mutation with `derived_from` provenance (B) Soft delete + versioned sections (C) Event sourcing | A | Hard delete originals, store `derived_from` on new sections for lightweight provenance. Soft deletes add query complexity; event sourcing is massive over-engineering for personal tool. Summary log entries for deleted sections remain as orphaned historical records. |
| 7 | **Extraction quality gate** | (A) Warn only (B) Soft gate with `--force` override (C) Hard gate blocking summarization | B | Soft gate balances safety with flexibility. Hard gate is frustrating when user knows content is intentionally short. Warn-only misses the chance to prevent wasted LLM spend on garbage input. |
| 8 | **Quality check approach** | (A) LLM-based analysis (B) Deterministic heuristics (C) Hybrid | B | Deterministic rules (regex, char counts, n-gram overlap) are fast, free, reproducible, and sufficient for the identified patterns. LLM analysis adds cost and latency for marginal benefit at this stage. |
| 9 | **V1 migration strategy** | (A) Backward-compatible migration preserving data (B) Clean migration, drop old data | B | Simpler migration code. No compatibility layer to maintain. Books retain parsed structure; only summaries (cheap to regenerate) are lost. |
| 10 | **Detail level abstraction** | (A) Keep as separate dimension (B) Merge into preset taxonomy (C) Rename to `compression` facet | C | `detail_level` (brief/standard/detailed) maps directly to compression ratio. Making it a facet alongside style/audience/content_focus is more consistent and composable. |
| 11 | **Profile naming** | (A) `summary_profile` (B) `prompt_profile` (C) `summary_preset` | C | "Preset" communicates the right mental model — a saved configuration to apply, like Handbrake/Lightroom presets. "Profile" is ambiguous (profile of the summary? of the user?). |
| 12 | **Facet dimensions** | (A) 4 dimensions: style, compression, audience, content_focus (B) Fewer (merge audience + content_focus) (C) More (add tone, length_unit, etc.) | A | 4 dimensions cover the independent axes users care about without combinatorial explosion. Audience and content_focus are distinct: audience determines framing/language, content_focus determines what to include/exclude. Additional dimensions like tone can be added later as new fragment folders. |
| 13 | **Preset file format** | (A) YAML (B) TOML (C) JSON | A | YAML is human-readable, supports comments, and is already familiar in the Python ecosystem. TOML is more strict but less readable for nested structures. JSON doesn't support comments. |
| 14 | **Summary compare approach** | (A) LLM-based concept diff (B) Deterministic regex extraction of bold terms/headers (C) Full semantic diff | B | Deterministic extraction is fast, free, and reproducible. LLM-based diff adds cost for a feature that should be instant. Semantic diff is overkill — users can read both summaries side-by-side. |
| 15 | **`book_id` on summary table** | (A) Only `content_type` + `content_id` (polymorphic) (B) Add denormalized `book_id` FK | B | Enables efficient "all summaries for this book" queries without joining through `BookSection`. Every summary belongs to a book regardless of content type. Small denormalization cost, large query benefit. |

---

## 10. Sources Consulted

### Existing Codebase (Explored)

| Area | Files | What Was Learned |
|------|-------|-----------------|
| CLI commands | `backend/app/cli/commands/*.py`, `main.py`, `deps.py` | Current command structure, `show` display logic, `add` parsing flow |
| Summarization | `backend/app/services/summarizer/summarizer_service.py` | Map-reduce flow, cumulative context building, compression targets, retry logic |
| Prompt templates | `backend/app/services/summarizer/prompts/*.txt` | All 7 template files (section, book, quick, eval×5, image caption, structure detection, references) |
| Data models | `backend/app/db/models.py` | All SQLAlchemy models, relationships, constraints, enums |
| Repositories | `backend/app/db/repositories/*.py` | Query patterns, eager loading, bulk operations |
| Config | `backend/app/config.py` | Settings structure, LLM/summarization/image config |
| V1 requirements | `docs/requirements/2026-04-01_book_companion_v1_requirements.md` | V1 scope, architecture decisions, deferred features |
| V1 spec | `docs/specs/2026-04-01_book_companion_v1_spec.md` | Detailed technical spec |
| Implementation plan | `docs/plans/2026-04-02_book_companion_v1_implementation.md` | 43-task plan |

### External Research (Web)

| Topic | Key Sources |
|-------|-------------|
| Summarization architectures | [NexusSum (ACL 2025)](https://arxiv.org/abs/2505.24575), [Context-Aware Hierarchical Merging (ACL 2025)](https://arxiv.org/abs/2502.00977), [BooookScore (ICLR 2024)](https://arxiv.org/abs/2310.00785), [CoTHSSum (2025)](https://link.springer.com/article/10.1007/s44443-025-00041-2) |
| Chain of Density prompting | [Adams et al. (arXiv 2309.04269)](https://arxiv.org/abs/2309.04269), [PromptHub guide](https://www.prompthub.us/blog/better-summarization-with-chain-of-density-prompting) |
| Self-critique & refinement | [SCRPO (arXiv 2512.05387)](https://arxiv.org/html/2512.05387v2) |
| Summary quality evaluation | [DeepEval Summarization Metric](https://deepeval.com/docs/metrics-summarization), [BooookScore GitHub](https://github.com/lilakk/BooookScore), [CMU SEI evaluation guide](https://www.sei.cmu.edu/blog/evaluating-llms-for-text-summarization-introduction/) |
| Composable prompt systems | [PromptLayer Jinja2](https://blog.promptlayer.com/prompt-templates-with-jinja2-2/), [mdx-prompt](https://github.com/edspencer/mdx-prompt), [SPEAR (CIDR 2026)](https://arxiv.org/html/2508.05012), [arXiv prompt taxonomy (2504.02052)](https://arxiv.org/html/2504.02052v2) |
| Prompt engineering for summarization | [Microsoft ISE](https://devblogs.microsoft.com/ise/gpt-summary-prompt-engineering/), [Galileo strategies](https://galileo.ai/blog/llm-summarization-strategies) |
| Existing summary products | [Shortform](https://www.shortform.com/), [Blinkist](https://www.blinkist.com/), [Readwise AI](https://learningaloud.com/blog/2025/02/12/ai-in-readwise/) |
| Chunking strategies | [Weaviate](https://weaviate.io/blog/chunking-strategies-for-rag), [Pinecone](https://www.pinecone.io/learn/chunking-strategies/), [Firecrawl (2026)](https://www.firecrawl.dev/blog/best-chunking-strategies-rag) |
| Preset UX patterns | [HandBrake presets](https://handbrake.fr/docs/en/latest/technical/official-presets.html), [Lightroom preset slider](https://www.lightroompresets.com/blogs/pretty-presets-blog/lightroom-preset-opacity-slider) |
| EPUB validation | [EPUBCheck](https://kb.daisy.org/publishing/docs/epub/validation/epubcheck.html), [Calibre validation](https://deepwiki.com/kiwidude68/calibre_plugins/3.2-epub-validation-checks) |
