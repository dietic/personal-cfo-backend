#!/usr/bin/env python
"""
Seed script to populate the database with Peruvian bank providers.

This script fills our bank_providers table with comprehensive data about
Peruvian banks - like creating a phone book of all financial institutions
in Peru so users can select their actual bank instead of typing it manually.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.bank_provider import BankProvider
import uuid

# Comprehensive list of Peruvian banks with their details
PERUVIAN_BANKS = [
    {
        "name": "Banco de Crédito del Perú",
        "short_name": "BCP",
        "website": "https://www.viabcp.com/",
        "color_primary": "#003d82",  # BCP Deep Blue (more authentic)
        "color_secondary": "#ff6900",  # BCP Orange (vibrant)
        "is_popular": True,
    },
    {
        "name": "Banco Continental",
        "short_name": "BBVA Continental",
        "website": "https://www.bbva.pe/",
        "color_primary": "#004481",  # BBVA Deep Blue (unchanged - correct)
        "color_secondary": "#1973be",  # BBVA Medium Blue (more authentic than light blue)
        "is_popular": True,
    },
    {
        "name": "Interbank",
        "short_name": "Interbank",
        "website": "https://interbank.pe/",
        "color_primary": "#00a651",  # Interbank Green (unchanged - correct)
        "color_secondary": "#7cc142",  # Interbank Light Green (more vibrant)
        "is_popular": True,
    },
    {
        "name": "Scotiabank Perú",
        "short_name": "Scotiabank",
        "website": "https://www.scotiabank.com.pe/",
        "color_primary": "#da020e",  # Scotia Red (unchanged - correct)
        "color_secondary": "#ffffff",  # White (cleaner than gold)
        "is_popular": True,
    },
    {
        "name": "Diners Club del Perú",
        "short_name": "Diners",
        "website": "https://www.dinersclub.com.pe/",
        "color_primary": "#003366",  # Diners Dark Navy
        "color_secondary": "#5b9bd5",  # Diners Light Blue
        "is_popular": True,
    },
    {
        "name": "Banco Pichincha",
        "short_name": "Pichincha",
        "website": "https://www.pichincha.pe/",
        "color_primary": "#FFD700",  # Pichincha Yellow/Gold
        "color_secondary": "#FF6B35",  # Orange accent
        "is_popular": False,
    },
    {
        "name": "Banco Financiero",
        "short_name": "BanBif",
        "website": "https://www.banbif.com.pe/",
        "color_primary": "#E31837",  # BanBif Red
        "color_secondary": "#FFA500",  # Orange accent
        "is_popular": False,
    },
    {
        "name": "Banco Falabella",
        "short_name": "Falabella",
        "website": "https://www.bancofalabella.pe/",
        "color_primary": "#FF6B00",  # Falabella Orange
        "color_secondary": "#FFE5CC",  # Light Orange
        "is_popular": False,
    },
    {
        "name": "Banco Ripley",
        "short_name": "Ripley",
        "website": "https://www.bancoripley.com.pe/",
        "color_primary": "#8B0000",  # Ripley Dark Red
        "color_secondary": "#FF6B6B",  # Light Red accent
        "is_popular": False,
    },
    {
        "name": "Banco Santander Perú",
        "short_name": "Santander",
        "website": "https://www.santander.com.pe/",
        "color_primary": "#EC0000",  # Santander Red
        "color_secondary": "#FFFFFF",  # White (clean contrast)
        "is_popular": False,
    },
    {
        "name": "Banco Azteca",
        "short_name": "Azteca",
        "website": "https://www.bancoazteca.com.pe/",
        "color_primary": "#00A0B0",  # Azteca Teal
        "color_secondary": "#40E0D0",  # Turquoise accent
        "is_popular": False,
    },
    {
        "name": "Banco de la Nación",
        "short_name": "Banco Nación",
        "website": "https://www.bn.com.pe/",
        "color_primary": "#003366",  # Deep Navy (Government Blue)
        "color_secondary": "#FFD700",  # Gold (Peru national colors)
        "is_popular": True,
    },
    {
        "name": "Mibanco",
        "short_name": "Mibanco",
        "website": "https://www.mibanco.com.pe/",
        "color_primary": "#FF9900",
        "color_secondary": "#FF6B35",
        "is_popular": False,
    },
    {
        "name": "Caja Municipal de Ahorro y Crédito de Arequipa",
        "short_name": "CMAC Arequipa",
        "website": "https://www.cmac-arequipa.com.pe/",
        "color_primary": "#0066CC",
        "color_secondary": "#4169E1",
        "is_popular": False,
    },
    {
        "name": "Caja Municipal de Ahorro y Crédito de Trujillo",
        "short_name": "CMAC Trujillo",
        "website": "https://www.cmactrujillo.com.pe/",
        "color_primary": "#006600",
        "color_secondary": "#228B22",
        "is_popular": False,
    },
    {
        "name": "Caja Municipal de Ahorro y Crédito de Cusco",
        "short_name": "CMAC Cusco",
        "website": "https://www.cmac-cusco.com.pe/",
        "color_primary": "#CC0000",
        "color_secondary": "#B71C1C",
        "is_popular": False,
    },
    {
        "name": "Caja Rural de Ahorro y Crédito Los Andes",
        "short_name": "CRAC Los Andes",
        "website": "https://www.cajalosandes.pe/",
        "color_primary": "#008000",
        "color_secondary": "#228B22",
        "is_popular": False,
    },
]

def seed_peruvian_banks():
    """
    Populate the database with Peruvian bank providers.
    
    This function is like filling a contact book with all the banks
    in Peru, so users can select from real institutions instead of
    typing them manually (which leads to typos and inconsistency).
    """
    
    # Get database session
    db = next(get_db())
    
    try:
        print("🏦 Seeding Peruvian banks...")
        
        for bank_data in PERUVIAN_BANKS:
            # Check if bank already exists
            existing_bank = db.query(BankProvider).filter(
                BankProvider.name == bank_data["name"]
            ).first()
            
            if existing_bank:
                print(f"  ✓ {bank_data['name']} already exists")
                continue
            
            # Create new bank provider
            bank = BankProvider(
                id=uuid.uuid4(),
                name=bank_data["name"],
                short_name=bank_data["short_name"],
                country="PE",
                country_name="Peru",
                website=bank_data.get("website"),
                color_primary=bank_data.get("color_primary"),
                color_secondary=bank_data.get("color_secondary"),
                is_active=True,
                is_popular=bank_data.get("is_popular", False)
            )
            
            db.add(bank)
            print(f"  + Added {bank_data['name']} ({bank_data['short_name']})")
        
        db.commit()
        print("✅ Successfully seeded Peruvian banks!")
        
        # Show summary
        total_banks = db.query(BankProvider).filter(BankProvider.country == "PE").count()
        popular_banks = db.query(BankProvider).filter(
            BankProvider.country == "PE",
            BankProvider.is_popular == True
        ).count()
        
        print(f"\n📊 Summary:")
        print(f"  Total Peruvian banks: {total_banks}")
        print(f"  Popular banks: {popular_banks}")
        
    except Exception as e:
        print(f"❌ Error seeding banks: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_peruvian_banks()
