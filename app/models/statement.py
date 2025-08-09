from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Date, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import json

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
    status = Column(String, default="uploaded")  # uploaded, extracting, extracted, categorizing, completed, failed, pending
    task_id = Column(String, nullable=True)  # Celery task ID for background processing
    processing_message = Column(String, nullable=True)  # User-friendly processing status message
    transactions_count = Column(Integer, default=0)  # Number of transactions extracted
    extraction_method = Column(String, nullable=True)  # ai, pattern, manual
    extraction_status = Column(String, default="pending")  # pending, in_progress, completed, failed
    categorization_status = Column(String, default="pending")  # pending, in_progress, completed, failed

    # Replace JSON retry_count with proper integer columns
    extraction_retries = Column(Integer, default=0)
    categorization_retries = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    processed_transactions = Column(Text)  # JSON string of parsed transactions
    ai_insights = Column(Text)  # JSON string of AI-generated insights and tips
    error_message = Column(Text)  # Store error details for failed operations
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="statements")
    alerts = relationship("Alert", back_populates="statement", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="statement", cascade="all, delete-orphan")

    @property
    def retry_count(self) -> str:
        """Generate retry_count JSON string for API compatibility"""
        return json.dumps({
            "extraction": self.extraction_retries or 0,
            "categorization": self.categorization_retries or 0
        })
