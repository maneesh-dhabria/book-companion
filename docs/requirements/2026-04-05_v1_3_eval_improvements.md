# V1.3 Eval System Improvements — Requirements

**Date:** 2026-04-05
**Status:** Draft
**Origin:** Analysis of eval failures for book 2 ("Understanding Michael Porter"), 17 section summaries using `practitioner_bullets` preset (summaries 110-127).

---

## Summary of Findings

The latest eval run across 17 sections scored between 12/16 and 16/16. No book-level summaries were evaluated with the assertion battery. Of the ~35 total failures across all sections, the vast majority trace to three root causes: an eval/prompt contract mismatch (`has_key_concepts`), a code bug (`reasonable_length`), and a context scope mismatch between summarizer and evaluator (`no_hallucinated_facts`). Only the `accurate_quotes` failures represent genuine summarization quality issues.

### Failure Distribution

| Assertion | Failures (of 17) | Category | Root Cause |
|---|---|---|---|
| `has_key_concepts` | 15 | advisory | Eval expects format the preset doesn't produce |
| `reasonable_length` | 4 | advisory | Template variables never populated (code bug) |
| `no_hallucinated_facts` | 3 | critical | Cross-chapter knowledge leaks from cumulative context |
| `covers_frameworks` | 3 | important | Legitimate omissions in peripheral chapters |
| `accurate_quotes` | 2 | critical | Paraphrased text presented in quotation marks |
| `covers_key_concepts` | 2 | important | Exhaustive coverage not achieved for glossary/notes |
| `no_contradictions` | 1 | critical | Arithmetic interpretation dispute (3-4x vs 4-5x) |
| `image_refs_preserved` | 1 | advisory | Activity system diagrams not noted in summary |

---

## Observation 1: `has_key_concepts` is a near-universal false failure (15/17)

**Severity:** High — inflates failure count, obscures real quality issues

**Problem:** The `eval_format_v1.txt` prompt checks whether the summary contains a literal "Key Concepts" section or equivalent structured list. The `practitioner_bullets` preset produces bullet-point summaries organized by theme, which are structured and useful but do not include a dedicated "Key Concepts" heading. The eval is checking for a specific structural element the preset was never designed to produce.

**Evidence:**
- 15 of 17 sections fail with identical reasoning: "The summary does not contain a key concepts section or equivalent."
- The two sections that pass (90 and 92) happen to organize their bullets in a way the LLM interprets as equivalent.
- The summaries *do* contain structured concept presentation — just not under that label.

**Impact:**
- Pass rates appear 1 point lower than they should for almost every section.
- Masks real failures by flooding results with a structural nitpick.

**Requirements:**
1. The eval assertion should be preset-aware: if the preset's style/structure doesn't call for a "Key Concepts" section, the assertion should either skip or adapt its criteria to check for "structured concept presentation" more broadly (e.g., bullet lists, bolded terms, concept groupings).
2. Alternatively, the summarization prompts for presets that should include a Key Concepts section should explicitly request one. Presets that don't need it should mark `has_key_concepts` as N/A in their facet config.
3. Consider adding a `skip_assertions` or `expected_format` field to preset YAML files so the eval system knows which structural checks are relevant.

---

## Observation 2: `reasonable_length` fails due to unpopulated template variables (code bug)

**Severity:** High — assertion is completely non-functional

**Problem:** The `eval_format_v1.txt` template for `reasonable_length` expects these variables: `compression_target`, `source_length`, `expected_length`, `min_length`, `max_length`, `summary_length`. However, `evaluator.py:_run_single_assertion()` (line 157) only passes `assertion_name`, `source_text`, `summary_text`, and `image_count` to the Jinja2 template. The `facets_used` parameter is accepted by `evaluate_summary()` but never forwarded to `_run_single_assertion()` or used to compute compression targets. The `_get_compression_range()` helper method exists (lines 56-67) but is never called.

