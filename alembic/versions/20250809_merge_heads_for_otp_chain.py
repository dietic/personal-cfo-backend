"""merge heads for otp chain

Revision ID: merge_otp
Revises: tail_tables, otp_meta
Create Date: 2025-08-09
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'merge_otp'
down_revision = ('tail_tables', 'otp_meta')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
