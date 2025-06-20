from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.types import GUID


class BankProvider(Base):
    """
    Master table of bank providers across different countries.
    
    Think of this as a comprehensive phone book of banks - instead of manually 
    typing bank names (which leads to typos and inconsistency), we maintain 
    a curated list with rich metadata.
    """
    __tablename__ = "bank_providers"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)  # "Banco de Crédito del Perú"
    short_name = Column(String, nullable=True)  # "BCP" - for display
    country = Column(String, nullable=False)  # "PE", "US", "MX" (ISO country codes)
    country_name = Column(String, nullable=False)  # "Peru", "United States", "Mexico"
    
    # Optional rich metadata for future features
    logo_url = Column(String, nullable=True)  # For displaying bank logos
    website = Column(String, nullable=True)  # Bank's official website
    color_primary = Column(String, nullable=True)  # Brand color for UI theming
    color_secondary = Column(String, nullable=True)  # Secondary/accent color for gradients
    
    # System flags
    is_active = Column(Boolean, default=True)  # Can be disabled without deletion
    is_popular = Column(Boolean, default=False)  # Show first in dropdowns
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    cards = relationship("Card", back_populates="bank_provider")
    
    def __repr__(self):
        return f"<BankProvider(name='{self.name}', country='{self.country}')>"
    
    @property
    def display_name(self):
        """Returns short_name if available, otherwise full name"""
        return self.short_name if self.short_name else self.name
