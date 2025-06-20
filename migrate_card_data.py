"""
Migration script to add network providers and card types tables,
and migrate existing card data.
"""

import sys
import os
import uuid

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.database import engine
from app.core.seed_data import NETWORK_PROVIDERS, CARD_TYPES

def migrate_database():
    """
    Add the new tables and migrate existing data.
    
    Like renovating a house - we're adding new rooms (tables) and
    updating the existing furniture (data) to fit the new layout.
    """
    
    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()
        
        try:
            print("Creating network_providers table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS network_providers (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    short_name VARCHAR,
                    country VARCHAR NOT NULL DEFAULT 'GLOBAL',
                    is_active BOOLEAN DEFAULT 1,
                    color_primary VARCHAR,
                    color_secondary VARCHAR,
                    logo_url VARCHAR
                )
            """))
            
            print("Creating card_types table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS card_types (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    short_name VARCHAR,
                    country VARCHAR NOT NULL DEFAULT 'GLOBAL',
                    is_active BOOLEAN DEFAULT 1,
                    description VARCHAR,
                    typical_interest_rate VARCHAR,
                    color_primary VARCHAR,
                    color_secondary VARCHAR
                )
            """))
            
            # Insert seed data for network providers
            print("Seeding network providers...")
            for provider in NETWORK_PROVIDERS:
                provider_id = str(uuid.uuid4())
                conn.execute(text("""
                    INSERT OR IGNORE INTO network_providers 
                    (id, name, short_name, country, is_active, color_primary, color_secondary)
                    VALUES (:id, :name, :short_name, :country, :is_active, :color_primary, :color_secondary)
                """), {
                    'id': provider_id,
                    'name': provider['name'],
                    'short_name': provider['short_name'],
                    'country': provider['country'],
                    'is_active': provider['is_active'],
                    'color_primary': provider['color_primary'],
                    'color_secondary': provider['color_secondary']
                })
            
            # Insert seed data for card types
            print("Seeding card types...")
            for card_type in CARD_TYPES:
                card_type_id = str(uuid.uuid4())
                conn.execute(text("""
                    INSERT OR IGNORE INTO card_types 
                    (id, name, short_name, country, is_active, description, typical_interest_rate, color_primary, color_secondary)
                    VALUES (:id, :name, :short_name, :country, :is_active, :description, :typical_interest_rate, :color_primary, :color_secondary)
                """), {
                    'id': card_type_id,
                    'name': card_type['name'],
                    'short_name': card_type['short_name'],
                    'country': card_type['country'],
                    'is_active': card_type['is_active'],
                    'description': card_type['description'],
                    'typical_interest_rate': card_type['typical_interest_rate'],
                    'color_primary': card_type['color_primary'],
                    'color_secondary': card_type['color_secondary']
                })
            
            # Add new columns to cards table
            print("Adding new columns to cards table...")
            
            # Check if columns already exist
            columns_info = conn.execute(text("PRAGMA table_info(cards)")).fetchall()
            existing_columns = [col[1] for col in columns_info]
            
            if 'network_provider_id' not in existing_columns:
                conn.execute(text("ALTER TABLE cards ADD COLUMN network_provider_id VARCHAR"))
            
            if 'card_type_id' not in existing_columns:
                conn.execute(text("ALTER TABLE cards ADD COLUMN card_type_id VARCHAR"))
            
            # Migrate existing network provider data
            print("Migrating network provider data...")
            
            # Get existing network provider values
            existing_cards = conn.execute(text("""
                SELECT id, network_provider FROM cards 
                WHERE network_provider IS NOT NULL AND network_provider != ''
            """)).fetchall()
            
            for card in existing_cards:
                card_id, network_provider = card
                
                # Find matching network provider ID
                provider_result = conn.execute(text("""
                    SELECT id FROM network_providers 
                    WHERE name = :name OR short_name = :name
                """), {'name': network_provider}).fetchone()
                
                if provider_result:
                    provider_id = provider_result[0]
                    conn.execute(text("""
                        UPDATE cards SET network_provider_id = :provider_id 
                        WHERE id = :card_id
                    """), {'provider_id': provider_id, 'card_id': card_id})
                    print(f"  Migrated card {card_id}: {network_provider} -> {provider_id}")
                else:
                    # Use "Other" as fallback
                    other_provider = conn.execute(text("""
                        SELECT id FROM network_providers WHERE name = 'Other'
                    """)).fetchone()
                    
                    if other_provider:
                        conn.execute(text("""
                            UPDATE cards SET network_provider_id = :provider_id 
                            WHERE id = :card_id
                        """), {'provider_id': other_provider[0], 'card_id': card_id})
                        print(f"  Migrated card {card_id}: {network_provider} -> Other (fallback)")
            
            # Migrate existing card type data
            print("Migrating card type data...")
            
            existing_cards = conn.execute(text("""
                SELECT id, card_type FROM cards 
                WHERE card_type IS NOT NULL AND card_type != ''
            """)).fetchall()
            
            for card in existing_cards:
                card_id, card_type = card
                
                # Find matching card type ID
                type_result = conn.execute(text("""
                    SELECT id FROM card_types 
                    WHERE name = :name
                """), {'name': card_type}).fetchone()
                
                if type_result:
                    type_id = type_result[0]
                    conn.execute(text("""
                        UPDATE cards SET card_type_id = :type_id 
                        WHERE id = :card_id
                    """), {'type_id': type_id, 'card_id': card_id})
                    print(f"  Migrated card {card_id}: {card_type} -> {type_id}")
                else:
                    print(f"  Warning: No matching card type found for '{card_type}' on card {card_id}")
            
            # Commit the transaction
            trans.commit()
            print("Migration completed successfully!")
            
        except Exception as e:
            trans.rollback()
            print(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate_database()
