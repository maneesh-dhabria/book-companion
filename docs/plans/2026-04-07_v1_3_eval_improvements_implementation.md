# V1.3 Eval System Improvements — Implementation Plan

**Spec:** [`docs/specs/2026-04-05_v1_3_eval_improvements_spec.md`](../specs/2026-04-05_v1_3_eval_improvements_spec.md)
**Requirements:** [`docs/requirements/2026-04-05_v1_3_eval_improvements.md`](../requirements/2026-04-05_v1_3_eval_improvements.md)

---

## Context

V1.3 overhauls the eval system based on analysis of 17 section evaluations on book 2 ("Understanding Michael Porter"). Of ~35 assertion failures, most trace to three root causes: eval/prompt contract mismatch (`has_key_concepts`), a code bug (`reasonable_length`), and context scope mismatch (`no_hallucinated_facts`). The changes: convert 3 assertions to deterministic, add preset-aware skipping, inject cumulative context into faithfulness eval, add section-type-aware thresholds, add diagnostic fields, implement cascade-safe traces, enable book-level eval, add paraphrased quote detection, and implement auto-retry on eval failure with targeted fix prompts.

**Scope:** 10 spec changes across schema, eval service, summarizer service, prompt templates, preset YAML, CLI commands, and parser. ~20 files modified, ~8 new test files, 1 Alembic migration.

## Decision Log

| # | Decision | Options | Choice | Rationale |
|---|----------|---------|--------|-----------|
| P1 | Task ordering | (A) Spec change order (B) Dependency-based phases matching spec §19 | **B** | Spec already defines A-F phases with correct dependency chains. Follow them with incremental testing per phase. |
| P2 | Deterministic assertion testing | (A) Test after all 3 implemented (B) Test each individually | **B** | User prefers smaller test chunks. Each deterministic assertion is independent — test immediately after implementation. |
| P3 | EvalTrace model `prompt_sent` nullability | (A) Make nullable for deterministic assertions (B) Store empty string | **A** | Deterministic assertions have no prompt. Nullable is semantically correct and the spec explicitly shows `prompt_sent=None` for deterministic traces. Requires model change but no migration (column is already TEXT, just needs `nullable=True` on the mapped_column). |
| P4 | Golden set fixture creation | (A) Export from DB after real eval run (B) Hand-craft synthetic fixtures | **A for all-pass, B for known-failure** | All-pass fixtures need realistic data. Known-failure fixtures need controlled content to test specific assertion behavior. |
| P5 | `_compute_eval_json` placement | (A) In EvalService (B) In eval_repo | **A** | It's business logic (aggregation + formatting), not a query builder. Keeps repo layer thin per project conventions. |
| P6 | `section_type` auto-detection placement | (A) In epub_parser.py (B) Shared utility function | **B — utility function called by parser** | PDF and MOBI parsers may also benefit. Place detection logic in a shared function, call from each parser. But since only EPUB is in scope for V1.3, implement in epub_parser and extract later if needed. |
| P7 | Cumulative context passing for batch eval | (A) Build in CLI, pass to eval (B) Build in SummarizerService, pass to eval | **B** | SummarizerService already builds cumulative context during the batch loop. Pass it directly to eval_service from within the loop. CLI standalone eval builds it separately. |
| P8 | EvalTrace `prompt_version` for deterministic | (A) Store "deterministic" (B) Store None | **A** | Allows filtering/querying by type. Matches spec pattern where `model_used="deterministic"`. |
| P9 | Test DB migration strategy | (A) Migrate both DBs in same task (B) Separate tasks | **A** | Migration is a single Alembic revision. Running on both DBs is a single command difference. Keep together to avoid forgotten test DB. |

---

## Task 1: Database Migration — Schema Changes

**Goal:** Add all new columns, alter FK, create indexes. Unblocks all subsequent tasks.

**Files:**
- Create: `backend/alembic/versions/xxxx_v1_3_eval_improvements.py` (auto-generated, then manually verified)
- Modify: `backend/app/db/models.py`

### Steps

**1a. Update SQLAlchemy models**

- [ ] `EvalTrace` model (`models.py` lines 279-309):
  - Change `section_id` from `Mapped[int]` to `Mapped[int | None]`, add `nullable=True`
  - Change FK from `ondelete="CASCADE"` to `ondelete="SET NULL"`
  - Add `is_stale: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")`
  - Add `eval_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)`
  - Add `likely_cause: Mapped[str | None] = mapped_column(String(50), nullable=True)`
  - Add `suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)`
  - Make `prompt_sent` nullable: `Mapped[str | None]` (for deterministic assertions)

- [ ] `BookSection` model (`models.py` lines 164-201):
  - Add `section_type: Mapped[str] = mapped_column(String(50), default="chapter", server_default="chapter")`

- [ ] `Summary` model (`models.py` lines 312-341):
  - Add `quality_warnings: Mapped[dict | None] = mapped_column(JSON, nullable=True)`
  - Add `retry_of_id: Mapped[int | None] = mapped_column(ForeignKey("summaries.id", ondelete="SET NULL"), nullable=True)`

- [ ] Add `SectionType` enum class in `models.py`:
  ```python
  class SectionType(str, enum.Enum):
      CHAPTER = "chapter"
      FOREWORD = "foreword"
      PREFACE = "preface"
      INTRODUCTION = "introduction"
      GLOSSARY = "glossary"
      NOTES = "notes"
      APPENDIX = "appendix"
      BIBLIOGRAPHY = "bibliography"
      INDEX = "index"
      ABOUT_AUTHOR = "about_author"
      EPILOGUE = "epilogue"
      CONCLUSION = "conclusion"
      OTHER = "other"
  ```

**1b. Generate and verify Alembic migration**

