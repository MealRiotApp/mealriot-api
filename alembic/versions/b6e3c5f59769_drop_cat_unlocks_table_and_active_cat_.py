"""drop cat_unlocks table and active_cat column

Revision ID: b6e3c5f59769
Revises: g7b8c9d0e1f2
Create Date: 2026-03-25 12:17:18.083044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b6e3c5f59769'
down_revision: Union[str, None] = 'g7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_cat_unlocks_user_id', table_name='cat_unlocks')
    op.drop_table('cat_unlocks')
    op.drop_column('users', 'active_cat')


def downgrade() -> None:
    op.add_column('users', sa.Column('active_cat', sa.VARCHAR(), server_default=sa.text("'whiskers'::character varying"), autoincrement=False, nullable=False))
    op.create_table('cat_unlocks',
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('cat_name', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column('unlocked_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='cat_unlocks_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='cat_unlocks_pkey'),
        sa.UniqueConstraint('user_id', 'cat_name', name='uq_cat_unlocks_user_cat')
    )
    op.create_index('ix_cat_unlocks_user_id', 'cat_unlocks', ['user_id'], unique=False)
