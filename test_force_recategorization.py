#!/usr/bin/env python3
"""
Test script to verify that recategorization works for all transactions.
"""
import sys
import os
sys.path.append('/home/diego/Documents/personal-cfo/personal-cfo-backend')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.transaction import Transaction
from app.models.statement import Statement
from app.models.category import Category
from app.models.category_keyword import CategoryKeyword
from app.services.keyword_categorization_service import KeywordCategorizationService
import uuid
from datetime import datetime

# Database setup
DATABASE_URL = "sqlite:///personalcfo.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_force_recategorization():
    """Test that force_recategorize actually updates all transactions."""
    db = SessionLocal()
    
    try:
        # Get first user
        user_id = "f47ac10b-58cc-4372-a567-0e02b2c3d479"  # Example user ID
        
        # Create some test transactions if they don't exist
        test_statement_id = str(uuid.uuid4())
        
        # Look for existing transactions or create some
        existing_transactions = db.query(Transaction).filter(
            Transaction.statement_id != None
        ).limit(3).all()
        
        if not existing_transactions:
            print("No existing transactions found. Creating test transactions...")
            # Create a test statement
            statement = Statement(
                id=test_statement_id,
                user_id=user_id,
                filename="test_statement.pdf",
                upload_date=datetime.now(),
                status="completed"
            )
            db.add(statement)
            db.commit()
            
            # Create test transactions
            test_transactions = [
                Transaction(
                    id=str(uuid.uuid4()),
                    statement_id=test_statement_id,
                    merchant="WALMART SUPERCENTER",
                    amount=45.67,
                    currency="USD",
                    category="Food",
                    transaction_date=datetime.now(),
                    description="Grocery shopping",
                    ai_confidence=0.8
                ),
                Transaction(
                    id=str(uuid.uuid4()),
                    statement_id=test_statement_id,
                    merchant="SHELL GAS STATION",
                    amount=35.00,
                    currency="USD",
                    category="Transportation",
                    transaction_date=datetime.now(),
                    description="Gas refill",
                    ai_confidence=0.9
                ),
                Transaction(
                    id=str(uuid.uuid4()),
                    statement_id=test_statement_id,
                    merchant="AMAZON MARKETPLACE",
                    amount=25.99,
                    currency="USD",
                    category="Shopping",
                    transaction_date=datetime.now(),
                    description="Online purchase",
                    ai_confidence=0.7
                )
            ]
            
            for txn in test_transactions:
                db.add(txn)
            db.commit()
            
            existing_transactions = test_transactions
        
        print(f"Testing with {len(existing_transactions)} transactions")
        
        # Show initial state
        print("\n=== INITIAL STATE ===")
        for txn in existing_transactions:
            print(f"Transaction {txn.id}: {txn.merchant} -> {txn.category}")
        
        # Test WITHOUT force_recategorize (should skip already categorized)
        print("\n=== TEST 1: WITHOUT force_recategorize ===")
        service = KeywordCategorizationService(db)
        result1 = service.categorize_database_transactions(
            user_id, existing_transactions, force_recategorize=False
        )
        print(f"Results: {result1}")
        
        # Refresh transactions to see changes
        db.refresh(existing_transactions[0])
        db.refresh(existing_transactions[1])
        db.refresh(existing_transactions[2])
        
        print("After WITHOUT force_recategorize:")
        for txn in existing_transactions:
            print(f"Transaction {txn.id}: {txn.merchant} -> {txn.category}")
        
        # Test WITH force_recategorize (should recategorize all)
        print("\n=== TEST 2: WITH force_recategorize=True ===")
        result2 = service.categorize_database_transactions(
            user_id, existing_transactions, force_recategorize=True
        )
        print(f"Results: {result2}")
        
        # Refresh transactions to see changes
        db.refresh(existing_transactions[0])
        db.refresh(existing_transactions[1])
        db.refresh(existing_transactions[2])
        
        print("After WITH force_recategorize=True:")
        for txn in existing_transactions:
            print(f"Transaction {txn.id}: {txn.merchant} -> {txn.category}")
        
        # Check if force_recategorize actually processed all transactions
        processed_count = result2.get('categorized', 0) + result2.get('uncategorized', 0)
        print(f"\nForce recategorization processed {processed_count} out of {len(existing_transactions)} transactions")
        
        if processed_count == len(existing_transactions):
            print("✅ SUCCESS: Force recategorization processed all transactions!")
        else:
            print("❌ FAILED: Force recategorization did not process all transactions")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_force_recategorization()
