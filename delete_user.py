#!/usr/bin/env python3
"""
Delete a specific user and all their related data
"""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import sessionmaker
from app.core.database import engine
from app.models.user import User
from app.models.card import Card
from app.models.transaction import Transaction
from app.models.category import Category
from app.models.category_keyword import CategoryKeyword
from app.models.budget import Budget
from app.models.alert import Alert
from app.models.statement import Statement
from app.models.recurring_service import RecurringService

def delete_user(email: str):
    """Delete user and all their related data"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Find the user
        user = session.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ User {email} not found")
            return
        
        print(f"🔍 Found user: {user.email} (ID: {user.id})")
        
        # Delete related data in correct order (respecting foreign key constraints)
        
        # First get all user's cards
        cards = session.query(Card).filter(Card.user_id == user.id).all()
        card_ids = [card.id for card in cards]
        
        # Delete transactions (linked through cards)
        if card_ids:
            transactions = session.query(Transaction).filter(Transaction.card_id.in_(card_ids)).all()
            for transaction in transactions:
                session.delete(transaction)
            print(f"🗑️ Deleted {len(transactions)} transactions")
        else:
            print(f"🗑️ Deleted 0 transactions")
        
        # Delete statements
        statements = session.query(Statement).filter(Statement.user_id == user.id).all()
        for statement in statements:
            session.delete(statement)
        print(f"🗑️ Deleted {len(statements)} statements")
        
        # Delete cards
        for card in cards:
            session.delete(card)
        print(f"🗑️ Deleted {len(cards)} cards")
        
        # Delete budgets
        budgets = session.query(Budget).filter(Budget.user_id == user.id).all()
        for budget in budgets:
            session.delete(budget)
        print(f"🗑️ Deleted {len(budgets)} budgets")
        
        # Delete alerts
        alerts = session.query(Alert).filter(Alert.user_id == user.id).all()
        for alert in alerts:
            session.delete(alert)
        print(f"🗑️ Deleted {len(alerts)} alerts")
        
        # Delete recurring services
        recurring_services = session.query(RecurringService).filter(RecurringService.user_id == user.id).all()
        for service in recurring_services:
            session.delete(service)
        print(f"🗑️ Deleted {len(recurring_services)} recurring services")
        
        # Delete category keywords
        keywords = session.query(CategoryKeyword).filter(CategoryKeyword.user_id == user.id).all()
        for keyword in keywords:
            session.delete(keyword)
        print(f"🗑️ Deleted {len(keywords)} category keywords")
        
        # Delete categories
        categories = session.query(Category).filter(Category.user_id == user.id).all()
        for category in categories:
            session.delete(category)
        print(f"🗑️ Deleted {len(categories)} categories")
        
        # Finally delete the user
        session.delete(user)
        
        # Commit all changes
        session.commit()
        print(f"✅ Successfully deleted user {email} and all related data!")
        
    except Exception as e:
        print(f"❌ Error deleting user: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python delete_user.py <email>")
        sys.exit(1)
    
    email = sys.argv[1]
    delete_user(email)