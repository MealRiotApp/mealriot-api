"""first_day_of_week + insight refresh tracking

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-23 20:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('users', sa.Column('first_day_of_week', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('insight_refreshes_today', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('insight_last_date', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'insight_last_date')
    op.drop_column('users', 'insight_refreshes_today')
    op.drop_column('users', 'first_day_of_week')
