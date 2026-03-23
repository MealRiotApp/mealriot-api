"""water + weight tracking tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-23 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('daily_water_goal_ml', sa.Integer(), nullable=False, server_default='2000'))

    op.create_table(
        'water_logs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('amount_ml', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('user_id', 'date', name='uq_water_logs_user_date'),
    )
    op.create_index('ix_water_logs_user_id', 'water_logs', ['user_id'])

    op.create_table(
        'weight_logs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('weight_kg', sa.Numeric(5, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'date', name='uq_weight_logs_user_date'),
    )
    op.create_index('ix_weight_logs_user_id', 'weight_logs', ['user_id'])


def downgrade() -> None:
    op.drop_table('weight_logs')
    op.drop_table('water_logs')
    op.drop_column('users', 'daily_water_goal_ml')
