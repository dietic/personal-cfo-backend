#!/usr/bin/env python
"""
Update script to fix bank colors with more authentic branding.

This script updates existing bank entries with more accurate brand colors
based on their official branding guidelines.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.bank_provider import BankProvider

# Updated color mappings for more authentic branding
COLOR_UPDATES = {
    "BCP": {
        "color_primary": "#003d82",  # BCP Deep Blue (more authentic)
        "color_secondary": "#ff6900",  # BCP Orange (vibrant)
    },
    "BBVA Continental": {
        "color_primary": "#004481",  # BBVA Deep Blue (unchanged - correct)
        "color_secondary": "#1973be",  # BBVA Medium Blue (more authentic than light blue)
    },
    "Interbank": {
        "color_primary": "#00a651",  # Interbank Green (unchanged - correct)
        "color_secondary": "#7cc142",  # Interbank Light Green (more vibrant)
    },
    "Scotiabank": {
        "color_primary": "#da020e",  # Scotia Red (unchanged - correct)
        "color_secondary": "#ffffff",  # White (cleaner than gold)
    },
    "Diners": {
        "color_primary": "#003366",  # Diners Dark Navy
        "color_secondary": "#5b9bd5",  # Diners Light Blue
    },
}

def update_bank_colors():
    """Update bank colors with more authentic branding"""
    print("🎨 Updating bank colors with authentic branding...")
    
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        for short_name, colors in COLOR_UPDATES.items():
            bank = db.query(BankProvider).filter(
                BankProvider.short_name == short_name
            ).first()
            
            if bank:
                bank.color_primary = colors["color_primary"]
                bank.color_secondary = colors["color_secondary"]
                print(f"  ✓ Updated {short_name}: {colors['color_primary']} / {colors['color_secondary']}")
            else:
                print(f"  ⚠️  Bank {short_name} not found")
        
        db.commit()
        print("✅ Successfully updated bank colors!")
        
    except Exception as e:
        print(f"❌ Error updating bank colors: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    update_bank_colors()
