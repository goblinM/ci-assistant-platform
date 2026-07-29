"""Create webhook delivery audit table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260728_0003"
down_revision = "20260725_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增每次 Webhook HTTP 投递的脱敏审计记录。"""
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True)),
        sa.Column("connection_external_id", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("provider_delivery_id", sa.String(300)),
        sa.Column("signature_valid", sa.Boolean()),
        sa.Column("processing_status", sa.String(30), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("event_type", sa.String(100)),
        sa.Column("external_event_id", sa.String(300)),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["ci_connections.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_webhook_deliveries_connection_received",
        "webhook_deliveries",
        ["connection_id", "created_at"],
    )
    op.create_index(
        "ix_webhook_deliveries_payload_hash",
        "webhook_deliveries",
        ["payload_hash"],
    )


def downgrade() -> None:
    """移除 Webhook 投递审计表。"""
    op.drop_index(
        "ix_webhook_deliveries_payload_hash",
        table_name="webhook_deliveries",
    )
    op.drop_index(
        "ix_webhook_deliveries_connection_received",
        table_name="webhook_deliveries",
    )
    op.drop_table("webhook_deliveries")
