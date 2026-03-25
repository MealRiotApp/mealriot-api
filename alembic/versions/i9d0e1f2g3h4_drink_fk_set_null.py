"""set ON DELETE SET NULL on drink_id FK

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-03-25 16:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'i9d0e1f2g3h4'
down_revision: Union[str, None] = 'h8c9d0e1f2g3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('fk_food_entries_drink_id', 'food_entries', type_='foreignkey')
    op.create_foreign_key(
        'fk_food_entries_drink_id', 'food_entries', 'custom_drinks',
        ['drink_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_food_entries_drink_id', 'food_entries', type_='foreignkey')
    op.create_foreign_key(
        'fk_food_entries_drink_id', 'food_entries', 'custom_drinks',
        ['drink_id'], ['id'],
    )
