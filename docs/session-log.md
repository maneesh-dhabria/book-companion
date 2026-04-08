# Session Log

## 2026-04-08 — V1.3 eval system improvements: full implementation + code review

- Implemented all 10 spec changes for V1.3 eval overhaul: 3 deterministic assertions (reasonable_length, has_key_concepts, image_refs_preserved), preset-aware skipping, section-type detection, cumulative context for faithfulness eval, paraphrased quote detection, book-level eval, cascade-safe traces (is_stale + SET NULL FK), diagnostic fields (likely_cause/suggestion), and auto-retry on critical/important failures
- Used git worktree (`.worktrees/v1.3-eval`) for isolated development — prevented main branch contamination during a 41-file, 2400-line change
- Parallelized independent tasks with 3 background subagents (preset skipping, section type detection, diagnostic prompts) while implementing cumulative context and quote detection in foreground — cut wall-clock time significantly
- Code review caught a critical bug: `section_id=0` for book-level eval caused FK violations silently swallowed by exception handler — book-level eval never actually ran. Fix: pass `None` instead, update signature to `int | None`
- Code review caught section_type REPL persistence gap: the `type` command modified in-memory state but the save-to-DB path only handled deletes and creates, not updates to existing sections — changes were silently lost
- Word-boundary regex matters for keyword matching: substring check for "visual" in "No visuals" was a false positive; switched to `\bkeywords?\b` pattern
- Spec mentioned `ix_book_sections_section_type` index but Alembic autogenerate missed it because the column lacked `index=True` — always cross-check spec's index requirements against the generated migration
- Gotcha: when adding a new key (`"retried"`) to `summarize_book()`'s return dict, existing tests that assert exact dict equality break — found and fixed in `test_summarizer.py`
- Final state: 312 tests passing (58 new), 3 commits on `feature/v1.3-eval-improvements` branch

## 2026-04-07 — V1.3 eval improvements implementation plan

- Built 21-task implementation plan for V1.3 eval system overhaul covering 10 spec changes: 3 deterministic assertion conversions, preset-aware skipping, cumulative context for faithfulness eval, section-type detection, diagnostic fields, cascade-safe traces, book-level eval, paraphrased quote detection, and auto-retry on eval failure
- Used an Explore agent to deeply read 20+ files (evaluator, summarizer service, models, CLI commands, prompt templates, repos, parser) before writing the plan — critical for identifying exact line numbers, method signatures, and data flow patterns
- Ran 3 review loops with gap analysis: Loop 1 caught 6 gaps (LLM cost budget, eval_format_v1.txt disposition, book 2 re-eval, prompt_sent nullability test, E2E test cases, high retry rate warning); Loop 2 caught 5 coherence issues (sub-step lettering, _generate_book_summary signature, section_type re-import preservation, section_edit specificity, Task 10 prerequisites); Loop 3 confirmed 100% spec coverage
- Key plan decision: Task 10 (eval pipeline overhaul) is the critical integration task that wires deterministic dispatch, skip lists, eval_run_id, cumulative context, and eval_json derivation — explicitly noted as depending on Tasks 2-5, 8, 9
- Spec has a ~16x increase in LLM calls per book (18 → 294) due to inline eval + retry — documented cost impact prominently and noted `--skip-eval` / `--no-retry` escape hatches
- Pattern: systematic gap analysis via dedicated Explore agent comparing spec sections against plan tasks is effective for catching coverage gaps that manual review misses

**References:**
- Spec: [`docs/specs/2026-04-05_v1_3_eval_improvements_spec.md`](specs/2026-04-05_v1_3_eval_improvements_spec.md)
- Plan: [`docs/plans/2026-04-07_v1_3_eval_improvements_implementation.md`](plans/2026-04-07_v1_3_eval_improvements_implementation.md)
- Requirements: [`docs/requirements/2026-04-05_v1_3_eval_improvements.md`](requirements/2026-04-05_v1_3_eval_improvements.md)

## 2026-04-04 — V1.2 Bugfixes: EPUB spine aggregation, markdown output, eval display

