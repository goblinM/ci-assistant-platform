import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Mapped, mapped_column

from ci_assistant.persistence.database import Database
from ci_assistant.persistence.models import Base
from ci_assistant.persistence.repositories import Repository


class ExampleRecord(Base):
    __tablename__ = "test_example_records"

    id: Mapped[int] = mapped_column(primary_key=True)


def test_repository_uses_session_without_committing() -> None:
    """验证 ``test_repository_uses_session_without_committing`` 所描述的预期行为。"""
    session = MagicMock()
    session.get = AsyncMock(return_value=ExampleRecord(id=1))
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    repository = Repository(session, ExampleRecord)
    record = ExampleRecord(id=1)

    async def exercise_repository() -> ExampleRecord | None:
        """提供 ``exercise_repository`` 场景所需的测试替身。"""
        await repository.add(record)
        loaded_record = await repository.get(uuid4())
        await repository.delete(record)
        return loaded_record

    loaded = asyncio.run(exercise_repository())

    assert loaded is not None
    session.add.assert_called_once_with(record)
    session.flush.assert_awaited()
    session.commit.assert_not_awaited()


def test_database_session_commits_and_closes() -> None:
    """验证 ``test_database_session_commits_and_closes`` 所描述的预期行为。"""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    database = Database(MagicMock(), session_factory=MagicMock(return_value=session))

    async def use_session() -> None:
        """提供 ``use_session`` 场景所需的测试替身。"""
        async with database.session() as yielded:
            assert yielded is session

    asyncio.run(use_session())

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


def test_database_session_rolls_back_on_error() -> None:
    """验证 ``test_database_session_rolls_back_on_error`` 所描述的预期行为。"""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    database = Database(MagicMock(), session_factory=MagicMock(return_value=session))

    async def fail_in_session() -> None:
        """提供 ``fail_in_session`` 场景所需的测试替身。"""
        async with database.session():
            raise RuntimeError("failure")

    with pytest.raises(RuntimeError, match="failure"):
        asyncio.run(fail_in_session())

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()
