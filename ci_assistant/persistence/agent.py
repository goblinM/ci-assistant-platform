from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.schemas.agent import AgentCheckpoint, AgentRunState, AgentStep

from .entities import ActionProposal, ActionProposalAudit, AgentRun, AgentStepRecord


class AgentRunRepository:
    """持久化 Agent 运行检查点并按租户提供安全回放数据。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, diagnosis_id: UUID, tenant_id: UUID, goal: str) -> AgentRun:
        """按诊断幂等获取或创建唯一 Agent Run。"""
        run = (await self.session.execute(select(AgentRun).where(AgentRun.diagnosis_id == diagnosis_id))).scalar_one_or_none()
        if run is None:
            run = AgentRun(diagnosis_id=diagnosis_id, tenant_id=tenant_id, goal=goal)
            self.session.add(run)
            await self.session.flush()
        return run

    async def get(self, run_id: UUID) -> AgentRun | None:
        """按主键读取 Agent Run。"""
        return await self.session.get(AgentRun, run_id)

    async def load_state(self, run: AgentRun) -> tuple[AgentRunState, list[dict]]:
        """从已提交步骤重建预算、指纹和脱敏 Observation 上下文。"""
        records = (await self.session.execute(select(AgentStepRecord).where(AgentStepRecord.agent_run_id == run.id).order_by(AgentStepRecord.ordinal))).scalars().all()
        steps = [AgentStep(round=item.round, action=item.action, tool_name=item.tool_name, tool_fingerprint=item.tool_fingerprint, observation=item.observation_summary, error_code=item.error_code) for item in records]
        state = AgentRunState(goal=run.goal, status="running", rounds=run.rounds, tool_calls=run.tool_calls, prompt_chars=run.prompt_chars, estimated_input_tokens=run.estimated_input_tokens, model_input_tokens=run.model_input_tokens, model_output_tokens=run.model_output_tokens, steps=steps)
        observations = [item.observation_context for item in records if item.observation_context]
        return state, observations

    async def checkpoint(self, run: AgentRun, checkpoint: AgentCheckpoint) -> None:
        """按步骤序号幂等保存检查点并同步运行预算。"""
        ordinal = len(checkpoint.state.steps)
        key = hashlib.sha256(f"{run.id}:{ordinal}:{checkpoint.step.tool_fingerprint or checkpoint.step.action}".encode()).hexdigest()
        exists = (await self.session.execute(select(AgentStepRecord.id).where(AgentStepRecord.agent_run_id == run.id, AgentStepRecord.idempotency_key == key))).scalar_one_or_none()
        if exists is None:
            self.session.add(AgentStepRecord(agent_run_id=run.id, tenant_id=run.tenant_id, ordinal=ordinal, idempotency_key=key, round=checkpoint.step.round, action=checkpoint.step.action, tool_name=checkpoint.step.tool_name, tool_fingerprint=checkpoint.step.tool_fingerprint, observation_summary=checkpoint.step.observation, observation_context=checkpoint.observation_context, error_code=checkpoint.step.error_code))
        self._copy_state(run, checkpoint.state)
        await self.session.flush()

    async def finish(self, run: AgentRun, state: AgentRunState) -> None:
        """同步 Agent Run 的最终状态和停止原因。"""
        self._copy_state(run, state)
        await self.session.flush()

    @staticmethod
    def _copy_state(run: AgentRun, state: AgentRunState) -> None:
        """把公开运行状态复制到 ORM 实体，不保存 Observation 正文。"""
        run.status = state.status
        run.rounds = state.rounds
        run.tool_calls = state.tool_calls
        run.prompt_chars = state.prompt_chars
        run.estimated_input_tokens = state.estimated_input_tokens
        run.model_input_tokens = state.model_input_tokens
        run.model_output_tokens = state.model_output_tokens
        run.stop_reason = state.stop_reason.value if state.stop_reason else None


class ActionProposalRepository:
    """管理只提案动作及不可变人工审批审计。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, diagnosis_id: UUID, tenant_id: UUID, action_type: str, target: str, arguments_summary: dict, risk: str, expires_at: datetime | None, agent_run_id: UUID | None = None) -> ActionProposal:
        """创建仅含脱敏摘要与不可逆参数指纹的待审批提案。"""
        payload = json.dumps(arguments_summary, ensure_ascii=False, sort_keys=True, default=str)
        proposal = ActionProposal(diagnosis_id=diagnosis_id, agent_run_id=agent_run_id, tenant_id=tenant_id, action_type=action_type, target=target, arguments_hash=hashlib.sha256(payload.encode()).hexdigest(), arguments_summary=arguments_summary, risk=risk, status="pending", expires_at=expires_at)
        self.session.add(proposal)
        await self.session.flush()
        return proposal

    async def get(self, proposal_id: UUID) -> ActionProposal | None:
        """按主键查询动作提案。"""
        return await self.session.get(ActionProposal, proposal_id)

    async def decide(self, proposal: ActionProposal, *, decision: str, reason: str | None, request_id: str) -> ActionProposalAudit:
        """记录审批结论；即使批准也只改变审计状态，不执行动作。"""
        if proposal.status != "pending":
            raise ValueError("proposal is no longer pending")
        if proposal.expires_at and proposal.expires_at <= datetime.now(timezone.utc):
            proposal.status = "expired"
            raise ValueError("proposal has expired")
        proposal.status = decision
        audit = ActionProposalAudit(proposal_id=proposal.id, tenant_id=proposal.tenant_id, decision=decision, reason=reason, request_id=request_id)
        self.session.add(audit)
        await self.session.flush()
        return audit