- **V1.2 scope**: 5 fixes from testing V1.1 on "Understanding Michael Porter" — EPUB spine content aggregation, XML stripping, markdown output (was JSON-wrapped), min content threshold skip, eval status/results split columns. Also: requirements doc, spec with multi-role review, 8-task implementation plan.
- **Root cause discovery**: EPUB chapters had 75-103 chars because each TOC entry points to a single HTML file (chapter cover page), but actual content spans multiple spine items not in the TOC. The stub merge algorithm cascaded incorrectly — merging stubs into each other in a chain. Real fix: `_aggregate_spine_content()` collects orphan spine items into the preceding TOC section. Chapters went from 75 chars to 25K-46K chars.
- **Chose spine aggregation over stub merging** as primary fix because stub merging treats the symptom (small sections) while spine aggregation treats the cause (content not collected). Kept stub merge as fallback for EPUBs that genuinely have small sections.
- **JSON output root cause**: Prompt templates ended with "Output as JSON matching the provided schema" but `generate()` never passed `--json-schema`. LLM wrapped responses in ` ```json ``` ` fencing. Fix: changed prompt to "Output your summary directly as markdown" + rewrote `_extract_summary_text()` to handle both formats for backward compat.
- **`extract_concepts` refactored to `@staticmethod`** — it doesn't use `self`, and the summarizer needs to call it without instantiating SummaryService. Clean DI pattern.
- **Academic_detailed preset timeout**: 43K-char sections with cumulative context exceed the 300s Claude CLI timeout. Practitioner_bullets and executive_brief completed all 17 sections. This is a known limitation, not a bug — large detailed summaries need a higher timeout or chunking strategy.
- **Compression ratios**: Dropped from 400-1000% (hallucinated summaries of stub content) to 0.1-1.4% (real summaries of real content). The metric was always correct — the input was wrong.
- Takeaway: When an EPUB has stub sections, check the spine structure before assuming the parser is wrong — the content may be in adjacent spine items not referenced by the TOC.

## 2026-04-04 — V1.1 Enhancements: Faceted presets, summary log, section editing

- **V1.1 scope**: Replaced monolithic summarization with a faceted preset system (4 dimensions: style/audience/compression/content_focus), append-only summary log (`summaries` table replacing inline `summary_md` columns), section editing REPL (merge/split/reorder/delete with undo), quality validation (10 deterministic heuristics), and summary comparison with concept diff. 4 new services, 3 new CLI sub-apps, 15 Jinja2 fragments, 5 system presets.
- Built across 13 tasks using subagent-driven development in a git worktree, dispatching 2-3 parallel implementation agents at a time for independent tasks — total 16 commits, 111 files changed, ~6500 insertions
- **Enum casing bug**: SQLAlchemy `Enum(SummaryContentType)` sends member NAMES (uppercase `BOOK`) to PostgreSQL by default, but the migration created the enum with lowercase VALUES (`book`). Fix: `values_callable=lambda x: [e.value for e in x]` on the mapped column
- **Alembic async enum creation**: `sa.Enum.create(checkfirst=True)` doesn't work reliably with asyncpg — the `checkfirst` query runs in a different transaction context. Fix: use raw SQL `DO $$ BEGIN CREATE TYPE ... EXCEPTION WHEN duplicate_object THEN NULL; END $$`
- **Missing session.commit() pattern**: Services use `flush()` (sends SQL, stays in transaction) but CLI commands must explicitly `commit()`. The `get_services()` context manager does NOT auto-commit — discovered when book-level summaries vanished after "successful" generation. Every CLI command that writes data needs an explicit `await svc["session"].commit()`
- **Rich table truncation in E2E tests**: Rich truncates long cell values with `…` when terminal width is narrow (subprocess capture). E2E assertions must check for partial strings, not full values
- **Worktree + Docker gotcha**: Docker compose in the worktree tries to create a new container with the same name as the original project's container. Use the existing container instead of `docker compose up` in the worktree.
- Takeaway: Always run real data through new pipelines during verification — unit/integration tests all passed but the missing `commit()` bug only surfaced when actually summarizing a book end-to-end with the CLI
