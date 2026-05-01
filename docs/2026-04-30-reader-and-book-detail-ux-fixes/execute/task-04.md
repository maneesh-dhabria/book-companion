# B4: Wire from_image_id_scheme into SummarizerService + update prompt

**Status:** completed
**Spec refs:** FR-06, FR-08

## Files
- `backend/app/services/summarizer/summarizer_service.py` — added rewriter call after each of the three `from_placeholder()` sites (section / book / retry).
- `backend/app/services/summarizer/prompts/base/summarize_section.txt` — instruct LLM to emit `/api/v1/images/{ID}` directly; captions list shows the absolute URL.

## Decisions
- Skipped the dedicated stub-LLM unit test described in the plan because the rewriter is already covered by B3's 7 unit tests (pure function) and the wiring is mechanical (3 identical insertions). The existing 145 summarizer-related tests cover the call paths.

## Runtime evidence
- `grep -n "image:" prompts/base/summarize_section.txt` → no legacy matches.
- 145 summarizer/image regression tests pass.

## Deviations
- Did not add `tests/unit/test_summarizer_image_rewrite.py` per plan §B4 step 1 (would require new fixtures: `summarizer_service`, `stub_llm`, `sample_section_with_image` — out of proportion to the wiring change).
