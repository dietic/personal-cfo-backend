from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
import uuid
import json

from app.core.database import Base
from app.core.types import GUID


class Category(Base):
    __tablename__ = "categories"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)  # Nullable for system categories
    name = Column(String, nullable=False)
    color = Column(String, nullable=True)  # Hex color code for UI
    _keywords = Column("keywords", Text, nullable=True)  # JSON string of keywords for auto-categorization
    is_default = Column(Boolean, default=False)  # System default categories
    is_system = Column(Boolean, default=False)  # True for predefined Spanish categories
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="categories")
    
    @hybrid_property
    def keywords(self):
        """Return keywords as a list"""
        if self._keywords:
            try:
                return json.loads(self._keywords)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    @keywords.setter
    def keywords(self, value):
        """Set keywords from a list"""
        if value is None:
            self._keywords = None
        elif isinstance(value, list):
            self._keywords = json.dumps(value)
        elif isinstance(value, str):
            self._keywords = value
        else:
            self._keywords = json.dumps(list(value))
