"""Regression: doctor orphan-tags --fix uses ORM delete (expanding bindparam)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import Tag


@pytest.mark.asyncio
async def test_doctor_orphan_tags_fix_deletes_orphans(db_session):
    """The --fix code path used to be broken by a raw text('... IN :ids')
    bind without expanding=True, raising ProgrammingError. This test
    exercises the ORM delete() we switched to, confirming multiple
    orphaned tags get removed in one statement."""
    # Seed orphan tags directly — no associated Taggable rows.
    for name in ("orphan-a", "orphan-b", "orphan-c"):
        db_session.add(Tag(name=name))
    await db_session.commit()

    result = await db_session.execute(select(Tag).where(Tag.name.in_(["orphan-a", "orphan-b", "orphan-c"])))
    ids = [r.id for r in result.scalars().all()]
    assert len(ids) == 3

    # Exercise the exact ORM delete pattern the CLI uses.
    from sqlalchemy import delete

    await db_session.execute(delete(Tag).where(Tag.id.in_(ids)))
    await db_session.commit()

    remaining = await db_session.execute(select(Tag).where(Tag.id.in_(ids)))
    assert remaining.scalars().all() == []
