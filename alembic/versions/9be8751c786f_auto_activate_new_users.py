"""auto activate new users

Revision ID: 9be8751c786f
Revises: 2890363d886d
Create Date: 2026-03-30 12:33:11.419395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9be8751c786f'
down_revision: Union[str, None] = '2890363d886d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET status = 'active' WHERE status = 'pending'")


def downgrade() -> None:
    pass
