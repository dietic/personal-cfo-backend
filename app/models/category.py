from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.types import GUID


class Category(Base):
    __tablename__ = "categories"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)  # Nullable for system categories
    name = Column(String, nullable=False)
    color = Column(String, nullable=True)  # Hex color code for UI
    emoji = Column(String, nullable=True)  # Emoji for category icon
    is_default = Column(Boolean, default=False)  # System default categories
    is_system = Column(Boolean, default=False)  # True for predefined Spanish categories
    is_active = Column(Boolean, default=True)
    ai_seeded_at = Column(DateTime(timezone=True), nullable=True)  # When AI keywords were generated
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="categories")
    keywords = relationship("CategoryKeyword", back_populates="category", cascade="all, delete-orphan")
    
    def get_keyword_strings(self):
        """Return list of keyword strings for this category"""
        return [kw.keyword.lower() for kw in self.keywords]
    
    def add_keyword(self, keyword_text: str, description: str = None):
        """Add a new keyword to this category"""
        from app.models.category_keyword import CategoryKeyword
        keyword = CategoryKeyword(
            user_id=self.user_id,
            category_id=self.id,
            keyword=keyword_text.lower().strip(),
            description=description
        )
        self.keywords.append(keyword)
        return keyword
    
    def remove_keyword(self, keyword_text: str):
        """Remove a keyword from this category"""
        keyword_text = keyword_text.lower().strip()
        for keyword in self.keywords:
            if keyword.keyword == keyword_text:
                self.keywords.remove(keyword)
                return True
        return False