from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from ci_assistant.api.dependencies import get_session
from ci_assistant.main import create_app
from ci_assistant.persistence.agent import ProposalDecisionResult
from ci_assistant.persistence.entities import ActionProposal, Diagnosis


def test_proposal_approval_only_updates_audit_state(monkeypatch) -> None:
    """验证批准提案只调用审计仓储，不存在任何动作执行调用。"""
    tenant_id = uuid4()
    proposal = ActionProposal(
        id=uuid4(), diagnosis_id=uuid4(), agent_run_id=None, tenant_id=tenant_id,
        action_type="draft_comment", target="merge-request/7", arguments_hash="a" * 64,
        arguments_summary={"body": "safe draft"}, risk="low", status="pending",
        expires_at=None, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )

    async def fake_session():
        """提供无需数据库的 API 依赖替身。"""
        yield object()

    async def fake_get(repository, identifier):
        """返回固定待审批提案。"""
        return proposal

    async def fake_decide(repository, proposal_id, **values):
        """模拟仅更新状态和写审计事件。"""
        del repository, values
        assert proposal_id == proposal.id
        proposal.status = "approved"
        return ProposalDecisionResult(proposal=proposal, audit=None)

    monkeypatch.setattr("ci_assistant.persistence.agent.ActionProposalRepository.get", fake_get)
    monkeypatch.setattr("ci_assistant.persistence.agent.ActionProposalRepository.decide", fake_decide)
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    response = TestClient(app).post(
        f"/api/v1/action-proposals/{proposal.id}/decision",
        json={"decision": "approved", "reason": "reviewed"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"


def test_expired_proposal_returns_conflict_with_persistable_state(monkeypatch) -> None:
    """验证过期提案通过正常响应返回 409，使 expired 状态可随事务提交。"""
    tenant_id = uuid4()
    proposal = ActionProposal(
        id=uuid4(), diagnosis_id=uuid4(), agent_run_id=None, tenant_id=tenant_id,
        action_type="ci_rerun", target="pipeline/7", arguments_hash="a" * 64,
        arguments_summary={}, risk="high", status="expired", expires_at=None,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )

    async def fake_session():
        """提供无需数据库的 API 依赖替身。"""
        yield object()

    async def fake_get(repository, identifier):
        """返回固定过期提案。"""
        del repository, identifier
        return proposal

    async def fake_decide(repository, proposal_id, **values):
        """返回仓储层原子过期结论。"""
        del repository, proposal_id, values
        return ProposalDecisionResult(
            proposal=proposal,
            audit=None,
            conflict="proposal has expired",
        )

    monkeypatch.setattr("ci_assistant.persistence.agent.ActionProposalRepository.get", fake_get)
    monkeypatch.setattr("ci_assistant.persistence.agent.ActionProposalRepository.decide", fake_decide)
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    response = TestClient(app).post(
        f"/api/v1/action-proposals/{proposal.id}/decision",
        json={"decision": "approved"},
    )
    assert response.status_code == 409
    assert response.json()["data"]["status"] == "expired"
    assert response.json()["error"]["message"] == "proposal has expired"


def test_create_proposal_masks_argument_summary(monkeypatch) -> None:
    """验证提案只保存脱敏参数摘要，而不保存敏感参数原值。"""
    tenant_id = uuid4()
    diagnosis = Diagnosis(id=uuid4(), tenant_id=tenant_id, project_id=None, trace_id="trace-proposal", status="succeeded", source="log", result={}, error_code=None)
    captured = {}

    async def fake_session():
        """提供无需数据库的 API 依赖替身。"""
        yield object()

    async def fake_diagnosis_get(repository, identifier):
        """返回提案关联的诊断。"""
        return diagnosis

    async def fake_create(repository, **values):
        """捕获脱敏提案并返回 ORM 实体。"""
        del repository
        captured.update(values)
        now = datetime.now(timezone.utc)
        return ActionProposal(id=uuid4(), agent_run_id=None, arguments_hash="b" * 64, status="pending", created_at=now, updated_at=now, **values)

    monkeypatch.setattr("ci_assistant.persistence.diagnoses.DiagnosisRepository.get", fake_diagnosis_get)
    monkeypatch.setattr("ci_assistant.persistence.agent.ActionProposalRepository.create", fake_create)
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    response = TestClient(app).post("/api/v1/action-proposals", json={"diagnosis_id": str(diagnosis.id), "action_type": "draft_comment", "target": "merge-request/7", "arguments_summary": {"body": "token=secret-value"}, "risk": "low"})
    assert response.status_code == 200
    assert captured["arguments_summary"]["body"] == "token=***"
