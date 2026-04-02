# Sample Output

These files contain sample outputs from processing a test book through the Book Companion pipeline.

Generated with: `bookcompanion` v0.1.0 using Claude Sonnet.

## Files

| File | Description |
|------|-------------|
| sample_book_summary.md | Full book-level summary |
| sample_section_summary.md | Section summary for a single chapter |
| sample_eval_results.md | Eval assertion results |
| sample_search_results.md | Hybrid search results |
| sample_cli_output.md | Key CLI command outputs |

## How to Generate

After processing a book through the full pipeline:

```bash
cd backend
uv run bookcompanion list --format json > ../docs/sample-output/sample_cli_output_list.json
uv run bookcompanion summary 1 > ../docs/sample-output/sample_book_summary.md
uv run bookcompanion summary 1 1 > ../docs/sample-output/sample_section_summary.md
uv run bookcompanion eval 1 > ../docs/sample-output/sample_eval_results.md
uv run bookcompanion search "strategy" > ../docs/sample-output/sample_search_results.md
```
