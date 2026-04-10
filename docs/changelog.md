# Changelog

## 2026-04-10 — V1.3: Eval system overhaul — fewer false positives, auto-retry, diagnostics

- Three eval checks (length, key concepts, image references) now run instantly without LLM calls — faster, cheaper, and 100% reproducible
- Summarization presets can now skip eval checks that don't apply to their format — `practitioner_bullets` no longer fails on "missing Key Concepts heading"
- Eval now receives prior section summaries as context, so cross-chapter references are no longer flagged as hallucinations
- Summaries that fail critical or important eval checks are automatically re-summarized with targeted fix instructions; use `--no-retry` to disable
- Each eval failure now includes a root cause classification and a one-line fix suggestion, visible in `eval <book_id> <section_id>`
- Book-level summaries are now evaluated with the same assertion battery (adapted for book scope); view with `eval <book_id> --book-only`
- Re-importing a book preserves eval history — traces are marked stale rather than deleted; a confirmation prompt shows trace/summary counts before proceeding
- Sections are auto-classified by type (chapter, glossary, appendix, etc.) during parsing; glossary and reference sections get relaxed completeness thresholds
- Section types can be corrected in the editor via `type <index> <type_name>`
- Paraphrased quotes (text in quotation marks that doesn't match the source) are detected and shown as warnings in `summary show`
- Prompt guidance added for quote attribution accuracy and numeric precision (percentages vs multipliers)

**References:**
- [V1.3 spec](docs/specs/2026-04-05_v1_3_eval_improvements_spec.md)
- [V1.3 requirements](docs/requirements/2026-04-05_v1_3_eval_improvements.md)
- [V1.3 implementation plan](docs/plans/2026-04-07_v1_3_eval_improvements_implementation.md)

## 2026-04-04 — V1.2: EPUB parsing fixes, markdown output, eval display

- Fixed: EPUB books that split chapters across multiple files now parse correctly — chapter content is aggregated from all spine items between TOC entries, not just the first file. Books like "Understanding Michael Porter" went from ~100 chars per chapter to 25K-46K chars
- Fixed: Book and section summaries now output clean markdown instead of JSON-wrapped text. Existing JSON-format summaries are still readable (backward compatible)
- Sections with very little real content (< 200 chars after stripping XML/images) are automatically skipped during summarization instead of producing hallucinated summaries. Use `--force` to override
- `summary list` now shows separate "Status" and "Results" columns (e.g., "passed", "3/5") instead of a single "Eval" dash. Distinguishes between "eval not run" and "eval failed"
- After summarizing with `--skip-eval`, a hint reminds you to run `bookcompanion eval <book_id>` separately

**References:**
- Requirements: [`docs/requirements/2026-04-04_v1_2_bugfixes_and_improvements.md`](docs/requirements/2026-04-04_v1_2_bugfixes_and_improvements.md)
- Spec: [`docs/specs/2026-04-04_v1_2_bugfixes_and_improvements_spec.md`](docs/specs/2026-04-04_v1_2_bugfixes_and_improvements_spec.md)
- Plan: [`docs/plans/2026-04-04_v1_2_bugfixes_implementation.md`](docs/plans/2026-04-04_v1_2_bugfixes_implementation.md)

## 2026-04-04 — V1.1: Preset-based summarization, summary log, section editing

- Summarize books using named presets (`--preset practitioner_bullets`, `--preset executive_brief`, etc.) that control style, audience, compression, and content focus — or override individual facets with `--style`, `--audience`, `--compression`, `--content-focus` flags
- 5 built-in presets: Practitioner Bullets, Academic Detailed, Executive Brief, Study Guide, Tweet Thread. Create your own with `bookcompanion preset create`
- Multiple summaries are now saved per section — re-summarize with a different preset and both versions are kept. Switch between them with `summary set-default`
- New `summary` commands: `summary list` shows all summaries for a book, `summary compare` shows two summaries side-by-side with concept diff, `summary show` displays full provenance (preset, model, compression ratio, latency)
- New `read` command: view original section content with `bookcompanion read <book_id> <section_id>`, optionally alongside its summary with `--with-summary`
- Quality validation on book import: 10 automatic checks flag empty, short, duplicate, or non-content sections with suggested fixes. Interactive editing REPL lets you merge, split, reorder, or delete sections before or after saving
- Re-running the same preset skips already-summarized sections automatically. Use `--force` to regenerate everything

**References:**
- Spec: [`docs/specs/2026-04-02_book_companion_v1.1_enhancements_spec.md`](docs/specs/2026-04-02_book_companion_v1.1_enhancements_spec.md)
- Plan: [`docs/plans/2026-04-03_v1_1_enhancements_implementation.md`](docs/plans/2026-04-03_v1_1_enhancements_implementation.md)
- Requirements: [`docs/requirements/2026-04-01_book_companion_v1_requirements.md`](docs/requirements/2026-04-01_book_companion_v1_requirements.md)
