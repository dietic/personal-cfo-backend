"""merge heads for otp chain

Revision ID: 20250809_merge_otp_chain
Revises: 20250808_add_missing_tail_tables, 20250809_add_otp_meta
Create Date: 2025-08-09
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '20250809_merge_otp_chain'
down_revision = ('20250808_add_missing_tail_tables', '20250809_add_otp_meta')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
