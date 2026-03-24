"""add FK constraints on food_entries and recent_foods

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-24 13:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_foreign_key("fk_food_entries_user_id", "food_entries", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_recent_foods_user_id", "recent_foods", "users", ["user_id"], ["id"], ondelete="CASCADE")

def downgrade() -> None:
    op.drop_constraint("fk_recent_foods_user_id", "recent_foods", type_="foreignkey")
    op.drop_constraint("fk_food_entries_user_id", "food_entries", type_="foreignkey")
