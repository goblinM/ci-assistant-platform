from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Base


ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    """为单个 ORM 模型提供不主动提交事务的基础持久化操作。"""

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get(self, entity_id: UUID) -> ModelT | None:
        """按 UUID 主键查询实体，不存在时返回空结果。"""
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        """加入当前事务并刷新生成字段，但不擅自提交事务。"""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def list(self, *, offset: int = 0, limit: int = 100) -> Sequence[ModelT]:
        """按偏移量和上限返回当前模型的实体列表，不主动提交事务。"""
        statement = select(self.model).offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def delete(self, entity: ModelT) -> None:
        """在当前事务中删除实体并刷新，但不擅自提交事务。"""
        await self.session.delete(entity)
        await self.session.flush()
