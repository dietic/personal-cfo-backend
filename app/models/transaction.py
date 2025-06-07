from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.types import GUID

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    card_id = Column(GUID(), ForeignKey("cards.id"), nullable=False)
    merchant = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")  # USD, PEN, etc.
    category = Column(String)
    transaction_date = Column(Date, nullable=False)
    tags = Column(String)  # JSON string for SQLite compatibility
    description = Column(String)
    ai_confidence = Column(Numeric(3, 2))  # AI categorization confidence (0.00-1.00)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    card = relationship("Card", back_populates="transactions")
