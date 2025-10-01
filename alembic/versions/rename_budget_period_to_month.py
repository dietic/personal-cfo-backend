"""rename_budget_period_to_month

Rename 'period' column to 'month' in budgets table to match model definition.

Revision ID: rename_period_to_month
Revises: db6f07341a74
Create Date: 2025-10-01 05:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'rename_period_to_month'
down_revision: Union[str, None] = 'db6f07341a74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename 'period' column to 'month' in budgets table
    op.alter_column('budgets', 'period', new_column_name='month')


def downgrade() -> None:
    # Rename 'month' column back to 'period' in budgets table
    op.alter_column('budgets', 'month', new_column_name='period')