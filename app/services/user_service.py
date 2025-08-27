from sqlalchemy.orm import Session
from app.models.user import User, CurrencyEnum, TimezoneEnum
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password
from typing import Optional
from app.core.config import settings
from datetime import datetime, timedelta, timezone
import random
import hashlib

from app.services.email_service import EmailService
from app.utils.audit import audit

MAX_OTP_ATTEMPTS = settings.OTP_MAX_ATTEMPTS
RESEND_COOLDOWN_SECONDS = settings.OTP_RESEND_COOLDOWN_SECONDS
OTP_EXP_MINUTES = settings.OTP_EXP_MINUTES

class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.email = EmailService()

    def _generate_otp(self) -> str:
        return f"{random.randint(100000, 999999)}"

    def _hash_otp(self, otp: str) -> str:
        return hashlib.sha256(otp.encode()).hexdigest()

    def _looks_hashed(self, value: Optional[str]) -> bool:
        if not value or len(value) != 64:
            return False
        try:
            int(value, 16)
            return True
        except Exception:
            return False

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, user_create: UserCreate) -> User:
        hashed_password = get_password_hash(user_create.password)
        otp = self._generate_otp()
        expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXP_MINUTES)
        db_user = User(
            email=user_create.email,
            password_hash=hashed_password,
            is_active=False,  # inactive until verified
            otp_code=self._hash_otp(otp),
            otp_expires_at=expires,
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
        # Seed first admin based on configured email, if matches on registration
        if settings and getattr(settings, 'ADMIN_EMAIL', None):
            if db_user.email.lower() == settings.ADMIN_EMAIL.lower():
                db_user.is_admin = True
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        # Send OTP email
        sent = self.email.send_otp(db_user.email, otp)
        db_user.otp_last_sent_at = datetime.now(timezone.utc)
        self.db.commit()
        audit("OTP_SENT", email=db_user.email, user_id=str(db_user.id), sent=bool(sent))

        # Create default categories and seed keywords for new user
        try:
            from app.services.category_service import CategoryService
            from app.services.keyword_service import KeywordService

            # Create default categories
            print(f"🔧 Creating categories for user {db_user.id} ({db_user.email})")
            categories = CategoryService.create_default_categories(self.db, db_user.id)
            print(f"✅ Created {len(categories)} categories for user {db_user.id}")

            # Seed default keywords (15 per category)
            print(f"🔧 Seeding keywords for user {db_user.id}")
            keyword_service = KeywordService(self.db)
            keyword_service.seed_default_keywords(str(db_user.id))
            print(f"✅ Seeded keywords for user {db_user.id}")
            
        except Exception as e:
            print(f"❌ ERROR seeding categories/keywords for user {db_user.id}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Don't fail user creation, just log the error
            audit("CATEGORY_SEED_ERROR", user_id=str(db_user.id), error=str(e))

        return db_user

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def verify_otp(self, email: str, code: str) -> bool:
        user = self.get_user_by_email(email)
        if not user:
            audit("OTP_VERIFY", email=email, result="user_not_found")
            return False
        if user.is_active:
            audit("OTP_VERIFY", email=email, user_id=str(user.id), result="already_active")
            return True
        if user.otp_attempts is not None and user.otp_attempts >= MAX_OTP_ATTEMPTS:
            audit("OTP_VERIFY", email=email, user_id=str(user.id), result="locked", attempts=user.otp_attempts)
            return False
        if not user.otp_code or not user.otp_expires_at:
            audit("OTP_VERIFY", email=email, user_id=str(user.id), result="missing_code")
            return False
        if datetime.now(timezone.utc) > user.otp_expires_at:
            audit("OTP_VERIFY", email=email, user_id=str(user.id), result="expired")
            return False
        # Compare considering hash/plaintext legacy
        stored = user.otp_code
        if self._looks_hashed(stored):
            match = (stored == self._hash_otp(code))
        else:
            match = (stored == code)
        if not match:
            user.otp_attempts = (user.otp_attempts or 0) + 1
            self.db.commit()
            audit("OTP_VERIFY", email=email, user_id=str(user.id), result="mismatch", attempts=user.otp_attempts)
            return False
        # Activate and clear OTP
        user.is_active = True
        user.otp_code = None
        user.otp_expires_at = None
        user.otp_attempts = 0
        self.db.commit()
        self.db.refresh(user)
        audit("OTP_VERIFY", email=email, user_id=str(user.id), result="success")
        return True

    def resend_otp(self, email: str) -> bool:
        user = self.get_user_by_email(email)
        if not user or user.is_active:
            audit("OTP_RESEND", email=email, result="blocked", active=getattr(user, 'is_active', None))
            return False
        now = datetime.now(timezone.utc)
        if user.otp_last_sent_at and (now - user.otp_last_sent_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
            audit("OTP_RESEND", email=email, user_id=str(user.id), result="cooldown")
            return True  # Treat as success to avoid client spam
        otp = self._generate_otp()
        user.otp_code = self._hash_otp(otp)
        user.otp_expires_at = now + timedelta(minutes=OTP_EXP_MINUTES)
        user.otp_last_sent_at = now
        user.otp_attempts = 0  # reset attempts on resend
        self.db.commit()
        sent = self.email.send_otp(email, otp)
        audit("OTP_RESEND", email=email, user_id=str(user.id), result="sent", sent=bool(sent))
        return True

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

    def purge_user_by_email(self, email: str) -> bool:
        """Hard-delete a user and all related records to avoid FK issues.
        Returns True on success, False otherwise.
        """
        user = self.get_user_by_email(email)
        if not user:
            audit("ADMIN_PURGE_USER", email=email, result="not_found")
            return False
        try:
            # Import locally to avoid circular imports
            from app.models.transaction import Transaction
            from app.models.card import Card
            from app.models.statement import Statement
            from app.models.alert import Alert
            from app.models.budget import Budget
            from app.models.recurring_service import RecurringService
            from app.models.category_keyword import CategoryKeyword
            from app.models.category import Category
            from app.models.user_excluded_keyword import UserExcludedKeyword
            from app.models.user_keyword_rule import UserKeywordRule
            from sqlalchemy import or_

            # Collect dependent IDs
            card_ids = [row[0] for row in self.db.query(Card.id).filter(Card.user_id == user.id).all()]
            stmt_ids = [row[0] for row in self.db.query(Statement.id).filter(Statement.user_id == user.id).all()]

            # Delete transactions referencing user's cards or statements
            if card_ids or stmt_ids:
                q = self.db.query(Transaction)
                conds = []
                if card_ids:
                    conds.append(Transaction.card_id.in_(card_ids))
                if stmt_ids:
                    conds.append(Transaction.statement_id.in_(stmt_ids))
                if conds:
                    self.db.query(Transaction).filter(or_(*conds)).delete(synchronize_session=False)

            # Delete other direct dependents
            self.db.query(CategoryKeyword).filter(CategoryKeyword.user_id == user.id).delete(synchronize_session=False)
            self.db.query(UserExcludedKeyword).filter(UserExcludedKeyword.user_id == user.id).delete(synchronize_session=False)
            self.db.query(UserKeywordRule).filter(UserKeywordRule.user_id == user.id).delete(synchronize_session=False)
            self.db.query(Alert).filter(Alert.user_id == user.id).delete(synchronize_session=False)
            self.db.query(Budget).filter(Budget.user_id == user.id).delete(synchronize_session=False)
            self.db.query(RecurringService).filter(RecurringService.user_id == user.id).delete(synchronize_session=False)

            # Delete statements, cards, categories
            if stmt_ids:
                self.db.query(Statement).filter(Statement.id.in_(stmt_ids)).delete(synchronize_session=False)
            if card_ids:
                self.db.query(Card).filter(Card.id.in_(card_ids)).delete(synchronize_session=False)
            self.db.query(Category).filter(Category.user_id == user.id).delete(synchronize_session=False)

            # Finally delete the user
            self.db.query(User).filter(User.id == user.id).delete(synchronize_session=False)

            self.db.commit()
            audit("ADMIN_PURGE_USER", email=email, user_id=str(user.id), result="success")
            return True
        except Exception as e:
            self.db.rollback()
            audit("ADMIN_PURGE_USER", email=email, user_id=str(user.id), result="error", error=str(e))
            return False
