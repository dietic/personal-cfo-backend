from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base
from app.core.types import GUID

class CardType(Base):
    """
    Types of cards like Credit Card, Debit Card, etc.
    
    Like categorizing different types of payment instruments - each type
    has different rules, benefits, and usage patterns.
    """
    __tablename__ = "card_types"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)  # "Credit Card", "Debit Card"
    short_name = Column(String, nullable=True)  # "Credit", "Debit" - for display
    country = Column(String, nullable=False, default="GLOBAL")  # Card types are mostly global
    is_active = Column(Boolean, default=True)
    
    # Additional metadata for different card types
    description = Column(String, nullable=True)  # "Revolving credit with monthly payments"
    typical_interest_rate = Column(String, nullable=True)  # "18-29% APR" - for reference
    
    # Visual styling
    color_primary = Column(String, nullable=True)    # Different colors for different types
    color_secondary = Column(String, nullable=True)
    
    # Relationships
    cards = relationship("Card", back_populates="card_type")
