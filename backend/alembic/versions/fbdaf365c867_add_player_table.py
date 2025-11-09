"""add_player_table

Revision ID: fbdaf365c867
Revises: 70c70888b30a
Create Date: 2025-11-09 22:43:36.285360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbdaf365c867'
down_revision: Union[str, Sequence[str], None] = '70c70888b30a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'players',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_players_id'), 'players', ['id'], unique=False)
    op.create_index(op.f('ix_players_username'), 'players', ['username'], unique=True)
    op.create_index(op.f('ix_players_email'), 'players', ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_players_email'), table_name='players')
    op.drop_index(op.f('ix_players_username'), table_name='players')
    op.drop_index(op.f('ix_players_id'), table_name='players')
    op.drop_table('players')
