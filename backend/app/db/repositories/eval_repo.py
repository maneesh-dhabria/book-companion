"""EvalTrace repository — data access layer."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvalTrace


class EvalTraceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, trace: EvalTrace) -> EvalTrace:
        self.session.add(trace)
        await self.session.flush()
        return trace

    async def get_by_section(self, section_id: int) -> list[EvalTrace]:
        result = await self.session.execute(
            select(EvalTrace)
            .where(EvalTrace.section_id == section_id)
            .order_by(EvalTrace.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_assertion(
        self, assertion_name: str, passed: bool | None = None
    ) -> list[EvalTrace]:
        query = select(EvalTrace).where(EvalTrace.assertion_name == assertion_name)
        if passed is not None:
            query = query.where(EvalTrace.passed == passed)
        result = await self.session.execute(query.order_by(EvalTrace.created_at.desc()))
        return list(result.scalars().all())

    async def get_by_summary(self, summary_id: int) -> list[EvalTrace]:
        result = await self.session.execute(
            select(EvalTrace)
            .where(EvalTrace.summary_id == summary_id)
            .order_by(EvalTrace.assertion_category, EvalTrace.assertion_name)
        )
        return list(result.scalars().all())

    async def get_aggregated_results(
        self, section_id: int | None = None
    ) -> list[tuple[str, str, int, int]]:
        """Return (assertion_name, assertion_category, pass_count, total_count)."""
        query = select(
            EvalTrace.assertion_name,
            EvalTrace.assertion_category,
            func.count().filter(EvalTrace.passed.is_(True)).label("pass_count"),
            func.count().label("total_count"),
        ).group_by(EvalTrace.assertion_name, EvalTrace.assertion_category)

        if section_id:
            query = query.where(EvalTrace.section_id == section_id)

        result = await self.session.execute(query)
        return list(result.all())
