from __future__ import annotations

from typing import Any
from uuid import UUID

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """表示平台数据隔离和 API Key 绑定的顶层租户。"""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)


class CIConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """保存租户下 CI Provider 连接的非敏感配置元数据。"""

    __tablename__ = "ci_connections"
    __table_args__ = (UniqueConstraint("tenant_id", "external_id"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(30))
    base_url: Mapped[str] = mapped_column(String(500))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """表示 Provider 连接下具有唯一引用的租户项目。"""

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("connection_id", "project_ref"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("ci_connections.id", ondelete="CASCADE")
    )
    project_ref: Mapped[str] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(300))


class CIEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """保存验签并规范化后的幂等 CI 业务事件。"""

    __tablename__ = "ci_events"
    __table_args__ = (
        UniqueConstraint("provider", "connection_id", "external_event_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("ci_connections.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(30))
    external_event_id: Mapped[str] = mapped_column(String(300))
    event_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="received")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class WebhookDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """记录每次 Webhook HTTP 投递的脱敏审计结果。"""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index(
            "ix_webhook_deliveries_connection_received",
            "connection_id",
            "created_at",
        ),
        Index("ix_webhook_deliveries_payload_hash", "payload_hash"),
    )

    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL")
    )
    connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ci_connections.id", ondelete="SET NULL")
    )
    connection_external_id: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(30))
    request_id: Mapped[str] = mapped_column(String(100))
    provider_delivery_id: Mapped[str | None] = mapped_column(String(300))
    signature_valid: Mapped[bool | None] = mapped_column(Boolean)
    processing_status: Mapped[str] = mapped_column(String(30))
    http_status: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str | None] = mapped_column(String(100))
    external_event_id: Mapped[str | None] = mapped_column(String(300))
    payload_hash: Mapped[str] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(100))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Diagnosis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """保存异步诊断生命周期、结构化结果和稳定失败码。"""

    __tablename__ = "diagnoses"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    trace_id: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    source: Mapped[str] = mapped_column(String(30))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(100))


class DiagnosisFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """保存租户对单条诊断的唯一评分、建议采纳状态和脱敏评论。"""

    __tablename__ = "diagnosis_feedback"
    __table_args__ = (UniqueConstraint("diagnosis_id"),)

    diagnosis_id: Mapped[UUID] = mapped_column(
        ForeignKey("diagnoses.id", ondelete="CASCADE")
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    rating: Mapped[str] = mapped_column(String(30))
    accepted_suggestion: Mapped[bool | None] = mapped_column(Boolean)
    corrected_error_type: Mapped[str | None] = mapped_column(String(100))
    comment: Mapped[str | None] = mapped_column(String(2000))


class AnalysisTrace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """保存单次诊断使用的模型、索引及脱敏追踪数据。"""

    __tablename__ = "analysis_traces"

    diagnosis_id: Mapped[UUID] = mapped_column(
        ForeignKey("diagnoses.id", ondelete="CASCADE"), unique=True
    )
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(200))
    index_version: Mapped[str | None] = mapped_column(String(100))
    trace_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """保存租户知识正文、来源、作用域、版本和生命周期状态。"""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "content_hash", "version"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    provider: Mapped[str | None] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(500))
    format: Mapped[str] = mapped_column(String(20))
    source_type: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    license: Mapped[str | None] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(30), default="uploaded")
    content: Mapped[str] = mapped_column(Text)


class KnowledgeChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """保存知识文档切片、ACL、向量标识和检索元数据。"""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("document_id", "ordinal"),)

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE")
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    provider: Mapped[str | None] = mapped_column(String(30))
    ordinal: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    vector_id: Mapped[int | None] = mapped_column(BigInteger)


class IngestionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """记录知识文档异步索引任务的幂等键、状态和受限错误信息。"""

    __tablename__ = "ingestion_jobs"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(30), default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    error: Mapped[str | None] = mapped_column(String(1000))


class EvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """保存代码、Prompt、模型和索引版本对应的离线评测指标。"""

    __tablename__ = "evaluation_runs"

    code_version: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(200))
    index_version: Mapped[str | None] = mapped_column(String(100))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
