"""Add resumable Agent runs and proposal-only approval audit."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260812_0005"
down_revision = "20260729_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增 Agent Run、Step、动作提案和审批审计表。"""
    op.create_table("agent_runs", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("goal", sa.String(500), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("rounds", sa.Integer(), nullable=False), sa.Column("tool_calls", sa.Integer(), nullable=False), sa.Column("prompt_chars", sa.Integer(), nullable=False), sa.Column("estimated_input_tokens", sa.Integer(), nullable=False), sa.Column("model_input_tokens", sa.Integer(), nullable=False), sa.Column("model_output_tokens", sa.Integer(), nullable=False), sa.Column("stop_reason", sa.String(50)), sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"), sa.UniqueConstraint("diagnosis_id"))
    op.create_table("agent_steps", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("idempotency_key", sa.String(100), nullable=False), sa.Column("round", sa.Integer(), nullable=False), sa.Column("action", sa.String(30), nullable=False), sa.Column("tool_name", sa.String(100)), sa.Column("tool_fingerprint", sa.String(64)), sa.Column("observation_summary", postgresql.JSONB()), sa.Column("observation_context", postgresql.JSONB()), sa.Column("error_code", sa.String(100)), sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"), sa.UniqueConstraint("agent_run_id", "ordinal"), sa.UniqueConstraint("agent_run_id", "idempotency_key"))
    op.create_table("action_proposals", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("agent_run_id", postgresql.UUID(as_uuid=True)), sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("action_type", sa.String(100), nullable=False), sa.Column("target", sa.String(500), nullable=False), sa.Column("arguments_hash", sa.String(64), nullable=False), sa.Column("arguments_summary", postgresql.JSONB(), nullable=False), sa.Column("risk", sa.String(20), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"))
    op.create_index("ix_action_proposals_tenant_status", "action_proposals", ["tenant_id", "status"])
    op.create_table("action_proposal_audits", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("decision", sa.String(20), nullable=False), sa.Column("reason", sa.String(1000)), sa.Column("request_id", sa.String(100), nullable=False), sa.ForeignKeyConstraint(["proposal_id"], ["action_proposals.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"))


def downgrade() -> None:
    """按依赖逆序移除 Agent P1 持久化结构。"""
    op.drop_table("action_proposal_audits")
    op.drop_index("ix_action_proposals_tenant_status", table_name="action_proposals")
    op.drop_table("action_proposals")
    op.drop_table("agent_steps")
    op.drop_table("agent_runs")
