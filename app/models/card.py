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
    
    # Upgraded from strings to proper relationships - like having a real address book instead of sticky notes
    network_provider_id = Column(GUID(), ForeignKey("network_providers.id"), nullable=True)
    bank_provider_id = Column(GUID(), ForeignKey("bank_providers.id"), nullable=True)
    card_type_id = Column(GUID(), ForeignKey("card_types.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="cards")
    bank_provider = relationship("BankProvider", back_populates="cards")
    network_provider = relationship("NetworkProvider", back_populates="cards")
    card_type = relationship("CardType", back_populates="cards")  # Clean name
    transactions = relationship("Transaction", back_populates="card", cascade="all, delete-orphan")
