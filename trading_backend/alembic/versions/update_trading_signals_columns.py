"""Create trading signals table with all columns.

Revision ID: update_trading_signals_columns
Revises:
Create Date: 2024-02-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'update_trading_signals_columns'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create trading_signals table with all required columns
    op.create_table('trading_signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('entry_price', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('take_profit', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('stop_loss', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('position_size', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('leverage', sa.Integer(), nullable=True),
        sa.Column('margin_type', sa.String(), nullable=True),
        sa.Column('direction', sa.String(), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('futures_config', postgresql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index on timestamp
    op.create_index(op.f('ix_trading_signals_timestamp'), 'trading_signals', ['timestamp'], unique=False)

def downgrade() -> None:
    # Drop the table and all its columns
    op.drop_index(op.f('ix_trading_signals_timestamp'), table_name='trading_signals')
    op.drop_table('trading_signals')
