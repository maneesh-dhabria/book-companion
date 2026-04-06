# V1.3 Eval System Improvements — Specification

**Date:** 2026-04-05
**Status:** Draft
**Requirements:** [`docs/requirements/2026-04-05_v1_3_eval_improvements.md`](../requirements/2026-04-05_v1_3_eval_improvements.md)
**V1.2 Spec:** [`docs/specs/2026-04-04_v1_2_bugfixes_and_improvements_spec.md`](2026-04-04_v1_2_bugfixes_and_improvements_spec.md)

---

## Table of Contents

1. [Decision Log](#decision-log)
2. [Overview](#overview)
3. [Change 1: Preset-Aware Assertion Skipping (`has_key_concepts`)](#change-1-preset-aware-assertion-skipping)
4. [Change 2: Deterministic `reasonable_length` Check](#change-2-deterministic-reasonable_length-check)
5. [Change 3: Cumulative Context for Faithfulness Eval](#change-3-cumulative-context-for-faithfulness-eval)
6. [Change 4: Paraphrased Quote Detection](#change-4-paraphrased-quote-detection)
7. [Change 5: Section-Type-Aware Eval Thresholds](#change-5-section-type-aware-eval-thresholds)
8. [Change 6: Numeric Accuracy Prompt Guidance](#change-6-numeric-accuracy-prompt-guidance)
9. [Change 7: Book-Level Summary Evaluation](#change-7-book-level-summary-evaluation)
10. [Change 8: Cascade-Safe Eval Traces](#change-8-cascade-safe-eval-traces)
11. [Change 9: Diagnostic Eval Reasoning](#change-9-diagnostic-eval-reasoning)
12. [Change 10: Auto-Retry on Eval Failure](#change-10-auto-retry-on-eval-failure)
13. [Consolidated EvalService Interface](#consolidated-evalservice-interface)
14. [Deterministic Assertion Conversions](#deterministic-assertion-conversions)
15. [Database Migrations](#database-migrations)
16. [Prompt Template Changes](#prompt-template-changes)
17. [Configuration & Preset Changes](#configuration--preset-changes)
18. [Verification Plan](#verification-plan)
19. [Deployment & Rollout](#deployment--rollout)
20. [Risk Mitigation](#risk-mitigation)
21. [Research Sources](#research-sources)

---

## Decision Log

| # | Decision | Options Considered | Choice | Rationale |
|---|----------|--------------------|--------|-----------|
| D1 | Deterministic assertion scope | (A) Only `reasonable_length` (B) 3 assertions: `reasonable_length`, `has_key_concepts`, `image_refs_preserved` (C) Up to 6 assertions including `accurate_quotes`, `no_dangling_references`, `preserves_author_terminology` | **B — 3 assertions** | Deterministic checks are faster (< 10ms), cheaper (zero LLM cost), and 100% reproducible. The 3 selected assertions have clear, codifiable criteria. The remaining assertions genuinely require LLM judgment. Cuts LLM calls from 16 to 13 per eval (~19% cost reduction). |
| D2 | EvalTrace cascade strategy | (A) Link via `summary_id` only (B) `SET NULL` + `is_stale` flag on `section_id` (C) Content-hash decoupling | **B — SET NULL + is_stale** | Preserves traces through section deletes/re-imports. Traces remain queryable by `summary_id` (stable) and `section_id` (if section still exists). `is_stale` flag allows queries to filter appropriately. Simple, reversible, no data loss. |
| D3 | Eval source context for faithfulness | (A) Full raw source up to section N (B) Cumulative section summaries (same as summarizer) (C) Claims-extraction pipeline with BM25 search | **B — Cumulative section summaries** | Matches what the summarizer actually "knew" when generating the summary. Much smaller than raw text (~5-20K chars vs 500K+). Avoids the "hallucination" false positives where the summarizer correctly referenced prior context. Aligns eval and summarizer information scope. |
| D4 | Eval result schema extensions | (A) `likely_cause` + `suggestion` + numeric `score` (float 0-1) (B) `likely_cause` + `suggestion` only (C) Full audit metadata (`eval_run_id`, `config_snapshot`, `source_hash`, weights) | **B + eval_run_id — likely_cause, suggestion, and eval_run_id** | `likely_cause` and `suggestion` directly address the diagnostic gap in Observation 9. Numeric scoring adds complexity without clear benefit for a personal tool. `eval_run_id` is added because it's low-cost (one UUID column) with high utility for grouping and querying. |
| D5 | Preset assertion configuration | (A) `skip_assertions` list in preset YAML (B) `expected_format` map with per-assertion config (C) Auto-detect from facets | **A — skip_assertions list** | Simple, explicit, easy to maintain. Each preset declares which assertions don't apply to its output format. Presets without the field run all assertions. No implicit logic to debug. |
| D6 | Book-level eval assertion set | (A) Same 16 assertions (B) Modified subset (skip inapplicable, adapt completeness) (C) Entirely separate book-level battery | **B — Modified subset** | Some assertions don't apply at book level (`image_refs_preserved`, `cross_summary_consistency`). Completeness assertions should check "representative coverage across chapters" rather than exhaustive listing. Reuses existing assertion infrastructure with a book-level skip list. |
| D7 | Paraphrased quote handling | (A) Prompt guidance only (B) Prompt + deterministic post-check (non-blocking) (C) Prompt + eval-side hybrid check | **B — Prompt + deterministic post-check** | Prompt guidance addresses root cause. Post-check catches remaining issues as non-blocking warnings stored in summary metadata. Doesn't add latency (no re-prompt). The eval's `accurate_quotes` assertion remains as the authoritative quality signal. |
| D8 | Section type tracking | (A) Infer from title heuristics at eval time (B) `section_type` field on `BookSection` model (C) Per-section-type overrides in preset YAML | **B — section_type field** | Explicit, reusable beyond eval (search weighting, export formatting, UI). Set during parsing with title-based auto-detection, overridable via section editing. Requires migration but creates a proper domain concept. |
| D9 | eval_json vs EvalTrace source of truth | (A) Traces as source of truth, eval_json derived (B) eval_json as primary store (C) Keep both independent | **A — Traces as source of truth** | EvalTrace rows contain full audit data (prompt, response, tokens, latency). `eval_json` on Summary becomes a cached denormalization rebuilt from traces. Single source of truth eliminates divergence. |
| D10 | Existing data migration | (A) Re-run evals for book 2 post-deploy (B) Backfill traces from eval_json (C) No backfill | **A — Re-run evals** | Generates fresh EvalTrace rows with new schema fields (`likely_cause`, `suggestion`). Validates all V1.3 fixes against real data. Old eval_json is overwritten. Worth the LLM cost for 17 sections (~221 LLM calls at 13 per section). |
| D11 | Quote post-check behavior | (A) Blocking with re-prompt (B) Non-blocking warning in CLI output (C) Store as quality_warnings field | **B — Non-blocking warning** | Logged in CLI output and stored in summary metadata. Doesn't block or add latency. The eval system remains the authoritative quality gate. |
| D12 | Re-import warning UX | (A) Warning + count with confirmation prompt (B) Warning + JSON export option (C) Silent stale marking | **A — Warning + count** | Since SET NULL + is_stale preserves data, the warning is informational. "'This book has N eval traces and M summaries. Re-import will mark traces as stale. Proceed? [y/N]'" |
| D13 | Golden set testing | (A) Book 2 all-pass sections only (B) All-pass + known-failure sections (C) Synthetic fixtures | **B — All-pass + known-failure** | All-pass sections validate that fixes don't regress working evals. Known-failure sections (91, 93, 96 from requirements) verify the eval correctly catches real issues. Both positive and negative test cases. |
| D14 | Verification approach | (A) Unit + integration only (B) Unit + integration + golden set (C) Full pipeline with real LLM | **B — Unit + integration + golden set** | Unit tests for deterministic assertions and new logic. Mock-LLM integration tests for eval pipeline. Golden set of pre-evaluated summaries from book 2 as regression fixtures. Comprehensive without requiring live LLM calls in CI. |
| D15 | Auto-retry scope | (A) 3 faithfulness only (exclude `cross_summary_consistency`) (B) All 4 critical (C) Critical + important (10 assertions) | **C — Critical + important** | Higher quality bar. 10 of 16 assertions can trigger retry. Advisory assertions (format/coherence) are informational — not worth retry cost. Important assertions (completeness, specificity) are genuine quality signals worth fixing. |
| D16 | Retry fix prompt strategy | (A) Inject `suggestion` fields from eval diagnostics (B) Assertion-specific fix templates (C) Full `reasoning` + `suggestion` | **A — Inject suggestion fields** | Targeted and concise. Uses the diagnostic data from Change 9. Falls back to assertion name if `suggestion` is null. Avoids prompt bloat from full reasoning. |
| D17 | Batch retry timing | (A) After all sections complete (B) Inline — eval + retry before next section (C) Inline eval, deferred retry | **B — Inline** | Retried summary feeds into cumulative context for subsequent sections, so quality propagates forward. Adds ~60-90s eval latency per section but ensures best available context at every step. |
| D18 | Max retries per section | (A) 1 retry (B) 2 retries | **A — 1 retry** | One attempt with a targeted fix prompt. If it still fails, accept the result and flag it. Keeps latency bounded (~3-5 min worst case per section). Most quality issues are fixable in one attempt. |
| D19 | Retry default behavior | (A) On by default, `--no-retry` to disable (B) Off by default, `--retry` to enable | **A — On by default** | Quality matters more than speed for a personal knowledge tool. `--skip-eval` implicitly disables retry too. |
| D20 | Original summary on retry | (A) Keep both, retry becomes default (B) Replace original | **A — Keep both** | Append-only summary log (V1.1 design). Retry summary becomes `default_summary_id`. Original preserved with its eval traces for audit trail. User can revert via `summary set-default`. |

---

## Overview

V1.3 is a comprehensive overhaul of the eval system, driven by analysis of 17 section evaluations on book 2 ("Understanding Michael Porter") using the `practitioner_bullets` preset. Of ~35 total assertion failures, the vast majority trace to three root causes: an eval/prompt contract mismatch (`has_key_concepts`), a code bug (`reasonable_length`), and a context scope mismatch (`no_hallucinated_facts`). Only `accurate_quotes` failures represent genuine summarization quality issues.

**Goals:**
- Eliminate false-positive eval failures caused by system issues (not summary quality)
- Make eval traces cascade-safe so re-imports don't destroy expensive evaluation data
- Add diagnostic fields so failures are actionable without manual investigation
- Enable book-level summary evaluation
- Convert appropriate assertions to deterministic checks for speed and reliability
- Auto-retry summaries that fail critical/important eval assertions with targeted fix prompts

**Scope:**
- All 9 observations from the requirements document + auto-retry on eval failure
- Schema changes: `EvalTrace` (new columns, FK change), `BookSection` (new `section_type`), `Summary` (new `quality_warnings`, `retry_of_id`)
- Prompt changes: summarization templates (quote guidance, numeric accuracy, retry fix instructions) and eval templates (cumulative context, facet injection)
- Service logic: `EvalService`, `SummarizerService` (inline eval + retry loop), `BookService` (re-import warning)
- Preset YAML: `skip_assertions` field
- CLI: re-import confirmation, eval display enhancements, `--no-retry` flag, retry progress output

**Out of scope:**
- New eval assertions beyond the existing 16
- Changes to the search/embedding pipeline
- PDF/MOBI parser changes
- UI/frontend (CLI-only tool)

### LLM Call Budget

V1.3 changes the cost profile significantly due to inline eval and auto-retry.

**Per section:**

| Stage | Current (V1.2) | V1.3 (no retry) | V1.3 (with retry) |
|-------|----------------|------------------|---------------------|
| Summarize | 1 LLM call | 1 LLM call | 1 + 1 retry = 2 |
| Compression retry | 0-1 | 0-1 | 0-1 |
| Eval | 0 (batch) / 16 (single) | 13 LLM + 3 deterministic | 13 + 13 re-eval = 26 LLM |
| **Total per section** | **1-2** (batch) | **14-15** | **28-29** (worst case) |

**Per book (17 sections, ~4 needing retry):**

| Metric | Current (V1.2) | V1.3 |
|--------|----------------|------|
| Summarize calls | 17-18 | 17 + 4 retries = 21 |
| Eval calls | 0 (batch) | 13 × 17 + 13 × 4 = 273 |
| **Total LLM calls** | **~18** | **~294** |
| Estimated cost | ~$1-2 | ~$5-8 |
| Estimated time | ~15-20 min | ~40-50 min |

The cost increase is driven by inline eval (previously not run in batch mode). The `--skip-eval` flag restores V1.2 behavior. `--no-retry` saves ~52 calls for the typical 4-retry scenario.

---

## Change 1: Preset-Aware Assertion Skipping

**Observation:** 1 (`has_key_concepts` near-universal false failure)
**Severity:** High — 15/17 sections fail on a structural check the preset was never designed to produce

### 1.1 Problem

The `eval_format_v1.txt` template checks for a literal "Key Concepts" section. The `practitioner_bullets` preset produces bullet-point summaries organized by theme — structured and useful, but without a dedicated "Key Concepts" heading. The eval penalizes a valid output format.

### 1.2 Solution

Add an optional `skip_assertions` field to preset YAML files. The `EvalService` reads the preset name from the summary being evaluated, loads the preset's `skip_assertions` list, and skips those assertions (returning `passed: true` with reasoning "Skipped: assertion not applicable for preset '{preset_name}'").

### 1.3 Preset YAML Schema Change

```yaml
# practitioner_bullets.yaml
name: Practitioner Bullets
description: Actionable frameworks in scannable bullet format
system: true
facets:
  style: bullet_points
  audience: practitioner
  compression: standard
  content_focus: frameworks_examples
skip_assertions:           # NEW — optional
  - has_key_concepts       # Bullet-point style doesn't use Key Concepts headings
```

**Presets that should skip `has_key_concepts`:** `practitioner_bullets`, `tweet_thread`, `executive_brief` (all non-section-headed formats).

**Presets that should NOT skip it:** `study_guide`, `academic_detailed` (formats that explicitly produce structured sections).

### 1.4 EvalService Changes

**File:** `backend/app/services/summarizer/evaluator.py`

In `evaluate_summary()`:
1. Accept `preset_name: str | None` parameter (already available via `Summary.preset_name`).
2. If `preset_name` is provided, load the preset YAML via `PresetService.load(preset_name)`.
3. Extract `skip_assertions` list (default: empty).
4. For each assertion in the skip list, return immediately with `{"passed": True, "reasoning": "Skipped: not applicable for preset '{preset_name}'", "skipped": True}`.
5. Store skipped assertions in EvalTrace with `passed=True` and a `skipped` flag for auditability.

### 1.5 Prompt Guidance for Presets That Should Produce Key Concepts

Presets where `has_key_concepts` is **not** skipped (e.g., `study_guide`, `academic_detailed`) should explicitly request structured concept presentation in their style fragment. This ensures the summarizer produces the structure the eval expects.

**File:** `backend/app/services/summarizer/prompts/fragments/style/study_guide.txt`

Add: `Include a "## Key Concepts" section listing the major concepts, frameworks, or terms from this section with brief definitions.`

**File:** `backend/app/services/summarizer/prompts/fragments/style/academic_detailed.txt`

Add: `Begin with a "## Key Concepts" section enumerating the principal ideas, theories, or frameworks, each with a one-sentence explanation.`

No changes needed for `practitioner_bullets`, `executive_brief`, or `tweet_thread` — they skip this assertion via `skip_assertions`.

### 1.6 Conversion of `has_key_concepts` to Deterministic

In addition to preset-based skipping, the `has_key_concepts` assertion itself is converted from LLM-based to deterministic (see [Deterministic Assertion Conversions](#deterministic-assertion-conversions)). When not skipped, it checks for structured concept presentation via regex pattern matching rather than LLM judgment.

### 1.7 Edge Cases

- **Preset is None (ad-hoc facets):** No assertions skipped. All 16 run.
- **Preset YAML missing `skip_assertions` field:** Treated as empty list. All assertions run.
- **Unknown assertion name in skip list:** Log a warning, ignore. Don't crash the eval.
- **All assertions skipped:** Technically valid. `eval_json` shows 16/16 passed. This would be a user configuration error — log a warning if >12 assertions are skipped.

---

## Change 2: Deterministic `reasonable_length` Check

**Observation:** 2 (template variables never populated — code bug)
**Severity:** High — assertion is completely non-functional

### 2.1 Problem

The `reasonable_length` assertion in `eval_format_v1.txt` expects compression variables (`compression_target`, `source_length`, `expected_length`, `min_length`, `max_length`, `summary_length`) that are never passed by `_run_single_assertion()`. The `_get_compression_range()` helper exists (lines 56-67) but is never called. Results are inconsistent: 4 sections fail, 13 pass based on LLM guessing.

### 2.2 Solution

Convert `reasonable_length` to a **fully deterministic check** — no LLM call needed. All inputs are known at eval time.

### 2.3 Algorithm

```python
def _check_reasonable_length(
    self,
    source_text: str,
    summary_text: str,
    facets_used: dict,
    section_id: int,
    summary_id: int | None,
    eval_run_id: str,
) -> dict:
    source_len = len(source_text)
    summary_len = len(summary_text)

    min_ratio, max_ratio = self._get_compression_range(facets_used)

    # Apply ±50% tolerance band around the compression range
    min_chars = int(source_len * min_ratio * 0.5)
    max_chars = int(source_len * max_ratio * 1.5)

    passed = min_chars <= summary_len <= max_chars
    actual_ratio = summary_len / source_len if source_len > 0 else 0

    reasoning = (
        f"Source: {source_len} chars, Summary: {summary_len} chars, "
        f"Ratio: {actual_ratio:.1%}. "
        f"Expected range: {min_ratio:.0%}-{max_ratio:.0%} "
        f"(tolerance: {min_chars}-{max_chars} chars). "
        f"{'Within' if passed else 'Outside'} acceptable range."
    )

    # Store trace (no LLM call, so prompt_sent/llm_response are null)
    trace = EvalTrace(
        section_id=section_id,
        summary_id=summary_id,
        eval_run_id=eval_run_id,
        assertion_name="reasonable_length",
        assertion_category="advisory",
        passed=passed,
        reasoning=reasoning,
        prompt_sent=None,
        llm_response=None,
        model_used="deterministic",
        input_tokens=None,
        output_tokens=None,
        latency_ms=0,
    )
    self.db.add(trace)

    return {
        "assertion_name": "reasonable_length",
        "category": "advisory",
        "passed": passed,
        "reasoning": reasoning,
    }
```

### 2.4 Compression Ranges (from existing `_get_compression_range`)

| Facet Combination | Min Ratio | Max Ratio | With ±50% Tolerance |
|---|---|---|---|
| `style=tweet_thread` | 2% | 8% | 1%-12% |
| `compression=brief` | 5% | 15% | 2.5%-22.5% |
| `compression=standard` (default) | 15% | 25% | 7.5%-37.5% |
| `compression=detailed` | 25% | 40% | 12.5%-60% |

### 2.5 Edge Cases

- **Source text is empty:** Return `passed: true` with reasoning "Source text is empty, length check not applicable."
- **Summary is empty:** Return `passed: false` with reasoning "Summary is empty."
- **Facets not provided:** Default to `standard` compression range (15-25%).
- **Very short sections** (< 500 chars): The tolerance band may be too tight. Apply a floor of 50 chars for `min_chars`.

---

## Change 3: Cumulative Context for Faithfulness Eval

**Observation:** 3 (`no_hallucinated_facts` flags cross-chapter knowledge)
**Severity:** High — critical assertion producing false positives

### 3.1 Problem

The summarizer receives cumulative context (summaries of all prior sections) to maintain cross-section coherence. When the summary references concepts from earlier chapters, the eval flags them as hallucinations because it only sees the current section's source text.

### 3.2 Solution

Pass cumulative section summaries to the eval as additional source context, matching the information scope the summarizer had when generating the summary.

### 3.3 Data Flow

**Current flow:**
```
Eval receives: source_text = section.content_md
```

**New flow:**
```
Eval receives: source_text = section.content_md
               cumulative_context = summaries of all sections with order_index < current
```

### 3.4 Implementation

#### 3.4.1 Building Cumulative Context at Eval Time

**File:** `backend/app/services/summarizer/evaluator.py` — `evaluate_summary()`

New parameter: `cumulative_context: str | None = None`

When provided, cumulative context is injected into the eval prompt template for **faithfulness assertions only** (`no_hallucinated_facts`, `no_contradictions`, `accurate_quotes`). Completeness and format assertions evaluate the summary against the current section only — they don't benefit from prior context.

#### 3.4.2 Fetching Cumulative Context

**File:** `backend/app/cli/commands/eval_cmd.py` (and `summarize_cmd.py` where eval is triggered post-summarization)

Before calling `evaluate_summary()`:
1. Fetch all sections for the book with `order_index < current_section.order_index`.
2. For each prior section, get `default_summary_id` → load summary → extract `summary_md`.
3. Build cumulative context string (same format as `SummarizerService`):
   ```
   - Section Title: [first 500 chars of summary]...
   ```
4. Pass as `cumulative_context` parameter.

**For post-summarization eval** (in `summarize_cmd.py`): The `SummarizerService` already builds cumulative context during the map step. Pass it through to the eval call.

#### 3.4.3 Prompt Template Changes

**File:** `backend/app/services/summarizer/prompts/eval_faithfulness_v1.txt`

Add conditional cumulative context block:

```jinja2
{% if cumulative_context %}
## Context from prior sections in this book
The summarizer had access to the following context from earlier sections when generating this summary.
Claims that reference information from prior sections should NOT be flagged as hallucinations
if that information appears in this context.

{{ cumulative_context }}
{% endif %}

## Source text for this section
{{ source_text }}
```

#### 3.4.4 Distinguishing Hard vs Soft Hallucinations

The eval prompt for `no_hallucinated_facts` should instruct the LLM to distinguish:
- **Hard hallucination:** A claim that contradicts or has no basis in any part of the book seen so far (cumulative context + current section).
- **Soft inference:** A reasonable editorial connection between facts individually present in the source (e.g., "the author's humanities background explains the book's unusual clarity"). Flag these as `likely_cause: "scope_mismatch"` rather than failing.

Update the `no_hallucinated_facts` section of `eval_faithfulness_v1.txt`:
```jinja2
{% if assertion_name == "no_hallucinated_facts" %}
Evaluate whether EVERY factual claim in the summary is supported by the source text
{% if cumulative_context %}or the prior section context provided above{% endif %}.

A claim is a HARD HALLUCINATION (fail) if it has no basis anywhere in the provided source material.
A claim is a SOFT INFERENCE (pass, but note in reasoning) if it makes a reasonable editorial
connection between facts that are individually present in the source.
{% endif %}
```

### 3.5 Edge Cases

- **First section of book:** `cumulative_context` is empty/None. Eval runs with current section only (same as today).
- **Prior sections have no summaries:** Skip those sections in cumulative context. Log a warning.
- **Cumulative context exceeds reasonable size:** Truncate to most recent 20K chars with a note: "...truncated, showing most recent context."
- **Book-level eval:** Uses all section summaries as source context (see Change 7).

---

## Change 4: Paraphrased Quote Detection

**Observation:** 4 (`accurate_quotes` fails on paraphrased attributions)
**Severity:** Medium — genuine quality issue

### 4.1 Problem

The summarizer sometimes paraphrases attributed statements but keeps them in quotation marks, creating misleading verbatim-looking quotes.

### 4.2 Solution (Two-Part)

#### 4.2.1 Part A: Summarizer Prompt Guidance

**File:** `backend/app/services/summarizer/prompts/base/summarize_section.txt`

Add to the output instructions section:

```
When attributing a statement to a specific person, either quote verbatim from the source
or paraphrase without quotation marks. Do not place paraphrased content in quotation marks.
```

#### 4.2.2 Part B: Deterministic Post-Processing Check

**File:** New function `_check_paraphrased_quotes()` in `backend/app/services/summarizer/summarizer_service.py`

After generating a summary and before storing it, run a non-blocking quote verification:

1. Extract double-quoted strings from summary (regex: `"([^"]{10,200})"` — 10-200 char range to avoid common short phrases).
2. For each quote, check exact substring match in source. If found, skip.
3. If no exact match, run a sliding-window fuzzy match over source words using `difflib.SequenceMatcher`. Window size = quote word count + 2 words margin.
4. If best match similarity < 0.85, emit a warning with: `type`, `quote`, `best_match` (if similarity > 0.5), `similarity` score, `message`.

**Key parameters:** threshold = 0.85 (below this = paraphrased), min quote length = 10 chars, max = 200 chars.

**Returns:** `list[dict]` of warnings (empty if all quotes match verbatim or no quotes found).

### 4.3 Warning Storage

Warnings are stored in a new `quality_warnings` JSON field on the `Summary` model:

```python
# Summary model addition
quality_warnings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Structure:
```json
{
  "paraphrased_quotes": [
    {
      "quote": "airlines increased costs 25%...",
      "best_match": "In order to get an additional 5 percent...",
      "similarity": 0.42,
      "message": "Quoted text does not appear verbatim in source."
    }
  ]
}
```

### 4.4 CLI Display

In `summary show` command output, if `quality_warnings` is non-empty, display:

```
⚠ Quality Warnings:
  - Paraphrased quote detected: "airlines increased costs 25%..." (42% match)
```

### 4.5 Edge Cases

- **No quoted text in summary:** No warnings generated. `quality_warnings` remains null.
- **Very short quotes (< 10 chars):** Excluded from check (too prone to false positives from common phrases).
- **Nested quotes / single quotes:** Only double-quoted strings are checked. Single quotes and nested quotes are ignored.
- **Source text contains markdown formatting:** Strip markdown before comparison (bold markers, headers, etc. could break matching).

---

## Change 5: Section-Type-Aware Eval Thresholds

**Observation:** 5 (`covers_frameworks` misses items in peripheral chapters)
**Severity:** Low — legitimate omissions, not systemic issues

### 5.1 Problem

Glossary, notes, and appendix sections contain many named items. Summaries correctly prioritize major frameworks over exhaustive listing, but completeness assertions penalize the omissions.

### 5.2 Solution

Add a `section_type` field to `BookSection` and make eval assertions section-type-aware.

### 5.3 Schema Change

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

**BookSection model addition:**
```python
section_type: Mapped[str] = mapped_column(
    String(50), default=SectionType.CHAPTER.value, server_default="chapter"
)
```

### 5.4 Auto-Detection During Parsing

**File:** `backend/app/services/parser/epub_parser.py`

After section extraction, infer `section_type` from title patterns:

```python
SECTION_TYPE_PATTERNS = {
    SectionType.GLOSSARY: r"(?i)^glossar",
    SectionType.NOTES: r"(?i)^(chapter\s+)?notes|^endnotes|^references",
    SectionType.APPENDIX: r"(?i)^appendix",
    SectionType.BIBLIOGRAPHY: r"(?i)^bibliograph|^works\s+cited|^sources",
    SectionType.INDEX: r"(?i)^index$",
    SectionType.ABOUT_AUTHOR: r"(?i)^about\s+the\s+author",
    SectionType.FOREWORD: r"(?i)^foreword",
    SectionType.PREFACE: r"(?i)^preface",
    SectionType.INTRODUCTION: r"(?i)^introduction",
    SectionType.EPILOGUE: r"(?i)^epilogue",
    SectionType.CONCLUSION: r"(?i)^conclusion",
}
```

Default: `SectionType.CHAPTER` if no pattern matches.

### 5.5 Manual Override

The existing `edit sections` command allows title and structure changes. Add `section_type` to the editable fields so users can correct mis-detected types.

### 5.6 Eval Behavior by Section Type

For `reference-type` sections (`glossary`, `notes`, `bibliography`, `index`, `appendix`):
- `covers_frameworks`: Inject into eval prompt: "This is a {section_type} section. Evaluate coverage of the MAJOR frameworks only, not exhaustive listing. A glossary summary should cover the most prominent entries."
- `covers_key_concepts`: Same relaxed threshold.
- `covers_examples`: Skip (reference sections don't have illustrative examples in the traditional sense).

Implementation: Pass `section_type` to `_run_single_assertion()` and include it in the Jinja2 template context. The eval prompt templates add conditional instructions.

### 5.7 Edge Cases

- **Section type detection ambiguous:** Default to `chapter`. User can correct via `edit sections`.
- **Re-import with section_type:** `_re_import_book` preserves `section_type` when updating in-place (same as other section fields).
- **New section types added later:** The `OTHER` catch-all and `String(50)` column allow extension without migration.

---

## Change 6: Numeric Accuracy Prompt Guidance

**Observation:** 6 | **Severity:** Low — one-off edge case the eval correctly caught

**Fix:** Add to `base/summarize_section.txt`: `"When converting percentages or premiums to multipliers, be precise: a '300% premium' means the premium is 3x, making the total price 4x the base."` Prompt-only change, no code or schema changes.

---

## Change 7: Book-Level Summary Evaluation

**Observation:** 7 (book-level summaries never evaluated with assertion battery)
**Severity:** Medium — gap in eval coverage

### 7.1 Problem

Book-level summaries have `eval_json` containing only extracted concept lists, not 16-assertion pass/fail results. The eval was never run on book-level summaries.

### 7.2 Solution

#### 7.2.1 Auto-Trigger Eval After Book Summary Generation

**File:** `backend/app/services/summarizer/summarizer_service.py` — `_generate_book_summary()`

After generating the book-level summary, automatically trigger evaluation (unless `--skip-eval` is set).

#### 7.2.2 Source Context for Book-Level Eval

The book-level summary is generated from **section summaries**, not raw source text. The eval should use the same input:

```python
# Build source context for book-level eval
source_for_eval = "\n\n".join(
    f"## {section.title}\n{section.default_summary.summary_md}"
    for section in book.sections
    if section.default_summary_id
)
```

No cumulative context needed for book-level eval (it already has the full book context).

#### 7.2.3 Book-Level Assertion Subset

Define a skip list for book-level summaries:

```python
BOOK_LEVEL_SKIP_ASSERTIONS = [
    "image_refs_preserved",         # Not meaningful at book level
    "cross_summary_consistency",    # No second independent book summary to compare
]
```

Adapt completeness assertion prompts for book level:

```jinja2
{% if eval_scope == "book" %}
This is a BOOK-LEVEL summary synthesizing {{ section_count }} section summaries.
Evaluate whether the summary provides representative coverage across major chapters
and themes. It should NOT exhaustively list every concept from every section.
{% endif %}
```

#### 7.2.4 CLI Changes

**File:** `backend/app/cli/commands/eval_cmd.py`

The `eval <book_id>` command (no section_id) should:
1. Display section-level eval results (existing behavior).
2. Also display book-level summary eval results if they exist.
3. New flag: `--book-only` to show only book-level results.
4. New flag: `--force` to re-run eval even if `eval_json` already exists on the summary. Without `--force`, eval skips summaries that already have traces for the current `eval_run_id` pattern. With `--force`, existing eval_json is overwritten and new traces are created (old traces for that summary are marked `is_stale`).

### 7.3 Edge Cases

- **No section summaries exist:** Cannot generate or evaluate book summary. Error message: "No section summaries found. Run `summarize <book_id>` first."
- **Some sections lack summaries:** Use available summaries. Log warning about missing sections.
- **Multiple book-level summaries (different presets):** Each has its own eval. Display grouped by preset.

---

## Change 8: Cascade-Safe Eval Traces

**Observation:** 8 (EvalTrace rows missing after re-import)
**Severity:** Medium — loss of debugging data and reproducibility

### 8.1 Problem

`EvalTrace.section_id` has `ON DELETE CASCADE`. When `_re_import_book()` deletes sections (for removed/reordered content), all associated eval traces are destroyed. Since eval traces cost 16 LLM calls per section, this is expensive data loss.

### 8.2 Solution

#### 8.2.1 FK Change: CASCADE → SET NULL

**Migration:**
```sql
ALTER TABLE eval_traces
    DROP CONSTRAINT eval_traces_section_id_fkey,
    ADD CONSTRAINT eval_traces_section_id_fkey
        FOREIGN KEY (section_id) REFERENCES book_sections(id)
        ON DELETE SET NULL;
```

Make `section_id` nullable:
```sql
ALTER TABLE eval_traces ALTER COLUMN section_id DROP NOT NULL;
```

#### 8.2.2 Add `is_stale` Flag

```sql
ALTER TABLE eval_traces ADD COLUMN is_stale BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX ix_eval_traces_is_stale ON eval_traces (is_stale) WHERE is_stale = FALSE;
```

**Stale marking timing:** Before deleting a section, `_re_import_book` explicitly marks its traces as `is_stale = True` AND sets `section_id = NULL`. This is done in application code, not via a DB trigger, because the FK `SET NULL` only handles the null-out — it cannot set `is_stale`. The explicit update happens before the section DELETE to ensure both fields are set atomically in the same transaction.

#### 8.2.3 Add `eval_run_id` Column

```sql
ALTER TABLE eval_traces ADD COLUMN eval_run_id UUID;
CREATE INDEX ix_eval_traces_eval_run_id ON eval_traces (eval_run_id);
```

Generated once per `evaluate_summary()` call. Groups all 13-16 traces from a single eval run.

#### 8.2.4 Update `_re_import_book` to Mark Stale

**File:** `backend/app/services/book_service.py`

Before deleting sections during re-import, run `UPDATE eval_traces SET is_stale = TRUE WHERE section_id = :id` for each section being removed. This must happen before the DELETE so the FK SET NULL doesn't null out the section_id before we can use it to find the traces.

#### 8.2.5 Re-Import Confirmation Warning

**File:** `backend/app/cli/commands/add_cmd.py`

Before calling `_re_import_book()`, count eval traces and summaries for the book. If either > 0, prompt: `"This book has {N} eval traces and {M} summaries. Re-import will mark traces as stale. Proceed? [y/N]"`. Abort if declined.

#### 8.2.6 EvalTrace Query Updates

All existing queries in `eval_repo.py` must add `WHERE is_stale = FALSE` by default. Add an optional `include_stale: bool = False` parameter for queries that need historical data.

#### 8.2.7 eval_json Derivation from Traces

**Current:** `eval_json` is written independently from trace storage.

**New:** After all traces are stored for an eval run, compute `eval_json` from the traces:

```python
async def _compute_eval_json(self, eval_run_id: str) -> dict:
    """Derive eval_json from EvalTrace rows for this run."""
    traces = await self.db.execute(
        select(EvalTrace).where(EvalTrace.eval_run_id == eval_run_id)
    )
    traces = traces.scalars().all()

    assertions = {}
    for t in traces:
        assertions[t.assertion_name] = {
            "assertion_name": t.assertion_name,
            "category": t.assertion_category,
            "passed": t.passed,
            "reasoning": t.reasoning,
        }
        if t.likely_cause:
            assertions[t.assertion_name]["likely_cause"] = t.likely_cause
        if t.suggestion:
            assertions[t.assertion_name]["suggestion"] = t.suggestion

    passed_count = sum(1 for a in assertions.values() if a["passed"])
    return {
        "passed": passed_count,
        "total": len(assertions),
        "eval_run_id": eval_run_id,
        "assertions": assertions,
    }
```

### 8.3 Edge Cases

- **Stale traces queried for display:** Default queries exclude stale. A `--include-stale` flag on the CLI could show historical data.
- **Section re-created with same order_index:** Traces from the old section have `section_id = NULL` + `is_stale = True`. New section gets fresh evals. No conflict.
- **summary_id still valid after re-import:** Yes — summaries are linked by `content_id` (not FK), so they survive re-import. Traces can still be queried by `summary_id`.

---

## Change 9: Diagnostic Eval Reasoning

**Observation:** 9 (eval reasoning is descriptive but not diagnostic)
**Severity:** Medium — limits actionability

### 9.1 Problem

Eval LLM returns reasoning that describes *what* failed but not *why* the summarizer made that choice or *how to fix it*.

### 9.2 Solution

#### 9.2.1 New Fields on EvalTrace

```sql
ALTER TABLE eval_traces ADD COLUMN likely_cause VARCHAR(50);
ALTER TABLE eval_traces ADD COLUMN suggestion TEXT;
```

`likely_cause` enum values (stored as string, validated in code):
- `content_quality` — the summary itself has a genuine quality issue
- `scope_mismatch` — the claim may be accurate in broader context but isn't in the provided source
- `format_mismatch` — the summary structure doesn't match what the assertion expects
- `insufficient_data` — the eval couldn't run properly due to missing inputs

#### 9.2.2 Updated JSON Schema for LLM Response

Current schema sent to LLM:
```json
{"passed": "boolean", "reasoning": "string"}
```

New schema:
```json
{
  "passed": "boolean",
  "reasoning": "string",
  "likely_cause": "string (one of: content_quality, scope_mismatch, format_mismatch, insufficient_data, or null if passed)",
  "suggestion": "string (one-line fix recommendation, or null if passed)"
}
```

#### 9.2.3 Prompt Template Updates

Add to all eval prompt templates, after the assertion-specific instructions:

```jinja2
If the assertion FAILS, you must also provide:
- "likely_cause": Classify the root cause:
  - "content_quality": The summary has a genuine quality problem.
  - "scope_mismatch": The claim may be correct in broader book context but is not supported by the provided source.
  - "format_mismatch": The summary format doesn't match what this assertion expects.
  - "insufficient_data": You cannot evaluate properly due to missing or ambiguous inputs.
- "suggestion": A one-line, actionable recommendation for how to fix the issue.
  Example: "Remove quotation marks around paraphrased attributions."
  Example: "Include cumulative context in eval source."

If the assertion PASSES, set both fields to null.
```

#### 9.2.4 Trace Storage

In `_run_single_assertion()`, after parsing the LLM response:
```python
trace = EvalTrace(
    ...
    likely_cause=result.get("likely_cause"),
    suggestion=result.get("suggestion"),
    ...
)
```

For deterministic assertions that fail, set `likely_cause` and `suggestion` programmatically:
- `reasonable_length` fail: `likely_cause="content_quality"`, `suggestion="Adjust compression level or re-summarize with different preset."`
- `has_key_concepts` fail: `likely_cause="format_mismatch"`, `suggestion="Add a 'Key Concepts' section heading to the summary."`

### 9.3 Edge Cases

- **LLM doesn't return likely_cause/suggestion:** Default to `None`. Don't fail the assertion over missing diagnostic fields.
- **LLM returns invalid likely_cause value:** Log a warning, store as-is. Don't crash. The field is informational, not load-bearing.
- **Deterministic assertions:** Set diagnostic fields programmatically (no LLM call to provide them).

---

## Change 10: Auto-Retry on Eval Failure

**Driven by:** Post-V1.3 quality strategy — eval failures on critical/important assertions indicate genuine summary quality issues worth fixing automatically.
**Severity:** Medium — directly impacts summary quality for the final library

### 10.1 Problem

When eval assertions fail, the current system records the failure and moves on. The user must manually re-summarize sections that have quality issues. With V1.3 eliminating most false positives (Changes 1-3, 5), remaining failures represent genuine summarization problems — hallucinations, misquotes, missing coverage — that the LLM can often fix with targeted guidance.

### 10.2 Solution

After evaluating each section's summary, check for failures in critical or important assertions. If any fail, re-summarize the section with a fix prompt that injects the `suggestion` field from each failing assertion. Re-evaluate the new summary. The retry summary becomes the new default; the original is preserved in the summary log.

### 10.3 Retry-Eligible Assertions

Retry triggers when **any** critical or important assertion fails (10 of 16):

| Category | Assertions | Count |
|----------|-----------|-------|
| **Critical** | `no_hallucinated_facts`, `no_contradictions`, `accurate_quotes`, `cross_summary_consistency` | 4 |
| **Important** | `covers_main_argument`, `covers_key_concepts`, `covers_frameworks`, `covers_examples`, `not_generic`, `preserves_author_terminology` | 6 |
| **Advisory** (no retry) | `standalone_readable`, `logical_flow`, `no_dangling_references`, `has_key_concepts`, `reasonable_length`, `image_refs_preserved` | 6 |

**Note on `cross_summary_consistency`:** This assertion generates a second independent summary and compares. Retrying the original doesn't guarantee improvement against a different random comparison. Included for completeness but expected to rarely trigger (it's often disabled via config). If it becomes a noise source, it can be excluded from retry scope via config without a code change (see 10.9).

### 10.4 Retry Flow — Inline Per Section

Retry happens **inline** during the batch summarization loop, before moving to the next section. This ensures the best available summary feeds into cumulative context for subsequent sections.

```
┌─────────────────────────────────────────────────────────┐
│  For each section (sequential):                         │
│                                                         │
│  ┌──────────────┐                                       │
│  │  Summarize   │─── compression retry if too long ──┐  │
│  └──────┬───────┘                                    │  │
│         │ summary                                    │  │
│         ▼                                            │  │
│  ┌──────────────┐                                    │  │
│  │  Eval (16)   │─── 3 deterministic + 13 LLM       │  │
│  └──────┬───────┘                                    │  │
│         │ eval_json                                  │  │
│         ▼                                            │  │
│  ┌──────────────┐  all pass    ┌────────────────┐    │  │
│  │ _should_     │─────────────→│ Add summary to │    │  │
│  │  retry()?    │              │ cumul. context  │    │  │
│  └──────┬───────┘              └────────┬───────┘    │  │
│    fail │                               │            │  │
│         ▼                               │            │  │
│  ┌──────────────┐                       │            │  │
│  │ Build fix    │                       │            │  │
│  │ prompt from  │                       │            │  │
│  │ suggestions  │                       │            │  │
│  └──────┬───────┘                       │            │  │
│         ▼                               │            │  │
│  ┌──────────────┐                       │            │  │
│  │ Re-summarize │                       │            │  │
│  │ + Re-eval    │                       │            │  │
│  └──────┬───────┘                       │            │  │
│         │ retry becomes default         │            │  │
│         ▼                               │            │  │
│  ┌──────────────┐                       │            │  │
│  │ Add BEST     │◄──────────────────────┘            │  │
│  │ summary to   │                                    │  │
│  │ cumul. ctxt  │                                    │  │
│  └──────┬───────┘                                    │  │
│         │                                            │  │
│         ▼ next section                               │  │
└─────────────────────────────────────────────────────────┘
```

#### 10.4.1 Single-Section Mode

**File:** `backend/app/cli/commands/summarize_cmd.py`

The CLI calls `summarizer._should_retry()` and `summarizer._build_fix_prompt()` — the same `SummarizerService` methods used by the batch loop (see 10.5). No standalone functions in the CLI layer.

```python
# After initial summarize + eval (existing code at line ~98):
if not skip_eval and svc.get("eval"):
    console.print("Running eval assertions...")
    eval_results = await svc["eval"].evaluate_summary(
        section_id=section_id,
        source_text=section.content_md or "",
        summary_text=summary.summary_md,
        facets_used=facets,
        summary_id=summary.id,
        preset_name=resolved_preset,
        cumulative_context="",  # single section, no prior context
        section_type=section.section_type,
    )

    if not no_retry and summarizer._should_retry(eval_results):
        console.print("  [yellow]Critical/important failures detected. Retrying...[/yellow]")
        fix_prompt = summarizer._build_fix_prompt(eval_results)
        retry_summary = await summarizer._summarize_single_section(
            book_id=book_id,
            section=section,
            facets=facets,
            preset_name=resolved_preset,
            model=model,
            cumulative_context="",
            fix_instructions=fix_prompt,
        )
        retry_summary.retry_of_id = summary.id
        await summarizer._section_repo.update_default_summary(section_id, retry_summary.id)
        await svc["session"].commit()

        # Re-eval the retry
        retry_eval = await svc["eval"].evaluate_summary(
            section_id=section_id,
            source_text=section.content_md or "",
            summary_text=retry_summary.summary_md,
            facets_used=facets,
            summary_id=retry_summary.id,
            preset_name=resolved_preset,
            cumulative_context="",
            section_type=section.section_type,
        )
        _display_retry_outcome(console, eval_results, retry_eval)
    else:
        print_success("Eval complete.")
```

#### 10.4.2 Batch Mode — Restructured Loop

**File:** `backend/app/services/summarizer/summarizer_service.py` — `summarize_book()`

The batch loop changes from "summarize all, then optionally eval" to "summarize → eval → retry per section." This requires `EvalService` as a new dependency of `SummarizerService`.

```python
async def summarize_book(
    self,
    book_id: int,
    preset_name: str | None = None,
    facets: dict[str, str] | None = None,
    force: bool = False,
    model: str | None = None,
    skip_eval: bool = False,
    no_retry: bool = False,              # NEW
    eval_service: "EvalService | None" = None,  # NEW — injected from CLI
    on_section_complete: Callable | None = None,
    on_section_skip: Callable | None = None,
    on_section_fail: Callable | None = None,
    on_section_retry: Callable | None = None,   # NEW callback
) -> dict:
```

Inside the per-section loop, after `_summarize_single_section()`:

```python
for i, section in enumerate(sections):
    # ... existing skip/threshold checks ...

    try:
        summary = await self._summarize_single_section(
            book_id, section, facets, preset_name, model, cumulative_context,
        )
        await self._section_repo.update_default_summary(section.id, summary.id)

        # Inline eval + retry
        retried = False
        if not skip_eval and eval_service:
            eval_results = await eval_service.evaluate_summary(
                section_id=section.id,
                source_text=section.content_md or "",
                summary_text=summary.summary_md,
                facets_used=facets,
                summary_id=summary.id,
                preset_name=preset_name,
                cumulative_context=cumulative_context,
                section_type=getattr(section, "section_type", "chapter"),
            )

            if not no_retry and self._should_retry(eval_results):
                fix_prompt = self._build_fix_prompt(eval_results)
                retry_summary = await self._summarize_single_section(
                    book_id, section, facets, preset_name, model,
                    cumulative_context, fix_instructions=fix_prompt,
                )
                retry_summary.retry_of_id = summary.id
                await self._summary_repo.create(retry_summary)
                await self._section_repo.update_default_summary(
                    section.id, retry_summary.id
                )

                # Re-eval retry
                retry_eval = await eval_service.evaluate_summary(
                    section_id=section.id,
                    source_text=section.content_md or "",
                    summary_text=retry_summary.summary_md,
                    facets_used=facets,
                    summary_id=retry_summary.id,
                    preset_name=preset_name,
                    cumulative_context=cumulative_context,
                    section_type=getattr(section, "section_type", "chapter"),
                )

                summary = retry_summary  # Use retry for cumulative context
                retried = True
                retried_sections.append(section.id)

                if on_section_retry:
                    original_pass = _pass_count(eval_results)
                    retry_pass = _pass_count(retry_eval)
                    on_section_retry(
                        i + 1, total, section.title,
                        original_pass, retry_pass, len(ASSERTION_REGISTRY),
                    )

        # Add best available summary to cumulative context
        summary_text = summary.summary_md
        cumulative_parts.append(
            f"- {section.title}: {summary_text[:500]}..."
            if len(summary_text) > 500
            else f"- {section.title}: {summary_text}"
        )

        completed += 1
        # ... existing on_section_complete callback ...
```

Return value updated:
```python
return {
    "completed": completed,
    "skipped": skipped,
    "failed": failed,
    "retried": retried_sections,  # NEW
}
```

### 10.5 Fix Prompt Construction

**File:** `backend/app/services/summarizer/summarizer_service.py` (new methods)

```python
RETRY_ELIGIBLE_CATEGORIES = {"critical", "important"}

def _should_retry(self, eval_results: dict) -> bool:
    """Return True if any critical or important assertion failed."""
    for name, result in eval_results.get("assertions", eval_results).items():
        if result.get("skipped"):
            continue
        meta = ASSERTION_REGISTRY.get(name, {})
        if meta.get("category") in RETRY_ELIGIBLE_CATEGORIES and not result.get("passed"):
            return True
    return False

def _build_fix_prompt(self, eval_results: dict) -> str:
    """Build a fix instruction string from failing assertion suggestions."""
    failures = []
    results = eval_results.get("assertions", eval_results)
    for name, result in results.items():
        if result.get("skipped"):
            continue
        meta = ASSERTION_REGISTRY.get(name, {})
        if meta.get("category") in RETRY_ELIGIBLE_CATEGORIES and not result.get("passed"):
            suggestion = result.get("suggestion") or f"Fix the issue flagged by '{name}'."
            failures.append(f"- {name}: {suggestion}")

    return (
        "IMPORTANT: Your previous summary had quality issues. "
        "Please fix these and regenerate:\n"
        + "\n".join(failures)
        + "\n\nKeep all other content unchanged."
    )
```

### 10.6 Summarizer Prompt Integration

**File:** `backend/app/services/summarizer/summarizer_service.py` — `_summarize_single_section()`

Add `fix_instructions: str | None = None` parameter. When provided, append to the rendered prompt:

```python
async def _summarize_single_section(
    self,
    book_id: int,
    section: BookSection,
    facets: dict[str, str],
    preset_name: str | None,
    model: str | None,
    cumulative_context: str,
    fix_instructions: str | None = None,  # NEW
) -> Summary:
    # ... existing prompt rendering ...

    prompt = template.render(...)

    if fix_instructions:
        prompt = f"{prompt}\n\n{fix_instructions}"

    # ... rest of method unchanged ...
```

The fix instructions are appended **after** the full original prompt (including source content), so the LLM has the complete context before seeing the fix guidance.

### 10.7 Summary Lineage Tracking

**Schema change on `summaries` table:**

```python
# Summary model addition
retry_of_id: Mapped[int | None] = mapped_column(
    ForeignKey("summaries.id", ondelete="SET NULL"),
    nullable=True,
)
```

This creates a self-referential FK. When a summary is a retry, `retry_of_id` points to the original summary it was retrying. Enables:
- `summary list` to show "(retry of #N)" label
- Querying retry success rates per assertion
- Tracking whether retries actually improve quality over time

### 10.8 CLI Changes

#### 10.8.1 New Flag

**File:** `backend/app/cli/commands/summarize_cmd.py`

```python
no_retry: bool = typer.Option(
    False, "--no-retry", help="Disable auto-retry on eval failures."
),
```

`--skip-eval` implicitly disables retry (no eval results → nothing to retry on).

#### 10.8.2 Batch Progress Output

```
Summarizing 17 sections with preset "practitioner_bullets"...
  [1/17]  Introduction                        done  (32s, 18.2%)
  [2/17]  Chapter 1: Competition              done  (45s, 21.1%)
  [3/17]  Chapter 2: The Five Forces          done  (38s, 19.7%)
  [4/17]  Chapter 3: Competitive Advantage    retry (12/16 → 15/16)  (2m 41s, 20.3%)
  [5/17]  Chapter 4: Value Chain              done  (41s, 22.0%)
  ...
Done. 17 section summaries (1 retried). 1 book summary generated.
```

#### 10.8.3 Single-Section Retry Output

```
Summarizing section #93 "Chapter 8: Strategic Positioning"...
  Done (38s, 19.4%)
Running eval assertions...
  ⚠ 2 critical/important failures:
    - accurate_quotes: Remove quotation marks around paraphrased attributions.
    - no_hallucinated_facts: Remove unsupported claim about "3-4x commodity price".
  Retrying with fix prompt...
  Retry done (35s, 19.1%)
  Re-evaluating...
  ✓ Retry improved: 14/16 → 16/16
  Original summary #45 preserved. Retry summary #48 set as default.
```

#### 10.8.4 Retry-Still-Failing Output

```
  ⚠ 2 critical/important failures:
    - accurate_quotes: Remove quotation marks around paraphrased attributions.
    - covers_main_argument: Include the chapter's central thesis.
  Retrying with fix prompt...
  Retry done (36s, 18.8%)
  Re-evaluating...
  ⚠ Retry partial improvement: 12/16 → 14/16 (1 critical still failing)
  Retry summary #48 set as default (best available).
```

### 10.9 Configuration

No new settings file entries. Retry is controlled via CLI flags:

| Flag | Default | Effect |
|------|---------|--------|
| `--no-retry` | `False` | Disables retry even when eval runs |
| `--skip-eval` | `False` | Disables eval AND retry |

**Future extensibility:** If `cross_summary_consistency` proves noisy as a retry trigger, a `retry_skip_assertions` list can be added to settings or presets (similar to `skip_assertions` for eval). Not needed for V1.3 — the existing config flag `llm.cross_summary_consistency` already controls whether this assertion runs at all.

### 10.10 EvalService Dependency Injection

The batch loop in `SummarizerService` now needs `EvalService`. Rather than making it a constructor dependency (which creates a circular risk), it's passed as an optional parameter to `summarize_book()`:

```python
# In summarize_cmd.py — batch mode:
stats = await summarizer.summarize_book(
    book_id=book_id,
    preset_name=resolved_preset,
    facets=facets,
    force=force,
    model=model,
    skip_eval=skip_eval,
    no_retry=no_retry,
    eval_service=svc.get("eval") if not skip_eval else None,  # NEW
    on_section_complete=...,
    on_section_skip=...,
    on_section_fail=...,
    on_section_retry=lambda i, total, title, orig, retry, assertions: console.print(
        f"  [{i}/{total}] {title[:35]:<35} retry ({orig}/{assertions} → {retry}/{assertions})"
    ),
)
```

This keeps `SummarizerService` independent — it doesn't import or construct `EvalService`. The CLI layer wires them together.

### 10.11 Interaction with Existing Compression Retry

`_summarize_single_section()` already has a compression retry (lines 196-214): if the summary is longer than the source, it retries once with a "keep it shorter" prompt. The eval-driven retry is a **separate concern** that happens after the compression check:

```
1. Generate summary
2. Compression check: if summary >= source length → retry with length constraint (existing)
3. Store summary
4. Eval: run 16 assertions
5. Quality check: if critical/important fail → retry with fix prompt (NEW)
6. Store retry summary (if generated)
```

The fix prompt for step 5 does **not** re-apply the compression constraint — the retry starts from the original full prompt plus fix instructions. If the retry summary happens to be too long, the compression check in step 2 handles it within that call.

### 10.12 Edge Cases

- **All assertions pass:** No retry. Normal flow.
- **Only advisory assertions fail:** No retry. Advisory failures are informational only.
- **Eval errors (exception, not assertion failure):** No retry. `result.get("error") == True` entries are excluded from retry logic. Log a warning.
- **`suggestion` is null on a failing assertion:** Fall back to `"Fix the issue flagged by '{assertion_name}'."` — generic but still provides direction.
- **Retry produces a worse summary:** The retry summary still becomes default (it was generated with awareness of the issues). Both summaries are preserved — user can revert via `summary set-default <original_id>`. The `on_section_retry` callback reports the score change so the user sees the regression.
- **Retry fails with an exception (LLM error, timeout):** Log the error. Keep the original summary as default. Don't crash the batch loop.
- **Section was skipped (already summarized, `--force` not set):** No eval, no retry. Existing summary used for cumulative context as-is.
- **`fix_instructions` makes the prompt exceed context window:** Unlikely — fix instructions are ~200-500 chars. The source content dominates prompt size. If the LLM truncates, the retry may be lower quality, but the eval will catch it.
- **Skipped assertions:** Assertions in the preset's `skip_assertions` list have `skipped: true` and are excluded from the retry check. A skipped assertion cannot trigger a retry.
- **Deterministic assertion fails (e.g., `reasonable_length`):** These are advisory category, so they don't trigger retry. If future deterministic assertions are promoted to important, the fix prompt should still work — the `suggestion` field is set programmatically for deterministic assertions.
- **Book-level summary retry:** The book-level summary is generated after all sections. If its eval fails critical/important assertions, the same retry logic applies: re-generate with fix prompt, re-eval, keep both. No cumulative context implications since it's the final step.

---

## Consolidated EvalService Interface

All changes across Changes 1-10 modify `EvalService` and/or `SummarizerService`. This section consolidates the final method signatures and dispatch logic.

**Responsibility split:**
- **`EvalService`** — pure evaluator. Runs assertions, stores traces, returns results. No retry logic.
- **`SummarizerService`** — owns `_should_retry()`, `_build_fix_prompt()`, and the inline eval+retry loop in `summarize_book()`.
- **CLI layer** (`summarize_cmd.py`) — wires them together. `svc.get("eval")` is already available from `deps.py:get_services()` (no new wiring needed). Passes `eval_service` to `summarize_book()` as an optional parameter.

**End-to-end flow per section (with retry enabled):**

```
summarize_cmd.py / summarize_book()
  │
  ├─ 1. SummarizerService._summarize_single_section()
  │     └─ [compression retry if summary >= source length]
  │     └─ Returns Summary (persisted)
  │
  ├─ 2. EvalService.evaluate_summary()
  │     ├─ Deterministic assertions (3)  ─→ EvalTrace rows
  │     ├─ LLM-based assertions (10-13)  ─→ EvalTrace rows
  │     ├─ Skipped assertions (0+)       ─→ EvalTrace rows (passed, skipped=True)
  │     └─ Returns eval_json (wrapped format with "assertions" key)
  │
  ├─ 3. SummarizerService._should_retry(eval_json)
  │     └─ Checks "assertions" dict for critical/important failures
  │
  ├─ 4. [If retry needed]:
  │     ├─ SummarizerService._build_fix_prompt(eval_json)
  │     ├─ SummarizerService._summarize_single_section(fix_instructions=...)
  │     ├─ Set retry_summary.retry_of_id = original.id
  │     ├─ Update default_summary_id → retry summary
  │     └─ EvalService.evaluate_summary() on retry summary
  │
  └─ 5. Add best summary to cumulative context → next section
```

### EvalService Dependency Change

`EvalService.__init__` currently takes `(db, llm, config)`. Loading presets for `skip_assertions` requires access to preset YAML files. Rather than injecting the full `PresetService`, `EvalService` will load preset YAML directly using a lightweight helper (the preset files are just YAML on disk — no DB needed):

```python
def __init__(self, db: AsyncSession, llm: LLMProvider, config):
    ...
    self._presets_dir = Path(__file__).parent / "prompts" / "presets"

def _load_skip_assertions(self, preset_name: str | None) -> set[str]:
    """Load skip_assertions from preset YAML. Returns empty set if preset is None."""
    if not preset_name:
        return set()
    path = self._presets_dir / f"{preset_name}.yaml"
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text())
    return set(data.get("skip_assertions", []))
```

This avoids a circular dependency (PresetService → EvalService or vice versa) and keeps eval self-contained.

### `evaluate_summary()` — Final Signature and Return Format

```python
async def evaluate_summary(
    self,
    section_id: int,
    source_text: str,
    summary_text: str,
    image_count: int = 0,
    facets_used: dict | None = None,       # NOW USED: passed to deterministic assertions
    summary_id: int | None = None,
    preset_name: str | None = None,        # NEW: for skip_assertions lookup
    cumulative_context: str | None = None,  # NEW: for faithfulness assertions
    section_type: str = "chapter",          # NEW: for completeness assertion adaptation
    eval_scope: str = "section",           # NEW: "section" or "book"
) -> dict:
```

**Return format** (the `_compute_eval_json` wrapped format — NOT a flat assertion dict):

```json
{
  "passed": 14,
  "total": 16,
  "eval_run_id": "a1b2c3d4-...",
  "assertions": {
    "no_hallucinated_facts": {
      "assertion_name": "no_hallucinated_facts",
      "category": "critical",
      "passed": true,
      "reasoning": "All claims supported by source or cumulative context.",
      "likely_cause": null,
      "suggestion": null
    },
    "accurate_quotes": {
      "assertion_name": "accurate_quotes",
      "category": "critical",
      "passed": false,
      "reasoning": "Quote does not appear verbatim in source.",
      "likely_cause": "content_quality",
      "suggestion": "Remove quotation marks around paraphrased attributions."
    }
  }
}
```

This is the same format stored as `Summary.eval_json`. All callers — including `_should_retry()`, `eval_cmd.py`, and `summarize_cmd.py` — consume this wrapped format. The `assertions` key contains per-assertion results; `passed` and `total` are top-level aggregates.

### Assertion Dispatch Logic

`evaluate_summary()` routes each assertion to the appropriate handler:

```python
import uuid

DETERMINISTIC_ASSERTIONS = {"reasonable_length", "has_key_concepts", "image_refs_preserved"}
FAITHFULNESS_ASSERTIONS = {"no_hallucinated_facts", "no_contradictions", "accurate_quotes", "cross_summary_consistency"}
BOOK_LEVEL_SKIP = {"image_refs_preserved", "cross_summary_consistency"}

async def evaluate_summary(self, ...):
    eval_run_id = str(uuid.uuid4())

    # 1. Compute combined skip list
    skip_list = self._load_skip_assertions(preset_name)
    if eval_scope == "book":
        skip_list.update(BOOK_LEVEL_SKIP)

    tasks = []
    for assertion_name, meta in ASSERTION_REGISTRY.items():
        if assertion_name in skip_list:
            # Return skipped result directly (no task needed)
            tasks.append(self._skipped_result(assertion_name, meta, preset_name, eval_run_id, ...))
        elif assertion_name in DETERMINISTIC_ASSERTIONS:
            # Run deterministic check synchronously (fast, no I/O)
            tasks.append(self._run_deterministic(assertion_name, source_text, summary_text, ...))
        else:
            # Run LLM-based assertion asynchronously
            extra_context = cumulative_context if assertion_name in FAITHFULNESS_ASSERTIONS else None
            tasks.append(self._run_single_assertion(
                assertion_name, source_text, summary_text, section_id,
                image_count=image_count, summary_id=summary_id,
                eval_run_id=eval_run_id, cumulative_context=extra_context,
                section_type=section_type, eval_scope=eval_scope,
            ))

    # Note: deterministic/skipped handlers are sync (return dicts directly).
    # Wrap them in coroutines or collect separately before gather.
    # Only LLM-based assertions need async gather.
    sync_results = [t for t in tasks if not asyncio.iscoroutine(t)]
    async_tasks = [t for t in tasks if asyncio.iscoroutine(t)]
    async_results = await asyncio.gather(*async_tasks, return_exceptions=True)

    # 2. Derive eval_json from traces (all handlers store their own EvalTrace rows)
    await self.db.flush()
    eval_json = await self._compute_eval_json(eval_run_id)
    return eval_json
```

### `_run_deterministic()` — Dispatcher

```python
def _run_deterministic(self, assertion_name: str, ...) -> dict:
    if assertion_name == "reasonable_length":
        return self._check_reasonable_length(source_text, summary_text, facets_used, ...)
    elif assertion_name == "has_key_concepts":
        return self._check_has_key_concepts(summary_text, ...)
    elif assertion_name == "image_refs_preserved":
        return self._check_image_refs_preserved(source_text, summary_text, image_count, ...)
```

### `eval_format_v1.txt` Disposition

With all 3 format assertions (`reasonable_length`, `has_key_concepts`, `image_refs_preserved`) converted to deterministic, the `eval_format_v1.txt` prompt template is **no longer used**. It should be retained in the codebase (not deleted) as a reference for the original LLM-based implementations, but is not loaded during evaluation. Add a comment at the top: `{# DEPRECATED: All format assertions are now deterministic. See evaluator.py. #}`.

### Cumulative Context Retrieval in CLI

When `eval <book_id> <section_id>` is run standalone (not post-summarization), the CLI must build cumulative context:

```python
# In eval_cmd.py, before calling evaluate_summary():
prior_sections = [s for s in book.sections if s.order_index < section.order_index]
cumulative_parts = []
for s in prior_sections:
    if s.default_summary_id:
        summary = await summary_repo.get_by_id(s.default_summary_id)
        if summary:
            cumulative_parts.append(f"- {s.title}: {summary.summary_md[:500]}")
cumulative_context = "\n".join(cumulative_parts) if cumulative_parts else None
```

### eval_run_id Generation

The `eval_run_id` UUID is generated once per `evaluate_summary()` call and passed to every assertion handler (deterministic and LLM-based). It is stored on each `EvalTrace` row and included in the derived `eval_json`.

---

## Deterministic Assertion Conversions

Three assertions are converted from LLM-based to deterministic/hybrid checks:

### `reasonable_length` → Fully Deterministic

See [Change 2](#change-2-deterministic-reasonable_length-check) for full algorithm. Pure math: `len(summary) / len(source)` against compression range derived from facets.

### `has_key_concepts` → Deterministic

**Logic:**
1. If preset skips this assertion (via `skip_assertions`), return passed + skipped.
2. Check for structured concept presentation via regex:
   - Look for heading patterns: `## Key Concepts`, `**Key Concepts**`, `### Concepts`, `## Core Ideas`, etc.
   - Look for definition-list patterns: `**Term**: Description` (3+ occurrences).
   - Look for structured bullet groups with bold lead terms (3+ occurrences).
3. If any pattern matches, pass. Otherwise, fail.

```python
KEY_CONCEPTS_PATTERNS = [
    r"(?mi)^#{1,3}\s*(key\s+concepts?|core\s+(ideas?|concepts?)|main\s+(ideas?|concepts?))",
    r"(?mi)^\*\*[A-Z][^*]+\*\*[:\s]",  # Bold term followed by colon (counted)
]

def _check_has_key_concepts(self, summary_text: str, ...) -> dict:
    # Check heading patterns
    for pattern in KEY_CONCEPTS_PATTERNS[:1]:
        if re.search(pattern, summary_text):
            return {"passed": True, "reasoning": "Found structured key concepts section."}

    # Check bold-term definitions (need 3+ for structured presentation)
    bold_terms = re.findall(KEY_CONCEPTS_PATTERNS[1], summary_text)
    if len(bold_terms) >= 3:
        return {"passed": True, "reasoning": f"Found {len(bold_terms)} structured concept definitions."}

    return {
        "passed": False,
        "reasoning": "No structured concept presentation found (no Key Concepts heading or 3+ bold-term definitions).",
        "likely_cause": "format_mismatch",
        "suggestion": "Add a 'Key Concepts' section or use bold terms for concept definitions.",
    }
```

### `image_refs_preserved` → Deterministic

**Logic:**
1. Count images in source: regex for `![`, `<img`, or image references.
2. If source has 0 images, pass (nothing to preserve).
3. If source has images, check if summary mentions visual content: regex for `figure`, `diagram`, `chart`, `image`, `illustration`, `table`, `graph`, `photo`.
4. Pass if at least one visual reference keyword is found when images exist.

```python
IMAGE_SOURCE_PATTERN = r"!\[|<img\s|\.(?:png|jpg|jpeg|gif|svg)"
IMAGE_REF_KEYWORDS = r"(?i)\b(figure|diagram|chart|image|illustration|table|graph|photo|visual)\b"

def _check_image_refs_preserved(self, source_text: str, summary_text: str, image_count: int, ...) -> dict:
    source_images = len(re.findall(IMAGE_SOURCE_PATTERN, source_text))
    total_images = max(source_images, image_count)

    if total_images == 0:
        return {"passed": True, "reasoning": "No images in source — nothing to preserve."}

    refs_in_summary = re.findall(IMAGE_REF_KEYWORDS, summary_text)
    passed = len(refs_in_summary) > 0

    return {
        "passed": passed,
        "reasoning": f"Source has {total_images} images. Summary has {len(refs_in_summary)} visual references." +
            (" Visual content acknowledged." if passed else " No visual content references found."),
        "likely_cause": None if passed else "content_quality",
        "suggestion": None if passed else "Add a note about diagrams or visual content from the section.",
    }
```

---

## Database Migrations

### Migration: `v1_3_eval_improvements`

**Changes:**

| Table | Column | Change | Details |
|-------|--------|--------|---------|
| `eval_traces` | `section_id` | ALTER | Make nullable, change FK from CASCADE to SET NULL |
| `eval_traces` | `is_stale` | ADD | `BOOLEAN NOT NULL DEFAULT FALSE` |
| `eval_traces` | `eval_run_id` | ADD | `UUID`, nullable, indexed |
| `eval_traces` | `likely_cause` | ADD | `VARCHAR(50)`, nullable |
| `eval_traces` | `suggestion` | ADD | `TEXT`, nullable |
| `book_sections` | `section_type` | ADD | `VARCHAR(50) NOT NULL DEFAULT 'chapter'` |
| `summaries` | `quality_warnings` | ADD | `JSON`, nullable |
| `summaries` | `retry_of_id` | ADD | `INTEGER`, nullable, FK to `summaries.id` ON DELETE SET NULL |

**Index changes:**

| Index | Table | Columns | Notes |
|-------|-------|---------|-------|
| `ix_eval_traces_is_stale` | `eval_traces` | `is_stale` | Partial index WHERE `is_stale = FALSE` |
| `ix_eval_traces_eval_run_id` | `eval_traces` | `eval_run_id` | For grouping traces by eval run |
| `ix_book_sections_section_type` | `book_sections` | `section_type` | For section-type queries |

**FK change — must execute in this exact order:**

```sql
-- Step 1: Drop old CASCADE constraint (must happen before nullable change)
ALTER TABLE eval_traces
    DROP CONSTRAINT IF EXISTS eval_traces_section_id_fkey;

-- Step 2: Make section_id nullable (column must be nullable before SET NULL FK)
ALTER TABLE eval_traces ALTER COLUMN section_id DROP NOT NULL;

-- Step 3: Add new SET NULL constraint (requires nullable column)
ALTER TABLE eval_traces
    ADD CONSTRAINT eval_traces_section_id_fkey
        FOREIGN KEY (section_id) REFERENCES book_sections(id)
        ON DELETE SET NULL;
```

**Important for Alembic:** Auto-generated migrations may not order these correctly. Manually verify the migration file puts DROP CONSTRAINT → ALTER COLUMN → ADD CONSTRAINT in sequence. Test on a copy of the production database before running on real data.

**Enum for section_type:**
No DB-level enum needed. Stored as `VARCHAR(50)` with application-level validation (same pattern as `BookStatus`).

---

## Prompt Template Changes

### Summarization Prompts

| File | Change | Purpose |
|------|--------|---------|
| `base/summarize_section.txt` | Add quote attribution guidance | Obs 4: prevent paraphrased quotes |
| `base/summarize_section.txt` | Add numeric accuracy guidance | Obs 6: prevent percentage/multiplier confusion |
| `fragments/style/study_guide.txt` | Add "## Key Concepts" instruction | Obs 1.2: ensure structured concept output |
| `fragments/style/academic_detailed.txt` | Add "## Key Concepts" instruction | Obs 1.2: ensure structured concept output |

### Eval Prompts

| File | Change | Purpose |
|------|--------|---------|
| `eval_faithfulness_v1.txt` | Add cumulative context block | Obs 3: faithfulness eval with book context |
| `eval_faithfulness_v1.txt` | Add hard/soft hallucination distinction | Obs 3: reduce false positives |
| `eval_faithfulness_v1.txt` | Add `likely_cause` + `suggestion` output fields | Obs 9: diagnostic reasoning |
| `eval_completeness_v1.txt` | Add section-type-aware instructions | Obs 5: relaxed thresholds for reference sections |
| `eval_completeness_v1.txt` | Add book-level scope instructions | Obs 7: representative vs exhaustive coverage |
| `eval_completeness_v1.txt` | Add `likely_cause` + `suggestion` output fields | Obs 9: diagnostic reasoning |
| `eval_coherence_v1.txt` | Add `likely_cause` + `suggestion` output fields | Obs 9: diagnostic reasoning |
| `eval_specificity_v1.txt` | Add `likely_cause` + `suggestion` output fields | Obs 9: diagnostic reasoning |
| `eval_format_v1.txt` | Remove `reasonable_length` and `has_key_concepts` LLM sections | Now deterministic |
| `eval_format_v1.txt` | Remove `image_refs_preserved` LLM section | Now deterministic |

---

## Configuration & Preset Changes

### Preset YAML Schema

Add optional `skip_assertions` field to all preset files:

| Preset | skip_assertions |
|--------|----------------|
| `practitioner_bullets` | `[has_key_concepts]` |
| `executive_brief` | `[has_key_concepts]` |
| `tweet_thread` | `[has_key_concepts, image_refs_preserved]` |
| `study_guide` | `[]` (empty — all assertions apply) |
| `academic_detailed` | `[]` (empty — all assertions apply) |

### PresetService Validation

`PresetService._parse_file()` should:
1. Accept `skip_assertions` as optional list of strings.
2. Validate that all assertion names in the list exist in `ASSERTION_REGISTRY`.
3. Warn (don't error) on unknown assertion names for forward compatibility.

### Settings

No new settings required. Existing `summarization.eval_prompt_version` continues to control template versioning.

---

## Verification Plan

### Unit Tests

**File:** `backend/tests/unit/test_eval_deterministic.py` (new)

| Test | Description |
|------|-------------|
| `test_reasonable_length_within_range` | Summary at 20% of source with standard compression passes |
| `test_reasonable_length_too_short` | Summary at 2% of source with standard compression fails |
| `test_reasonable_length_too_long` | Summary at 80% of source with standard compression fails |
| `test_reasonable_length_empty_source` | Empty source returns passed with "not applicable" reasoning |
| `test_reasonable_length_brief_preset` | 8% summary passes for brief compression |
| `test_reasonable_length_detailed_preset` | 35% summary passes for detailed compression |
| `test_reasonable_length_no_facets_defaults_standard` | Missing facets defaults to standard range |
| `test_has_key_concepts_heading_found` | Summary with `## Key Concepts` heading passes |
| `test_has_key_concepts_bold_terms` | Summary with 3+ `**Term**: description` patterns passes |
| `test_has_key_concepts_no_structure` | Plain prose fails |
| `test_has_key_concepts_bullets_with_bold_leads` | Bullet-point summary with bold lead terms passes |
| `test_image_refs_no_images` | Source without images always passes |
| `test_image_refs_images_mentioned` | Source with images + summary mentioning "diagram" passes |
| `test_image_refs_images_not_mentioned` | Source with images + summary without visual keywords fails |
| `test_paraphrased_quote_exact_match` | Verbatim quote in source returns no warning |
| `test_paraphrased_quote_paraphrased` | Paraphrased quote returns warning with similarity score |
| `test_paraphrased_quote_no_quotes` | Summary without quotes returns empty warnings |

**File:** `backend/tests/unit/test_eval_service.py` (extend existing)

| Test | Description |
|------|-------------|
| `test_preset_skip_assertions` | Assertions in skip list return passed + skipped flag |
| `test_preset_no_skip_list` | Preset without skip_assertions runs all assertions |
| `test_eval_run_id_groups_traces` | All traces from one eval call share same `eval_run_id` |
| `test_eval_json_derived_from_traces` | `_compute_eval_json()` correctly aggregates trace results |
| `test_cumulative_context_passed_to_faithfulness` | Faithfulness assertions receive cumulative context |
| `test_cumulative_context_not_passed_to_format` | Format assertions don't receive cumulative context |
| `test_section_type_injected_in_completeness` | Section type appears in completeness eval prompt |
| `test_book_level_skip_assertions` | Book-level eval skips `image_refs_preserved` and `cross_summary_consistency` |
| `test_diagnostic_fields_stored` | `likely_cause` and `suggestion` stored on EvalTrace |
| `test_diagnostic_fields_null_on_pass` | Passing assertions have null `likely_cause` and `suggestion` |

**File:** `backend/tests/unit/test_section_type.py` (new)

| Test | Description |
|------|-------------|
| `test_detect_glossary` | Title "Glossary" → `SectionType.GLOSSARY` |
| `test_detect_notes` | Title "Chapter Notes" → `SectionType.NOTES` |
| `test_detect_about_author` | Title "About the Author" → `SectionType.ABOUT_AUTHOR` |
| `test_detect_default_chapter` | Title "Chapter 3: Strategy" → `SectionType.CHAPTER` |
| `test_detect_case_insensitive` | Title "APPENDIX A" → `SectionType.APPENDIX` |

**File:** `backend/tests/unit/test_preset_service.py` (extend existing)

| Test | Description |
|------|-------------|
| `test_load_preset_with_skip_assertions` | YAML with `skip_assertions` loads correctly |
| `test_load_preset_without_skip_assertions` | YAML without field returns empty list |
| `test_invalid_assertion_name_warns` | Unknown assertion name in skip list logs warning |

**File:** `backend/tests/unit/test_auto_retry.py` (new)

| Test | Description |
|------|-------------|
| `test_should_retry_critical_failure` | One critical assertion fails → `_should_retry()` returns True |
| `test_should_retry_important_failure` | One important assertion fails → `_should_retry()` returns True |
| `test_should_retry_advisory_only` | Only advisory assertions fail → `_should_retry()` returns False |
| `test_should_retry_all_pass` | All assertions pass → `_should_retry()` returns False |
| `test_should_retry_skipped_ignored` | Skipped assertion (even critical) does not trigger retry |
| `test_should_retry_error_ignored` | Assertion with `error: true` does not trigger retry |
| `test_build_fix_prompt_uses_suggestions` | Failing assertions' `suggestion` fields appear in fix prompt |
| `test_build_fix_prompt_null_suggestion_fallback` | Null `suggestion` falls back to assertion name |
| `test_build_fix_prompt_multiple_failures` | Multiple failing assertions produce multi-line fix prompt |
| `test_fix_instructions_appended_to_prompt` | `_summarize_single_section(fix_instructions=...)` appends to rendered prompt |
| `test_retry_summary_has_retry_of_id` | Retry summary's `retry_of_id` points to original summary |

### Integration Tests

**File:** `backend/tests/integration/test_eval_cascade.py` (new)

| Test | Description |
|------|-------------|
| `test_section_delete_sets_trace_null` | Deleting a section sets `EvalTrace.section_id = NULL` and `is_stale = True` |
| `test_stale_traces_excluded_by_default` | Default trace queries exclude `is_stale = True` rows |
| `test_re_import_preserves_traces` | `_re_import_book` with section changes preserves eval traces as stale |
| `test_re_import_warning_count` | Confirmation prompt shows correct trace/summary counts |
| `test_eval_json_matches_traces` | After eval, `Summary.eval_json` matches aggregated traces |

**File:** `backend/tests/integration/test_eval_pipeline.py` (extend existing)

| Test | Description |
|------|-------------|
| `test_full_eval_with_deterministic_assertions` | Eval run uses deterministic checks for 3 assertions, LLM for rest |
| `test_book_level_eval_triggered` | Book-level summary auto-triggers eval after generation |
| `test_cumulative_context_built_correctly` | Prior section summaries assembled and passed to eval |

**File:** `backend/tests/integration/test_auto_retry.py` (new)

| Test | Description |
|------|-------------|
| `test_retry_creates_new_summary` | Retry produces a second Summary row, original preserved |
| `test_retry_becomes_default` | After retry, `section.default_summary_id` points to retry summary |
| `test_retry_of_id_set` | Retry summary's `retry_of_id` FK points to original |
| `test_no_retry_when_skip_eval` | `skip_eval=True` skips both eval and retry |
| `test_no_retry_when_no_retry_flag` | `no_retry=True` runs eval but skips retry |
| `test_batch_retry_feeds_cumulative_context` | Retried section's improved summary used in cumulative context for next section |
| `test_retry_on_exception_preserves_original` | If retry LLM call throws, original summary stays as default |
| `test_batch_stats_include_retried` | `summarize_book()` return dict includes `retried` section list |

### Golden Set Tests

**File:** `backend/tests/integration/test_eval_golden_set.py` (new)

**Fixtures:** Store in `backend/tests/fixtures/golden_eval/`

| Fixture | Source | Purpose |
|---------|--------|---------|
| `book2_section_92.json` | Book 2, section 92 (16/16 pass) | All-pass positive test |
| `book2_section_97.json` | Book 2, section 97 (16/16 pass) | All-pass positive test |
| `book2_section_91.json` | Book 2, section 91 (hallucination false positive) | Verify cumulative context fix |
| `book2_section_93.json` | Book 2, section 93 (paraphrased quote) | Verify quote detection |
| `book2_section_101.json` | Book 2, section 101 (glossary) | Verify section-type-aware thresholds |

Each fixture contains: `source_text`, `summary_text`, `cumulative_context`, `facets_used`, `section_type`, `expected_results` (per-assertion pass/fail).

Golden set tests run deterministic assertions against the fixture data and verify results match expectations. LLM-based assertions are tested separately with mocked LLM responses.

### E2E Tests

| Test | Description |
|------|-------------|
| `test_eval_command_shows_diagnostic_fields` | `bookcompanion eval <book_id> <section_id>` displays `likely_cause` and `suggestion` |
| `test_eval_command_shows_book_level` | `bookcompanion eval <book_id>` includes book-level eval results |
| `test_re_import_confirmation_prompt` | `bookcompanion add --force` shows confirmation with trace counts |
| `test_summary_show_displays_warnings` | `bookcompanion summary show <id>` displays paraphrased quote warnings |
| `test_summarize_with_retry_output` | `bookcompanion summarize <book_id> <section_id>` shows retry progress when eval fails |
| `test_summarize_no_retry_flag` | `bookcompanion summarize <book_id> --no-retry` skips retry on eval failure |
| `test_summary_list_shows_retry_lineage` | `bookcompanion summary list <book_id>` shows "(retry of #N)" for retry summaries |

---

## Deployment & Rollout

### Step 1: Database Migration
```bash
cd backend
uv run alembic revision --autogenerate -m "V1.3 eval improvements"
# Manual review: verify FK change, new columns, indexes
uv run alembic upgrade head
# Migrate test DB
BOOKCOMPANION_DATABASE__URL=postgresql+asyncpg://bookcompanion:bookcompanion@localhost:5438/bookcompanion_test uv run alembic upgrade head
```

### Step 2: Code Changes — Implementation Phases

Changes have dependencies. Implement in this order:

**Phase A: Schema + Models** (no logic changes, unblocks everything)
1. Run Alembic migration: new columns, FK change, indexes (see migration ordering note in §15)
2. Update SQLAlchemy models: `EvalTrace` (new columns, nullable `section_id`), `BookSection` (`section_type`), `Summary` (`quality_warnings`, `retry_of_id`)

**Phase B: Deterministic Assertions + Preset Skipping** (Changes 1, 2, 5 — no dependencies on other phases)
3. Implement `_check_reasonable_length()`, `_check_has_key_concepts()`, `_check_image_refs_preserved()` in `evaluator.py`
4. Add `skip_assertions` to preset YAML files
5. Update `PresetService._parse_file()` to load/validate `skip_assertions`
6. Add `_load_skip_assertions()` to `EvalService`
7. Add `section_type` auto-detection to epub parser
8. Add `section_type` to `edit sections` editable fields

**Phase C: Eval Pipeline Overhaul** (Changes 3, 7, 8, 9 — depends on Phase A models)
9. Implement `_compute_eval_json()` for trace-based derivation
10. Update `_run_single_assertion()` to accept and pass new context (`cumulative_context`, `section_type`, `eval_scope`, `eval_run_id`)
11. Implement assertion dispatch logic in `evaluate_summary()` (deterministic vs LLM routing, skip list merge)
12. Update `_re_import_book()` with stale marking and confirmation prompt
13. Update eval prompt templates (cumulative context, section-type, diagnostics, hard/soft hallucination)

**Phase D: Summarizer Changes** (Changes 4, 6 — independent of eval changes)
14. Add quote attribution guidance + numeric accuracy guidance to summarization prompts
15. Implement `_check_paraphrased_quotes()` in `SummarizerService`

**Phase E: Auto-Retry Loop** (Change 10 — depends on Phases B + C)
16. Implement `_should_retry()`, `_build_fix_prompt()` in `SummarizerService`
17. Add `fix_instructions` parameter to `_summarize_single_section()`
18. Restructure `summarize_book()` batch loop for inline eval + retry
19. Update `summarize_cmd.py` for `--no-retry` flag and retry progress output

**Phase F: CLI Polish** (depends on Phases C + E)
20. Update `eval_cmd.py` for book-level display, diagnostic fields, `--force` flag
21. Update `summary list` CLI to show retry lineage
22. Update `summary show` to display `quality_warnings`

### Step 3: Run Tests
```bash
uv run python -m pytest tests/unit/test_eval_deterministic.py -v
uv run python -m pytest tests/unit/test_section_type.py -v
uv run python -m pytest tests/unit/test_eval_service.py -v
uv run python -m pytest tests/unit/test_auto_retry.py -v
uv run python -m pytest tests/integration/test_eval_cascade.py -v
uv run python -m pytest tests/integration/test_auto_retry.py -v
uv run python -m pytest tests/integration/test_eval_golden_set.py -v
uv run python -m pytest tests/ -v  # Full suite
uv run ruff check . && uv run ruff format --check .
```

### Step 4: Validate with Real Data
```bash
# Re-run eval on book 2 sections
bookcompanion eval 2 --force

# Check results — should see:
# - has_key_concepts passes or is skipped for practitioner_bullets
# - reasonable_length has actual numbers (not "cannot evaluate")
# - no_hallucinated_facts reduces false positives on sections 91, 99
# - Diagnostic fields (likely_cause, suggestion) populated on failures

# Run book-level eval
bookcompanion eval 2 --book-only

# Check paraphrased quote warnings
bookcompanion summary show <summary_id_for_section_93>
```

### Step 5: Rollback Plan

If issues are found:
1. **Schema is additive only** — new columns with defaults don't break existing code.
2. **FK change is the riskiest**: If SET NULL causes issues, can revert FK to CASCADE in a new migration.
3. **Deterministic assertions**: If results are worse than LLM-based, revert by changing the assertion dispatch back to LLM (the prompt templates still exist).
4. **Prompt changes**: Version-controlled. Revert by setting `eval_prompt_version` to "v1" (though this would need the old templates preserved as v1, new as v2).

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Deterministic assertions are less accurate than LLM | Low | Medium | Golden set testing validates accuracy. Deterministic checks are well-defined (length, pattern matching). Can revert to LLM for specific assertions if needed. |
| Cumulative context makes eval prompts too large | Low | Medium | Truncate to 20K chars. Cumulative context uses summaries (compressed), not raw text. Typical size: 5-15K chars. |
| FK change from CASCADE to SET NULL creates orphaned traces | Low | Low | `is_stale` flag ensures orphaned traces are filtered out of default queries. Periodic cleanup query can remove old stale traces. |
| Re-run eval on book 2 produces different results | High | Low | Expected — that's the point. New results should be more accurate. Compare before/after to validate improvements. |
| LLM doesn't reliably return `likely_cause`/`suggestion` | Medium | Low | Fields are nullable. Code handles missing values gracefully. Worst case: diagnostic fields are null, falls back to current behavior. |
| `section_type` auto-detection misclassifies | Medium | Low | Conservative regex patterns (only match obvious titles). Default is `chapter`. Users can correct via `edit sections`. |
| Preset `skip_assertions` accidentally skips important checks | Low | Medium | Validation warns if >12 assertions skipped. `skip_assertions` only on system presets initially — user presets start with none. |
| Migration failure on existing data | Low | High | Test migration on a copy of the production database first. All changes are additive (new columns with defaults). FK change is the only destructive alteration. |
| Retry produces worse summary than original | Medium | Low | Both summaries preserved. User can revert via `summary set-default`. CLI reports score change so regression is visible immediately. |
| Inline eval adds significant latency to batch runs | High | Medium | Expected: ~60-90s eval per section adds ~17-25 min to a 17-section book. `--skip-eval` and `--no-retry` provide escape hatches. Quality tradeoff is worth it for a personal knowledge tool. |
| Retry loop masks systemic prompt issues | Low | Medium | If many sections retry, the root cause is likely the prompt or preset, not individual summaries. Log retry rate per book and warn if >50% of sections retry: "High retry rate — consider adjusting your preset or prompt." |
| `cross_summary_consistency` retry is ineffective | Medium | Low | Retrying doesn't control the second independent summary. If this becomes a noise source, disable via existing `llm.cross_summary_consistency` config flag. |
| Fix prompt confuses the LLM | Low | Medium | Fix instructions are appended after the full original prompt, so context is complete. Instructions are concise (~200-500 chars). If retry quality is consistently poor, can fall back to `--no-retry` and investigate prompt phrasing. |

---

## Research Sources

### Existing Code Explored

| File | Key Findings |
|------|-------------|
| `backend/app/services/summarizer/evaluator.py` (217 lines) | ASSERTION_REGISTRY (16 assertions), `_get_compression_range()` exists but never called, `facets_used` accepted but unused, `_run_single_assertion()` missing compression variables |
| `backend/app/db/models.py` (EvalTrace: 279-309) | `section_id` FK with CASCADE, `summary_id` FK with SET NULL, full audit fields (prompt_sent, llm_response, tokens, latency) |
| `backend/app/db/models.py` (Summary: 312-341) | `eval_json` JSON field, `facets_used` JSONB field, `preset_name` String field |
| `backend/app/services/summarizer/summarizer_service.py` | Cumulative context built as markdown bullet list, truncated to 500 chars per section, passed to LLM as `cumulative_context` parameter |
| `backend/app/services/book_service.py` (192-265) | `_re_import_book` updates by order_index match, deletes unmatched sections (cascades to EvalTrace) |
| `backend/app/services/preset_service.py` | FACET_DIMENSIONS, `resolve_facets()`, YAML load/validate, 5 system presets |
| `backend/app/services/summarizer/prompts/eval_format_v1.txt` | Template expects 6 compression variables that are never passed |
| `backend/app/services/summarizer/prompts/eval_faithfulness_v1.txt` | Receives only `source_text` for current section, no cumulative context |
| `backend/app/services/summarizer/prompts/presets/practitioner_bullets.yaml` | style=bullet_points, audience=practitioner, no skip_assertions field |
| `backend/app/cli/commands/eval_cmd.py` | Writes `eval_json` independently from traces, `--summary-id` mode exists |
| `backend/app/cli/commands/summarize_cmd.py` | Calls eval after section summarization, passes `facets_used` (unused by eval) |
| `docs/specs/2026-04-04_v1_2_bugfixes_and_improvements_spec.md` | Spec template: Decision Log, numbered changes, verification plan, risk table |

### External Research

| Topic | Key Finding | Source |
|-------|------------|--------|
| Deterministic vs LLM assertions | "Favor deterministic checks over LLM-as-judge" — industry consensus. Pure math/regex for codifiable criteria. | Hamel Husain (evals FAQ), Promptfoo docs |
| LLM-as-judge failure modes | Position bias (~40% inconsistency), verbosity bias (~15% inflation), self-enhancement bias (5-7% boost when same model family) | Evidently AI, Monte Carlo Data, Label Your Data |
| Eval result schemas | Universal fields: `eval_run_id` (UUID), `score` (float), `config_snapshot`. Priority additions for this system: `eval_run_id` and `config_snapshot`. | OpenAI Evals, Braintrust, DeepEval, LangSmith, Promptfoo |
| Cascade-safe audit trails | Soft-delete pattern, content-addressed storage (source_hash), SET NULL + stale flag. Replace CASCADE with SET NULL for audit data. | Audit trail best practices (Datadog, compliance systems) |
| Faithfulness evaluation | Claims-extraction pattern (RAGAS/DeepEval): extract atomic claims → match to source passages → verify each. More reliable for long contexts. | RAGAS docs, DeepEval faithfulness metric |
| Preset-aware evaluation | Parametric assertions (Promptfoo pattern): assertions accept params that vary by config. Assertion set selection per preset. Rubric injection into judge prompts. | Promptfoo, EvalLM (Microsoft Research) |
| Context window management | Sliding window, hierarchical evaluation (eval against intermediate summaries), truncation with disclosure flag. | Redis context management guide, Langfuse docs |
