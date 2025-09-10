"""Add ai_seeded_at column to categories table

Revision ID: add_ai_seeded_at_to_categories_manual
Revises: c0276a2cff0e_add_card_id_to_incomes
Create Date: 2024-09-09 13:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_ai_seeded_at_to_categories_manual'
down_revision = 'c0276a2cff0e_add_card_id_to_incomes'
branch_labels = None
depends_on = None


def upgrade():
    # Add ai_seeded_at column (nullable first)
    op.add_column('categories', sa.Column('ai_seeded_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Remove ai_seeded_at column
    op.drop_column('categories', 'ai_seeded_at')