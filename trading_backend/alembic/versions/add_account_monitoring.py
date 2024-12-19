"""add account monitoring tables

Revision ID: add_account_monitoring
Revises: update_trading_signals_table
Create Date: 2024-01-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

# revision identifiers, used by Alembic
revision = "add_account_monitoring"
down_revision = "update_trading_signals_table"
branch_labels = None
depends_on = None


def upgrade():
    # Create account_balance_history table
    op.create_table(
        "account_balance_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column("balance", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("account_stage", sa.String(50), nullable=False),
        sa.Column("total_positions", sa.Integer(), nullable=False),
        sa.Column("active_pairs", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create position_sizing_history table
    op.create_table(
        "position_sizing_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column("signal_id", sa.Integer(), nullable=False),
        sa.Column("account_balance", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("position_size", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("account_stage", sa.String(50), nullable=False),
        sa.Column("market_volume", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("market_impact", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column("volatility", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column("entry_stages", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["signal_id"], ["trading_signals.id"], ondelete="CASCADE"
        ),
    )

    # Create strategy_adaptation_history table
    op.create_table(
        "strategy_adaptation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column("account_stage", sa.String(50), nullable=False),
        sa.Column("account_balance", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("strategy_type", sa.String(50), nullable=False),
        sa.Column("adaptation_reason", sa.String(255), nullable=False),
        sa.Column("previous_config", JSONB, nullable=True),
        sa.Column("new_config", JSONB, nullable=True),
        sa.Column("performance_metrics", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add indices for better query performance
    op.create_index(
        "ix_account_balance_history_timestamp", "account_balance_history", ["timestamp"]
    )
    op.create_index(
        "ix_position_sizing_history_timestamp", "position_sizing_history", ["timestamp"]
    )
    op.create_index(
        "ix_strategy_adaptation_history_timestamp",
        "strategy_adaptation_history",
        ["timestamp"],
    )
    op.create_index(
        "ix_position_sizing_history_signal_id", "position_sizing_history", ["signal_id"]
    )


def downgrade():
    op.drop_index("ix_position_sizing_history_signal_id")
    op.drop_index("ix_strategy_adaptation_history_timestamp")
    op.drop_index("ix_position_sizing_history_timestamp")
    op.drop_index("ix_account_balance_history_timestamp")
    op.drop_table("strategy_adaptation_history")
    op.drop_table("position_sizing_history")
    op.drop_table("account_balance_history")
