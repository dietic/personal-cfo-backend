"""add_is_admin_to_users

Revision ID: 20250807_add_is_admin_to_users
Revises: add_bank_providers_2025
Create Date: 2025-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20250807_add_is_admin_to_users'
down_revision: Union[str, None] = 'add_bank_providers_2025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_admin column to users with nullable then backfill and set default False
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=True))
    # Backfill existing rows to False
    op.execute("UPDATE users SET is_admin = false WHERE is_admin IS NULL")
    # Seed initial admin
    op.execute("UPDATE users SET is_admin = true WHERE lower(email) = 'dierios93@gmail.com'")
    # Make column non-nullable going forward
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('is_admin', existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_admin')
