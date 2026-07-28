from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import CIEvent
from .models import utc_now


class CIEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_once(
        self,
        *,
        tenant_id: UUID,
        connection_id: UUID,
        provider: str,
        external_event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> tuple[UUID | None, bool]:
        """创建 ``create_once`` 对应的领域对象或结果。"""
        now = utc_now()
        statement = (
            insert(CIEvent)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                connection_id=connection_id,
                provider=provider,
                external_event_id=external_event_id,
                event_type=event_type,
                status="received",
                payload=payload,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=["provider", "connection_id", "external_event_id"]
            )
            .returning(CIEvent.id)
        )
        event_id = (await self.session.execute(statement)).scalar_one_or_none()
        return event_id, event_id is not None

