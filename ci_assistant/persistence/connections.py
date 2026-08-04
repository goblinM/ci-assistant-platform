from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import CIConnection
from .repositories import Repository


class CIConnectionRepository(Repository[CIConnection]):
    """提供 CI 连接的通用持久化能力及外部连接 ID 查询。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CIConnection)

    async def get_by_external_id(self, external_id: str) -> CIConnection | None:
        """获取 ``get_by_external_id`` 对应的数据。"""
        result = await self.session.execute(
            select(CIConnection).where(CIConnection.external_id == external_id)
        )
        return result.scalar_one_or_none()