**Evidence:**
- 4 sections fail with: "Cannot evaluate: all task parameters (compression ratio, source length, target length, acceptable range) are blank/missing."
- The remaining 13 sections pass because the LLM guesses a reasonable range or gives the benefit of the doubt when it can see the source and summary inline.
- Results are inconsistent: some sections pass, others fail, based on LLM interpretation of blank fields.

**Impact:**
- Length checking is effectively random — depends on LLM mood rather than actual measurement.
- A deterministic check is being delegated to an LLM with missing inputs.

**Requirements:**
1. `_run_single_assertion()` must compute and pass compression variables to the template:
   - Accept `facets_used` parameter.
   - Call `_get_compression_range()` to get expected range.
   - Calculate `source_length = len(source_text)`, `summary_length = len(summary_text)`.
   - Derive `compression_target`, `expected_length`, `min_length`, `max_length` from the range.
2. Consider making `reasonable_length` a deterministic check (pure math, no LLM call) since all inputs are known at eval time. This would be faster, cheaper, and 100% reproducible.

---

## Observation 3: `no_hallucinated_facts` flags cross-chapter knowledge from cumulative context

**Severity:** High — critical assertion producing false positives for a design-level reason

**Problem:** The summarizer receives cumulative context (summaries of all prior sections) to maintain coherence across the book. This means the LLM "knows" concepts from earlier chapters and sometimes references them in the current section's summary. However, the eval only receives the current section's source text. Concepts that are accurate in book context get flagged as hallucinations because they aren't in the local source passage.

**Evidence:**
- **Section 91 (Ch. 1):** Summary mentions "Five Forces" and "Value Chain" — core Porter frameworks introduced in later chapters but not mentioned in Ch. 1's source text. The summarizer added these from cumulative context or general knowledge to provide useful cross-references.
- **Section 99 (Epilogue):** Summary names "(Five Forces, Value Chain, Five Tests)" where source just says "guiding frameworks" without naming them.
- **Section 103 (About the Author):** Summary infers that the author's humanities background "explains the book's unusual clarity" — an editorial connection not stated in the source.

**Impact:**
- Critical assertion failures that aren't real quality issues (for sections 91 and 99).
- Section 103 is arguably a real hallucination (editorial inference).
- Undermines trust in the eval system when critical failures are false positives.

**Requirements:**
1. **Expand the eval's source context to include all content up to and including the current section.** The eval should have access to the same information the summarizer had when generating the summary. If the summarizer received cumulative context from sections 1-N, the eval for section N should validate claims against sections 1-N, not just section N alone. This is the most accurate approach: a fact is only hallucinated if it doesn't appear *anywhere in the book up to that point*.
2. Implementation approach: when running eval for section N, concatenate source text from all sections with `order_index <= N` (or at minimum, include the cumulative context summaries that were fed to the summarizer). Pass this as the source context to faithfulness assertions.
3. For the book-level summary eval, the full book content should be the source context.
4. The eval prompt should distinguish between:
   - **Hard hallucination:** A claim that contradicts or has no basis in any part of the book seen so far.
   - **Soft inference:** A reasonable editorial connection between facts that are individually present in the source (like the "humanities background explains clarity" case). These should be flagged at a lower severity or as a separate assertion.

---

## Observation 4: `accurate_quotes` fails on paraphrased attributions in quotation marks

**Severity:** Medium — genuine summarization quality issue

**Problem:** The summarizer sometimes paraphrases attributed statements but keeps them in quotation marks, making them look like verbatim quotes when they aren't.

**Evidence:**
- **Section 93 (Ch. 3):** Herb Kelleher quote is reworded: summary says `"airlines increased costs 25% to gain 5% market share"` but source says `"In order to get an additional 5 percent of the market, some companies increased their costs by 25 percent."` The summary changes "some companies" to "airlines," reverses the order, and condenses.
- **Section 96 (Ch. 5):** `"Nothing is sustainable"` appears in quotes but this exact phrase doesn't exist in the source. It's a shorthand summary of the chapter's second misconception.

**Impact:**
- Readers may take quoted text as verbatim when it's paraphrased.
- The eval correctly catches this — these are real quality failures.

