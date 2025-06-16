"""add_category_keywords_table_simple

Revision ID: cbc47a4a05fc
Revises: 7dc00e0d485a
Create Date: 2025-06-13 15:09:39.090080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.core.types import GUID


# revision identifiers, used by Alembic.
revision: str = 'cbc47a4a05fc'
down_revision: Union[str, None] = '7dc00e0d485a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create category_keywords table
    op.create_table('category_keywords',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('category_id', GUID(), nullable=False),
        sa.Column('keyword', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('category_keywords')
