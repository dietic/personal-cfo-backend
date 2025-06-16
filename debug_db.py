#!/usr/bin/env python3
"""
Debug database setup
"""
import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import Base

# Import all models to ensure they're registered
from app.models import (
    user, transaction, card, category, budget, 
    alert, recurring_service, statement, category_keyword
)

def debug_database():
    """Debug database setup"""
    print(f"Database URL: {settings.DATABASE_URL}")
    
    engine = create_engine(settings.DATABASE_URL, echo=True)
    
    # Check existing tables
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        existing_tables = [row[0] for row in result.fetchall()]
        print(f"Existing tables: {existing_tables}")
    
    # Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created!")
    
    # Check tables again
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        tables = [row[0] for row in result.fetchall()]
        print(f"Tables after creation: {tables}")
        
        # Show table info for each table
        for table in tables:
            print(f"\n--- Table: {table} ---")
            result = conn.execute(text(f"PRAGMA table_info({table});"))
            columns = result.fetchall()
            for col in columns:
                print(f"  Column: {col[1]} ({col[2]})")

if __name__ == "__main__":
    debug_database()
