# V1.2 Bugfixes & Improvements — Requirements

**Date:** 2026-04-04
**Status:** Draft
**Origin:** Manual testing of V1.1 features on book 2 ("Understanding Michael Porter")

---

## Observation 1: EPUB chapter cover pages parsed as content sections

**Severity:** High — affects summarization quality for many EPUB books

**Problem:** The EPUB parser splits chapters at EPUB spine items, but many EPUBs use separate HTML files for chapter cover pages (containing just a heading, image, and TOC link). These are stored as full sections with ~115-144 chars of XML boilerplate instead of actual chapter content.

**Evidence (book 2):**
- 10 of 17 sections have < 200 chars
- Chapter sections contain only: `xml version='1.0' encoding='utf-8'?` + a heading link + `![image](images/00003.jpg)`
- Actual chapter content is missing — it lives in a separate spine item that isn't linked to the chapter title

**Impact:**
- Quality checks flag these sections but summarization still runs on them
- LLM generates summaries from cumulative context rather than source content (hallucination risk)
- Compression ratio > 100% because summary is longer than input

**Requirements:**
1. EPUB parser should detect and merge chapter cover pages with their content spine items
2. Heuristic: if a spine item is < 500 chars and followed by a content-rich spine item, merge them
3. Alternatively: strip XML declarations and image-only content during parsing, then merge adjacent sections with < 200 chars of text content into the next section
4. Quality checks should auto-skip or flag sections with < 200 chars for summarization (not just warn)

---

## Observation 2: Compression ratio > 100% for stub sections

**Severity:** Medium — misleading metrics, downstream eval confusion

**Problem:** When a section has very little content (115-144 chars of XML boilerplate), the LLM generates a summary using cumulative context from prior sections. The summary (600-1400 chars) is much longer than the input, producing compression ratios of 400-1000%.

**Evidence:**
| Section | Input chars | Summary chars | Compression |
|---------|------------|---------------|-------------|
| Part One: What Is Competition? | 115 | 701 | 609.6% |
| 2. The Five Forces | 144 | 1,454 | 1009.7% |
| Part Two: What Is Strategy? | 115 | 1,195 | 1039.1% |

**Root cause:** This is a consequence of Observation 1 (stub sections). The compression metric itself is correct — it's the input that's wrong.

**Requirements:**
1. Fix Observation 1 (primary fix)
2. Summarizer should skip sections below a configurable minimum char threshold (e.g., 200 chars) unless `--force` is used
3. When a section is skipped due to low content, log it as "skipped (insufficient content)" rather than treating it as an error
4. Consider using `input_char_count` from the actual content passed to the LLM (which includes cumulative context) rather than just `section.content_md` length, for more accurate compression tracking

---

## Observation 3: Eval results always empty

**Severity:** Low — expected behavior given `--skip-eval` flag, but UX could be better

**Problem:** All summaries show `Eval: -` in listing. Users ran summarize with `--skip-eval` and there's no prompt or reminder to run eval separately.

**Evidence:** Every summary in `summary list` shows `-` for eval column.

**Requirements:**
1. After summarization completes, if `--skip-eval` was used, print a hint: `"Run 'bookcompanion eval <book_id>' to evaluate summary quality"`
2. `summary list` should distinguish between "eval not run" vs "eval failed" vs "eval passed"
3. Consider running eval by default (without `--skip-eval`) for a sampling of sections (e.g., first, middle, last) to provide at least partial quality signals without the full cost

---

## Observation 4: Book summary output is JSON instead of markdown

**Severity:** High — primary user-facing output is unreadable

**Problem:** The summarize templates end with `"Output as JSON matching the provided schema."` but the LLM `generate()` call does not pass a `json_schema` parameter. The LLM wraps its response in ````json ... ``` `` fencing. The `_extract_summary_text()` method tries to parse JSON and extract `detailed_summary` key, but:
- Some responses use different key names
- Some responses include the ````json``` wrapper which breaks `json.loads()`
- Fallback returns raw `response.content` including JSON wrapping

**Evidence:**
```
summary_md starts with: ```json\n{\n  "summary": "\"Understanding Michael Porter\"...
```

**Root cause:** Mismatch between prompt instruction ("Output as JSON") and LLM call (no json_schema enforcement).

**Requirements:**
1. Remove `"Output as JSON matching the provided schema."` from both base templates (`summarize_section.txt` and `summarize_book.txt`)
2. Replace with: `"Output your summary as markdown."` or simply remove the output format instruction (the style fragments already specify format)
3. Update `_extract_summary_text()` to:
   - Strip ````json ... ``` `` fencing if present
   - Try to extract `summary` or `detailed_summary` key from JSON if the response is valid JSON
   - Otherwise return the raw text as-is
4. For existing summaries stored with JSON wrapping, provide a one-time migration or cleanup script
5. Consider whether `--json-schema` should be used for structured output — if so, define the schema and pass it through the `generate()` call consistently

---

## Priority Order

1. **Observation 4** (JSON output) — Quick fix, immediate UX improvement
2. **Observation 1** (EPUB parsing) — Root cause of most other issues, needs careful implementation
3. **Observation 2** (Compression ratio) — Mostly resolved by fixing #1, plus minor skip logic
4. **Observation 3** (Eval hint) — Nice-to-have UX improvement
