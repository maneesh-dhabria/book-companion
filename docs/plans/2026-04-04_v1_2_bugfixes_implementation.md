# V1.2 Bugfixes & Improvements — Implementation Plan

**Spec:** [`docs/specs/2026-04-04_v1_2_bugfixes_and_improvements_spec.md`](../specs/2026-04-04_v1_2_bugfixes_and_improvements_spec.md)
**Requirements:** [`docs/requirements/2026-04-04_v1_2_bugfixes_and_improvements.md`](../requirements/2026-04-04_v1_2_bugfixes_and_improvements.md)

---

## Context

V1.1 was tested on "Understanding Michael Porter" (book 2). Four bugs were found: (1) EPUB parser stores chapter cover pages as stub sections with 115-144 chars of XML boilerplate, (2) LLM output is JSON-wrapped instead of markdown, (3) stub sections get summarized producing hallucinated content with >100% compression ratios, (4) eval status is always empty with no guidance. This plan fixes all four issues plus XML boilerplate stripping.

## Decision Log

| # | Decision | Options | Choice | Rationale |
|---|----------|---------|--------|-----------|
| P1 | Task ordering | (A) Fix by spec number (B) Dependency order with parallel opportunities | **B** | text_utils first (shared dep), then XML strip → merge → markdown → threshold → eval display, each tested incrementally |
| P2 | extract_concepts reuse | (A) Refactor to @staticmethod (B) Duplicate regex | **A** | SummaryService.extract_concepts doesn't use self — make it @staticmethod so summarizer can call it without instantiating the service |
| P3 | eval display functions location | (A) In summary_cmds.py (B) In formatting.py (shared) | **B** | Both books.py and summary_cmds.py need _eval_status/_eval_results. Put in formatting.py to avoid circular imports |
| P4 | on_section_skip callback signature | (A) Add 4th reason param (B) Keep 3 params, use different callback for threshold | **A** | Single callback with optional reason string. Simpler, backward-compatible via default value |

---

## Task 1: Shared text_utils Module

**Goal:** Create shared text cleaning utilities used by Fix 1 (merge) and Fix 3 (threshold).

**Files:**
- Create: `backend/app/services/parser/text_utils.py`
- Create: `backend/tests/unit/test_text_utils.py`

### Steps

- [ ] Create `text_utils.py` with:
  ```python
  import re

  _XML_DECL = re.compile(r"<\?xml[^?]*\?>")
  _PROCESSING_INST = re.compile(r"<\?[^?]*\?>")
  _IMAGE_ONLY_LINE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$", re.MULTILINE)

  def strip_non_content(text: str) -> str:
      text = _XML_DECL.sub("", text)
      text = _PROCESSING_INST.sub("", text)
      text = _IMAGE_ONLY_LINE.sub("", text)
      return text.strip()

  def text_char_count(text: str) -> int:
      return len(strip_non_content(text))
  ```
- [ ] Write tests: XML removal, image line removal, plain text passthrough, empty input, char count on mixed content
- [ ] Run: `uv run python -m pytest tests/unit/test_text_utils.py -v`

---

## Task 2: Fix 5 — XML/HTML Boilerplate Stripping

**Goal:** Strip `<?xml ...?>` from HTML before markdownify in EPUB parser.

**Files:**
- Modify: `backend/app/services/parser/epub_parser.py` (lines 96-97, 100-103)
- Modify: `backend/tests/unit/test_epub_parser.py`

### Steps

- [ ] Add `_clean_html()` static method to EPUBParser:
  ```python
  @staticmethod
  def _clean_html(html: str) -> str:
      import re
      html = re.sub(r"<\?xml[^?]*\?>", "", html)
      html = re.sub(r"<\?[^?]*\?>", "", html)
      return html
  ```
- [ ] Call `_clean_html()` at line 96 before markdownify: `html = self._clean_html(html)`
- [ ] Call `_clean_html()` at line 100 for alt-text extraction HTML too
- [ ] Add tests: XML declaration stripped, processing instructions stripped, normal HTML unchanged
- [ ] Run: `uv run python -m pytest tests/unit/test_epub_parser.py -v`

