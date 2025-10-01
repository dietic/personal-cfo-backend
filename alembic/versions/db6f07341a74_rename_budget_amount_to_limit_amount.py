"""rename_budget_amount_to_limit_amount

Revision ID: db6f07341a74
Revises: clean_baseline_001
Create Date: 2025-09-30 23:55:33.283492

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db6f07341a74'
down_revision: Union[str, None] = 'clean_baseline_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename 'amount' column to 'limit_amount' in budgets table
    op.alter_column('budgets', 'amount', new_column_name='limit_amount')


def downgrade() -> None:
    # Rename 'limit_amount' column back to 'amount' in budgets table
    op.alter_column('budgets', 'limit_amount', new_column_name='amount')
