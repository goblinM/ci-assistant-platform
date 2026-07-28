from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Base


ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    """Small transaction-neutral repository for one mapped model."""

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get(self, entity_id: UUID) -> ModelT | None:
        """执行 ``get`` 对应的领域操作。"""
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        """创建 ``add`` 对应的领域对象或结果。"""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def list(self, *, offset: int = 0, limit: int = 100) -> Sequence[ModelT]:
        """列出 ``list`` 对应的数据。"""
        statement = select(self.model).offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def delete(self, entity: ModelT) -> None:
        """删除 ``delete`` 对应的数据。"""
        await self.session.delete(entity)
        await self.session.flush()

