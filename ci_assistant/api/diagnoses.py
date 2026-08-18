from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.api.dependencies import get_session
from ci_assistant.api.auth import enforce_tenant
from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.persistence.diagnoses import DiagnosisRepository
from ci_assistant.persistence.connections import CIConnectionRepository
from ci_assistant.persistence.entities import Diagnosis
from ci_assistant.schemas.diagnosis import (
    CreateLogDiagnosisRequest,
    CreateRunDiagnosisRequest,
    DiagnosisAccepted,
    DiagnosisView,
)
from ci_assistant.diagnosis.log_preprocessor import preprocess_log


router = APIRouter(prefix="/api/v1/diagnoses", tags=["diagnoses"])


def _dispatch(request: Request, diagnosis_id: UUID) -> None:
    """将诊断 ID 派发给 Celery 诊断任务；未配置派发器时保持无操作。"""

    dispatcher = getattr(request.app.state, "task_dispatcher", None)
    if dispatcher is not None:
        dispatcher("ci_assistant.diagnose", str(diagnosis_id))


@router.post("/logs", status_code=status.HTTP_202_ACCEPTED)
async def create_log_diagnosis(
    payload: CreateLogDiagnosisRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """接收原始 CI 日志并创建异步诊断。
    校验租户后对日志执行截断、错误片段提取和敏感信息脱敏，再保存 ``queued`` 记录。
    数据库生成诊断 ID 后，将其派发给 ``ci_assistant.diagnose`` Celery 任务，并返回诊断
    ID、追踪 ID 和初始状态。
    """
    # Tenant 鉴权
    enforce_tenant(request, payload.tenant_id)
    # diagnoses 写入 queued
    repository = DiagnosisRepository(session)
    diagnosis = Diagnosis(
        tenant_id=payload.tenant_id,
        project_id=payload.project_id,
        trace_id=f"trace_{uuid4().hex}",
        status="queued",
        source="log",
        result={
            "log": preprocess_log(payload.log_text),
            "use_rag": payload.use_rag,
            "use_tools": payload.use_tools,
            "mode": payload.mode,
        },
        error_code=None,
    )
    await repository.add(diagnosis)

    _dispatch(request, diagnosis.id)

    data = DiagnosisAccepted(
        diagnosis_id=diagnosis.id,
        trace_id=diagnosis.trace_id,
        status="queued",
    )
    return {"request_id": request.state.request_id, "data": data, "error": None}


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run_diagnosis(
    payload: CreateRunDiagnosisRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """根据已配置的 CI Run 创建异步诊断。
    查询连接并按其所属租户鉴权，再通过统一 Provider 获取规范化 Run；
    连接不存在或未配置时返回稳定错误。
    随后保存 ``queued`` 记录并派发其 ID。
    Job 与日志由 Celery Worker 按已保存的 Run 上下文获取。
    """
    connection = await CIConnectionRepository(session).get_by_external_id(
        payload.connection_id
    )
    if connection is None:
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "CI connection not found",
            status_code=404,
        )
    enforce_tenant(request, connection.tenant_id)
    try:
        provider = request.app.state.provider_manager.get(payload.connection_id)
        run = await provider.get_run(payload.project_ref, payload.run_id)
    except KeyError as exc:
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "CI connection not configured",
            status_code=404,
        ) from exc

    diagnosis = Diagnosis(
        tenant_id=connection.tenant_id,
        project_id=payload.project_id,
        trace_id=f"trace_{uuid4().hex}",
        status="queued",
        source="run",
        result={
            "connection_id": payload.connection_id,
            "project_ref": payload.project_ref,
            "run": run.model_dump(mode="json"),
            "use_rag": payload.use_rag,
            "use_tools": payload.use_tools,
            "mode": payload.mode,
        },
        error_code=None,
    )
    await DiagnosisRepository(session).add(diagnosis)
    _dispatch(request, diagnosis.id)
    data = DiagnosisAccepted(
        diagnosis_id=diagnosis.id,
        trace_id=diagnosis.trace_id,
        status="queued",
    )
    return {"request_id": request.state.request_id, "data": data, "error": None}


@router.get("/{diagnosis_id}")
async def get_diagnosis(
    diagnosis_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """按诊断 ID 查询当前状态和结果，并强制执行记录所属租户隔离。

    诊断不存在时返回稳定的资源不存在错误；存在时将持久化实体转换为 ``DiagnosisView``，
    与当前请求 ID 一并封装为统一 API Envelope。该接口只查询状态，不会重复派发诊断任务。
    """
    diagnosis = await DiagnosisRepository(session).get(diagnosis_id)
    if diagnosis is None:
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Diagnosis not found",
            status_code=404,
        )
    enforce_tenant(request, diagnosis.tenant_id)
    return {
        "request_id": request.state.request_id,
        "data": DiagnosisView.model_validate(diagnosis),
        "error": None,
    }
