from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Float, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base
from app.core.types import GUID


class AlertType(enum.Enum):
    SPENDING_LIMIT = "spending_limit"
    MERCHANT_WATCH = "merchant_watch"
    CATEGORY_BUDGET = "category_budget"
    UNUSUAL_SPENDING = "unusual_spending"
    LARGE_TRANSACTION = "large_transaction"
    NEW_MERCHANT = "new_merchant"
    BUDGET_EXCEEDED = "budget_exceeded"


class AlertSeverity(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    statement_id = Column(GUID(), ForeignKey("statements.id"), nullable=True)  # Optional link to statement
    
    # Alert details
    alert_type = Column(Enum(AlertType), nullable=False)
    severity = Column(Enum(AlertSeverity), nullable=False, default=AlertSeverity.MEDIUM)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)  # Changed from 'description' to 'message' to match DB
    
    # Alert state (only is_read exists in DB)
    is_read = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="alerts")
    statement = relationship("Statement", back_populates="alerts")
