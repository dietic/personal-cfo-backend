from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.types import GUID

class Statement(Base):
    __tablename__ = "statements"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, csv
    statement_month = Column(Date)  # Month this statement covers (first day of month)
    status = Column(String, default="uploaded")  # uploaded, extracting, extracted, categorizing, completed, failed
    extraction_status = Column(String, default="pending")  # pending, in_progress, completed, failed
    categorization_status = Column(String, default="pending")  # pending, in_progress, completed, failed
    retry_count = Column(String, default="0")  # Track retry attempts for each step (JSON: {"extraction": 0, "categorization": 0})
    processed_transactions = Column(Text)  # JSON string of parsed transactions
    ai_insights = Column(Text)  # JSON string of AI-generated insights and tips
    error_message = Column(Text)  # Store error details for failed operations
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="statements")
    alerts = relationship("Alert", back_populates="statement", cascade="all, delete-orphan")
