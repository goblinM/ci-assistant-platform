"""Harden Agent recovery and proposal decision consistency."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260824_0006"
down_revision = "20260812_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加 Agent 结果恢复字段，并限制每个提案只能产生一次决策审计。"""
    op.add_column(
        "agent_runs",
        sa.Column("phase", sa.String(30), nullable=False, server_default="running"),
    )
    op.add_column(
        "agent_runs",
        sa.Column("result_snapshot", postgresql.JSONB(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_action_proposal_audits_proposal_id",
        "action_proposal_audits",
        ["proposal_id"],
    )


def downgrade() -> None:
    """移除 Agent 可靠性增强字段和单次审批约束。"""
    op.drop_constraint(
        "uq_action_proposal_audits_proposal_id",
        "action_proposal_audits",
        type_="unique",
    )
    op.drop_column("agent_runs", "result_snapshot")
    op.drop_column("agent_runs", "phase")
