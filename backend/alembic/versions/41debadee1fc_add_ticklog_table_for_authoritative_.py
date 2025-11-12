"""Add TickLog table for authoritative tick loop

Revision ID: 41debadee1fc
Revises: fbdaf365c867
Create Date: 2025-11-13 00:47:10.649281

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41debadee1fc'
down_revision: Union[str, Sequence[str], None] = 'fbdaf365c867'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tick_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tick', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('worker_id', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('rng_seed', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tick_logs_id'), 'tick_logs', ['id'], unique=False)
    op.create_index(op.f('ix_tick_logs_tick'), 'tick_logs', ['tick'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tick_logs_tick'), table_name='tick_logs')
    op.drop_index(op.f('ix_tick_logs_id'), table_name='tick_logs')
    op.drop_table('tick_logs')