---

## Task 3: Fix 1 — EPUB Parser Auto-Merge Stub Sections

**Goal:** Auto-merge stub sections (< 500 chars text) into adjacent content-rich sections during parsing.

**Files:**
- Modify: `backend/app/services/parser/epub_parser.py`
- Modify: `backend/tests/unit/test_epub_parser.py`

### Steps

- [ ] Add `_merge_stub_sections(self, sections: list[ParsedSection]) -> list[ParsedSection]` method:
  - Import `text_char_count` from `app.services.parser.text_utils`
  - Forward pass: for each section where `text_char_count(content_md) < 500`:
    - If next section exists: prepend stub content to next section, keep next section's title, use `min(stub.depth, next.depth)`, drop stub's images
    - If last section: append stub content to previous section
    - Mark stub for removal
  - Handle cascading: two consecutive stubs merge into the first content-rich section
  - After merge: recalculate `content_token_count = len(content_md) // 4` on surviving sections
  - Reindex `order_index` 0-based
  - Log each merge: `logger.info("section_merged", stub_title=..., into_title=..., reason=...)`
- [ ] Call `_merge_stub_sections(sections)` at end of `_extract_sections()` before return (line ~140)
- [ ] Also call after the spine fallback block (line ~138)
- [ ] Add tests:
  - `test_merge_stub_into_next` — 2 sections: 100-char stub + 5000-char content → 1 section, content title kept
  - `test_merge_part_divider` — "Part One" (115 chars) + "Ch 1" (5000 chars) → "Ch 1" with prepended part text
  - `test_merge_cascading_stubs` — stub + stub + content → content with both stubs prepended
  - `test_merge_last_stub_backward` — content + stub → content with stub appended
  - `test_no_merge_above_threshold` — all sections > 500 chars → no change
  - `test_single_section_no_merge` — 1 section → no crash
  - `test_merge_drops_stub_images` — stub has images, merged section doesn't get them
  - `test_merge_reindexes_order` — order_index is sequential after merge
  - `test_merge_recalculates_tokens` — content_token_count updated
- [ ] Run: `uv run python -m pytest tests/unit/test_epub_parser.py -v`
- [ ] Verify with real EPUB (if fixtures available): `uv run python -c "import asyncio; from app.services.parser.epub_parser import EPUBParser; p = EPUBParser(); r = asyncio.run(p.parse('tests/fixtures/sample_epub/art_of_war.epub')); print(f'{len(r.sections)} sections'); [print(f'  {s.order_index}: {s.title} ({len(s.content_md)} chars)') for s in r.sections]"`

---

## Task 4: Fix 2 — Markdown Output (Remove JSON Wrapping)

**Goal:** Switch summarization output from JSON to markdown. Add concept extraction.

**Files:**
- Modify: `backend/app/services/summarizer/prompts/base/summarize_section.txt` (line 26)
- Modify: `backend/app/services/summarizer/prompts/base/summarize_book.txt` (line 15)
- Modify: `backend/app/services/summarizer/summarizer_service.py` (`_extract_summary_text`, `_summarize_single_section`)
- Modify: `backend/app/services/summary_service.py` (make `extract_concepts` a `@staticmethod`)
- Modify: `backend/tests/unit/test_summarizer.py`
- Modify: `backend/tests/unit/test_prompt_fragments.py` (if assertions check for "JSON" text)

### Steps

- [ ] **Template changes:**
  - `summarize_section.txt` line 26: replace `Output as JSON matching the provided schema.` with `Output your summary directly as markdown. Do not wrap in JSON or code fences.`
  - `summarize_book.txt` line 15: same replacement
