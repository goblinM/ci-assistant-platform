from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ci_assistant.schemas.result import DiagnosisResult


class AgentStopReason(str, Enum):
    """定义只读 Agent Loop 可观测且稳定的终止原因。"""

    COMPLETED = "completed"
    MAX_ROUNDS = "max_rounds"
    TOOL_BUDGET_EXHAUSTED = "tool_budget_exhausted"
    CONTEXT_BUDGET_EXHAUSTED = "context_budget_exhausted"
    TIMEOUT = "timeout"
    REPEATED_CALL = "repeated_call"
    POLICY_DENIED = "policy_denied"
    MODEL_ERROR = "model_error"
    FALLBACK = "fallback"
    APPROVAL_REQUIRED = "approval_required"


class AgentDecision(BaseModel):
    """表示模型在单轮中做出的最终回答或只读工具请求。"""

    action: Literal["final_answer", "tool_request"]
    tool_name: str | None = None
    evidence_gap: str | None = Field(default=None, max_length=500)
    final_result: DiagnosisResult | None = None
    input_tokens: int = Field(default=0, ge=0, exclude=True)
    output_tokens: int = Field(default=0, ge=0, exclude=True)

    @model_validator(mode="after")
    def validate_action_payload(self) -> AgentDecision:
        """保证每轮决策只携带当前动作需要的一种有效载荷。"""
        if self.action == "tool_request":
            if not self.tool_name:
                raise ValueError("tool_request requires tool_name")
            if not self.evidence_gap or not self.evidence_gap.strip():
                raise ValueError("tool_request requires evidence_gap")
        if self.action == "final_answer" and self.final_result is None:
            raise ValueError("final_answer requires final_result")
        return self


class AgentStep(BaseModel):
    """保存单轮 Agent 决策及经过脱敏裁剪的 Observation 摘要。"""

    round: int = Field(ge=1)
    action: Literal["final_answer", "tool_request", "self_check"]
    tool_name: str | None = None
    evidence_gap: str | None = None
    tool_fingerprint: str | None = None
    observation: dict[str, Any] | None = None
    error_code: str | None = None


class AgentRunState(BaseModel):
    """聚合只读 Agent Loop 的目标、预算消耗、步骤和最终停止原因。"""

    goal: str
    status: Literal["running", "succeeded", "stopped", "fallback"] = "running"
    rounds: int = 0
    tool_calls: int = 0
    prompt_chars: int = 0
    estimated_input_tokens: int = 0
    model_input_tokens: int = 0
    model_output_tokens: int = 0
    stop_reason: AgentStopReason | None = None
    steps: list[AgentStep] = Field(default_factory=list)


class AgentCheckpoint(BaseModel):
    """封装可恢复步骤及仅供内部续跑的脱敏受限 Observation。"""

    state: AgentRunState
    step: AgentStep
    observation_context: dict[str, Any] | None = None
    result_snapshot: DiagnosisResult | None = None


class ActionProposalCreate(BaseModel):
    """定义仅记录、不执行的外部动作提案。"""

    diagnosis_id: UUID
    action_type: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=500)
    arguments_summary: dict[str, Any] = Field(default_factory=dict)
    risk: Literal["low", "medium", "high"] = "medium"
    expires_at: datetime | None = None


class ActionProposalDecision(BaseModel):
    """定义提案审批或拒绝请求，审批结果不会触发动作执行。"""

    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=1000)


class ActionProposalView(BaseModel):
    """返回不含完整动作参数的租户级提案与审批状态。"""

    model_config = {"from_attributes": True}

    id: UUID
    diagnosis_id: UUID
    agent_run_id: UUID | None
    tenant_id: UUID
    action_type: str
    target: str
    arguments_hash: str
    arguments_summary: dict[str, Any]
    risk: str
    status: str
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ActionProposalAuditView(BaseModel):
    """返回单次不可变审批审计事件。"""

    model_config = {"from_attributes": True}

    id: UUID
    proposal_id: UUID
    tenant_id: UUID
    decision: str
    reason: str | None
    request_id: str
    created_at: datetime
