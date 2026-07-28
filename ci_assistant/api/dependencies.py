from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """获取 ``get_session`` 对应的数据。"""
    async with request.app.state.database.session() as session:
        yield session

