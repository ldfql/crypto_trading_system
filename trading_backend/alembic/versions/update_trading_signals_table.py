"""Update trading signals table with enhanced fields

Revision ID: update_trading_signals_table
Revises: add_trading_signals_table
Create Date: 2024-01-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "update_trading_signals_table"
down_revision = "add_trading_signals_table"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns for enhanced signal tracking
    op.add_column(
        "trading_signals", sa.Column("target_price", sa.Float(), nullable=True)
    )
    op.add_column("trading_signals", sa.Column("stop_loss", sa.Float(), nullable=True))
    op.add_column(
        "trading_signals", sa.Column("market_volatility", sa.Float(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("market_volume", sa.Float(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("market_sentiment", sa.String(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("position_size", sa.Float(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("entry_reason", sa.Text(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("technical_indicators", sa.JSON(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("sentiment_sources", sa.JSON(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("validation_count", sa.Integer(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("max_profit_reached", sa.Float(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("max_loss_reached", sa.Float(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("final_outcome", sa.Float(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("accuracy_improvement", sa.Float(), nullable=True)
    )
    op.add_column("trading_signals", sa.Column("last_price", sa.Float(), nullable=True))
    op.add_column(
        "trading_signals", sa.Column("price_updates", sa.JSON(), nullable=True)
    )
    op.add_column(
        "trading_signals", sa.Column("validation_history", sa.JSON(), nullable=True)
    )

    # Update existing signal_type values
    op.execute(
        "UPDATE trading_signals SET signal_type = 'long' WHERE signal_type = 'bullish'"
    )
    op.execute(
        "UPDATE trading_signals SET signal_type = 'short' WHERE signal_type = 'bearish'"
    )


def downgrade():
    # Remove added columns
    columns_to_remove = [
        "target_price",
        "stop_loss",
        "market_volatility",
        "market_volume",
        "market_sentiment",
        "position_size",
        "entry_reason",
        "technical_indicators",
        "sentiment_sources",
        "validation_count",
        "max_profit_reached",
        "max_loss_reached",
        "final_outcome",
        "accuracy_improvement",
        "last_price",
        "price_updates",
        "validation_history",
    ]
    for column in columns_to_remove:
        op.drop_column("trading_signals", column)

    # Revert signal_type values
    op.execute(
        "UPDATE trading_signals SET signal_type = 'bullish' WHERE signal_type = 'long'"
    )
    op.execute(
        "UPDATE trading_signals SET signal_type = 'bearish' WHERE signal_type = 'short'"
    )
