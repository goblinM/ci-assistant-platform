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
    session = MagicMock()
    session.get = AsyncMock(return_value=ExampleRecord(id=1))
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    repository = Repository(session, ExampleRecord)
    record = ExampleRecord(id=1)

    async def exercise_repository() -> ExampleRecord | None:
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
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    database = Database(MagicMock(), session_factory=MagicMock(return_value=session))

    async def use_session() -> None:
        async with database.session() as yielded:
            assert yielded is session

    asyncio.run(use_session())

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


def test_database_session_rolls_back_on_error() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    database = Database(MagicMock(), session_factory=MagicMock(return_value=session))

    async def fail_in_session() -> None:
        async with database.session():
            raise RuntimeError("failure")

    with pytest.raises(RuntimeError, match="failure"):
        asyncio.run(fail_in_session())

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()
