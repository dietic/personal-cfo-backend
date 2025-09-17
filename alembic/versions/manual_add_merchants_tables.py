"""manual_add_merchants_tables

Manual migration to add merchants table only (simplified design)

Revision ID: manual_merchants_001
Revises: dc4c00f19760
Create Date: 2025-09-06 21:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'manual_merchants_001'
down_revision: Union[str, None] = 'c0276a2cff0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands manually added ###
    
    # Create merchants table
    op.create_table('merchants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('canonical_name', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('description_patterns', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('transaction_count', sa.String(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_merchants_user_id'), 'merchants', ['user_id'], unique=False)
    
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands manually added ###
    op.drop_index(op.f('ix_merchants_user_id'), table_name='merchants')
    op.drop_table('merchants')
    # ### end Alembic commands ###