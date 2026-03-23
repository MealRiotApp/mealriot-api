"""phase 2c+2d tables and user social cols

Revision ID: a1b2c3d4e5f6
Revises: f57b87ff8d4e
Create Date: 2026-03-23 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f57b87ff8d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- User social columns ---
    op.add_column('users', sa.Column('username', sa.String(30), nullable=True))
    op.add_column('users', sa.Column('friend_code', sa.String(10), nullable=True))
    op.add_column('users', sa.Column('macro_bonus_enabled', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('timezone', sa.String(50), nullable=False, server_default='UTC'))
    op.create_unique_constraint('uq_users_username', 'users', ['username'])
    op.create_unique_constraint('uq_users_friend_code', 'users', ['friend_code'])

    # --- cat_unlocks ---
    op.create_table(
        'cat_unlocks',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cat_name', sa.String(20), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'cat_name', name='uq_cat_unlocks_user_cat'),
    )
    op.create_index('ix_cat_unlocks_user_id', 'cat_unlocks', ['user_id'])

    # --- eating_windows ---
    op.create_table(
        'eating_windows',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('meal_type', sa.String(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.UniqueConstraint('user_id', 'meal_type', name='uq_eating_windows_user_meal'),
    )
    op.create_index('ix_eating_windows_user_id', 'eating_windows', ['user_id'])

    # --- friendships ---
    op.create_table(
        'friendships',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('requester_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('addressee_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('requester_id', 'addressee_id', name='uq_friendships_pair'),
    )
    op.create_index('ix_friendships_addressee_id', 'friendships', ['addressee_id'])

    # --- competition_groups ---
    op.create_table(
        'competition_groups',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- competition_members ---
    op.create_table(
        'competition_members',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('group_id', sa.Uuid(), sa.ForeignKey('competition_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('group_id', 'user_id', name='uq_competition_members_pair'),
    )

    # --- daily_points ---
    op.create_table(
        'daily_points',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('calorie_points', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('logging_points', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('macro_points', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('total_points', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'date', name='uq_daily_points_user_date'),
    )
    op.create_index('idx_daily_points_user_date', 'daily_points', ['user_id', 'date'])

    # --- weekly_summaries ---
    op.create_table(
        'weekly_summaries',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('group_id', sa.Uuid(), sa.ForeignKey('competition_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('total_points', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('rank', sa.SmallInteger(), nullable=True),
        sa.Column('winner', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'group_id', 'week_start', name='uq_weekly_summary'),
    )
    op.create_index('idx_weekly_summaries_group_week', 'weekly_summaries', ['group_id', 'week_start'])


def downgrade() -> None:
    op.drop_table('weekly_summaries')
    op.drop_table('daily_points')
    op.drop_table('competition_members')
    op.drop_table('competition_groups')
    op.drop_table('friendships')
    op.drop_table('eating_windows')
    op.drop_table('cat_unlocks')
    op.drop_constraint('uq_users_friend_code', 'users', type_='unique')
    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.drop_column('users', 'timezone')
    op.drop_column('users', 'macro_bonus_enabled')
    op.drop_column('users', 'friend_code')
    op.drop_column('users', 'username')
