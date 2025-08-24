#!/usr/bin/env python3
"""
Seed the database with initial data (bank providers, etc.)
This script is safe to run multiple times.
"""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import sessionmaker
from app.core.database import engine
from app.services.seeding_service import SeedingService

def seed_database():
    """Seed database with initial data"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        print("Seeding bank providers...")
        bank_count = SeedingService.seed_bank_providers(session)
        print(f"✅ Inserted {bank_count} new bank providers")
        
        print("Seeding user categories and keywords...")
        user_stats = SeedingService.backfill_user_categories_and_keywords(session)
        print(f"✅ Created categories for {user_stats['users_with_new_categories']} users")
        print(f"✅ Seeded keywords for {user_stats['users_with_seeded_keywords']} users")
        
        session.commit()
        print("✅ Database seeding completed successfully!")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    seed_database()