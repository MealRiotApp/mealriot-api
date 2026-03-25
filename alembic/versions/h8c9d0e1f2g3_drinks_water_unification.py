"""drinks water unification: add columns and seed default drinks

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-03-25 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from uuid import uuid4

revision: str = 'h8c9d0e1f2g3'
down_revision: Union[str, None] = 'g7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- CustomDrink: add is_default and use_count ---
    op.add_column('custom_drinks', sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('custom_drinks', sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'))

    # --- FoodEntry: add drink_id FK ---
    op.add_column('food_entries', sa.Column('drink_id', sa.String(36), nullable=True))
    op.create_index('ix_food_entries_drink_id', 'food_entries', ['drink_id'])
    op.create_foreign_key(
        'fk_food_entries_drink_id', 'food_entries', 'custom_drinks',
        ['drink_id'], ['id'],
    )

    # --- Data migration: seed default water drink for existing users ---
    users = table('users', column('id', sa.String(36)))
    custom_drinks = table('custom_drinks',
        column('id', sa.String(36)),
        column('user_id', sa.String(36)),
        column('name', sa.String),
        column('name_he', sa.String),
        column('icon', sa.String),
        column('volume_ml', sa.Integer),
        column('calories', sa.Integer),
        column('sugar_g', sa.Numeric),
        column('protein_g', sa.Numeric),
        column('fat_g', sa.Numeric),
        column('carbs_g', sa.Numeric),
        column('counts_as_water', sa.Boolean),
        column('water_pct', sa.Integer),
        column('is_default', sa.Boolean),
        column('use_count', sa.Integer),
    )

    conn = op.get_bind()
    existing_user_ids = conn.execute(sa.select(users.c.id)).fetchall()

    for (user_id,) in existing_user_ids:
        has_default = conn.execute(
            sa.select(custom_drinks.c.id).where(
                custom_drinks.c.user_id == user_id,
                custom_drinks.c.is_default == True,
            )
        ).fetchone()
        if not has_default:
            conn.execute(custom_drinks.insert().values(
                id=str(uuid4()),
                user_id=user_id,
                name="Glass of Water",
                name_he="כוס מים",
                icon="💧",
                volume_ml=250,
                calories=0,
                sugar_g=0,
                protein_g=0,
                fat_g=0,
                carbs_g=0,
                counts_as_water=True,
                water_pct=100,
                is_default=True,
                use_count=0,
            ))


def downgrade() -> None:
    op.execute("DELETE FROM custom_drinks WHERE is_default = true")
    op.drop_constraint('fk_food_entries_drink_id', 'food_entries', type_='foreignkey')
    op.drop_index('ix_food_entries_drink_id', table_name='food_entries')
    op.drop_column('food_entries', 'drink_id')
    op.drop_column('custom_drinks', 'use_count')
    op.drop_column('custom_drinks', 'is_default')
