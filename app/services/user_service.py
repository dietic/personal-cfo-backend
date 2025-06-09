from sqlalchemy.orm import Session
from app.models.user import User, CurrencyEnum, TimezoneEnum
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password
from typing import Optional

class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()
    
    def create_user(self, user_create: UserCreate) -> User:
        hashed_password = get_password_hash(user_create.password)
        db_user = User(
            email=user_create.email,
            password_hash=hashed_password,
            # Set default preferences
            preferred_currency=CurrencyEnum.USD,
            timezone=TimezoneEnum.UTC_MINUS_8,
            budget_alerts_enabled=True,
            payment_reminders_enabled=True,
            transaction_alerts_enabled=False,
            weekly_summary_enabled=True,
            monthly_reports_enabled=True,
            email_notifications_enabled=True,
            push_notifications_enabled=False
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
    
    def update_user_password(self, user: User, new_password: str) -> User:
        """Update user password"""
        user.password_hash = get_password_hash(new_password)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def delete_user(self, user: User) -> bool:
        """Delete user account and all associated data"""
        try:
            self.db.delete(user)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
    
    def get_user_statistics(self, user: User) -> dict:
        """Get user account statistics"""
        from app.models.card import Card
        from app.models.transaction import Transaction
        from app.models.budget import Budget
        from app.models.statement import Statement
        from app.models.alert import Alert
        
        return {
            "total_cards": self.db.query(Card).filter(Card.user_id == user.id).count(),
            "total_transactions": self.db.query(Transaction).join(Card).filter(Card.user_id == user.id).count(),
            "total_budgets": self.db.query(Budget).filter(Budget.user_id == user.id).count(),
            "total_statements": self.db.query(Statement).filter(Statement.user_id == user.id).count(),
            "total_alerts": self.db.query(Alert).filter(Alert.user_id == user.id).count(),
            "account_created": user.created_at,
            "last_updated": user.updated_at
        }