- [ ] **Rewrite `_extract_summary_text()`** (line 254 of summarizer_service.py):
  ```python
  def _extract_summary_text(self, response) -> str:
      content = response.content.strip()
      # Strip code fences
      if content.startswith("```"):
          lines = content.split("\n")
          if lines[-1].strip() == "```":
              content = "\n".join(lines[1:-1]).strip()
      # Try JSON extraction (backward compat)
      try:
          parsed = json.loads(content)
          if isinstance(parsed, dict):
              for key in ("summary", "detailed_summary", "content"):
                  if key in parsed:
                      return parsed[key]
              return content
      except (json.JSONDecodeError, AttributeError):
          pass
      return content
  ```
- [ ] **Make `extract_concepts` a @staticmethod** in `summary_service.py`:
  - Change `def extract_concepts(self, text: str)` → `@staticmethod def extract_concepts(text: str)`
  - Update `concept_diff` to call `SummaryService.extract_concepts(...)` instead of `self.extract_concepts(...)`
- [ ] **Add concept extraction** in `_summarize_single_section()` after getting summary_text:
  ```python
  from app.services.summary_service import SummaryService
  concepts = SummaryService.extract_concepts(summary_text)
  ```
  Set `eval_json={"concepts": sorted(concepts)} if concepts else None` on the Summary object.
  Same for `_generate_book_summary()`.
- [ ] **Update tests:**
  - Existing `test_extract_summary_text_json` — still passes (backward compat with "detailed_summary" key)
  - Existing `test_extract_summary_text_plain` — still passes
  - Add `test_extract_summary_text_code_fenced` — ` ```json\n{"summary": "text"}\n``` ` → extracts "text"
  - Add `test_extract_summary_text_markdown_fenced` — ` ```markdown\nsome text\n``` ` → returns "some text"
  - Add `test_extract_summary_text_summary_key` — `{"summary": "text"}` → extracts "text"
  - Add `test_concept_extraction_stored` — verify concepts in eval_json after summarization (mock test)
  - Update `test_prompt_fragments.py` if any test checks for "JSON" in rendered template
- [ ] Run: `uv run python -m pytest tests/unit/test_summarizer.py tests/unit/test_prompt_fragments.py tests/unit/test_summary_service.py -v`

---

## Task 5: Fix 3 — Minimum Content Threshold

**Goal:** Skip sections below configurable char threshold during summarization.

**Files:**
- Modify: `backend/app/config.py` (SummarizationConfig, line 27)
- Modify: `backend/app/services/summarizer/summarizer_service.py` (`summarize_book()`)
- Modify: `backend/app/cli/commands/summarize_cmd.py` (skip callback)
- Modify: `backend/tests/unit/test_summarizer.py`
- Modify: `backend/tests/unit/test_config.py`

### Steps

- [ ] **Config change** — add `min_section_chars: int = 200` to `SummarizationConfig`
- [ ] **Update `on_section_skip` callback signature** — add optional 4th param `reason: str | None = None`:
  - In `summarize_book()` idempotency skip (line ~75): `on_section_skip(i + 1, total, section.title, "already summarized")`
  - In `summarize_book()` after idempotency check, add threshold check:
    ```python
    from app.services.parser.text_utils import text_char_count
    char_count = text_char_count(section.content_md or "")
    min_chars = self.config.summarization.min_section_chars
    if not force and char_count < min_chars:
        skipped += 1
        if on_section_skip:
            on_section_skip(i + 1, total, section.title, f"{char_count} chars < {min_chars} min")
        logger.info("section_skipped_insufficient_content", section_id=section.id, char_count=char_count)
        continue
    ```
- [ ] **Update CLI skip callback** in `summarize_cmd.py` (line ~122):
  ```python
  on_section_skip=lambda i, total, title, reason=None: console.print(
      f"  [{i}/{total}] {title[:35]:<35} skipped ({reason or 'already summarized'})"
  ),
  ```
- [ ] **Tests:**
  - `test_config_min_section_chars` — default 200, settable
  - `test_skip_below_threshold` — section with 100 real chars → skipped, callback called with reason
  - `test_force_bypasses_threshold` — `force=True` → not skipped
  - `test_above_threshold_proceeds` — section with 500 chars → summarized normally
- [ ] Run: `uv run python -m pytest tests/unit/test_summarizer.py tests/unit/test_config.py -v`

---

## Task 6: Fix 4 — Eval Hint & Eval Display

**Goal:** Add eval hint after --skip-eval. Replace single Eval column with Status + Results.

**Files:**
- Modify: `backend/app/cli/commands/summarize_cmd.py` (add hint, line ~151)
- Modify: `backend/app/cli/formatting.py` (add `eval_status()`, `eval_results()`)
- Modify: `backend/app/cli/commands/summary_cmds.py` (replace `_format_eval`, update all tables)
- Modify: `backend/app/cli/commands/books.py` (update show command eval columns)
- Create: `backend/tests/unit/test_eval_display.py`

### Steps

- [ ] **Add eval hint** in `summarize_cmd.py` after the final report:
  ```python
  if skip_eval:
      console.print(f"\n  [dim]Tip: Run bookcompanion eval {book_id} to evaluate quality[/dim]")
  ```
- [ ] **Add to `formatting.py`:**
  ```python
  def eval_status(eval_json: dict | None) -> str:
      if not eval_json or not isinstance(eval_json, dict):
          return "—"
      total = eval_json.get("total", 0)
      passed = eval_json.get("passed", 0)
      if total == 0:
          return "—"
      if passed == total:
          return "[green]passed[/green]"
      results = eval_json.get("results", eval_json.get("assertions", {}))
      if isinstance(results, dict):
          from app.services.summarizer.evaluator import ASSERTION_REGISTRY
          for name, r in results.items():
              if not r.get("passed") and ASSERTION_REGISTRY.get(name, {}).get("category") == "critical":
                  return "[red]failed[/red]"
      return "[yellow]partial[/yellow]"

  def eval_results(eval_json: dict | None) -> str:
      if not eval_json or not isinstance(eval_json, dict):
          return "—"
      passed = eval_json.get("passed", 0)
      total = eval_json.get("total", 0)
      return f"{passed}/{total}" if total else "—"
  ```
- [ ] **Update `summary_cmds.py`:**
  - Remove `_format_eval()` function
  - Import `eval_status, eval_results` from `app.cli.formatting`
  - Replace single "Eval" column with "Status" + "Results" in: book-level list, section list
  - Update `summary_show` to display detailed breakdown when eval ran
  - Update `summary compare` table row
- [ ] **Update `books.py` show command:**
  - Import `eval_status` from `app.cli.formatting`
  - Replace "Eval" column with "Status" column in wide mode
- [ ] **Tests (`test_eval_display.py`):**
  - `test_eval_status_none` → "—"
  - `test_eval_status_all_passed` → contains "passed"
  - `test_eval_status_critical_failed` → contains "failed"
  - `test_eval_status_partial` → contains "partial"
  - `test_eval_results_none` → "—"
  - `test_eval_results_with_data` → "14/16"
- [ ] Run: `uv run python -m pytest tests/unit/test_eval_display.py -v`

---

## Task 7: E2E Tests & Documentation

**Goal:** E2E tests for all fixes. Update CLAUDE.md.

**Files:**
- Create: `backend/tests/e2e/test_v1_2_flows.py`
- Modify: `CLAUDE.md`

### Steps

- [ ] **E2E tests** using `run_cli()` subprocess pattern:
  - `test_summarize_skip_eval_hint` — `summarize <id> --skip-eval` output contains "eval"
  - `test_preset_list_still_works` — regression check
  - `test_config_shows_min_section_chars` — `config` output includes "min_section_chars"
  - `test_summary_list_has_status_column` — output contains "Status" (not just "Eval")
- [ ] **Update CLAUDE.md:**
  - Gotchas: add note about EPUB stub section merging (500 char threshold)
  - Gotchas: add note about `_extract_summary_text()` handling multiple formats
  - Configuration: document `min_section_chars` setting
- [ ] Run: `uv run python -m pytest tests/e2e/test_v1_2_flows.py -v`

---

## Task 8: Final Verification & Deploy

**Goal:** Run full suite, lint, manual CLI verification, re-parse + re-summarize book 2, run eval.

### Steps

- [ ] **Lint & format:**
  ```bash
  cd backend && uv run ruff check . && uv run ruff format --check .
  ```
- [ ] **Full test suite:**
  ```bash
  cd backend && uv run python -m pytest tests/ -v --tb=short
  ```
- [ ] **Verify Docker DB is running:**
  ```bash
  docker ps | grep bookcompanion-db
  ```
- [ ] **Re-parse book 2:**
  ```bash
  uv run bookcompanion add tests/fixtures/sample_epub/understanding_porter.epub --force
  ```
  - Verify: `uv run bookcompanion show 2` — expect fewer sections (stubs merged), no sections < 200 chars, quality warnings reduced
- [ ] **Re-summarize book 2 with 3 presets:**
  ```bash
  uv run bookcompanion summarize 2 --preset practitioner_bullets --skip-images
  uv run bookcompanion summarize 2 --preset executive_brief --skip-images
  uv run bookcompanion summarize 2 --preset academic_detailed --skip-images
  ```
  - Verify: `uv run bookcompanion summary read 2` — output is clean markdown (not JSON)
  - Verify: skip hint printed after each run (all use default --skip-eval behavior)
  - Verify: compression ratios are 10-30% (not >100%)
- [ ] **Run full eval:**
  ```bash
  uv run bookcompanion eval 2
  ```
  - Verify: `uv run bookcompanion summary list 2 <section_id>` — Status and Results columns populated
  - Verify: `uv run bookcompanion summary show <summary_id>` — detailed eval breakdown
- [ ] **Verify other commands still work:**
  ```bash
  uv run bookcompanion preset list
  uv run bookcompanion summary compare <id1> <id2>
  uv run bookcompanion read 2 <section_id> --with-summary
  ```
- [ ] **Commit all changes**

---

## Task Dependencies

```
Task 1 (text_utils) ─┬─→ Task 2 (XML strip) → Task 3 (EPUB merge)
                      └─→ Task 5 (threshold)
