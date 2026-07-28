from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import AnalysisTrace, Diagnosis
from .repositories import Repository


class DiagnosisRepository(Repository[Diagnosis]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Diagnosis)

    async def get_by_trace_id(self, trace_id: str) -> Diagnosis | None:
        """获取 ``get_by_trace_id`` 对应的数据。"""
        result = await self.session.execute(
            select(Diagnosis).where(Diagnosis.trace_id == trace_id)
        )
        return result.scalar_one_or_none()

    async def mark_running(self, diagnosis: Diagnosis) -> None:
        """更新 ``mark_running`` 对应的状态。"""
        diagnosis.status = "running"
        await self.session.flush()

    async def mark_succeeded(
        self,
        diagnosis: Diagnosis,
        *,
        result: dict[str, Any],
        trace: dict[str, Any],
        prompt_version: str | None = None,
        model_name: str | None = None,
        index_version: str | None = None,
    ) -> AnalysisTrace:
        """更新 ``mark_succeeded`` 对应的状态。"""
        diagnosis.status = "succeeded"
        diagnosis.result = result
        analysis_trace = AnalysisTrace(
            diagnosis_id=diagnosis.id,
            prompt_version=prompt_version,
            model_name=model_name,
            index_version=index_version,
            trace_data=trace,
        )
        self.session.add(analysis_trace)
        await self.session.flush()
        return analysis_trace

    async def mark_failed(self, diagnosis: Diagnosis, error_code: str) -> None:
        """更新 ``mark_failed`` 对应的状态。"""
        diagnosis.status = "failed"
        diagnosis.error_code = error_code
        await self.session.flush()

