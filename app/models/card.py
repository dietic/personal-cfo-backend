from sqlalchemy import Column, String, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.types import GUID

class Card(Base):
    __tablename__ = "cards"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    card_name = Column(String, nullable=False)
    payment_due_date = Column(Date)
    network_provider = Column(String)  # VISA, Mastercard, etc.
    
    # Changed from string to relationship - like upgrading from sticky notes to a proper database
    bank_provider_id = Column(GUID(), ForeignKey("bank_providers.id"), nullable=True)
    
    card_type = Column(String)         # credit, debit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="cards")
    bank_provider = relationship("BankProvider", back_populates="cards")
    transactions = relationship("Transaction", back_populates="card", cascade="all, delete-orphan")
