import asyncio
from uuid import uuid4

from ci_assistant.persistence.entities import WebhookDelivery
from ci_assistant.persistence.webhook_deliveries import WebhookDeliveryRepository


class FakeSession:
    """提供 Webhook 投递 Repository 所需的最小 Session 替身。"""

    def __init__(self, existing: WebhookDelivery | None = None) -> None:
        self.added = None
        self.existing = existing

    def add(self, value) -> None:
        """记录待持久化实体。"""
        self.added = value

    async def flush(self) -> None:
        """模拟刷新事务。"""

    async def get(self, model, identifier):
        """返回预置的投递实体。"""
        return self.existing


def test_delivery_repository_stores_hash_without_raw_payload() -> None:
    """验证接收审计只保存 Payload Hash，不保存原始请求体。"""
    session = FakeSession()
    repository = WebhookDeliveryRepository(session)

    delivery = asyncio.run(
        repository.create_received(
            connection_external_id="local-gitlab",
            provider="gitlab",
            request_id="req_test",
            provider_delivery_id="delivery-1",
            payload_hash="a" * 64,
        )
    )

    assert delivery.processing_status == "received"
    assert delivery.payload_hash == "a" * 64
    assert "payload" not in WebhookDelivery.__table__.columns


def test_delivery_repository_finishes_rejected_request() -> None:
    """验证验签失败投递可独立更新为 rejected。"""
    delivery = WebhookDelivery(
        id=uuid4(),
        tenant_id=None,
        connection_id=None,
        connection_external_id="local-gitlab",
        provider="gitlab",
        request_id="req_test",
        provider_delivery_id=None,
        signature_valid=None,
        processing_status="received",
        http_status=None,
        event_type=None,
        external_event_id=None,
        payload_hash="b" * 64,
        error_code=None,
        processed_at=None,
    )
    session = FakeSession(delivery)

    asyncio.run(
        WebhookDeliveryRepository(session).finish(
            delivery.id,
            tenant_id=None,
            connection_id=None,
            signature_valid=False,
            processing_status="rejected",
            http_status=401,
            error_code="WEBHOOK_INVALID",
        )
    )

    assert delivery.signature_valid is False
    assert delivery.processing_status == "rejected"
    assert delivery.http_status == 401
    assert delivery.processed_at is not None
