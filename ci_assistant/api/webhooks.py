from __future__ import annotations

import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.api.dependencies import get_session
from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.persistence.connections import CIConnectionRepository
from ci_assistant.persistence.webhook_deliveries import WebhookDeliveryRepository
from ci_assistant.providers.base import AuthenticationError
from ci_assistant.services.webhooks import WebhookService


router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def _provider_delivery_id(headers: dict[str, str]) -> str | None:
    """提取不同 Provider 提供的投递标识，不读取认证 Header。"""
    for name in (
        "x-gitlab-webhook-uuid",
        "x-gitlab-event-uuid",
        "x-github-delivery",
        "x-jenkins-notification",
    ):
        value = headers.get(name)
        if value:
            return value[:300]
    return None


async def _finish_delivery(
    request: Request,
    delivery_id: UUID,
    **values,
) -> None:
    """在独立事务中完成审计记录，避免业务事务回滚抹除失败证据。"""
    async with request.app.state.database.session() as audit_session:
        await WebhookDeliveryRepository(audit_session).finish(delivery_id, **values)


@router.post("/{connection_id}/gitlab", status_code=202)
@router.post("/{connection_id}/jenkins", status_code=202)
@router.post("/{connection_id}/github", status_code=202)
async def receive_ci_webhook(
    connection_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """处理 ``receive_ci_webhook`` 对应的请求或事件。"""
    body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}
    provider_name = request.url.path.rsplit("/", 1)[-1]
    async with request.app.state.database.session() as audit_session:
        delivery = await WebhookDeliveryRepository(audit_session).create_received(
            connection_external_id=connection_id,
            provider=provider_name,
            request_id=request.state.request_id,
            provider_delivery_id=_provider_delivery_id(headers),
            payload_hash=hashlib.sha256(body).hexdigest(),
        )
        delivery_id = delivery.id

    connection = await CIConnectionRepository(session).get_by_external_id(connection_id)
    if connection is None:
        await _finish_delivery(
            request,
            delivery_id,
            tenant_id=None,
            connection_id=None,
            signature_valid=None,
            processing_status="failed",
            http_status=404,
            error_code=ErrorCode.RESOURCE_NOT_FOUND.value,
        )
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "CI connection not found",
            status_code=404,
        )
    try:
        provider = request.app.state.provider_manager.get(connection_id)
        await provider.verify_webhook(headers, body)
    except AuthenticationError as exc:
        await _finish_delivery(
            request,
            delivery_id,
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            signature_valid=False,
            processing_status="rejected",
            http_status=401,
            error_code=ErrorCode.WEBHOOK_INVALID.value,
        )
        raise PlatformError(
            ErrorCode.WEBHOOK_INVALID,
            str(exc),
            status_code=401,
        ) from exc
    except Exception:
        await _finish_delivery(
            request,
            delivery_id,
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            signature_valid=None,
            processing_status="failed",
            http_status=500,
            error_code=ErrorCode.INTERNAL_ERROR.value,
        )
        raise

    try:
        outcome = await WebhookService().handle(
            session=session,
            provider=provider,
            connection=connection,
            headers=headers,
            body=body,
            verify_signature=False,
        )
    except json.JSONDecodeError as exc:
        await _finish_delivery(
            request,
            delivery_id,
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            signature_valid=True,
            processing_status="failed",
            http_status=400,
            error_code=ErrorCode.WEBHOOK_INVALID.value,
        )
        raise PlatformError(
            ErrorCode.WEBHOOK_INVALID,
            "Invalid webhook JSON payload",
            status_code=400,
        ) from exc
    except Exception:
        await _finish_delivery(
            request,
            delivery_id,
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            signature_valid=True,
            processing_status="failed",
            http_status=500,
            error_code=ErrorCode.INTERNAL_ERROR.value,
        )
        raise

    await _finish_delivery(
        request,
        delivery_id,
        tenant_id=connection.tenant_id,
        connection_id=connection.id,
        signature_valid=True,
        processing_status="duplicate" if outcome.duplicate else "processed",
        http_status=202,
        event_type=outcome.event_type,
        external_event_id=outcome.external_event_id,
    )

    if outcome.diagnosis_id is not None:
        dispatcher = getattr(request.app.state, "task_dispatcher", None)
        if dispatcher is not None:
            dispatcher("ci_assistant.diagnose", str(outcome.diagnosis_id))
    return {
        "request_id": request.state.request_id,
        "data": {
            "event_id": outcome.event_id,
            "diagnosis_id": outcome.diagnosis_id,
            "duplicate": outcome.duplicate,
        },
        "error": None,
    }
