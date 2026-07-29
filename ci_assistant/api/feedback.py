from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.api.auth import enforce_tenant
from ci_assistant.api.dependencies import get_session
from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.knowledge.processing import mask_secrets
from ci_assistant.persistence.diagnoses import DiagnosisRepository
from ci_assistant.persistence.feedback import DiagnosisFeedbackRepository
from ci_assistant.schemas.feedback import (
    DiagnosisFeedbackRequest,
    DiagnosisFeedbackView,
    FeedbackSummaryView,
)


router = APIRouter(tags=["feedback"])


@router.post("/api/v1/diagnoses/{diagnosis_id}/feedback")
async def upsert_diagnosis_feedback(
    diagnosis_id: UUID,
    payload: DiagnosisFeedbackRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """创建或更新单条诊断的结构化用户反馈。"""
    diagnosis = await DiagnosisRepository(session).get(diagnosis_id)
    if diagnosis is None:
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Diagnosis not found",
            status_code=404,
        )
    enforce_tenant(request, diagnosis.tenant_id)
    comment = mask_secrets(payload.comment).strip() if payload.comment else None
    feedback = await DiagnosisFeedbackRepository(session).upsert(
        diagnosis_id=diagnosis.id,
        tenant_id=diagnosis.tenant_id,
        rating=payload.rating,
        accepted_suggestion=payload.accepted_suggestion,
        corrected_error_type=payload.corrected_error_type,
        comment=comment or None,
    )
    return {
        "request_id": request.state.request_id,
        "data": DiagnosisFeedbackView.model_validate(feedback),
        "error": None,
    }


@router.get("/api/v1/diagnoses/{diagnosis_id}/feedback")
async def get_diagnosis_feedback(
    diagnosis_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """获取单条诊断的反馈。"""
    diagnosis = await DiagnosisRepository(session).get(diagnosis_id)
    if diagnosis is None:
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Diagnosis not found",
            status_code=404,
        )
    enforce_tenant(request, diagnosis.tenant_id)
    feedback = await DiagnosisFeedbackRepository(session).get_by_diagnosis(
        diagnosis.id
    )
    if feedback is None:
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Diagnosis feedback not found",
            status_code=404,
        )
    return {
        "request_id": request.state.request_id,
        "data": DiagnosisFeedbackView.model_validate(feedback),
        "error": None,
    }


@router.get("/api/v1/feedback/summary")
async def get_feedback_summary(
    tenant_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """获取租户级反馈评分和建议采纳汇总。"""
    enforce_tenant(request, tenant_id)
    summary = await DiagnosisFeedbackRepository(session).summary(tenant_id)
    return {
        "request_id": request.state.request_id,
        "data": FeedbackSummaryView.model_validate(summary),
        "error": None,
    }
