"""Початкова міграція."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "logs_raw",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("payload_raw", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("hash", sa.String(length=128), nullable=False, unique=True),
    )
    op.create_index("ix_logs_raw_received_at", "logs_raw", ["received_at"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("rule_id", sa.String(length=64), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"], unique=False)
    op.create_index("ix_alerts_rule_id", "alerts", ["rule_id"], unique=False)

    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("signal", sa.String(length=255), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("window", sa.Integer(), nullable=False),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_anomalies_created_at", "anomalies", ["created_at"], unique=False)

    op.create_table(
        "logs_normalized",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("raw_id", sa.Integer(), sa.ForeignKey("logs_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("app", sa.String(length=255), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("msg", sa.Text(), nullable=False),
        sa.Column("meta_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("correlation_key", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_logs_normalized_ts", "logs_normalized", ["ts"], unique=False)
    op.create_index("ix_logs_normalized_host", "logs_normalized", ["host"], unique=False)
    op.create_index("ix_logs_normalized_app", "logs_normalized", ["app"], unique=False)
    op.create_index("ix_logs_normalized_severity", "logs_normalized", ["severity"], unique=False)
    op.create_index("ix_logs_normalized_corr", "logs_normalized", ["correlation_key"], unique=False)


def downgrade() -> None:
    op.drop_table("logs_normalized")
    op.drop_table("anomalies")
    op.drop_table("alerts")
    op.drop_table("logs_raw")
