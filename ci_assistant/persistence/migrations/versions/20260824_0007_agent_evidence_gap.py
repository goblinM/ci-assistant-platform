"""Persist Agent tool evidence gaps for safe replay."""

from alembic import op
import sqlalchemy as sa


revision = "20260824_0007"
down_revision = "20260824_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为 Agent Step 增加可回放的受限证据缺口字段。"""
    op.add_column(
        "agent_steps",
        sa.Column("evidence_gap", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    """移除 Agent Step 证据缺口字段。"""
    op.drop_column("agent_steps", "evidence_gap")
