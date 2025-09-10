from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.types import GUID

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    canonical_name = Column(String, nullable=False)  # Standardized name (e.g., "Makro")
    display_name = Column(String, nullable=False)    # Display name (can be same as canonical)
    description_patterns = Column(String)  # JSON array of patterns that match this merchant
    category = Column(String)  # Most common category for this merchant
    transaction_count = Column(String, default="0")  # Number of transactions with this merchant
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="merchants")

    def __repr__(self):
        return f"<Merchant {self.canonical_name} (User: {self.user_id})>"