Task 4 (markdown output)
Task 6 (eval display)
                         ↓ all above ↓
Task 7 (E2E + docs) → Task 8 (final verification)
```

Tasks 2-6 can proceed in parallel after Task 1 (2→3 must be sequential). Task 4 and Task 6 are independent of the parser tasks.

---

## Files Summary

| File | Tasks | Change Type |
|------|-------|-------------|
| `app/services/parser/text_utils.py` | 1 | Create |
| `app/services/parser/epub_parser.py` | 2, 3 | Modify |
| `app/services/summarizer/summarizer_service.py` | 4, 5 | Modify |
| `app/services/summarizer/prompts/base/summarize_section.txt` | 4 | Modify |
| `app/services/summarizer/prompts/base/summarize_book.txt` | 4 | Modify |
| `app/services/summary_service.py` | 4 | Modify (staticmethod) |
| `app/config.py` | 5 | Modify |
| `app/cli/commands/summarize_cmd.py` | 5, 6 | Modify |
| `app/cli/formatting.py` | 6 | Modify |
| `app/cli/commands/summary_cmds.py` | 6 | Modify |
| `app/cli/commands/books.py` | 6 | Modify |
| `CLAUDE.md` | 7 | Modify |
| `tests/unit/test_text_utils.py` | 1 | Create |
| `tests/unit/test_epub_parser.py` | 2, 3 | Modify |
| `tests/unit/test_summarizer.py` | 4, 5 | Modify |
| `tests/unit/test_prompt_fragments.py` | 4 | Modify |
| `tests/unit/test_summary_service.py` | 4 | Modify |
| `tests/unit/test_config.py` | 5 | Modify |
| `tests/unit/test_eval_display.py` | 6 | Create |
| `tests/e2e/test_v1_2_flows.py` | 7 | Create |
