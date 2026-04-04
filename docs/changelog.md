# Changelog

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
