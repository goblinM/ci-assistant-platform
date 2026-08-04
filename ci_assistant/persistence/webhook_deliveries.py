from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .entities import WebhookDelivery
from .models import utc_now


class WebhookDeliveryRepository:
    """持久化不包含原始请求体的 Webhook 投递审计记录。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_received(
        self,
        *,
        connection_external_id: str,
        provider: str,
        request_id: str,
        provider_delivery_id: str | None,
        payload_hash: str,
    ) -> WebhookDelivery:
        """创建处于 received 状态的投递审计记录。"""
        delivery = WebhookDelivery(
            tenant_id=None,
            connection_id=None,
            connection_external_id=connection_external_id,
            provider=provider,
            request_id=request_id,
            provider_delivery_id=provider_delivery_id,
            signature_valid=None,
            processing_status="received",
            http_status=None,
            event_type=None,
            external_event_id=None,
            payload_hash=payload_hash,
            error_code=None,
            processed_at=None,
        )
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def finish(
        self,
        delivery_id: UUID,
        *,
        tenant_id: UUID | None,
        connection_id: UUID | None,
        signature_valid: bool | None,
        processing_status: str,
        http_status: int,
        event_type: str | None = None,
        external_event_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """补全投递的租户、验签、状态和错误信息，并记录处理完成时间。"""
        delivery = await self.session.get(WebhookDelivery, delivery_id)
        if delivery is None:
            raise RuntimeError("Webhook delivery audit record not found")
        delivery.tenant_id = tenant_id
        delivery.connection_id = connection_id
        delivery.signature_valid = signature_valid
        delivery.processing_status = processing_status
        delivery.http_status = http_status
        delivery.event_type = event_type
        delivery.external_event_id = external_event_id
        delivery.error_code = error_code
        delivery.processed_at = utc_now()
