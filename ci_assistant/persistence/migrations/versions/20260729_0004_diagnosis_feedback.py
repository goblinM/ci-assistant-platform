"""Create diagnosis feedback table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260729_0004"
down_revision = "20260728_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增诊断反馈表。"""
    op.create_table(
        "diagnosis_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.String(30), nullable=False),
        sa.Column("accepted_suggestion", sa.Boolean()),
        sa.Column("corrected_error_type", sa.String(100)),
        sa.Column("comment", sa.String(2000)),
        sa.ForeignKeyConstraint(
            ["diagnosis_id"],
            ["diagnoses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("diagnosis_id"),
    )


def downgrade() -> None:
    """移除诊断反馈表。"""
    op.drop_table("diagnosis_feedback")
