from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base
from app.core.types import GUID

class NetworkProvider(Base):
    """
    Network providers like Visa, Mastercard, etc.
    
    Like having a catalog of credit card networks - each network has its own
    processing rules, acceptance rates, and brand identity.
    """
    __tablename__ = "network_providers"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)  # "Visa", "Mastercard"
    short_name = Column(String, nullable=True)  # "VISA", "MC" - for display
    country = Column(String, nullable=False, default="GLOBAL")  # Most networks are global
    is_active = Column(Boolean, default=True)
    
    # Visual branding for UI
    color_primary = Column(String, nullable=True)    # "#1A1F71" for Visa blue
    color_secondary = Column(String, nullable=True)  # "#F7B600" for Visa gold
    logo_url = Column(String, nullable=True)         # Path to network logo
    
    # Relationships
    cards = relationship("Card", back_populates="network_provider")
