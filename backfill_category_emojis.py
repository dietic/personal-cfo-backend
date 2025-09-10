#!/usr/bin/env python3
"""
Backfill emojis for existing categories that might be missing them.
This script ensures all categories have appropriate emojis.
"""

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.category import Category

# Emoji mappings for categories
EMOJI_MAPPINGS = {
    # Default 5-category system
    "Alimentación": "🍕",
    "Salud": "🏥", 
    "Transporte": "🚗",
    "Vivienda": "🏠",
    "Otros": "📦",
    
    # Additional categories from 7-category system
    "Compras": "🛍️",
    "Entretenimiento": "🎬",
    "Servicios Públicos": "💡",
    
    # Fallback for any other categories
    "Sin categoría": "❓",
}

def backfill_category_emojis():
    """Backfill emojis for all categories that are missing them"""
    db: Session = SessionLocal()
    
    try:
        # Get all categories that need emojis
        categories = db.query(Category).all()
        
        updated_count = 0
        
        for category in categories:
            # Skip if already has an emoji
            if category.emoji:
                continue
                
            # Find appropriate emoji
            emoji = EMOJI_MAPPINGS.get(category.name)
            if not emoji:
                # Try to find a close match
                for key, value in EMOJI_MAPPINGS.items():
                    if key.lower() in category.name.lower() or category.name.lower() in key.lower():
                        emoji = value
                        break
                
                # Default emoji if no match found
                if not emoji:
                    emoji = "📋"
            
            # Update the category
            category.emoji = emoji
            updated_count += 1
            print(f"Updated '{category.name}' with emoji: {emoji}")
        
        if updated_count > 0:
            db.commit()
            print(f"✅ Updated {updated_count} categories with emojis")
        else:
            print("✅ All categories already have emojis")
            
    except Exception as e:
        print(f"❌ Error backfilling emojis: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    backfill_category_emojis()