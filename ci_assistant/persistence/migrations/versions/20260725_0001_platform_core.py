"""Create platform core tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260725_0001"
down_revision = None
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
        "tenants",
        *_identity_columns(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
    )
    op.create_table(
        "ci_connections",
        *_identity_columns(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "external_id"),
    )
    op.create_table(
        "projects",
        *_identity_columns(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_ref", sa.String(500), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["ci_connections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("connection_id", "project_ref"),
    )
    op.create_table(
        "ci_events",
        *_identity_columns(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("external_event_id", sa.String(300), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["ci_connections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "connection_id", "external_event_id"),
    )
    op.create_table(
        "diagnoses",
        *_identity_columns(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("trace_id", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("result", postgresql.JSONB()),
        sa.Column("error_code", sa.String(100)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "analysis_traces",
        *_identity_columns(),
        sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("prompt_version", sa.String(100)),
        sa.Column("model_name", sa.String(200)),
        sa.Column("index_version", sa.String(100)),
        sa.Column("trace_data", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    """回退当前迁移版本的数据库结构。"""
    for table in (
        "analysis_traces",
        "diagnoses",
        "ci_events",
        "projects",
        "ci_connections",
        "tenants",
    ):
        op.drop_table(table)

