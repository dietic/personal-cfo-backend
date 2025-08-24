from sqlalchemy import Column, String, DateTime, Boolean, Enum as SQLEnum, Integer, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base
from app.core.types import GUID

class CurrencyEnum(enum.Enum):
    USD = "USD"
    PEN = "PEN"
    EUR = "EUR"
    GBP = "GBP"

class TimezoneEnum(enum.Enum):
    UTC_MINUS_8 = "UTC-8 (Pacific Time)"
    UTC_MINUS_7 = "UTC-7 (Mountain Time)"
    UTC_MINUS_6 = "UTC-6 (Central Time)"
    UTC_MINUS_5 = "UTC-5 (Eastern Time)"
    UTC_MINUS_3 = "UTC-3 (Argentina Time)"
    UTC_0 = "UTC+0 (London Time)"
    UTC_PLUS_1 = "UTC+1 (Central European Time)"

class UserTypeEnum(enum.Enum):
    FREE = "free"
    PLUS = "plus"
    PRO = "pro"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)

    # Email verification (OTP)
    otp_code = Column(String, nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    otp_attempts = Column(Integer, nullable=True, default=0)
    otp_last_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Profile Information
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    profile_picture_url = Column(String, nullable=True)

    # Preferences
    preferred_currency = Column(SQLEnum(CurrencyEnum, name="currencyenum"), default=CurrencyEnum.USD)
    timezone = Column(
        SQLEnum(
            TimezoneEnum,
            name="timezoneenum",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=TimezoneEnum.UTC_MINUS_8,
    )

    # Notification Preferences
    budget_alerts_enabled = Column(Boolean, default=True)
    payment_reminders_enabled = Column(Boolean, default=True)
    transaction_alerts_enabled = Column(Boolean, default=False)
    weekly_summary_enabled = Column(Boolean, default=True)
    monthly_reports_enabled = Column(Boolean, default=True)

    # Delivery Methods
    email_notifications_enabled = Column(Boolean, default=True)
    push_notifications_enabled = Column(Boolean, default=False)

    # Subscription / Billing Fields
    plan_tier = Column(SQLEnum(UserTypeEnum, name="usertypeenum", values_callable=lambda x: [e.value for e in x]), default=UserTypeEnum.FREE, nullable=False, index=True)
    plan_status = Column(String, default="inactive", nullable=False)  # inactive|active|past_due|canceled
    billing_currency = Column(String, default="PEN", nullable=False)  # PEN only for now
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    provider_customer_id = Column(String, nullable=True)  # Mercado Pago payer id
    provider_subscription_id = Column(String, nullable=True)  # Future recurring sub id
    last_payment_status = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    cards = relationship("Card", back_populates="user", cascade="all, delete-orphan")
    recurring_services = relationship("RecurringService", back_populates="user", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
    statements = relationship("Statement", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    category_keywords = relationship("CategoryKeyword", back_populates="user", cascade="all, delete-orphan")