**Requirements:**
1. Add explicit guidance in summarization prompts: "When attributing a statement to a specific person, either quote verbatim from the source or paraphrase without quotation marks. Do not place paraphrased content in quotation marks."
2. Consider a summarizer-side post-processing check: if quotation marks appear with an attribution, verify the quoted text exists in the source. This could be a deterministic string-matching check before the summary is stored.

---

## Observation 5: `covers_frameworks` and `covers_key_concepts` miss items in peripheral chapters

**Severity:** Low — legitimate omissions, not systemic issues

**Problem:** Some sections that are reference material (glossary, chapter notes, about the author) contain many named items. The summaries prioritize major frameworks over exhaustive listing, so minor items get omitted.

**Evidence:**
- **Section 91 (Ch. 1):** Missing "Blue Ocean Strategy" as a named competing framework discussed in the source as a foil to Porter's view.
- **Section 101 (Glossary):** Missing SWOT Analysis, Competitor Analysis, and ~15 other glossary entries. Summary covers the most prominent frameworks (five forces, value chain, generic strategies, five tests) but omits many standalone definitions.
- **Section 102 (Chapter Notes):** Missing all Chapter 1 source references and several other specific citations.
- **Section 103 (About the Author):** Missing "activity-based costing" as a named methodology.

**Impact:**
- Minor completeness gaps. The summaries still capture the most important frameworks.
- Glossary and notes sections are inherently list-heavy; summarizing them means prioritizing.

**Requirements:**
1. For list-heavy reference sections (glossary, notes, bibliography), consider a different eval threshold or a modified assertion: "covers major frameworks" rather than "covers all frameworks."
2. The eval could be section-type-aware: if a section is tagged as `glossary`, `notes`, or `appendix`, completeness assertions should expect coverage of top items rather than exhaustive listing.
3. Alternatively, the summarizer could be prompted to include a "Also discussed:" one-liner listing minor items it chose not to expand on, satisfying completeness without bloating the summary.

---

## Observation 6: `no_contradictions` flags an arithmetic interpretation edge case

**Severity:** Low — borderline case, not a systemic issue

**Problem:** Section 93 (Ch. 3) summary says premium eggs cost "3-4x commodity price." The source says consumers pay "price premiums of three or four hundred percent." The eval flags this as a contradiction: a 300-400% premium means the total price is 4-5x the commodity price, not 3-4x.

**Evidence:** The eval reasoning correctly identifies the mathematical distinction: "3-4x" describes the multiplier, while "300-400% premium" means the premium alone is 3-4x, making the total price 4-5x.

**Impact:** A real (if subtle) accuracy issue. The summarizer misinterpreted "premium" as "total price."

**Requirements:**
1. No systemic fix needed — this is a one-off arithmetic error the eval correctly caught.
2. The summarizer prompt could include guidance: "When converting percentages or premiums to multipliers, be precise about whether the figure represents a premium (added on top) or a total multiplier."

---

## Observation 7: Book-level summaries were never evaluated with the assertion battery

**Severity:** Medium — gap in eval coverage

**Problem:** Book 2 has 4+ book-level summaries (IDs 55, 56, 81, 94, 109, 127) across different presets. Their `eval_json` fields contain only extracted concept lists — not the 16-assertion pass/fail results. The eval command's `--summary-id` mode should work for these, but it was never run on book-level summaries.

**Evidence:**
- All book-level summary `eval_json` values contain `{"concepts": [...]}` — a concept extraction result, not assertion results.
- No `passed`/`total` keys in any book-level `eval_json`.

**Impact:**
- No quality signal on the most important output (the full book summary).
- Cannot compare quality across presets at the book level.

**Requirements:**
1. The `summarize` command or a post-summarization step should automatically trigger eval on book-level summaries, not just section summaries.
2. The eval for book-level summaries needs special handling: the "source text" should be either the full book content or the concatenation of all section summaries (whichever the book summary was derived from).
3. Some assertions need adaptation for book summaries (e.g., `image_refs_preserved` may not apply; `covers_examples` should check for representative examples across chapters, not exhaustive listing).

