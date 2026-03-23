"""drinks, goals, summary

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-23 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('goal_weight_kg', sa.Numeric(5, 2), nullable=True))
    op.add_column('users', sa.Column('daily_summary', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('summary_updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('onboarding_done', sa.Boolean(), nullable=False, server_default='false'))

    op.create_table(
        'custom_drinks',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('name_he', sa.String(), nullable=True),
        sa.Column('icon', sa.String(), nullable=False, server_default='☕'),
        sa.Column('volume_ml', sa.Integer(), nullable=False),
        sa.Column('calories', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sugar_g', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.Column('protein_g', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.Column('fat_g', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.Column('carbs_g', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.Column('counts_as_water', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_custom_drinks_user_id', 'custom_drinks', ['user_id'])


def downgrade() -> None:
    op.drop_table('custom_drinks')
    op.drop_column('users', 'onboarding_done')
    op.drop_column('users', 'summary_updated_at')
    op.drop_column('users', 'daily_summary')
    op.drop_column('users', 'goal_weight_kg')