- [ ] Run: `cd backend && uv run alembic revision --autogenerate -m "V1.3 eval improvements"`
- [ ] **Manually verify** the generated migration:
  - FK change order: DROP CONSTRAINT → ALTER COLUMN nullable → ADD CONSTRAINT (see spec §15)
  - Partial index `ix_eval_traces_is_stale` with `WHERE is_stale = FALSE`
  - Index on `eval_run_id`
  - Index on `section_type`
  - Self-referential FK on `summaries.retry_of_id`
  - No pgvector import issues (gotcha #8)
- [ ] Run migration on dev DB: `uv run alembic upgrade head`
- [ ] Run migration on test DB: `BOOKCOMPANION_DATABASE__URL=postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test uv run alembic upgrade head`

**1c. Verify migration**

- [ ] Connect to dev DB and verify:
  ```bash
  docker exec bookcompanion-db psql -U bookcompanion -c "\d eval_traces"
  docker exec bookcompanion-db psql -U bookcompanion -c "\d book_sections"
  docker exec bookcompanion-db psql -U bookcompanion -c "\d summaries"
  ```
- [ ] Verify FK change: `docker exec bookcompanion-db psql -U bookcompanion -c "SELECT conname, confdeltype FROM pg_constraint WHERE conname = 'eval_traces_section_id_fkey';"`
  - Should show `confdeltype = 'n'` (SET NULL)
- [ ] Run existing test suite to confirm no regressions: `cd backend && uv run python -m pytest tests/ -v`

---

## Task 2: Deterministic `reasonable_length` Assertion (Change 2)

**Goal:** Replace LLM-based length check with pure math. Fixes the code bug where compression variables were never populated.

**Files:**
- Modify: `backend/app/services/summarizer/evaluator.py`
- Create: `backend/tests/unit/test_eval_deterministic.py`

### Steps

- [ ] In `evaluator.py`, add constant: `DETERMINISTIC_ASSERTIONS = {"reasonable_length", "has_key_concepts", "image_refs_preserved"}`
- [ ] Implement `_check_reasonable_length()` method on `EvalService` (spec §2.3):
  - Accept: `source_text, summary_text, facets_used, section_id, summary_id, eval_run_id`
  - Call existing `_get_compression_range(facets_used)` — already exists at lines 56-67
  - Apply ±50% tolerance band
  - Floor of 50 chars for `min_chars` (short sections)
  - Handle edge cases: empty source (pass), empty summary (fail), no facets (default standard)
  - Create `EvalTrace` with `model_used="deterministic"`, `prompt_sent=None`, `latency_ms=0`
  - Set `likely_cause` and `suggestion` programmatically on failure
  - Return dict with `assertion_name, category, passed, reasoning`

- [ ] Write tests in `test_eval_deterministic.py`:
  - `test_reasonable_length_within_range` — 20% ratio with standard compression
  - `test_reasonable_length_too_short` — 2% ratio with standard compression
  - `test_reasonable_length_too_long` — 80% ratio with standard compression
  - `test_reasonable_length_empty_source` — empty source passes
  - `test_reasonable_length_empty_summary` — empty summary fails
  - `test_reasonable_length_brief_preset` — 8% passes for brief
  - `test_reasonable_length_detailed_preset` — 35% passes for detailed
  - `test_reasonable_length_tweet_thread` — 5% passes for tweet_thread
  - `test_reasonable_length_no_facets_defaults_standard` — missing facets defaults to standard
  - `test_reasonable_length_short_section_floor` — very short source uses 50-char floor

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_deterministic.py -v`

---

## Task 3: Deterministic `has_key_concepts` Assertion (Change 1 partial)

**Goal:** Convert from LLM-based to regex pattern matching.

**Files:**
- Modify: `backend/app/services/summarizer/evaluator.py`
- Extend: `backend/tests/unit/test_eval_deterministic.py`

### Steps

- [ ] Implement `_check_has_key_concepts()` method on `EvalService` (spec §14):
  - Check heading patterns: `## Key Concepts`, `**Key Concepts**`, `### Concepts`, `## Core Ideas`, etc.
  - Check definition-list patterns: `**Term**: Description` (3+ occurrences)
  - Check structured bullet groups with bold lead terms (3+ occurrences)
  - Create `EvalTrace` with `model_used="deterministic"`
  - Set diagnostic fields on failure: `likely_cause="format_mismatch"`, `suggestion="Add a 'Key Concepts' section heading..."`
  - Return result dict

- [ ] Add tests:
  - `test_has_key_concepts_heading_found` — `## Key Concepts` heading passes
  - `test_has_key_concepts_core_ideas_heading` — `## Core Ideas` variant passes
  - `test_has_key_concepts_bold_terms` — 3+ `**Term**: description` passes
  - `test_has_key_concepts_two_bold_terms` — only 2 bold terms fails
  - `test_has_key_concepts_no_structure` — plain prose fails
  - `test_has_key_concepts_bullets_with_bold_leads` — bullet-point with bold leads passes

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_deterministic.py -v`

---

## Task 4: Deterministic `image_refs_preserved` Assertion (Change 1 partial)

**Goal:** Convert from LLM-based to regex keyword matching.

**Files:**
- Modify: `backend/app/services/summarizer/evaluator.py`
- Extend: `backend/tests/unit/test_eval_deterministic.py`

### Steps

- [ ] Implement `_check_image_refs_preserved()` method on `EvalService` (spec §14):
  - Count images in source via regex: `![`, `<img`, image extensions
  - Also use `image_count` parameter (max of both)
  - If no images: pass with "nothing to preserve"
  - If images exist: check summary for visual reference keywords (figure, diagram, chart, image, illustration, table, graph, photo, visual)
  - Create `EvalTrace`, set diagnostic fields on failure
  - Return result dict

- [ ] Add tests:
  - `test_image_refs_no_images` — source without images always passes
  - `test_image_refs_images_mentioned` — source with images + "diagram" in summary passes
  - `test_image_refs_images_not_mentioned` — source with images + no visual keywords fails
  - `test_image_refs_uses_image_count_param` — `image_count=3` with no source patterns still checks summary

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_deterministic.py -v`

---

## Task 5: Preset-Aware Assertion Skipping (Change 1)

**Goal:** Add `skip_assertions` to preset YAML files. EvalService loads and applies skip lists.

**Files:**
- Modify: `backend/app/services/summarizer/prompts/presets/practitioner_bullets.yaml`
- Modify: `backend/app/services/summarizer/prompts/presets/executive_brief.yaml`
- Modify: `backend/app/services/summarizer/prompts/presets/tweet_thread.yaml`
- Modify: `backend/app/services/summarizer/prompts/presets/study_guide.yaml`
- Modify: `backend/app/services/summarizer/prompts/presets/academic_detailed.yaml`
- Modify: `backend/app/services/preset_service.py`
- Modify: `backend/app/services/summarizer/evaluator.py`
- Extend: `backend/tests/unit/test_preset_service.py`
- Create: `backend/tests/unit/test_eval_service.py`

### Steps

**5a. Update preset YAML files**

- [ ] `practitioner_bullets.yaml`: Add `skip_assertions: [has_key_concepts]`
- [ ] `executive_brief.yaml`: Add `skip_assertions: [has_key_concepts]`
- [ ] `tweet_thread.yaml`: Add `skip_assertions: [has_key_concepts, image_refs_preserved]`
- [ ] `study_guide.yaml`: Add `skip_assertions: []` (explicit empty)
- [ ] `academic_detailed.yaml`: Add `skip_assertions: []` (explicit empty)

**5b. Update PresetService**

- [ ] In `_parse_file()` (line ~128): Extract `skip_assertions` from YAML data, default to empty list
- [ ] Add validation: warn on unknown assertion names (check against `ASSERTION_REGISTRY` keys), don't error
- [ ] Warn if >12 assertions skipped

**5c. Update EvalService**

- [ ] Add `_load_skip_assertions(preset_name: str | None) -> set[str]` method:
  - Load preset YAML directly from `self._presets_dir` (avoid PresetService dependency)
  - Return `skip_assertions` set, empty if no preset or no field
- [ ] Add `_skipped_result()` helper that creates EvalTrace with `passed=True`, `reasoning="Skipped: not applicable for preset '{preset_name}'"`, `model_used="skipped"`

**5d. Update style fragments for presets that keep `has_key_concepts`**

- [ ] `fragments/style/study_guide.txt`: Add Key Concepts section instruction (spec §1.5)
- [ ] `fragments/style/academic_detailed.txt`: Add Key Concepts section instruction (spec §1.5)

**5e. Tests**

- [ ] Extend `test_preset_service.py`:
  - `test_load_preset_with_skip_assertions` — YAML with skip_assertions loads correctly
  - `test_load_preset_without_skip_assertions` — YAML without field returns empty list
  - `test_invalid_assertion_name_warns` — unknown assertion name logs warning (use caplog)

- [ ] Create `test_eval_service.py`:
  - `test_preset_skip_assertions` — assertions in skip list return passed + skipped
  - `test_preset_no_skip_list` — preset without skip_assertions runs all
  - `test_preset_none_no_skip` — no preset skips nothing
  - `test_unknown_assertion_in_skip_list_ignored` — unknown name logged, not crashed

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_preset_service.py tests/unit/test_eval_service.py -v`

---

## Task 6: Section-Type Auto-Detection (Change 5)

**Goal:** Add `section_type` field to `BookSection` with auto-detection during EPUB parsing.

**Files:**
- Modify: `backend/app/services/parser/epub_parser.py`
- Create: `backend/tests/unit/test_section_type.py`

### Steps

- [ ] Add `SECTION_TYPE_PATTERNS` dict in `epub_parser.py` (spec §5.4):
  - Map `SectionType` enum values to compiled regex patterns
  - Patterns: glossary, notes, appendix, bibliography, index, about_author, foreword, preface, introduction, epilogue, conclusion
  - Default: `SectionType.CHAPTER`

- [ ] Add `_detect_section_type(title: str) -> str` static method:
  - Iterate patterns, return first match
  - Return `"chapter"` as default

- [ ] Call `_detect_section_type()` in `_add_section()` (line ~321) when creating `ParsedSection`
  - Store as `section_type` attribute on the ParsedSection

- [ ] In `BookService.add_book()` / section creation: pass `section_type` from ParsedSection to BookSection model

- [ ] Write tests in `test_section_type.py`:
  - `test_detect_glossary` — "Glossary" → `"glossary"`
  - `test_detect_notes` — "Chapter Notes" → `"notes"`
  - `test_detect_endnotes` — "Endnotes" → `"notes"`
  - `test_detect_about_author` — "About the Author" → `"about_author"`
  - `test_detect_default_chapter` — "Chapter 3: Strategy" → `"chapter"`
  - `test_detect_case_insensitive` — "APPENDIX A" → `"appendix"`
  - `test_detect_introduction` — "Introduction" → `"introduction"`
  - `test_detect_foreword` — "Foreword" → `"foreword"`
  - `test_detect_bibliography` — "Works Cited" → `"bibliography"`

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_section_type.py -v`

---

## Task 7: Section-Type-Aware Eval + Edit Sections (Change 5 continued)

**Goal:** Make eval assertions section-type-aware for reference-type sections. Add section_type to editable fields.

**Files:**
- Modify: `backend/app/services/summarizer/evaluator.py`
- Modify: `backend/app/services/summarizer/prompts/eval_completeness_v1.txt`
- Modify: `backend/app/services/section_edit_service.py` (add section_type to editable fields)
- Extend: `backend/tests/unit/test_eval_service.py`

### Steps

- [ ] Define reference-type sections constant in `evaluator.py`:
  ```python
  REFERENCE_SECTION_TYPES = {"glossary", "notes", "bibliography", "index", "appendix"}
  ```

- [ ] Update `_run_single_assertion()` to accept `section_type` parameter and pass to template context

- [ ] Update `eval_completeness_v1.txt` template:
  - Add conditional block for reference sections:
    ```jinja2
    {% if section_type in ["glossary", "notes", "bibliography", "index", "appendix"] %}
    This is a {{ section_type }} section. Evaluate coverage of the MAJOR frameworks only...
    {% endif %}
    ```
  - For reference sections, `covers_examples` should be skipped (add to dynamic skip list in `evaluate_summary()`)

- [ ] Update `section_edit_service.py`: Add `section_type` as an editable field in the REPL

- [ ] Add tests:
  - `test_section_type_injected_in_completeness` — section type appears in rendered completeness prompt
  - `test_reference_section_skips_covers_examples` — glossary section skips `covers_examples`
  - `test_chapter_type_no_skip` — chapter sections don't skip any completeness assertions

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_service.py -v`

---

## Task 8: Diagnostic Eval Reasoning (Change 9)

**Goal:** Add `likely_cause` and `suggestion` fields to eval LLM responses and traces.

**Files:**
- Modify: `backend/app/services/summarizer/evaluator.py`
- Modify: `backend/app/services/summarizer/prompts/eval_faithfulness_v1.txt`
- Modify: `backend/app/services/summarizer/prompts/eval_completeness_v1.txt`
- Modify: `backend/app/services/summarizer/prompts/eval_coherence_v1.txt`
- Modify: `backend/app/services/summarizer/prompts/eval_specificity_v1.txt`
- Extend: `backend/tests/unit/test_eval_service.py`

### Steps

**8a. Update JSON schema for LLM eval calls**

- [ ] In `_run_single_assertion()`, update the JSON schema passed to `llm.generate()`:
  ```python
  json_schema = {
      "type": "object",
      "properties": {
          "passed": {"type": "boolean"},
          "reasoning": {"type": "string"},
          "likely_cause": {"type": ["string", "null"]},
          "suggestion": {"type": ["string", "null"]},
      },
      "required": ["passed", "reasoning"],
  }
  ```

**8b. Update all eval prompt templates**

- [ ] Add diagnostic instruction block to all 4 active eval templates (faithfulness, completeness, coherence, specificity):
  ```
  If the assertion FAILS, also provide:
  - "likely_cause": one of "content_quality", "scope_mismatch", "format_mismatch", "insufficient_data"
  - "suggestion": one-line actionable fix recommendation
  If the assertion PASSES, set both to null.
  ```

**8c. Update trace storage**

- [ ] In `_run_single_assertion()`, after parsing LLM response:
  - Extract `likely_cause` and `suggestion` from result
  - Store on EvalTrace: `likely_cause=result.get("likely_cause")`, `suggestion=result.get("suggestion")`
  - Handle missing fields gracefully (default to None)

**8d. Tests**

- [ ] Add tests:
  - `test_diagnostic_fields_stored` — mock LLM returns likely_cause + suggestion, verify stored on trace
  - `test_diagnostic_fields_null_on_pass` — passing assertion has null diagnostic fields
  - `test_diagnostic_fields_missing_graceful` — LLM omits fields, no crash

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_service.py -v`

---

## Task 9: Cumulative Context for Faithfulness Eval (Change 3)

**Goal:** Pass prior section summaries as context to faithfulness eval assertions, eliminating false-positive hallucination flags.

**Files:**
- Modify: `backend/app/services/summarizer/evaluator.py`
- Modify: `backend/app/services/summarizer/prompts/eval_faithfulness_v1.txt`
- Extend: `backend/tests/unit/test_eval_service.py`

### Steps

**9a. Update `evaluate_summary()` signature**

- [ ] Add `cumulative_context: str | None = None` parameter
- [ ] Add `section_type: str = "chapter"` parameter
- [ ] Add `eval_scope: str = "section"` parameter (for book-level eval, Task 12)
- [ ] Add `preset_name: str | None = None` parameter (for skip lookup, Task 5)

**9b. Route cumulative context to faithfulness assertions only**

- [ ] Define constant: `FAITHFULNESS_ASSERTIONS = {"no_hallucinated_facts", "no_contradictions", "accurate_quotes", "cross_summary_consistency"}`
- [ ] In assertion dispatch, pass `cumulative_context` only when `assertion_name in FAITHFULNESS_ASSERTIONS`
- [ ] Update `_run_single_assertion()` to accept and forward `cumulative_context` to template

**9c. Update faithfulness prompt template**

- [ ] Add cumulative context block to `eval_faithfulness_v1.txt` (spec §3.4.3):
  - Conditional `{% if cumulative_context %}` block before source text
  - Hard vs soft hallucination distinction for `no_hallucinated_facts` (spec §3.4.4)

- [ ] Truncation: If cumulative context > 20K chars, truncate with note

**9d. Tests**

- [ ] Add tests:
  - `test_cumulative_context_passed_to_faithfulness` — faithfulness prompt includes cumulative context
  - `test_cumulative_context_not_passed_to_completeness` — completeness prompt does not include it
  - `test_cumulative_context_truncated_at_20k` — long context gets truncated
  - `test_cumulative_context_none_for_first_section` — None context works (no template error)

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_service.py -v`

---

## Task 10: Eval Pipeline Overhaul — Dispatch Logic + eval_run_id + eval_json Derivation (Changes 8, 9 partial)

**Goal:** Rewrite `evaluate_summary()` with the consolidated dispatch logic: deterministic vs LLM routing, skip list merge, eval_run_id grouping, and eval_json derivation from traces.

**Files:**
- Modify: `backend/app/services/summarizer/evaluator.py`
- Modify: `backend/app/db/repositories/eval_repo.py`
- Extend: `backend/tests/unit/test_eval_service.py`

### Steps

**10a. Implement consolidated dispatch in `evaluate_summary()`**

- [ ] Generate `eval_run_id = str(uuid.uuid4())` at start of each call
- [ ] Compute combined skip list: preset skips + book-level skips (if `eval_scope == "book"`)
- [ ] For reference sections, dynamically add `covers_examples` to skip list
- [ ] Route each assertion:
  - Skipped → `_skipped_result()` (sync, returns dict)
  - Deterministic → `_run_deterministic()` dispatcher (sync)
  - LLM-based → `_run_single_assertion()` (async, with cumulative_context for faithfulness)
- [ ] Gather async results via `asyncio.gather(return_exceptions=True)`
- [ ] Handle exceptions in gather results: mark as error, don't crash

**10b. Implement `_compute_eval_json()`**

- [ ] Query all EvalTrace rows for the given `eval_run_id`
- [ ] Aggregate into spec format: `{passed: int, total: int, eval_run_id: str, assertions: {name: {assertion_name, category, passed, reasoning, likely_cause, suggestion}}}`
- [ ] Store on Summary: `summary.eval_json = eval_json`

**10c. Deprecate `eval_format_v1.txt`**

- [ ] Add deprecation comment at top of `eval_format_v1.txt`: `{# DEPRECATED: All format assertions are now deterministic. See evaluator.py. #}`

**10d. Update eval_repo queries**

- [ ] All existing queries in `eval_repo.py` add `WHERE is_stale = FALSE` by default
- [ ] Add `include_stale: bool = False` parameter to `get_by_section()`, `get_by_summary()`, `get_aggregated_results()`
- [ ] Add `get_by_eval_run_id(eval_run_id: str) -> list[EvalTrace]` method

**10e. Update return format**

- [ ] `evaluate_summary()` now returns the wrapped format (with `assertions` key), not flat dict
- [ ] Update all callers to consume new format:
  - `eval_cmd.py` — reads `eval_results["assertions"]` for display
  - `summarize_cmd.py` — stores as `summary.eval_json`

**10f. Tests**

- [ ] Add tests:
  - `test_eval_run_id_groups_traces` — all traces share same UUID
  - `test_eval_json_derived_from_traces` — `_compute_eval_json()` output matches expected format
  - `test_dispatch_routes_deterministic` — reasonable_length, has_key_concepts, image_refs go to deterministic
  - `test_dispatch_routes_llm` — faithfulness assertions go to LLM
  - `test_dispatch_routes_skipped` — skipped assertions produce skipped traces
  - `test_stale_traces_excluded` — default queries exclude stale traces
  - `test_book_level_skip_assertions` — book scope skips image_refs + cross_summary_consistency
  - `test_exception_in_assertion_doesnt_crash` — one assertion error doesn't kill the whole eval

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_service.py tests/unit/test_eval_deterministic.py -v`

---

## Task 11: Cascade-Safe Eval Traces + Re-Import Warning (Change 8)

**Goal:** Make re-import mark traces as stale instead of deleting. Add confirmation prompt.

**Files:**
- Modify: `backend/app/services/book_service.py`
- Modify: `backend/app/cli/commands/books.py` (add_cmd)
- Create: `backend/tests/integration/test_eval_cascade.py`

### Steps

**11a. Update `_re_import_book()`**

- [ ] Before deleting sections (line ~259), for each section being removed:
  ```python
  await session.execute(
      update(EvalTrace)
      .where(EvalTrace.section_id == section_id)
      .values(is_stale=True)
  )
  ```
  - This must happen **before** the DELETE so `section_id` is still set for the WHERE clause
  - The FK SET NULL will then null out `section_id` on the actual DELETE

**11b. Add re-import confirmation**

- [ ] In `books.py` `add()` function, before calling `_re_import_book()`:
  - Count eval traces: `SELECT COUNT(*) FROM eval_traces WHERE section_id IN (book's section IDs)`
  - Count summaries: `SELECT COUNT(*) FROM summaries WHERE book_id = book.id`
  - If either > 0: prompt `"This book has {N} eval traces and {M} summaries. Re-import will mark traces as stale. Proceed? [y/N]"`
  - Use `typer.confirm()` for the prompt
  - Abort if declined

**11c. Integration tests**

- [ ] Create `test_eval_cascade.py`:
  - `test_section_delete_sets_trace_stale` — delete section, verify trace has `is_stale=True` and `section_id=NULL`
  - `test_stale_traces_excluded_by_default` — `get_by_section()` excludes stale
  - `test_re_import_preserves_traces` — re-import marks traces stale, doesn't delete
  - `test_eval_json_matches_traces` — after eval, Summary.eval_json matches aggregated traces

- [ ] Run: `cd backend && uv run python -m pytest tests/integration/test_eval_cascade.py -v`

---

## Task 12: Book-Level Summary Evaluation (Change 7)

**Goal:** Auto-trigger eval after book-level summary generation with modified assertion subset.

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py`
- Modify: `backend/app/services/summarizer/prompts/eval_completeness_v1.txt`
- Modify: `backend/app/cli/commands/eval_cmd.py`
- Extend: `backend/tests/unit/test_eval_service.py`

### Steps

**12a. Define book-level skip list**

- [ ] In `evaluator.py`, add constant:
  ```python
  BOOK_LEVEL_SKIP = {"image_refs_preserved", "cross_summary_consistency"}
  ```
  (Already used in dispatch logic from Task 10)

**12b. Update completeness prompt for book scope**

- [ ] Add `eval_scope` to template context in `_run_single_assertion()`
- [ ] In `eval_completeness_v1.txt`, add:
  ```jinja2
  {% if eval_scope == "book" %}
  This is a BOOK-LEVEL summary synthesizing {{ section_count }} section summaries.
  Evaluate whether the summary provides representative coverage across major chapters and themes.
  It should NOT exhaustively list every concept from every section.
  {% endif %}
  ```

**12c. Auto-trigger eval in `_generate_book_summary()`**

- [ ] After generating book-level summary in `summarizer_service.py`:
  - Build source context from section summaries (as per spec §7.2.2)
  - If `eval_service` is available and `not skip_eval`: call `evaluate_summary()` with `eval_scope="book"`
  - Store eval_json on book-level Summary

**12d. Update eval CLI for book-level display**

- [ ] In `eval_cmd.py`, the book-level view (no section_id):
  - Also display book-level summary eval results if they exist
  - Add `--book-only` flag to show only book-level results
  - Add `--force` flag to re-run eval (mark old traces as stale, create new ones)

**12e. Tests**

- [ ] Add tests:
  - `test_book_level_eval_skip_list` — book scope skips correct assertions
  - `test_book_level_completeness_prompt` — book scope prompt includes section_count
  - `test_book_level_eval_triggered` — book summary generation triggers eval

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_service.py -v`

---

## Task 13: Summarizer Prompt Changes — Quote + Numeric Guidance (Changes 4, 6)

**Goal:** Add prompt guidance to prevent paraphrased quotes and numeric inaccuracies.

**Files:**
- Modify: `backend/app/services/summarizer/prompts/base/summarize_section.txt`

### Steps

- [ ] Add quote attribution guidance to output instructions section (spec §4.2.1):
  ```
  When attributing a statement to a specific person, either quote verbatim from the source
  or paraphrase without quotation marks. Do not place paraphrased content in quotation marks.
  ```

- [ ] Add numeric accuracy guidance (spec §6):
  ```
  When converting percentages or premiums to multipliers, be precise: a '300% premium' means
  the premium is 3x, making the total price 4x the base.
  ```

- [ ] Run existing summarizer tests to verify no regression: `cd backend && uv run python -m pytest tests/unit/test_summarizer.py -v`

---

## Task 14: Paraphrased Quote Detection Post-Check (Change 4)

**Goal:** Implement deterministic post-processing check for paraphrased quotes in summaries.

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py`
- Extend: `backend/tests/unit/test_eval_deterministic.py`

### Steps

- [ ] Implement `_check_paraphrased_quotes(source_text: str, summary_text: str) -> list[dict]`:
  - Extract double-quoted strings from summary: regex `"([^"]{10,200})"`
  - For each quote: check exact substring match in source (pass if found)
  - If no exact match: sliding-window fuzzy match using `difflib.SequenceMatcher`
    - Window size = quote word count + 2 words margin
    - Threshold = 0.85
  - Strip markdown from source before comparison
  - Return list of warning dicts: `{type, quote, best_match, similarity, message}`

- [ ] In `_summarize_single_section()`, after extracting summary text:
  - Call `_check_paraphrased_quotes(section.content_md, summary_text)`
  - Store warnings in `summary.quality_warnings = {"paraphrased_quotes": warnings}` if non-empty

- [ ] Add tests:
  - `test_paraphrased_quote_exact_match` — verbatim quote returns no warning
  - `test_paraphrased_quote_paraphrased` — paraphrased quote returns warning with similarity
  - `test_paraphrased_quote_no_quotes` — no quotes returns empty list
  - `test_paraphrased_quote_short_excluded` — quotes < 10 chars excluded
  - `test_paraphrased_quote_markdown_stripped` — markdown formatting doesn't break matching

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_deterministic.py -v`

---

## Task 15: Auto-Retry — Core Logic (Change 10)

**Goal:** Implement `_should_retry()`, `_build_fix_prompt()`, and `fix_instructions` parameter.

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py`
- Create: `backend/tests/unit/test_auto_retry.py`

### Steps

**15a. Implement retry helpers in `SummarizerService`**

- [ ] Add constant: `RETRY_ELIGIBLE_CATEGORIES = {"critical", "important"}`

- [ ] Implement `_should_retry(eval_results: dict) -> bool` (spec §10.5):
  - Iterate `eval_results["assertions"]`
  - Skip entries with `skipped: true` or `error: true`
  - Return True if any critical/important assertion failed

- [ ] Implement `_build_fix_prompt(eval_results: dict) -> str` (spec §10.5):
  - Collect failing critical/important assertions
  - Use `suggestion` field, fallback to generic message
  - Return formatted fix instruction string

**15b. Add `fix_instructions` to `_summarize_single_section()`**

- [ ] Add parameter `fix_instructions: str | None = None`
- [ ] When provided, append to rendered prompt: `prompt = f"{prompt}\n\n{fix_instructions}"`

**15c. Add `retry_of_id` support**

- [ ] After creating retry summary, set `retry_summary.retry_of_id = original_summary.id`

**15d. Tests**

- [ ] Create `test_auto_retry.py`:
  - `test_should_retry_critical_failure` — critical fail → True
  - `test_should_retry_important_failure` — important fail → True
  - `test_should_retry_advisory_only` — advisory-only fail → False
  - `test_should_retry_all_pass` — all pass → False
  - `test_should_retry_skipped_ignored` — skipped critical doesn't trigger
  - `test_should_retry_error_ignored` — error entries don't trigger
  - `test_build_fix_prompt_uses_suggestions` — suggestions appear in output
  - `test_build_fix_prompt_null_suggestion_fallback` — null suggestion → generic message
  - `test_build_fix_prompt_multiple_failures` — multi-line output
  - `test_fix_instructions_appended_to_prompt` — verify appended after full prompt
  - `test_retry_summary_has_retry_of_id` — FK set correctly

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_auto_retry.py -v`

---

## Task 16: Auto-Retry — Batch Loop Integration (Change 10)

**Goal:** Restructure `summarize_book()` for inline eval + retry per section.

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py`
- Modify: `backend/app/cli/commands/summarize_cmd.py`
- Create: `backend/tests/integration/test_auto_retry.py`

### Steps

**16a. Update `summarize_book()` signature**

- [ ] Add parameters (spec §10.4.2):
  - `no_retry: bool = False`
  - `eval_service: "EvalService | None" = None`
  - `on_section_retry: Callable | None = None`
- [ ] Add `retried_sections: list[int]` tracking list
- [ ] Update return dict to include `"retried": retried_sections`

**16b. Restructure per-section loop**

- [ ] After `_summarize_single_section()` and `update_default_summary()`:
  1. If `not skip_eval and eval_service`: call `eval_service.evaluate_summary()` with cumulative_context
  2. If `not no_retry and self._should_retry(eval_results)`:
     - Build fix prompt
     - Re-summarize with `fix_instructions`
     - Set `retry_summary.retry_of_id = summary.id`
     - Update default_summary_id to retry
     - Re-eval the retry summary
     - Use retry summary for cumulative context
     - Call `on_section_retry` callback
  3. Add best available summary to `cumulative_parts`

**16c. Book-level summary retry**

- [ ] After `_generate_book_summary()`, if eval fails critical/important:
  - Same retry logic as sections
  - No cumulative context implications (it's the final step)

**16d. Update CLI**

- [ ] Add `--no-retry` flag to `summarize` command
- [ ] `--skip-eval` implicitly disables retry
- [ ] Pass `eval_service=svc.get("eval") if not skip_eval else None` to `summarize_book()`
- [ ] Add `on_section_retry` callback for progress output (spec §10.8.2)
- [ ] Single-section mode: same inline eval + retry logic (spec §10.4.1)

**16e. Integration tests**

- [ ] Create `test_auto_retry.py` (integration):
  - `test_retry_creates_new_summary` — retry produces second Summary, original preserved
  - `test_retry_becomes_default` — default_summary_id updated
  - `test_retry_of_id_set` — FK correct
  - `test_no_retry_when_skip_eval` — skip_eval disables retry
  - `test_no_retry_when_no_retry_flag` — no_retry flag works
  - `test_batch_retry_feeds_cumulative_context` — improved summary in cumulative context
  - `test_retry_on_exception_preserves_original` — LLM error keeps original
  - `test_batch_stats_include_retried` — return dict has retried list

- [ ] Run: `cd backend && uv run python -m pytest tests/integration/test_auto_retry.py -v`

---

## Task 17: CLI Polish — Eval Display + Summary Commands (Phase F)

**Goal:** Update eval display for diagnostic fields, book-level results, quality warnings, retry lineage.

**Files:**
- Modify: `backend/app/cli/commands/eval_cmd.py`
- Modify: `backend/app/cli/commands/summary_cmds.py`
- Modify: `backend/app/cli/formatting.py`

### Steps

**17a. Update eval_cmd.py**

- [ ] Section-detailed view: Add `likely_cause` and `suggestion` columns to assertion table
- [ ] Book-level view: Display book-level summary eval alongside section summaries
- [ ] Add `--book-only` flag
- [ ] Add `--force` flag: re-run eval, mark old traces as stale, create new ones

**17b. Update summary commands**

- [ ] `summary show`: Display `quality_warnings` section if non-empty (spec §4.4):
  ```
  Warning: Quality Warnings:
    - Paraphrased quote detected: "airlines increased costs 25%..." (42% match)
  ```
- [ ] `summary list`: Show "(retry of #N)" label for retry summaries (check `retry_of_id`)

**17c. Update formatting.py**

- [ ] `eval_status()`: Handle new wrapped format with `assertions` key
- [ ] `eval_results()`: Same wrapped format handling

**17d. Run existing CLI tests**

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_display.py tests/e2e/ -v`

---

## Task 18: Cumulative Context in Standalone Eval CLI

**Goal:** When `eval <book_id> <section_id>` is run standalone (not post-summarization), build cumulative context from prior section summaries.

**Files:**
- Modify: `backend/app/cli/commands/eval_cmd.py`

### Steps

- [ ] In `eval_cmd` when running eval on a specific section:
  - Fetch book's sections ordered by `order_index`
  - Build cumulative context from sections with `order_index < current` that have a default summary
  - Truncate each to 500 chars, join with newlines (spec §3.4.2)
  - Pass as `cumulative_context` to `evaluate_summary()`

- [ ] For book-level eval:
  - Build source context from all section summaries (spec §7.2.2)
  - No cumulative context needed

- [ ] Run: `cd backend && uv run python -m pytest tests/unit/test_eval_service.py -v`

---

## Task 19: Golden Set Test Fixtures

**Goal:** Create golden set test fixtures from book 2 data for regression testing.

**Files:**
- Create: `backend/tests/fixtures/golden_eval/` directory
- Create: `backend/tests/fixtures/golden_eval/README.md`
- Create: `backend/tests/integration/test_eval_golden_set.py`

### Steps

- [ ] Create fixture directory structure

- [ ] Create synthetic golden set fixtures (since we can't extract from DB in plan):
  - `book2_section_all_pass.json` — section with content that should pass all deterministic assertions
  - `book2_section_hallucination.json` — section with cross-chapter reference (tests cumulative context)
  - `book2_section_paraphrased_quote.json` — section with paraphrased quote
  - `book2_section_glossary.json` — glossary section (tests section-type thresholds)
  - Each fixture: `{source_text, summary_text, cumulative_context, facets_used, section_type, preset_name, expected_deterministic_results}`

- [ ] Write golden set tests:
  - `test_golden_deterministic_all_pass` — all-pass fixture passes deterministic assertions
  - `test_golden_reasonable_length_pass` — fixture ratio within range
  - `test_golden_glossary_skips_examples` — glossary fixture skips covers_examples
  - `test_golden_paraphrased_quote_detected` — quote fixture produces warning
  - `test_golden_preset_skips_key_concepts` — practitioner_bullets skips has_key_concepts

- [ ] Run: `cd backend && uv run python -m pytest tests/integration/test_eval_golden_set.py -v`

---

## Task 20: Full Test Suite + Linting + Documentation Updates

**Goal:** Run all tests, fix regressions, update documentation.

**Files:**
- Modify: `backend/CLAUDE.md` (or project root)
- Potentially fix any files with test failures

### Steps

**20a. Run full test suite**

- [ ] `cd backend && uv run python -m pytest tests/ -v`
- [ ] Fix any failures — iterate until green

**20b. Linting and formatting**

- [ ] `cd backend && uv run ruff check .`
- [ ] `cd backend && uv run ruff format --check .`
- [ ] Fix any issues: `cd backend && uv run ruff format .`

**20c. Update CLAUDE.md**

- [ ] Update domain terms table: add `Section Type`, `Eval Run ID`, `Golden Set`, `Deterministic Assertion`, `Quality Warning`, `Auto-Retry`
- [ ] Update gotchas: add note about eval_json being derived from traces (D9)
- [ ] Update CLI commands section: add `--no-retry`, `--book-only`, `--force` flags
- [ ] Update architecture diagram: note EvalService changes (deterministic dispatch, skip logic)

**20d. Update spec status**

- [ ] Change spec status from "Draft" to "Implemented"

---

## Task 21: Deploy and Manual Verification

**Goal:** Deploy changes, run migrations, verify with real CLI commands.

### Steps

**21a. Database verification**

- [ ] Ensure Docker is running: `docker compose up -d`
- [ ] Run migrations: `cd backend && uv run alembic upgrade head`
- [ ] Verify schema: inspect eval_traces, book_sections, summaries tables

**21b. CLI command verification**

- [ ] `uv run bookcompanion preset list` — verify presets load with skip_assertions
- [ ] `uv run bookcompanion preset show practitioner_bullets` — verify skip_assertions displayed
- [ ] `uv run bookcompanion --help` — verify no import errors

**21c. Eval system verification (if book 2 exists in DB)**

- [ ] `uv run bookcompanion eval 2` — verify book-level display works
- [ ] `uv run bookcompanion eval 2 <section_id>` — verify diagnostic fields display
- [ ] `uv run bookcompanion summary list 2` — verify retry lineage display

**21d. Re-import confirmation test**

- [ ] `uv run bookcompanion add <book_path> --force` — verify confirmation prompt appears with trace/summary counts

**21e. Summarize with retry (if willing to spend LLM cost)**

- [ ] `uv run bookcompanion summarize 2 <section_id> --preset practitioner_bullets` — verify inline eval + retry flow
- [ ] `uv run bookcompanion summarize 2 <section_id> --no-retry` — verify retry is skipped
- [ ] `uv run bookcompanion summarize 2 <section_id> --skip-eval` — verify eval and retry both skipped

**21f. Quality warnings check**

- [ ] After summarization, check: `uv run bookcompanion summary show <summary_id>` — verify quality_warnings displayed if present

**21g. Final full test run**

- [ ] `cd backend && uv run python -m pytest tests/ -v --tb=short`
- [ ] `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] Confirm all passing, no lint errors

---

## Dependencies

```
Task 1 (Migration + Models)
  ├── Task 2 (reasonable_length deterministic)
  ├── Task 3 (has_key_concepts deterministic)
  ├── Task 4 (image_refs deterministic)
  ├── Task 5 (Preset skip_assertions)
  │     └── needs ASSERTION_REGISTRY from Task 2-4
  ├── Task 6 (Section type detection)
  ├── Task 7 (Section-type-aware eval)
  │     └── needs Task 6 + Task 10
  ├── Task 8 (Diagnostic fields)
  ├── Task 9 (Cumulative context)
  ├── Task 10 (Dispatch logic overhaul)
  │     └── needs Tasks 2-5, 8, 9
  ├── Task 11 (Cascade-safe traces)
  ├── Task 12 (Book-level eval)
  │     └── needs Task 10
  ├── Task 13 (Prompt changes)
  │     └── independent
  ├── Task 14 (Quote detection)
  │     └── independent
  ├── Task 15 (Retry core logic)
  │     └── needs Task 10
  ├── Task 16 (Retry batch integration)
  │     └── needs Tasks 10, 15
  ├── Task 17 (CLI polish)
  │     └── needs Tasks 10, 12, 14, 16
  ├── Task 18 (Standalone eval context)
  │     └── needs Task 9
  ├── Task 19 (Golden set)
  │     └── needs Tasks 2-7, 10, 14
  ├── Task 20 (Full suite + docs)
  │     └── needs all above
  └── Task 21 (Deploy + verify)
        └── needs Task 20
```

**Parallel opportunities:**
- Tasks 2, 3, 4 can run in parallel (independent deterministic assertions)
- Tasks 6, 8, 13, 14 can run in parallel (independent changes)
- Tasks 11, 12 can run in parallel after Task 10
- Tasks 15, 18, 19 can start after Task 10

**Critical path:** 1 → 2-4 → 5 → 9 → 10 → 15 → 16 → 17 → 20 → 21
