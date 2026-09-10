import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from ci_assistant.api.diagnoses import create_log_diagnosis
from ci_assistant.persistence.agent import ActionProposalRepository, AgentRunRepository
from ci_assistant.persistence.diagnoses import DiagnosisRepository
from ci_assistant.persistence.entities import ActionProposal, AgentRun, AgentStepRecord, Diagnosis
from ci_assistant.schemas.agent import AgentCheckpoint, AgentRunState, AgentStep
from ci_assistant.schemas.diagnosis import CreateLogDiagnosisRequest


def test_diagnosis_is_committed_before_task_dispatch(monkeypatch) -> None:
    """验证 API 只在诊断事务提交后向 Celery 派发任务。"""
    events: list[str] = []
    session = MagicMock()
    session.commit = AsyncMock(side_effect=lambda: events.append("commit"))

    async def fake_add(repository, diagnosis):
        """模拟刷新后已有主键的 Diagnosis。"""
        del repository
        diagnosis.id = uuid4()
        events.append("add")
        return diagnosis

    request = MagicMock()
    request.state.request_id = "req-test"
    request.app.state.task_dispatcher = (
        lambda task, identifier: events.append(f"dispatch:{task}:{identifier}")
    )
    monkeypatch.setattr(DiagnosisRepository, "add", fake_add)
    payload = CreateLogDiagnosisRequest(
        tenant_id=uuid4(),
        log_text="ModuleNotFoundError: requests",
        use_rag=False,
        use_tools=False,
        mode="agent",
    )
    asyncio.run(create_log_diagnosis(payload, request, session))
    assert events[0:2] == ["add", "commit"]
    assert events[2].startswith("dispatch:ci_assistant.diagnose:")


def test_diagnosis_claim_uses_skip_locked_row_lock() -> None:
    """验证 Worker 通过 PostgreSQL SKIP LOCKED 防止并发消费同一诊断。"""
    diagnosis = Diagnosis(
        id=uuid4(), tenant_id=uuid4(), project_id=None, trace_id="trace-claim",
        status="queued", source="log", result={}, error_code=None,
    )
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = diagnosis
    session = MagicMock()
    session.execute = AsyncMock(return_value=scalar_result)
    loaded = asyncio.run(DiagnosisRepository(session).get_for_processing(diagnosis.id))
    statement = session.execute.await_args.args[0]
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert loaded is diagnosis
    assert "FOR UPDATE" in compiled
    assert "SKIP LOCKED" in compiled


def test_expired_proposal_state_is_returned_without_raising() -> None:
    """验证仓储层持久化 expired 后正常返回冲突，避免事务回滚。"""
    proposal = ActionProposal(
        id=uuid4(), diagnosis_id=uuid4(), agent_run_id=None, tenant_id=uuid4(),
        action_type="ci_rerun", target="pipeline/7", arguments_hash="a" * 64,
        arguments_summary={}, risk="high", status="pending",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = proposal
    session = MagicMock()
    session.execute = AsyncMock(return_value=scalar_result)
    session.flush = AsyncMock()
    outcome = asyncio.run(
        ActionProposalRepository(session).decide(
            proposal.id,
            decision="approved",
            reason=None,
            request_id="req-expired",
        )
    )
    assert outcome is not None
    assert outcome.conflict == "proposal has expired"
    assert outcome.proposal.status == "expired"
    session.flush.assert_awaited_once()


def test_non_pending_proposal_cannot_create_second_audit() -> None:
    """验证已决策提案在行锁内返回冲突且不会新增 Audit。"""
    proposal = ActionProposal(
        id=uuid4(), diagnosis_id=uuid4(), agent_run_id=None, tenant_id=uuid4(),
        action_type="draft_comment", target="merge-request/7", arguments_hash="b" * 64,
        arguments_summary={}, risk="low", status="approved", expires_at=None,
    )
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = proposal
    session = MagicMock()
    session.execute = AsyncMock(return_value=scalar_result)
    session.flush = AsyncMock()
    outcome = asyncio.run(
        ActionProposalRepository(session).decide(
            proposal.id,
            decision="rejected",
            reason="late decision",
            request_id="req-second",
        )
    )
    assert outcome is not None
    assert outcome.conflict == "proposal is no longer pending"
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


def test_checkpoint_replay_is_idempotent() -> None:
    """验证同一序号和幂等键的 Step 重放不会重复插入。"""
    run = AgentRun(
        id=uuid4(), diagnosis_id=uuid4(), tenant_id=uuid4(), goal="Diagnose",
        status="running", rounds=1, tool_calls=1, prompt_chars=100,
        estimated_input_tokens=25, model_input_tokens=0, model_output_tokens=0,
        stop_reason=None, phase="running", result_snapshot=None,
    )
    step = AgentStep(
        round=1,
        action="tool_request",
        tool_name="get_job_context",
        evidence_gap="Need current job status",
        tool_fingerprint="f" * 64,
    )
    state = AgentRunState(
        goal=run.goal,
        rounds=1,
        tool_calls=1,
        prompt_chars=100,
        estimated_input_tokens=25,
        steps=[step],
    )
    ordinal = 1
    key = hashlib.sha256(
        f"{run.id}:{ordinal}:{step.tool_fingerprint}".encode()
    ).hexdigest()
    existing = AgentStepRecord(
        id=uuid4(), agent_run_id=run.id, tenant_id=run.tenant_id,
        ordinal=ordinal, idempotency_key=key, round=1, action=step.action,
        tool_name=step.tool_name, evidence_gap=step.evidence_gap,
        tool_fingerprint=step.tool_fingerprint,
        observation_summary=None, observation_context=None, error_code=None,
    )
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = existing
    session = MagicMock()
    session.execute = AsyncMock(return_value=scalar_result)
    session.flush = AsyncMock()
    asyncio.run(
        AgentRunRepository(session).checkpoint(
            run,
            AgentCheckpoint(state=state, step=step),
        )
    )
    session.add.assert_not_called()
    session.flush.assert_awaited_once()
