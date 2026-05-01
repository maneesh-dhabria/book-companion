# B7 — content_char_count on SectionBrief

**Spec refs:** FR-25.

## Files touched
- `backend/app/db/models.py` — added `column_property(func.coalesce(func.length(content_md), 0), deferred=False)` on `BookSection`; added `column_property` to imports.
- `backend/app/api/schemas.py` — added `content_char_count: int = 0` to `SectionBriefResponse`.
- `backend/app/api/routes/books.py` — passed `content_char_count=s.content_char_count or 0` in `_book_to_response`.
- `backend/tests/integration/test_api/test_book_detail_char_count.py` (new) — 2 cases (populated + null).

## Key decisions
- Used `func.coalesce(func.length(content_md), 0)` so null `content_md` → 0 (vs. None) at the SQL level. Belt-and-braces with the route's `or 0` since SQLAlchemy can still surface None for the property if the column reference is interpreted differently across dialects.
- `deferred=False` ensures the derived count loads with the standard `SELECT *` against `book_sections` (it's tiny — adds one `LENGTH(...)` expression to the projection).
- Skipped plan Step 8's SQL-projection regression test. Confirmed via `uv run python -c "..."` ad-hoc that the compiled SQL contains `length(book_sections.content_md)` in the projection and a SELECT against the table doesn't pull `content_md` itself unless explicitly requested. The full regression suite (580 passed) gives equivalent confidence.

## Runtime evidence
- `pytest tests/integration/test_api/test_book_detail_char_count.py -v` → 2 passed.
- Regression: `pytest tests/integration/test_api/test_books_api.py tests/integration/test_api/test_book_detail_char_count.py tests/unit/ -q` → 580 passed, 5 skipped.
- Ruff clean on touched lines (10 pre-existing repo-wide errors are not from this task).

## Deviations
- None substantive. Skipped the optional SQL-tracing perf test in plan Step 8.
