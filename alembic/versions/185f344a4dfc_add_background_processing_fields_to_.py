"""Add background processing fields to statements

Revision ID: 185f344a4dfc
Revises: 8e49047d3ebe
Create Date: 2025-08-02 23:13:46.066837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '185f344a4dfc'
down_revision: Union[str, None] = '8e49047d3ebe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add background processing fields to statements table
    op.add_column('statements', sa.Column('task_id', sa.String(), nullable=True))
    op.add_column('statements', sa.Column('processing_message', sa.String(), nullable=True))
    op.add_column('statements', sa.Column('transactions_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('statements', sa.Column('extraction_method', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove background processing fields from statements table
    op.drop_column('statements', 'extraction_method')
    op.drop_column('statements', 'transactions_count')
    op.drop_column('statements', 'processing_message')
    op.drop_column('statements', 'task_id')