---

## Observation 8: EvalTrace rows are missing for the latest eval run

**Severity:** Medium — loss of debugging data and reproducibility

**Problem:** Summaries 110-127 have `eval_json` with full assertion results, but zero `EvalTrace` rows exist in the database for these summaries. The traces were likely deleted during a forced re-parse of the book (re-import deletes and recreates sections, which cascades to eval traces since `EvalTrace.section_id` is a FK).

**Context from user:** The eval traces were deleted while force-reparsing the book. This points to a broader issue: `_re_import_book` deletes sections (or their IDs change), which cascades to eval traces. Since eval traces are expensive to regenerate (16 LLM calls per section), losing them silently is costly.

**Impact:**
- Cannot inspect the full prompt sent, raw LLM response, model used, token counts, or latency for any assertion.
- `eval <book_id> <section_id>` mode (which reads EvalTrace rows) returns nothing, even though eval results exist in `eval_json`.
- Debugging eval failures requires re-running the eval, which costs time and money.

**Requirements:**
1. **Investigate whether re-import cascades are deleting eval traces.** If `BookSection` rows are deleted and recreated during re-import, FK cascades on `EvalTrace.section_id` will delete traces. If sections are updated in-place (by `order_index`), traces should survive — but if section IDs change, the traces become orphaned or deleted.
2. **Eval traces should survive re-imports.** Options:
   - Link eval traces to `summary_id` (which is stable across re-imports) rather than `section_id` as the primary lookup key.
   - Before re-import, detach eval traces from sections (null out `section_id`), re-import, then re-link by matching `summary_id`.
   - Store eval traces as an immutable audit log that is never cascade-deleted. Use soft deletes or archive tables.
3. **`eval_json` and `EvalTrace` should be kept in sync.** Currently `eval_json` is stored on the summary and `EvalTrace` rows are stored separately. If one is deleted, the other becomes the only record. Consider making `eval_json` the source of truth (derived from traces) or vice versa, rather than maintaining two independent stores.
4. **Add a warning when re-import would delete eval data.** The CLI should warn: "This book has N eval traces that will be deleted. Proceed? [y/N]" before destructive re-imports.

---

## Observation 9: Eval reasoning is descriptive but not diagnostic

**Severity:** Medium — limits actionability of eval results

**Problem:** The eval LLM returns reasoning that describes *what* failed but not *why the summarizer likely made that choice* or *what should be done differently*. This makes failures informational but not actionable without manual investigation.

**Evidence:**
- `no_hallucinated_facts` on Section 91: "The terms 'Five Forces' and 'Value Chain' do not appear anywhere in the source text — these are hallucinated additions, even if they are accurate descriptions of Porter's frameworks from other chapters." — Describes the failure but doesn't note that cumulative context is the likely source.
- `has_key_concepts`: "The summary does not contain a key concepts section or equivalent." — States the obvious without suggesting whether one should have been included given the preset.

**Impact:**
- Each failure requires manual investigation to determine root cause.
- Cannot programmatically categorize failures (prompt issue vs. code bug vs. genuine quality problem).
- Difficult to prioritize which failures to fix.

**Requirements:**
1. Extend the eval JSON schema to include a `likely_cause` field alongside `passed` and `reasoning`. Prompt the eval LLM to classify the failure into categories:
   - `content_quality` — the summary itself has a genuine quality issue.
   - `scope_mismatch` — the claim may be accurate in broader context but isn't in the provided source.
   - `format_mismatch` — the summary structure doesn't match what the assertion expects.
   - `insufficient_data` — the eval couldn't run properly due to missing inputs.
2. Include a `suggestion` field: a one-line recommendation for how to fix the failure (e.g., "Remove quotation marks around paraphrased attributions" or "Include cumulative context in eval source").
3. These fields should be stored in both `eval_json` and `EvalTrace.reasoning` for full traceability.
