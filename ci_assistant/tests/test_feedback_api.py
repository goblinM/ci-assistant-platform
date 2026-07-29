from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from ci_assistant.api.dependencies import get_session
from ci_assistant.main import create_app
from ci_assistant.persistence.entities import Diagnosis, DiagnosisFeedback


def test_feedback_api_masks_comment_and_returns_feedback(monkeypatch) -> None:
    """验证反馈接口执行租户诊断关联和 Secret Mask。"""
    tenant_id = uuid4()
    diagnosis_id = uuid4()
    diagnosis = Diagnosis(
        id=diagnosis_id,
        tenant_id=tenant_id,
        project_id=None,
        trace_id="trace_feedback",
        status="succeeded",
        source="log",
        result={},
        error_code=None,
    )
    captured = {}

    async def fake_get(repository, identifier):
        """返回测试诊断。"""
        return diagnosis

    async def fake_upsert(repository, **values):
        """捕获脱敏后的反馈并返回实体。"""
        captured.update(values)
        now = datetime.now(timezone.utc)
        return DiagnosisFeedback(id=uuid4(), created_at=now, updated_at=now, **values)

    async def fake_session():
        """提供无需数据库的依赖替身。"""
        yield object()

    monkeypatch.setattr(
        "ci_assistant.persistence.diagnoses.DiagnosisRepository.get",
        fake_get,
    )
    monkeypatch.setattr(
        "ci_assistant.persistence.feedback.DiagnosisFeedbackRepository.upsert",
        fake_upsert,
    )
    app = create_app()
    app.dependency_overrides[get_session] = fake_session

    response = TestClient(app).post(
        f"/api/v1/diagnoses/{diagnosis_id}/feedback",
        json={
            "rating": "helpful",
            "accepted_suggestion": True,
            "corrected_error_type": "dependency_missing",
            "comment": "token=very-sensitive-value",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["rating"] == "helpful"
    assert captured["comment"] == "token=***"


def test_feedback_api_rejects_invalid_rating() -> None:
    """验证反馈评分只能使用稳定枚举。"""
    async def fake_session():
        """提供不会在参数校验前访问数据库的依赖替身。"""
        yield object()

    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    response = TestClient(app).post(
        f"/api/v1/diagnoses/{uuid4()}/feedback",
        json={"rating": "excellent"},
    )

    assert response.status_code == 422
