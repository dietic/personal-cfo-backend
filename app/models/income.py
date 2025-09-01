from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Numeric, Boolean, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.types import GUID

class Income(Base):
    __tablename__ = "incomes"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    card_id = Column(GUID(), ForeignKey("cards.id"), nullable=False)
    
    # Income details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    description = Column(String, nullable=False)
    income_date = Column(Date, nullable=False)
    
    # Recurring income settings
    is_recurring = Column(Boolean, default=False)
    recurrence_day = Column(Integer, nullable=True)  # Day of month for recurrence (1-31)
    last_processed_date = Column(Date, nullable=True)  # Last date this recurring income was processed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="incomes")
    card = relationship("Card", back_populates="incomes")

    def __repr__(self):
        return f"<Income {self.description}: {self.amount} {self.currency} on {self.income_date}>"
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "card_id": str(self.card_id),
            "amount": float(self.amount),
            "currency": self.currency,
            "description": self.description,
            "income_date": self.income_date.isoformat(),
            "is_recurring": self.is_recurring,
            "recurrence_day": self.recurrence_day,
            "last_processed_date": self.last_processed_date.isoformat() if self.last_processed_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }