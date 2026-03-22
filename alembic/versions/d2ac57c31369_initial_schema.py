"""initial schema

Revision ID: d2ac57c31369
Revises:
Create Date: 2026-03-22 19:41:20.290017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd2ac57c31369'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("supabase_id", sa.String(), nullable=False, unique=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
        sa.Column("theme", sa.String(), nullable=False, server_default="ocean"),
        sa.Column("daily_cal_goal", sa.Integer(), nullable=True),
        sa.Column("daily_protein_goal_g", sa.Integer(), nullable=True),
        sa.Column("daily_fat_goal_g", sa.Integer(), nullable=True),
        sa.Column("daily_carbs_goal_g", sa.Integer(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("height_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("activity_level", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "food_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meal_type", sa.String(), nullable=False, server_default="snack"),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("total_calories", sa.Integer(), nullable=False),
        sa.Column("total_protein_g", sa.Numeric(6, 2), nullable=False),
        sa.Column("total_fat_g", sa.Numeric(6, 2), nullable=False),
        sa.Column("total_carbs_g", sa.Numeric(6, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "recent_foods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("food_name", sa.String(), nullable=False),
        sa.Column("food_name_he", sa.String(), nullable=True),
        sa.Column("grams", sa.Numeric(6, 2), nullable=False),
        sa.Column("calories", sa.Integer(), nullable=False),
        sa.Column("protein_g", sa.Numeric(6, 2), nullable=False),
        sa.Column("fat_g", sa.Numeric(6, 2), nullable=False),
        sa.Column("carbs_g", sa.Numeric(6, 2), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "food_name", name="uq_recent_foods_user_food"),
    )


def downgrade() -> None:
    op.drop_table("recent_foods")
    op.drop_table("food_entries")
    op.drop_table("users")
