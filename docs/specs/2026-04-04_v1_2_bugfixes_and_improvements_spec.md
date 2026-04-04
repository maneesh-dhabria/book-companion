# V1.2 Bugfixes & Improvements — Specification

**Date:** 2026-04-04
**Status:** Draft
**Requirements:** [`docs/requirements/2026-04-04_v1_2_bugfixes_and_improvements.md`](../requirements/2026-04-04_v1_2_bugfixes_and_improvements.md)
**V1.1 Spec:** [`docs/specs/2026-04-02_book_companion_v1.1_enhancements_spec.md`](2026-04-02_book_companion_v1.1_enhancements_spec.md)

---

## Table of Contents

1. [Decision Log](#decision-log)
2. [Overview](#overview)
3. [Fix 1: EPUB Parser — Auto-Merge Stub Sections](#fix-1-epub-parser--auto-merge-stub-sections)
4. [Fix 2: Markdown Output — Remove JSON Wrapping](#fix-2-markdown-output--remove-json-wrapping)
5. [Fix 3: Summarizer — Minimum Content Threshold](#fix-3-summarizer--minimum-content-threshold)
6. [Fix 4: Eval Hint & Eval Display Improvements](#fix-4-eval-hint--eval-display-improvements)
7. [Fix 5: XML/HTML Boilerplate Stripping](#fix-5-xmlhtml-boilerplate-stripping)
8. [Shared Utilities](#shared-utilities)
9. [Re-Parse Cascade Behavior](#re-parse-cascade-behavior)
10. [Database Migrations](#database-migrations)
11. [Configuration Changes](#configuration-changes)
12. [Verification Plan](#verification-plan)
13. [Deployment & Rollout](#deployment-rollout)
14. [Risk Mitigation](#risk-mitigation)
15. [Research Sources](#research-sources)

---

## Decision Log

| # | Decision | Options Considered | Choice | Rationale |
|---|----------|--------------------|--------|-----------|
| D1 | EPUB stub section handling | (A) Auto-merge during parse (B) Flag + user REPL (C) Auto-merge + show log | **A — Auto-merge** | Transparent to user. Produces clean sections from the start. Covers the 90% case where cover pages are noise. User can still edit sections post-parse if needed. |
| D2 | Summary output format | (A) Pure markdown (B) JSON via --json-schema (C) Markdown + optional regex metadata | **C — Markdown + regex metadata** | Markdown is the primary output for readability. Regex-based concept extraction (already in SummaryService.extract_concepts) provides structured metadata at zero LLM cost. No need for a second LLM call. |
| D3 | Minimum content threshold | (A) Fixed 200 chars (B) Fixed 500 chars (C) Configurable default 200 | **C — Configurable** | Default 200 chars matches existing quality check "short" threshold. Configurable via settings for edge cases (very short poetry, etc.). |
| D4 | Existing JSON summary cleanup | (A) Fix forward only (B) One-time script (C) Script + re-summarize | **A — Fix forward + re-summarize** | New summaries will be clean markdown. After deploy, re-summarize book 2 with `--force` to replace JSON-wrapped summaries. No migration script needed. |
| D5 | Metadata extraction approach | (A) Regex post-processing (B) Separate LLM call (C) Skip | **A — Regex** | SummaryService.extract_concepts() already extracts bold terms, headers, named entities via regex. Apply this automatically after summarization and store in eval_json or a new metadata field. Zero cost. |
| D6 | Re-parse behavior | (A) Delete + re-parse (B) Versioned parse | **A — Delete + re-parse** | Existing `--force` flag already deletes sections and re-parses. Simple and clean. Versioning adds schema complexity for no user benefit at this stage. |
| D7 | Eval after --skip-eval | (A) Hint text only (B) Sampled eval (C) Hint + --sample-eval flag | **A — Hint text** | Simple, no extra LLM cost. User explicitly wants a full eval pass on book 2 after fixes are deployed — that's a separate manual step, not an automated sampling feature. |
| D8 | Part divider handling | (A) Merge into next chapter (B) Keep as thin section (C) Delete | **A — Merge into next** | Part dividers (e.g., "Part One: What Is Competition?" with 115 chars) contain no summarizable content. Merging into the first chapter of that part preserves structural context without creating empty sections. |
| D9 | XML stripping approach | (A) Pre-markdownify (B) Post-markdownify | **A — Pre-markdownify** | Strip XML declarations and processing instructions from raw HTML before markdownify conversion. Cleaner pipeline — markdownify doesn't need to handle XML artifacts. |
| D10 | Merged section title | (A) Content-rich section title (B) Cover page title (C) Combined | **A — Content-rich title** | When a cover page merges into a content section, the content section's title is used. Most EPUBs repeat the title in both — if they differ, the content section title is more descriptive. |

---

## Overview

V1.2 addresses four bugs discovered during manual testing of V1.1 features on "Understanding Michael Porter" (book 2). The fixes span three layers: EPUB parsing, summarization output, and CLI UX.

**Scope:**
- EPUB parser auto-merge for stub/cover-page sections
- Markdown output replacing JSON-wrapped summaries
- Configurable minimum content threshold for summarization skip
- Eval hint after `--skip-eval`
- XML/HTML boilerplate stripping from parsed content

**Out of scope:**
- PDF parser improvements (different issue set)
- MOBI parser changes (delegates to EPUB parser, inherits fixes)
- New eval assertions or prompt improvements
- Schema versioning or parse history

---

## Fix 1: EPUB Parser — Auto-Merge Stub Sections

### 1.1 Problem

The EPUB parser (`app/services/parser/epub_parser.py`) creates one section per EPUB spine item. Many commercial EPUBs use separate HTML files for:
- Chapter cover pages (heading + decorative image, ~144 chars)
- Part divider pages ("Part One: ...", ~115 chars)
- Section separator pages

These produce sections with only XML boilerplate and no summarizable content.

### 1.2 Merge Algorithm

After initial section extraction (TOC walk or spine fallback), run a **forward-merge pass**:

```
for each section S[i] in order:
    text_content = strip_xml_and_images(S[i].content_md)
    if len(text_content) < MERGE_THRESHOLD (default 500 chars):
        if S[i+1] exists:
            S[i+1].content_md = S[i].content_md + "\n\n" + S[i+1].content_md
            # Title: use S[i+1].title (content-rich section)
            # Depth: use min(S[i].depth, S[i+1].depth)
            mark S[i] for removal
        else:
            # Last section is thin — merge into S[i-1] instead
            S[i-1].content_md = S[i-1].content_md + "\n\n" + S[i].content_md
            mark S[i] for removal
    remove marked sections
    reindex order_index 0-based
```

**`strip_xml_and_images(text)`** removes:
- XML declarations: `<?xml ... ?>`
- Image-only lines: `![image](...)` with no surrounding text
- Empty lines and whitespace

This gives the "real" text character count for the merge decision.

### 1.3 Image Handling During Merge

- **Book cover image**: Retained — already extracted and stored as `Book.cover_image` during initial parse. Not affected by section merging.
- **Section cover page images** (decorative chapter art, dividers): **Dropped** during merge. These are non-informational and add noise for the summarizer. The `ParsedImage` objects from stub sections are not carried into the merged section.
- **Content images** in the target section: Preserved — images in the content-rich section remain unchanged.

### 1.4 Merge Threshold

- Default: **500 chars** of text content (after stripping XML/images)
- Rationale: Cover pages are typically 100-150 chars. Short forewords/dedications are 200-400 chars. Real chapter content starts at 1000+ chars. 500 is a safe boundary.
- Not configurable (internal parser heuristic, not user-facing)
- **Distinct from** `min_section_chars` (Fix 3): The merge threshold operates during parsing to combine spine items. The min_section_chars threshold operates during summarization to skip sections. Both serve different purposes at different stages.

### 1.5 Part Divider Handling

Part dividers ("Part One: What Is Competition?") are merged into the first chapter of that part:
- "Part One" (115 chars) + "Chapter 1: Competition" (content) → Section titled "Chapter 1: Competition" with part divider text prepended

### 1.6 Post-Merge Cleanup

After merging, update derived fields on merged sections:
- `content_token_count`: Recalculate as `len(content_md) // 4`
- `order_index`: Reindex 0-based after removing merged stubs

### 1.7 Logging

When sections are merged, log at `info` level:
```
section_merged, source_title="Part One: What Is Competition?", target_title="1. Competition: The Right Mind-Set", reason="stub_section (115 chars text)"
```

### 1.8 Files Changed

| File | Change |
|------|--------|
| `app/services/parser/epub_parser.py` | Add `_merge_stub_sections()` method, call after `_extract_sections()` |
| `app/services/parser/epub_parser.py` | Add `_strip_xml_and_images()` helper |
| `tests/unit/test_epub_parser.py` | Add tests for merge logic |

### 1.9 Edge Cases

| Case | Behavior |
|------|----------|
| All sections < 500 chars | No merge — single section remains |
| Two consecutive stubs | First merges into second, second may then merge into third (cascading) |
| Last section is a stub | Merge backward into previous section |
| Only one section in book | No merge possible — keep as-is |
| Section with image but real text > 500 chars | Not merged (image content doesn't count, but text does) |
| Spine fallback (no TOC) | Merge logic applies equally — operates on sections regardless of source |

---

## Fix 2: Markdown Output — Remove JSON Wrapping

### 2.1 Problem

The base templates (`prompts/base/summarize_section.txt` line 26 and `summarize_book.txt` line 15) instruct: `"Output as JSON matching the provided schema."` But `_summarize_single_section()` (line 164) and `_generate_book_summary()` (line 216) call `self.llm.generate(prompt, model=...)` **without** a `json_schema` parameter.

The LLM responds with JSON-fenced markdown:
```json
{
  "summary": "The actual summary text..."
}
```

The `_extract_summary_text()` method (line 254) tries `json.loads()` → `.get("detailed_summary")`, but:
- Responses use `"summary"` key, not `"detailed_summary"`
- Some responses include ``` ```json ``` fencing that breaks `json.loads()`
- Fallback returns raw `response.content` including JSON wrapping

### 2.2 Solution

**Template changes:**

Remove from `summarize_section.txt` (line 26):
```
Output as JSON matching the provided schema.
```

Replace with:
```
Output your summary directly as markdown. Do not wrap in JSON or code fences.
```

Same change for `summarize_book.txt` (line 15).

**`_extract_summary_text()` update:**

Make it robust to handle both old JSON responses and new markdown responses:

```python
def _extract_summary_text(self, response) -> str:
    """Extract summary text from LLM response.
    
    Handles: raw markdown, JSON-wrapped, code-fenced JSON.
    """
    content = response.content.strip()
    
    # Strip code fence wrapping (```json ... ``` or ``` ... ```)
    if content.startswith("```"):
        # Remove first line (```json or ```) and last line (```)
        lines = content.split("\n")
        if lines[-1].strip() == "```":
            content = "\n".join(lines[1:-1]).strip()
    
    # Try JSON extraction (backward compat with old responses)
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            # Try common key names
            for key in ("summary", "detailed_summary", "content"):
                if key in parsed:
                    return parsed[key]
            # If dict but no known key, return the whole thing as text
            return content
    except (json.JSONDecodeError, AttributeError):
        pass
    
    return content
```

### 2.3 Metadata Extraction

After summarization, automatically extract structured metadata from the markdown output using existing regex patterns in `SummaryService.extract_concepts()`:

- Bold terms (`**term**`)
- Headers (`## heading`)
- Named entities (capitalized multi-word phrases)

Store extracted concepts in `Summary.eval_json` field under a `"concepts"` key:
```json
{
  "concepts": ["Five Forces", "Value Chain", "Competitive Advantage"]
}
```

This happens in `_summarize_single_section()` after getting the summary text, before creating the Summary object.

### 2.4 Files Changed

| File | Change |
|------|--------|
| `app/services/summarizer/prompts/base/summarize_section.txt` | Replace JSON instruction with markdown instruction |
| `app/services/summarizer/prompts/base/summarize_book.txt` | Same |
| `app/services/summarizer/summarizer_service.py` | Update `_extract_summary_text()`, add concept extraction after summarization |
| `tests/unit/test_summarizer.py` | Update tests for new extraction logic |

### 2.5 Edge Cases

| Case | Behavior |
|------|----------|
| LLM still returns JSON despite markdown instruction | `_extract_summary_text()` extracts the value — backward compatible |
| LLM returns code-fenced markdown (not JSON) | Strip code fences, return content |
| LLM returns plain markdown | Pass through unchanged |
| Empty response | Return empty string |
| Response is a JSON array | Return as-is (unusual but safe) |

---

## Fix 3: Summarizer — Minimum Content Threshold

### 3.1 Problem

Sections with < 200 chars of content (XML boilerplate, cover pages) are still sent to the LLM for summarization. The LLM generates summaries from cumulative context rather than source content, producing hallucinated summaries with compression ratios > 100%.

### 3.2 Solution

Add a configurable `min_section_chars` setting. During `summarize_book()`, skip sections below this threshold with a specific skip reason.

**In `SummarizationConfig` (`app/config.py`):**
```python
class SummarizationConfig(BaseModel):
    default_preset: str = "practitioner_bullets"
    eval_prompt_version: str = "v1"
    min_section_chars: int = 200  # NEW
```

**In `SummarizerService.summarize_book()` — add check before LLM call:**
```python
# Check minimum content threshold
text_content = self._strip_non_content(section.content_md or "")
if len(text_content) < self.config.summarization.min_section_chars and not force:
    skipped += 1
    if on_section_skip:
        on_section_skip(i + 1, total, section.title)
    logger.info(
        "section_skipped_insufficient_content",
        section_id=section.id,
        char_count=len(text_content),
        threshold=self.config.summarization.min_section_chars,
    )
    continue
```

**`_strip_non_content(text)`** — reuse the same XML/image stripping from Fix 1:
```python
def _strip_non_content(self, text: str) -> str:
    """Remove XML declarations, image-only lines, whitespace for content measurement."""
    text = re.sub(r'<\?xml[^?]*\?>', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)\s*', '', text)
    return text.strip()
```

### 3.3 Progress Display

Skipped sections show a distinct message:
```
  [4/17] Part One: What Is Competition?      skipped (115 chars < 200 min)
```

### 3.4 Files Changed

| File | Change |
|------|--------|
| `app/config.py` | Add `min_section_chars: int = 200` to SummarizationConfig |
| `app/services/summarizer/summarizer_service.py` | Add threshold check in `summarize_book()`, add `_strip_non_content()` |
| `app/cli/commands/summarize_cmd.py` | Update skip callback to show char count and threshold |
| `tests/unit/test_summarizer.py` | Test threshold skip logic |
| `tests/unit/test_config.py` | Test new config field |

### 3.5 Edge Cases

| Case | Behavior |
|------|----------|
| Section has 199 chars of real text | Skipped (below default 200) |
| Section has 200 chars of real text | Summarized |
| `--force` flag used | Threshold ignored, all sections summarized |
| `min_section_chars` set to 0 | Effectively disabled — all sections summarized |
| Section content is all images, 0 text chars | Skipped (0 < 200) |

---

## Fix 4: Eval Hint & Eval Display Improvements

### 4.1 Problem

After summarization with `--skip-eval`, there's no indication that eval wasn't run. Users see `Eval: -` in summary lists with no context. Additionally, the single `Eval` column doesn't distinguish between "not run", "passed", "partially passed", and "failed".

### 4.2 Solution: Eval Hint

After the final summary report in `summarize_cmd.py`, add:

```python
if skip_eval:
    console.print(
        f"\n  Tip: Run [bold]bookcompanion eval {book_id}[/bold] to evaluate summary quality."
    )
```

### 4.3 Solution: Eval Status & Results Columns

Replace the single `Eval` column in `summary list` with two columns:

| Column | Values | Description |
|--------|--------|-------------|
| **Eval Status** | `—` (not run), `running`, `passed`, `failed`, `partial` | Whether eval has been executed |
| **Eval Results** | `—`, `14/16`, `16/16` | Pass count / total assertions |

**Status derivation logic:**

```python
def _eval_status(eval_json: dict | None) -> str:
    """Derive eval status from eval_json."""
    if not eval_json or not isinstance(eval_json, dict):
        return "—"            # Not run
    total = eval_json.get("total", 0)
    passed = eval_json.get("passed", 0)
    if total == 0:
        return "—"
    if passed == total:
        return "[green]passed[/green]"
    # Check if any critical assertions failed
    results = eval_json.get("results", {})
    critical_failed = any(
        not r.get("passed") for name, r in results.items()
        if ASSERTION_REGISTRY.get(name, {}).get("category") == "critical"
    )
    if critical_failed:
        return "[red]failed[/red]"
    return "[yellow]partial[/yellow]"


def _eval_results(eval_json: dict | None) -> str:
    """Format eval pass/total as string."""
    if not eval_json or not isinstance(eval_json, dict):
        return "—"
    passed = eval_json.get("passed", 0)
    total = eval_json.get("total", 0)
    if total == 0:
        return "—"
    return f"{passed}/{total}"
```

**Apply to these views:**

| View | Change |
|------|--------|
| `summary list <book_id>` (overview) | No eval columns (too noisy for overview) |
| `summary list <book_id> <section_id>` | Replace `Eval` with `Status` + `Results` columns |
| `summary list <book_id> --book-level` | Replace `Eval` with `Status` + `Results` columns |
| `summary show <id>` | Show status line + detailed breakdown if available |
| `summary compare <id1> <id2>` | Show `Status` + `Results` rows in comparison table |
| `show <book_id>` (section table) | Replace `Eval` with `Status` column (narrow) |

**`summary show` detailed eval display** (when eval has been run):
```
Eval Status: passed
Eval Results: 14/16 assertions passed
  Critical (4/4):  ✓ no_hallucinated_facts  ✓ no_contradictions  ✓ accurate_quotes  ✓ cross_summary_consistency
  Important (6/6): ✓ covers_main_argument  ✓ covers_key_concepts  ✓ covers_frameworks  ...
  Advisory (4/6):  ✓ standalone_readable  ✗ reasonable_length  ✗ image_refs_preserved  ...
```

### 4.4 Files Changed

| File | Change |
|------|--------|
| `app/cli/commands/summarize_cmd.py` | Add hint after final report when `--skip-eval` |
| `app/cli/commands/summary_cmds.py` | Replace `_format_eval()` with `_eval_status()` + `_eval_results()`, update all table columns |
| `app/cli/commands/books.py` | Update `show` command eval column to use `_eval_status()` |
| `tests/e2e/test_v1_1_flows.py` | Update any assertions checking eval column output |

---

## Fix 5: XML/HTML Boilerplate Stripping

### 5.1 Problem

EPUB HTML files often start with `<?xml version='1.0' encoding='utf-8'?>` which passes through markdownify unchanged, appearing as `xml version='1.0' encoding='utf-8'?` in the markdown output.

### 5.2 Solution

Strip XML declarations and processing instructions from raw HTML **before** passing to markdownify:

```python
def _clean_html(self, html: str) -> str:
    """Remove XML declarations and processing instructions from HTML."""
    # Remove XML declarations: <?xml ... ?>
    html = re.sub(r'<\?xml[^?]*\?>', '', html)
    # Remove other processing instructions: <?...?>
    html = re.sub(r'<\?[^?]*\?>', '', html)
    return html.strip()
```

Call in `_extract_sections()` before markdownify:

```python
# Current (line 97):
md = markdownify(html, heading_style="ATX", strip=["script", "style"])

# New:
html = self._clean_html(html)
md = markdownify(html, heading_style="ATX", strip=["script", "style"])
```

### 5.3 Files Changed

| File | Change |
|------|--------|
| `app/services/parser/epub_parser.py` | Add `_clean_html()`, call before markdownify |
| `tests/unit/test_epub_parser.py` | Test XML stripping |

---

## Shared Utilities

The XML/image stripping logic is used in both Fix 1 (merge decision) and Fix 3 (threshold check). Extract into a shared helper in `app/services/parser/text_utils.py`:

```python
"""Text cleaning utilities shared across parser and summarizer."""
import re

_XML_DECL = re.compile(r'<\?xml[^?]*\?>')
_PROCESSING_INST = re.compile(r'<\?[^?]*\?>')
_IMAGE_ONLY_LINE = re.compile(r'^\s*!\[.*?\]\(.*?\)\s*$', re.MULTILINE)

def strip_non_content(text: str) -> str:
    """Remove XML declarations, processing instructions, image-only lines."""
    text = _XML_DECL.sub('', text)
    text = _PROCESSING_INST.sub('', text)
    text = _IMAGE_ONLY_LINE.sub('', text)
    return text.strip()

def text_char_count(text: str) -> int:
    """Character count of text after stripping non-content."""
    return len(strip_non_content(text))
```

## Re-Parse Cascade Behavior

When `bookcompanion add <path> --force` re-parses a book:
1. Existing `BookSection` rows are deleted (cascade)
2. `Summary` rows are cascade-deleted via `book_id` FK (`ON DELETE CASCADE`)
3. `Book.default_summary_id` is set to NULL
4. New sections are created from the re-parsed content
5. User must re-summarize to generate new summaries

This is the expected and desired behavior for V1.2 — old JSON-wrapped summaries are replaced by re-summarizing after the parser fix.

---

## Database Migrations

**No migration needed.** All fixes operate on:
- Parser logic (no schema changes)
- Template content (file changes only)
- Service logic (Python code only)
- Config defaults (pydantic model, no DB)

Existing summaries with JSON wrapping will be replaced by re-summarizing with `--force` after deployment.

---

## Configuration Changes

**New setting in `SummarizationConfig`:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `min_section_chars` | `int` | `200` | Minimum text character count for a section to be summarized. Sections below this are skipped with a log message. Set to 0 to disable. |

**YAML config example:**
```yaml
summarization:
  default_preset: practitioner_bullets
  min_section_chars: 200
```

**CLI override:** None — use `config set summarization.min_section_chars 500` for persistent change.

---

## Verification Plan

### Unit Tests

| Test | File | Description |
|------|------|-------------|
| `test_merge_stub_sections` | `test_epub_parser.py` | Two sections: 100-char stub + 5000-char content → merged into one |
| `test_merge_part_divider` | `test_epub_parser.py` | Part divider + chapter → merged, chapter title kept |
| `test_merge_cascade` | `test_epub_parser.py` | Three consecutive stubs + content → all merge into content section |
| `test_merge_last_stub` | `test_epub_parser.py` | Last section is stub → merges backward |
| `test_no_merge_above_threshold` | `test_epub_parser.py` | Section with 600 chars → not merged |
| `test_single_section_no_merge` | `test_epub_parser.py` | Only one section → no crash, no merge |
| `test_clean_html_xml_decl` | `test_epub_parser.py` | `<?xml ...?>` stripped before markdownify |
| `test_extract_summary_markdown` | `test_summarizer.py` | Plain markdown returned as-is |
| `test_extract_summary_json_wrapped` | `test_summarizer.py` | `{"summary": "text"}` → extracts "text" |
| `test_extract_summary_code_fenced` | `test_summarizer.py` | ` ```json\n{...}\n``` ` → extracts value |
| `test_extract_summary_old_key` | `test_summarizer.py` | `{"detailed_summary": "text"}` → extracts "text" |
| `test_min_chars_skip` | `test_summarizer.py` | Section with 100 chars skipped, callback called |
| `test_min_chars_force_override` | `test_summarizer.py` | `--force` bypasses threshold |
| `test_config_min_section_chars` | `test_config.py` | Default 200, configurable |
| `test_concept_extraction_after_summary` | `test_summarizer.py` | Concepts stored in eval_json after summarization |
| `test_eval_status_not_run` | `test_summary_cmds.py` | eval_json=None → status "—", results "—" |
| `test_eval_status_passed` | `test_summary_cmds.py` | All 16 passed → status "passed", results "16/16" |
| `test_eval_status_failed` | `test_summary_cmds.py` | Critical assertion failed → status "failed" |
| `test_eval_status_partial` | `test_summary_cmds.py` | Non-critical failures only → status "partial" |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_epub_parse_porter_book` | Parse book 2 EPUB, verify sections have real content (no 144-char stubs) |
| `test_summarize_produces_markdown` | Summarize a section, verify output is markdown not JSON |
| `test_summarize_skips_short` | Create a book with a 50-char section, verify it's skipped |

### E2E Tests (CLI)

| Test | Command | Assertion |
|------|---------|-----------|
| Parse + verify | `bookcompanion add <epub> --force` | Section count reduced, no sections < 200 chars |
| Summarize + verify format | `bookcompanion summarize <id> --preset practitioner_bullets --skip-eval` | `summary read` output is markdown, not JSON |
| Skip hint | `bookcompanion summarize <id> --skip-eval` | stdout contains "Run bookcompanion eval" |
| Threshold skip | `bookcompanion summarize <id>` (with stub sections) | stdout contains "skipped (X chars < 200 min)" |
| Show quality | `bookcompanion show <id>` | Quality line shows fewer warnings after re-parse |
| Eval display | `bookcompanion eval <id>` then `summary list <id> <section>` | Status + Results columns show "passed"/"partial"/"failed" + "14/16" |
| Eval not run | `summary list <id>` (before eval) | Status shows "—", Results shows "—" |

### Manual Verification (Post-Deploy)

1. Re-parse book 2: `bookcompanion add tests/fixtures/sample_epub/understanding_porter.epub --force`
2. Verify sections: `bookcompanion show 2` — expect ~7-8 content sections instead of 17
3. Summarize: `bookcompanion summarize 2 --preset practitioner_bullets`
4. Verify markdown: `bookcompanion summary read 2` — expect clean markdown, no JSON
5. Verify eval hint: stdout after summarize shows "Run bookcompanion eval..."
6. Run full eval: `bookcompanion eval 2`
7. Verify eval display: `bookcompanion summary list 2 <section_id>` — Status shows "passed"/"partial", Results shows "X/16"
8. Verify summary show: `bookcompanion summary show <id>` — detailed eval breakdown with categories
9. Compare summaries: `bookcompanion summary list 2` — verify compression ratios are 10-30%

---

## Deployment & Rollout

### Steps

1. **Deploy code changes** — all fixes in one release
2. **Re-parse book 2**: `bookcompanion add <porter_epub_path> --force`
3. **Re-summarize book 2** with all three presets:
   ```bash
   bookcompanion summarize 2 --preset practitioner_bullets --skip-images
   bookcompanion summarize 2 --preset executive_brief --skip-images
   bookcompanion summarize 2 --preset academic_detailed --skip-images
   ```
4. **Run full eval**: `bookcompanion eval 2`
5. **Verify**: `bookcompanion summary list 2`, `bookcompanion summary read 2`

### Rollback

All changes are backward-compatible:
- Auto-merge is additive (fewer sections, but no data loss)
- Markdown output is a superset of JSON extraction (old extraction still works)
- Threshold skip is configurable and can be set to 0
- No database migration to rollback

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Auto-merge combines sections that shouldn't be merged | Low | Medium | 500-char threshold is conservative. Only affects XML-boilerplate sections. User can undo via `edit sections`. |
| LLM still returns JSON despite markdown instruction | Medium | Low | `_extract_summary_text()` handles both formats. Backward compatible. |
| Threshold skips legitimate short sections (poetry, quotes) | Low | Low | Configurable `min_section_chars`. Set to 0 to disable. `--force` bypasses. |
| Re-parse deletes existing summaries for book 2 | Expected | Accepted | This is the desired behavior — old summaries are JSON-wrapped and need replacement. |
| Regex metadata extraction misses important concepts | Medium | Low | Extraction is supplementary — primary output is the markdown summary itself. Can be enhanced later. |

---

## Research Sources

### Existing Code Explored

| Component | File | Key Findings |
|-----------|------|-------------|
| EPUB parser | `app/services/parser/epub_parser.py` | Spine-based extraction, TOC walk, no existing merge logic |
| Structure detector | `app/services/parser/structure_detector.py` | 3-tier detection (TOC → heuristic → LLM), operates after parse |
| Quality service | `app/services/quality_service.py` | 10 checks including "short" at 200 chars, but detection only — no auto-fix |
| Summarizer service | `app/services/summarizer/summarizer_service.py` | `_extract_summary_text()` at line 254, `generate()` with no json_schema |
| Claude CLI provider | `app/services/summarizer/claude_cli.py` | `--json-schema` flag available but unused for summarization |
| LLM response model | `app/services/summarizer/llm_provider.py` | LLMResponse with content, model, tokens, latency |
| Summary service | `app/services/summary_service.py` | `extract_concepts()` with bold/header/named-entity regex — reusable for metadata |

### External Research

| Topic | Finding | Source |
|-------|---------|--------|
| EPUB spine structure | Many commercial EPUBs use separate HTML files for chapter covers, part dividers, and front matter — each as a spine item | EPUB 3.0 spec, ebooklib documentation |
| markdownify XML handling | markdownify does not strip XML processing instructions — they pass through as text. Must be removed before conversion. | markdownify source code, GitHub issues |
| Content detection heuristics | Text-content-after-stripping-markup is the standard approach for detecting "real" content in HTML. Threshold of 200-500 chars is common in readability extractors. | Readability.js, newspaper3k patterns |
| Python XML stripping | `re.sub(r'<\?xml[^?]*\?>', '', html)` is the standard regex approach. BeautifulSoup can also strip processing instructions but adds overhead for a simple regex task. | Python re module, BeautifulSoup docs |
