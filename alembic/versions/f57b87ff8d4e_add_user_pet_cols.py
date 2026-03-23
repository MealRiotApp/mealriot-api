"""add user pet cols

Revision ID: f57b87ff8d4e
Revises: d2ac57c31369
Create Date: 2026-03-23 13:06:35.472817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f57b87ff8d4e'
down_revision: Union[str, None] = 'd2ac57c31369'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('active_cat', sa.String(), nullable=False, server_default='whiskers'))
    op.add_column('users', sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('last_log_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_log_date')
    op.drop_column('users', 'longest_streak')
    op.drop_column('users', 'current_streak')
    op.drop_column('users', 'active_cat')
