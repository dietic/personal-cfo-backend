"""add_source_to_incomes

Revision ID: 20250908_add_source_to_incomes
Revises: c0276a2cff0e
Create Date: 2025-09-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250908_add_source_to_incomes'
down_revision: Union[str, None] = 'manual_merchants_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source column to incomes table with default value
    op.add_column('incomes', sa.Column('source', sa.String(), nullable=False, server_default='General Income'))


def downgrade() -> None:
    # Remove source column
    op.drop_column('incomes', 'source')