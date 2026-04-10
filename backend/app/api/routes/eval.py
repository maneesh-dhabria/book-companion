"""Eval results endpoints for sections and books."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.api.schemas import (
    AssertionResultResponse,
    BookEvalResponse,
    EvalResultResponse,
)
from app.db.models import Book, BookSection, EvalTrace

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])


@router.get("/section/{section_id}")
async def get_section_eval(
    section_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get eval results for a section's default summary."""
    result = await db.execute(select(BookSection).where(BookSection.id == section_id))
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    if not section.default_summary_id:
        raise HTTPException(status_code=404, detail="No default summary for section")

    result = await db.execute(
        select(EvalTrace)
        .where(
            EvalTrace.summary_id == section.default_summary_id,
            EvalTrace.is_stale == False,  # noqa: E712
        )
        .order_by(EvalTrace.created_at.desc())
    )
    traces = result.scalars().all()

    if not traces:
        raise HTTPException(status_code=404, detail="No eval results found")

    passed = sum(1 for t in traces if t.passed)
    eval_run_id = traces[0].eval_run_id if traces else None

    return EvalResultResponse(
        section_id=section_id,
        summary_id=section.default_summary_id,
        passed=passed,
        total=len(traces),
        eval_run_id=eval_run_id,
        assertions=[
            AssertionResultResponse(
                name=t.assertion_name,
                category=t.assertion_category,
                passed=t.passed,
                reasoning=t.reasoning,
                likely_cause=t.likely_cause,
                suggestion=t.suggestion,
            )
            for t in traces
        ],
    )


@router.get("/book/{book_id}")
async def get_book_eval(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated eval results across all sections of a book."""
    result = await db.execute(
        select(Book).where(Book.id == book_id).options(selectinload(Book.sections))
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    sections_with_eval = []
    overall_passed = 0
    overall_total = 0

    for section in book.sections:
        if not section.default_summary_id:
            continue
        result = await db.execute(
            select(EvalTrace)
            .where(
                EvalTrace.summary_id == section.default_summary_id,
                EvalTrace.is_stale == False,  # noqa: E712
            )
            .order_by(EvalTrace.created_at.desc())
        )
        traces = result.scalars().all()
        if not traces:
            continue

        passed = sum(1 for t in traces if t.passed)
        overall_passed += passed
        overall_total += len(traces)

        sections_with_eval.append(
            EvalResultResponse(
                section_id=section.id,
                summary_id=section.default_summary_id,
                passed=passed,
                total=len(traces),
                eval_run_id=traces[0].eval_run_id if traces else None,
                assertions=[
                    AssertionResultResponse(
                        name=t.assertion_name,
                        category=t.assertion_category,
                        passed=t.passed,
                        reasoning=t.reasoning,
                        likely_cause=t.likely_cause,
                        suggestion=t.suggestion,
                    )
                    for t in traces
                ],
            )
        )

    return BookEvalResponse(
        book_id=book_id,
        total_sections=len(book.sections),
        evaluated_sections=len(sections_with_eval),
        overall_passed=overall_passed,
        overall_total=overall_total,
        sections=sections_with_eval,
    )
