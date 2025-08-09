"""merge heads for is_admin

Revision ID: a0cc212792fa
Revises: 185f344a4dfc, 20250807_add_is_admin_to_users
Create Date: 2025-08-08 00:20:06.083360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0cc212792fa'
down_revision: Union[str, None] = ('185f344a4dfc', '20250807_add_is_admin_to_users')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
