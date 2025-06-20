"""add_bank_providers_table_and_update_cards

Revision ID: add_bank_providers_2025
Revises: add_user_keyword_rules
Create Date: 2025-06-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.core.types import GUID


# revision identifiers, used by Alembic.
revision: str = 'add_bank_providers_2025'
down_revision: Union[str, None] = 'add_user_keyword_rules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add bank_providers table and update cards table to use relationships.
    
    This is like upgrading from sticky notes to a proper filing system -
    instead of writing bank names manually, we reference a master list.
    """
    # Create bank_providers table
    op.create_table('bank_providers',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('short_name', sa.String(), nullable=True),
        sa.Column('country', sa.String(), nullable=False),
        sa.Column('country_name', sa.String(), nullable=False),
        sa.Column('logo_url', sa.String(), nullable=True),
        sa.Column('website', sa.String(), nullable=True),
        sa.Column('color_primary', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_popular', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Use batch mode for SQLite to add column and foreign key
    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bank_provider_id', GUID(), nullable=True))
        batch_op.create_foreign_key('fk_cards_bank_provider', 'bank_providers', ['bank_provider_id'], ['id'])
    
    # Note: We'll keep the old bank_provider column for now to allow data migration
    # It will be removed in a separate migration after data is migrated


def downgrade() -> None:
    """Remove bank providers table and relationship"""
    # Use batch mode for SQLite
    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.drop_constraint('fk_cards_bank_provider', type_='foreignkey')
        batch_op.drop_column('bank_provider_id')
    
    # Drop bank_providers table
    op.drop_table('bank_providers')
