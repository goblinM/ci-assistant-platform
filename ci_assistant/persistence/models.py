from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间，供 ORM 默认值和更新时间复用。"""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """平台全部 SQLAlchemy ORM 实体共享的声明式基类。"""


class UUIDPrimaryKeyMixin:
    """为 ORM 实体提供自动生成的 PostgreSQL UUID 主键。"""

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )


class TimestampMixin:
    """为 ORM 实体提供带时区的创建和更新时间字段。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
