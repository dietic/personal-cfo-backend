"""add otp fields to users

Revision ID: 20250809_add_otp
Revises: card_id_stmt
Create Date: 2025-08-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250809_add_otp'
down_revision = 'card_id_stmt'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('otp_code', sa.String(), nullable=True))
    op.add_column('users', sa.Column('otp_expires_at', sa.DateTime(timezone=True), nullable=True))
    # New signups should start inactive until verified
    try:
        op.alter_column('users', 'is_active', existing_type=sa.Boolean(), server_default=sa.text('false'))
    except Exception:
        # Some backends may already have default set
        pass


def downgrade() -> None:
    try:
        op.alter_column('users', 'is_active', existing_type=sa.Boolean(), server_default=sa.text('true'))
    except Exception:
        pass
    op.drop_column('users', 'otp_expires_at')
    op.drop_column('users', 'otp_code')
