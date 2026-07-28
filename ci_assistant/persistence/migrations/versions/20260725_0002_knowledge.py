"""Create knowledge platform tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260725_0002"
down_revision = "20260725_0001"
branch_labels = None
depends_on = None


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    """升级数据库结构到当前迁移版本。"""
    op.create_table(
        "knowledge_documents",
        *_identity_columns(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("provider", sa.String(30)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("license", sa.String(100)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "content_hash", "version"),
    )
    op.create_table(
        "knowledge_chunks",
        *_identity_columns(),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("provider", sa.String(30)),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("vector_id", sa.BigInteger()),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "ordinal"),
    )
    op.create_table(
        "ingestion_jobs",
        *_identity_columns(),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("error", sa.String(1000)),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "evaluation_runs",
        *_identity_columns(),
        sa.Column("code_version", sa.String(100)),
        sa.Column("prompt_version", sa.String(100)),
        sa.Column("model_name", sa.String(200)),
        sa.Column("index_version", sa.String(100)),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    """回退当前迁移版本的数据库结构。"""
    op.drop_table("evaluation_runs")
    op.drop_table("ingestion_jobs")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")

