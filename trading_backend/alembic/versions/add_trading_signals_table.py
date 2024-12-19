"""add trading signals table

Revision ID: add_trading_signals_table
Revises:
Create Date: 2024-01-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_trading_signals_table"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trading_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("timeframe", sa.String(length=6), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("market_cycle_phase", sa.String(), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index("ix_trading_signals_symbol", "trading_signals", ["symbol"])
    op.create_index("ix_trading_signals_timeframe", "trading_signals", ["timeframe"])
    op.create_index("ix_trading_signals_confidence", "trading_signals", ["confidence"])
    op.create_index("ix_trading_signals_created_at", "trading_signals", ["created_at"])


def downgrade():
    op.drop_index("ix_trading_signals_created_at")
    op.drop_index("ix_trading_signals_confidence")
    op.drop_index("ix_trading_signals_timeframe")
    op.drop_index("ix_trading_signals_symbol")
    op.drop_table("trading_signals")
