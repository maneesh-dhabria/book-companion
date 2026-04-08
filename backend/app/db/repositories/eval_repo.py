"""EvalTrace repository — data access layer."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvalTrace


class EvalTraceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, trace: EvalTrace) -> EvalTrace:
        self.session.add(trace)
        await self.session.flush()
        return trace

    async def get_by_section(self, section_id: int, include_stale: bool = False) -> list[EvalTrace]:
        query = select(EvalTrace).where(EvalTrace.section_id == section_id)
        if not include_stale:
            query = query.where(EvalTrace.is_stale.is_(False))
        result = await self.session.execute(query.order_by(EvalTrace.created_at.desc()))
        return list(result.scalars().all())

    async def get_by_assertion(
        self, assertion_name: str, passed: bool | None = None
    ) -> list[EvalTrace]:
        query = select(EvalTrace).where(
            EvalTrace.assertion_name == assertion_name,
            EvalTrace.is_stale.is_(False),
        )
        if passed is not None:
            query = query.where(EvalTrace.passed == passed)
        result = await self.session.execute(query.order_by(EvalTrace.created_at.desc()))
        return list(result.scalars().all())

    async def get_by_summary(self, summary_id: int, include_stale: bool = False) -> list[EvalTrace]:
        query = select(EvalTrace).where(EvalTrace.summary_id == summary_id)
        if not include_stale:
            query = query.where(EvalTrace.is_stale.is_(False))
        result = await self.session.execute(
            query.order_by(EvalTrace.assertion_category, EvalTrace.assertion_name)
        )
        return list(result.scalars().all())

    async def get_by_eval_run_id(self, eval_run_id: str) -> list[EvalTrace]:
        result = await self.session.execute(
            select(EvalTrace)
            .where(EvalTrace.eval_run_id == eval_run_id)
            .order_by(EvalTrace.assertion_category, EvalTrace.assertion_name)
        )
        return list(result.scalars().all())

    async def get_aggregated_results(
        self, section_id: int | None = None, include_stale: bool = False
    ) -> list[tuple[str, str, int, int]]:
        """Return (assertion_name, assertion_category, pass_count, total_count)."""
        query = select(
            EvalTrace.assertion_name,
            EvalTrace.assertion_category,
            func.count().filter(EvalTrace.passed.is_(True)).label("pass_count"),
            func.count().label("total_count"),
        )
        if not include_stale:
            query = query.where(EvalTrace.is_stale.is_(False))
        query = query.group_by(EvalTrace.assertion_name, EvalTrace.assertion_category)

        if section_id:
            query = query.where(EvalTrace.section_id == section_id)

        result = await self.session.execute(query)
        return list(result.all())

    async def mark_stale_by_section(self, section_id: int) -> int:
        """Mark all traces for a section as stale. Returns count of affected rows."""
        result = await self.session.execute(
            update(EvalTrace)
            .where(EvalTrace.section_id == section_id, EvalTrace.is_stale.is_(False))
            .values(is_stale=True)
        )
        return result.rowcount

    async def mark_stale_by_summary(self, summary_id: int) -> int:
        """Mark all traces for a summary as stale. Returns count of affected rows."""
        result = await self.session.execute(
            update(EvalTrace)
            .where(EvalTrace.summary_id == summary_id, EvalTrace.is_stale.is_(False))
            .values(is_stale=True)
        )
        return result.rowcount

    async def count_by_section_ids(self, section_ids: list[int]) -> int:
        """Count non-stale traces for a list of section IDs."""
        result = await self.session.execute(
            select(func.count())
            .select_from(EvalTrace)
            .where(EvalTrace.section_id.in_(section_ids), EvalTrace.is_stale.is_(False))
        )
        return result.scalar() or 0
