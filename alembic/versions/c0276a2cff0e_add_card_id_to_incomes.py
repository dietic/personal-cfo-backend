"""add_card_id_to_incomes

Revision ID: c0276a2cff0e
Revises: 87c3836d1e64
Create Date: 2025-09-03 12:34:58.309100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.core.types import GUID


# revision identifiers, used by Alembic.
revision: str = 'c0276a2cff0e'
down_revision: Union[str, None] = '87c3836d1e64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add card_id column to incomes table
    op.add_column('incomes', sa.Column('card_id', GUID(), nullable=False))
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_incomes_card_id',
        'incomes', 'cards',
        ['card_id'], ['id']
    )


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint('fk_incomes_card_id', 'incomes', type_='foreignkey')
    
    # Remove card_id column
    op.drop_column('incomes', 'card_id')
