"""v1.4b data backfill — cleanup empty summaries + set default_summary_id

Two-phase migration (per spec FR-A6.3 / FR-A6.4):

1. Pre-backup — copy ``library.db`` to ``library.db.pre-v1-4-<ts>.bak``
   before touching anything. Abort on backup failure.
2. Part A — delete any ``summaries`` row with an empty / whitespace-only
   ``summary_md``. For each deleted row, stamp its ``BookSection`` with
   ``last_failure_type='empty_output'`` UNLESS the section already carries
   a non-empty, non-``empty_output`` failure (P-3 guard: don't overwrite
   newer diagnostic state with older reconstructed state).
3. Part B — for every section with at least one non-empty summary but
   ``default_summary_id IS NULL``, set it to the latest non-empty summary
   by created_at.

Idempotent. A second run finds zero empty rows and zero missing defaults.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-22 13:00:00
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence  # noqa: TC003
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
import structlog
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = structlog.get_logger()


def _resolve_db_path() -> Path | None:
    """Derive the live SQLite path from the current Settings. Returns
    ``None`` for non-SQLite DBs or if the path can't be resolved."""
    try:
        from app.config import Settings

        settings = Settings()
    except Exception:  # pragma: no cover — defensive
        return None
    url = settings.database.url
    # ``sqlite+aiosqlite:///...`` or ``sqlite:///...``
    prefix_candidates = ("sqlite+aiosqlite:///", "sqlite:///")
    for prefix in prefix_candidates:
        if url.startswith(prefix):
            return Path(url[len(prefix):])
    return None


def _create_pre_backup() -> Path | None:
    db_path = _resolve_db_path()
    if db_path is None or not db_path.exists():
        log.info("v1_4b_pre_backup_skipped", reason="no_db_path")
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"library.db.pre-v1-4-{ts}.bak"
    shutil.copy2(str(db_path), str(backup_path))
    log.info("v1_4b_pre_backup_created", path=str(backup_path))
    return backup_path


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1 — pre-backup. Spec FR-A6.3 mandates we abort on failure.
    try:
        _create_pre_backup()
    except Exception as exc:
        log.error("v1_4b_pre_backup_failed", error=str(exc))
        raise

    # Step 2 — locate empty-summary rows.
    empty_rows = list(
        conn.execute(
            sa.text(
                "SELECT s.id AS summary_id, s.content_id AS section_id "
                "FROM summaries s "
                "WHERE s.content_type = 'section' "
                "  AND TRIM(COALESCE(s.summary_md,'')) = ''"
            )
        )
    )

    deleted = 0
    stamped = 0
    for row in empty_rows:
        summary_id = row.summary_id
        section_id = row.section_id
        # Delete the summary row first.
        conn.execute(
            sa.text("DELETE FROM summaries WHERE id = :id"),
            {"id": summary_id},
        )
        deleted += 1
        # Clear default_summary_id if it was pointing at the deleted row.
        conn.execute(
            sa.text(
                "UPDATE book_sections "
                "SET default_summary_id = NULL "
                "WHERE default_summary_id = :sid"
            ),
            {"sid": summary_id},
        )
        # P-3 guard — only stamp if the section has no failure, OR the
        # existing failure was itself the empty-output type. Never overwrite
        # a freshly captured typed failure with reconstructed state.
        result = conn.execute(
            sa.text(
                "UPDATE book_sections "
                "SET last_failure_type = 'empty_output', "
                "    last_failure_message = COALESCE(last_failure_message, "
                "       'Previous run produced an empty summary.') "
                "WHERE id = :sid "
                "  AND (last_failure_type IS NULL OR last_failure_type = 'empty_output')"
            ),
            {"sid": section_id},
        )
        if result.rowcount:
            stamped += 1

    # Step 3 — backfill default_summary_id for sections that have ≥1 non-empty
    # summary but no default set. Pick the latest non-empty summary by
    # created_at (tie-break: highest id).
    backfilled = list(
        conn.execute(
            sa.text(
                """
                WITH candidate AS (
                    SELECT bs.id AS section_id,
                           (
                               SELECT s2.id FROM summaries s2
                               WHERE s2.content_type = 'section'
                                 AND s2.content_id = bs.id
                                 AND TRIM(COALESCE(s2.summary_md,'')) <> ''
                               ORDER BY s2.created_at DESC, s2.id DESC
                               LIMIT 1
                           ) AS summary_id
                    FROM book_sections bs
                    WHERE bs.default_summary_id IS NULL
                )
                SELECT section_id, summary_id FROM candidate
                WHERE summary_id IS NOT NULL
                """
            )
        )
    )
    for row in backfilled:
        conn.execute(
            sa.text(
                "UPDATE book_sections SET default_summary_id = :sid WHERE id = :bid"
            ),
            {"sid": row.summary_id, "bid": row.section_id},
        )

    log.info(
        "v1_4b_backfill_totals",
        empty_summaries_deleted=deleted,
        failure_cols_stamped=stamped,
        default_summary_id_backfilled=len(backfilled),
    )


def downgrade() -> None:
    # Data migrations are intentionally one-way. The pre-backup file lets
    # operators restore manually; Alembic just forgets the revision.
    log.info("v1_4b_backfill_downgrade_noop")
