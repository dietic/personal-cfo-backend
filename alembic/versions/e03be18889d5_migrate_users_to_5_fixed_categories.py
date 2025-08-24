"""migrate_users_to_5_fixed_categories

Revision ID: e03be18889d5
Revises: 3e3dbc9b11f5
Create Date: 2025-08-17 19:08:17.218262

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e03be18889d5'
down_revision: Union[str, None] = '3e3dbc9b11f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Migrate existing users to use only the 5 fixed default categories:
    - Alimentación, Salud, Transporte, Vivienda, Otros
    """
    # Get connection for raw SQL operations
    conn = op.get_bind()
    
    # Define the 5 fixed categories with their properties
    fixed_categories = [
        {"name": "Alimentación", "color": "#FF6B6B"},
        {"name": "Salud", "color": "#DDA0DD"},
        {"name": "Transporte", "color": "#4ECDC4"},
        {"name": "Vivienda", "color": "#F39C12"},
        {"name": "Otros", "color": "#95A5A6"},
    ]
    
    # Get all users
    users_result = conn.execute(sa.text("SELECT id FROM users"))
    user_ids = [str(row[0]) for row in users_result]
    
    for user_id in user_ids:
        # Get existing categories for this user
        existing_categories = conn.execute(
            sa.text("SELECT id, name FROM categories WHERE user_id = :user_id AND is_active = true"),
            {"user_id": user_id}
        ).fetchall()
        
        existing_names = [cat[1] for cat in existing_categories]
        existing_dict = {cat[1]: cat[0] for cat in existing_categories}
        
        # Create or update to ensure we have exactly these 5 categories
        for cat_data in fixed_categories:
            if cat_data["name"] in existing_names:
                # Update existing category to be default and set correct color
                conn.execute(
                    sa.text("""
                        UPDATE categories 
                        SET is_default = true, color = :color, is_active = true
                        WHERE user_id = :user_id AND name = :name
                    """),
                    {"user_id": user_id, "name": cat_data["name"], "color": cat_data["color"]}
                )
            else:
                # Create missing category
                conn.execute(
                    sa.text("""
                        INSERT INTO categories (id, user_id, name, color, is_default, is_active, created_at)
                        VALUES (gen_random_uuid(), :user_id, :name, :color, true, true, NOW())
                    """),
                    {"user_id": user_id, "name": cat_data["name"], "color": cat_data["color"]}
                )
        
        # Mark all other categories as inactive (soft delete) but keep them for transaction history
        for cat_name in existing_names:
            if cat_name not in [fc["name"] for fc in fixed_categories]:
                conn.execute(
                    sa.text("""
                        UPDATE categories 
                        SET is_active = false 
                        WHERE user_id = :user_id AND name = :name
                    """),
                    {"user_id": user_id, "name": cat_name}
                )


def downgrade() -> None:
    """
    Downgrade would reactivate all previously deactivated categories.
    This is not recommended as it could cause issues with the free plan restrictions.
    """
    conn = op.get_bind()
    
    # Reactivate all categories that were deactivated
    conn.execute(
        sa.text("UPDATE categories SET is_active = true WHERE is_active = false")
    )
