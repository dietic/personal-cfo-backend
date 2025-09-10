"""add_emoji_column_to_categories

Revision ID: 87c3836d1e64
Revises: 455c5429e781
Create Date: 2025-09-02 20:12:23.251176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87c3836d1e64'
down_revision: Union[str, None] = '455c5429e781'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add emoji column to categories table
    op.add_column('categories', sa.Column('emoji', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove emoji column from categories table
    op.drop_column('categories', 'emoji')
