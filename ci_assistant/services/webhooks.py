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
    event_id: UUID | None
    diagnosis_id: UUID | None
    duplicate: bool


class WebhookService:
    async def handle(
        self,
        *,
        session: AsyncSession,
        provider: CIProvider,
        connection: CIConnection,
        headers: dict[str, str],
        body: bytes,
    ) -> WebhookOutcome:
        """处理 ``handle`` 对应的请求或事件。"""
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
            return WebhookOutcome(None, None, True)

        diagnosis_id = None
        if event.status == RunStatus.FAILED:
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
                },
                error_code=None,
            )
            await DiagnosisRepository(session).add(diagnosis)
            diagnosis_id = diagnosis.id
        return WebhookOutcome(event_id, diagnosis_id, False)

