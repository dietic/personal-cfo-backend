"""add otp attempts and last sent

Revision ID: 20250809_add_otp_meta
Revises: 20250809_add_otp
Create Date: 2025-08-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250809_add_otp_meta'
down_revision = '20250809_add_otp'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('otp_attempts', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('users', sa.Column('otp_last_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'otp_last_sent_at')
    op.drop_column('users', 'otp_attempts')
