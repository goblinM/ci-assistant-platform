from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.domain.ci import RunStatus
from ci_assistant.persistence.diagnoses import DiagnosisRepository
from ci_assistant.persistence.entities import CIConnection, Diagnosis
from ci_assistant.persistence.events import CIEventRepository
from ci_assistant.providers.base import CIProvider


@dataclass(frozen=True)
class WebhookOutcome:
    """描述一次已验签 Webhook 的幂等处理结果及关联诊断。"""

    event_id: UUID | None
    diagnosis_id: UUID | None
    duplicate: bool
    event_type: str
    external_event_id: str


class WebhookService:
    """验证并规范化 CI Webhook，幂等保存事件并按策略创建诊断。"""

    async def handle(
        self,
        *,
        session: AsyncSession,
        provider: CIProvider,
        connection: CIConnection,
        headers: dict[str, str],
        body: bytes,
        verify_signature: bool = True,
    ) -> WebhookOutcome:
        """处理单次 Webhook；重复事件不再创建诊断，失败事件进入异步诊断队列。"""
        if verify_signature:
            await provider.verify_webhook(headers, body)
        payload = json.loads(body)
        event = await provider.parse_webhook(payload)
        event_id, created = await CIEventRepository(session).create_once(
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            provider=event.provider,
            external_event_id=event.external_event_id,
            event_type=event.event_type,
            payload=payload,
        )
        if not created:
            return WebhookOutcome(
                None,
                None,
                True,
                event.event_type,
                event.external_event_id,
            )

        diagnosis_id = None
        if event.status == RunStatus.FAILED or event.diagnostic_reason:
            diagnostic_log = ""
            if event.diagnostic_reason == "runner_unavailable":
                diagnostic_log = (
                    "runner unavailable: no online GitLab runner matches "
                    "the pending job tags"
                )
            diagnosis = Diagnosis(
                tenant_id=connection.tenant_id,
                project_id=None,
                trace_id=f"trace_{uuid4().hex}",
                status="queued",
                source="webhook",
                result={
                    "connection_id": provider.connection_id,
                    "project_ref": event.project_ref,
                    "run_id": event.run_id,
                    "job_id": event.job_id,
                    "log": diagnostic_log,
                    "diagnostic_reason": event.diagnostic_reason,
                    "use_rag": event.diagnostic_reason is None,
                    "use_tools": event.diagnostic_reason is None,
                },
                error_code=None,
            )
            await DiagnosisRepository(session).add(diagnosis)
            diagnosis_id = diagnosis.id
        return WebhookOutcome(
            event_id,
            diagnosis_id,
            False,
            event.event_type,
            event.external_event_id,
        )
