"""add_schema_versioning_for_s2_05

Revision ID: e111a0b30274
Revises: aa1713489de7
Create Date: 2025-11-15 12:48:52.090608

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e111a0b30274'
down_revision: Union[str, Sequence[str], None] = 'aa1713489de7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for S2-05: Minimal Schema & Versioning Discipline."""
    # Add schema_version column to action_commands table
    op.add_column('action_commands', sa.Column('schema_version', sa.Integer(), nullable=False, server_default='1'))

    # Rename event_type to type in events table
    op.alter_column('events', 'event_type', new_column_name='type')


def downgrade() -> None:
    """Downgrade schema for S2-05."""
    # Rename type back to event_type in events table
    op.alter_column('events', 'type', new_column_name='event_type')

    # Remove schema_version column from action_commands table
    op.drop_column('action_commands', 'schema_version')
