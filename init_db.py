#!/usr/bin/env python3
"""
Initialize database with tables and test data
"""
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import Base
from app.models.user import User
from app.models.transaction import Transaction
from app.models.category import Category

# Import all models to ensure they're registered with Base
from app.models import (
    user, transaction, card, category, budget, 
    alert, recurring_service, statement, category_keyword
)

def init_database():
    """Initialize database with tables and test data"""
    engine = create_engine(settings.DATABASE_URL)
    
    # Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Check if test user already exists
        existing_user = session.query(User).filter(User.email == "dierios93@gmail.com").first()
        if existing_user:
            print("Test user already exists!")
            return
        
        # Create password hasher
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Create test user
        test_user = User(
            email="dierios93@gmail.com",
            password_hash=pwd_context.hash("Lima2023$"),
            first_name="Diego",
            last_name="Rios",
            is_active=True
        )
        session.add(test_user)
        session.commit()
        session.refresh(test_user)
        
        print(f"Created test user: {test_user.email} (ID: {test_user.id})")
        
        # Create some default categories
        default_categories = [
            "Food & Dining",
            "Shopping",
            "Transportation",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Income",
            "Transfers"
        ]
        
        for cat_name in default_categories:
            existing_cat = session.query(Category).filter(
                Category.name == cat_name,
                Category.user_id == test_user.id
            ).first()
            
            if not existing_cat:
                category = Category(
                    name=cat_name,
                    user_id=test_user.id,
                    description=f"Default {cat_name} category"
                )
                session.add(category)
        
        session.commit()
        print(f"Created {len(default_categories)} default categories")
        
        # Create some sample transactions for monthly data
        from datetime import datetime, timedelta
        import random
        
        # Create transactions for the last 6 months
        base_date = datetime.now()
        for month_offset in range(6):
            month_date = base_date - timedelta(days=30 * month_offset)
            
            # Create 5-10 random transactions per month
            for _ in range(random.randint(5, 10)):
                transaction_date = month_date - timedelta(days=random.randint(0, 29))
                
                # Random transaction amount (mix of positive and negative)
                amount = random.choice([
                    -random.randint(10, 500),  # Expenses
                    random.randint(100, 2000)  # Income (less frequent)
                ]) if random.random() > 0.8 else -random.randint(10, 500)
                
                transaction = Transaction(
                    user_id=test_user.id,
                    description=f"Sample transaction {random.randint(1000, 9999)}",
                    amount=amount,
                    transaction_date=transaction_date,
                    category_id=random.randint(1, len(default_categories))
                )
                session.add(transaction)
        
        session.commit()
        print("Created sample transactions for testing")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    init_database()
    print("Database initialization complete!")
