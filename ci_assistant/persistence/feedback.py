from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import DiagnosisFeedback


class DiagnosisFeedbackRepository:
    """持久化诊断反馈并生成租户级汇总。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        diagnosis_id: UUID,
        tenant_id: UUID,
        rating: str,
        accepted_suggestion: bool | None,
        corrected_error_type: str | None,
        comment: str | None,
    ) -> DiagnosisFeedback:
        """按诊断 ID 创建或更新唯一反馈。"""
        feedback = (
            await self.session.execute(
                select(DiagnosisFeedback).where(
                    DiagnosisFeedback.diagnosis_id == diagnosis_id
                )
            )
        ).scalar_one_or_none()
        if feedback is None:
            feedback = DiagnosisFeedback(
                diagnosis_id=diagnosis_id,
                tenant_id=tenant_id,
                rating=rating,
                accepted_suggestion=accepted_suggestion,
                corrected_error_type=corrected_error_type,
                comment=comment,
            )
            self.session.add(feedback)
        else:
            feedback.rating = rating
            feedback.accepted_suggestion = accepted_suggestion
            feedback.corrected_error_type = corrected_error_type
            feedback.comment = comment
        await self.session.flush()
        return feedback

    async def get_by_diagnosis(
        self, diagnosis_id: UUID
    ) -> DiagnosisFeedback | None:
        """按诊断 ID 获取反馈。"""
        return (
            await self.session.execute(
                select(DiagnosisFeedback).where(
                    DiagnosisFeedback.diagnosis_id == diagnosis_id
                )
            )
        ).scalar_one_or_none()

    async def summary(self, tenant_id: UUID) -> dict[str, Any]:
        """汇总租户反馈数量、评分与建议采纳率。"""
        counts = (
            await self.session.execute(
                select(
                    func.count(DiagnosisFeedback.id),
                    func.count(
                        case(
                            (DiagnosisFeedback.accepted_suggestion.is_(True), 1)
                        )
                    ),
                    func.count(DiagnosisFeedback.accepted_suggestion),
                ).where(DiagnosisFeedback.tenant_id == tenant_id)
            )
        ).one()
        ratings = (
            await self.session.execute(
                select(
                    DiagnosisFeedback.rating,
                    func.count(DiagnosisFeedback.id),
                )
                .where(DiagnosisFeedback.tenant_id == tenant_id)
                .group_by(DiagnosisFeedback.rating)
            )
        ).all()
        total, accepted, acceptance_total = (int(value or 0) for value in counts)
        return {
            "total": total,
            "ratings": {rating: int(count) for rating, count in ratings},
            "accepted_suggestions": accepted,
            "acceptance_total": acceptance_total,
            "acceptance_rate": (
                accepted / acceptance_total if acceptance_total else None
            ),
        }
