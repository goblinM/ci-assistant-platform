from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.api.auth import enforce_tenant
from ci_assistant.api.dependencies import get_session
from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.knowledge.processing import mask_secrets
from ci_assistant.persistence.agent import ActionProposalRepository, AgentRunRepository
from ci_assistant.persistence.diagnoses import DiagnosisRepository
from ci_assistant.persistence.entities import AgentStepRecord
from ci_assistant.schemas.agent import ActionProposalCreate, ActionProposalDecision, ActionProposalView


router = APIRouter(tags=["agent"])


@router.get("/api/v1/agent-runs/{run_id}")
async def replay_agent_run(run_id: UUID, request: Request, session: AsyncSession = Depends(get_session)):
    """按租户返回只读 Agent 回放，明确排除内部 Observation 上下文。"""
    run = await AgentRunRepository(session).get(run_id)
    if run is None:
        raise PlatformError(ErrorCode.RESOURCE_NOT_FOUND, "Agent run not found", status_code=404)
    enforce_tenant(request, run.tenant_id)
    steps = (await session.execute(select(AgentStepRecord).where(AgentStepRecord.agent_run_id == run.id).order_by(AgentStepRecord.ordinal))).scalars().all()
    return {"request_id": request.state.request_id, "data": {"id": run.id, "diagnosis_id": run.diagnosis_id, "status": run.status, "goal": run.goal, "rounds": run.rounds, "tool_calls": run.tool_calls, "stop_reason": run.stop_reason, "steps": [{"ordinal": item.ordinal, "round": item.round, "action": item.action, "tool_name": item.tool_name, "tool_fingerprint": item.tool_fingerprint, "observation": item.observation_summary, "error_code": item.error_code} for item in steps]}, "error": None}


@router.post("/api/v1/action-proposals")
async def create_action_proposal(payload: ActionProposalCreate, request: Request, session: AsyncSession = Depends(get_session)):
    """为已有诊断创建脱敏动作提案，不注册或调用任何写执行器。"""
    diagnosis = await DiagnosisRepository(session).get(payload.diagnosis_id)
    if diagnosis is None:
        raise PlatformError(ErrorCode.RESOURCE_NOT_FOUND, "Diagnosis not found", status_code=404)
    enforce_tenant(request, diagnosis.tenant_id)
    summary = {str(key): mask_secrets(str(value))[:500] for key, value in payload.arguments_summary.items()}
    proposal = await ActionProposalRepository(session).create(diagnosis_id=diagnosis.id, tenant_id=diagnosis.tenant_id, action_type=payload.action_type, target=mask_secrets(payload.target), arguments_summary=summary, risk=payload.risk, expires_at=payload.expires_at)
    return {"request_id": request.state.request_id, "data": ActionProposalView.model_validate(proposal), "error": None}


@router.post("/api/v1/action-proposals/{proposal_id}/decision")
async def decide_action_proposal(proposal_id: UUID, payload: ActionProposalDecision, request: Request, session: AsyncSession = Depends(get_session)):
    """审计批准或拒绝提案；批准仅记账且不会触发外部动作。"""
    repository = ActionProposalRepository(session)
    proposal = await repository.get(proposal_id)
    if proposal is None:
        raise PlatformError(ErrorCode.RESOURCE_NOT_FOUND, "Action proposal not found", status_code=404)
    enforce_tenant(request, proposal.tenant_id)
    try:
        await repository.decide(proposal, decision=payload.decision, reason=mask_secrets(payload.reason) if payload.reason else None, request_id=request.state.request_id)
    except ValueError as exc:
        raise PlatformError(ErrorCode.PERMISSION_DENIED, str(exc), status_code=409) from exc
    return {"request_id": request.state.request_id, "data": ActionProposalView.model_validate(proposal), "error": None}
