# Session Log

## 2026-04-04 — V1.1 Enhancements: Faceted presets, summary log, section editing

- **V1.1 scope**: Replaced monolithic summarization with a faceted preset system (4 dimensions: style/audience/compression/content_focus), append-only summary log (`summaries` table replacing inline `summary_md` columns), section editing REPL (merge/split/reorder/delete with undo), quality validation (10 deterministic heuristics), and summary comparison with concept diff. 4 new services, 3 new CLI sub-apps, 15 Jinja2 fragments, 5 system presets.
- Built across 13 tasks using subagent-driven development in a git worktree, dispatching 2-3 parallel implementation agents at a time for independent tasks — total 16 commits, 111 files changed, ~6500 insertions
- **Enum casing bug**: SQLAlchemy `Enum(SummaryContentType)` sends member NAMES (uppercase `BOOK`) to PostgreSQL by default, but the migration created the enum with lowercase VALUES (`book`). Fix: `values_callable=lambda x: [e.value for e in x]` on the mapped column
- **Alembic async enum creation**: `sa.Enum.create(checkfirst=True)` doesn't work reliably with asyncpg — the `checkfirst` query runs in a different transaction context. Fix: use raw SQL `DO $$ BEGIN CREATE TYPE ... EXCEPTION WHEN duplicate_object THEN NULL; END $$`
- **Missing session.commit() pattern**: Services use `flush()` (sends SQL, stays in transaction) but CLI commands must explicitly `commit()`. The `get_services()` context manager does NOT auto-commit — discovered when book-level summaries vanished after "successful" generation. Every CLI command that writes data needs an explicit `await svc["session"].commit()`
- **Rich table truncation in E2E tests**: Rich truncates long cell values with `…` when terminal width is narrow (subprocess capture). E2E assertions must check for partial strings, not full values
- **Worktree + Docker gotcha**: Docker compose in the worktree tries to create a new container with the same name as the original project's container. Use the existing container instead of `docker compose up` in the worktree.
- Takeaway: Always run real data through new pipelines during verification — unit/integration tests all passed but the missing `commit()` bug only surfaced when actually summarizing a book end-to-end with the CLI
