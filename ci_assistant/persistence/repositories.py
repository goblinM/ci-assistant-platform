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
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def list(self, *, offset: int = 0, limit: int = 100) -> Sequence[ModelT]:
        statement = select(self.model).offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()

