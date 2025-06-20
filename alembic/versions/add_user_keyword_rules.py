# New migration for user keyword rules
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite
import uuid

# revision identifiers
revision = 'add_user_keyword_rules'
down_revision = 'ca26460dbd46'  # Fixed: pointing to the correct migration ID
branch_labels = None
depends_on = None

def upgrade():
    # Create user_keyword_rules table
    op.create_table('user_keyword_rules',
        sa.Column('id', sa.String, primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('user_id', sa.String, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('category_id', sa.String, sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('keyword', sa.String(100), nullable=False),
        sa.Column('priority', sa.Integer, default=1),  # Higher priority = checked first
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('match_type', sa.String(20), default='contains'),  # contains, starts_with, ends_with, exact
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    
    # Create indexes for performance
    op.create_index('idx_keyword_rules_user_id', 'user_keyword_rules', ['user_id'])
    op.create_index('idx_keyword_rules_category_id', 'user_keyword_rules', ['category_id'])
    op.create_index('idx_keyword_rules_keyword', 'user_keyword_rules', ['keyword'])
    op.create_index('idx_keyword_rules_active', 'user_keyword_rules', ['is_active'])

def downgrade():
    op.drop_table('user_keyword_rules')
