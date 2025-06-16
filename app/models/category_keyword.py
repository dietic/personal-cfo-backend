from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.types import GUID
import uuid

class CategoryKeyword(Base):
    __tablename__ = "category_keywords"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    category_id = Column(GUID(), ForeignKey("categories.id"), nullable=False)
    keyword = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)  # Optional description for the keyword
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="category_keywords")
    category = relationship("Category", back_populates="keywords")
    
    def __repr__(self):
        return f"<CategoryKeyword(keyword='{self.keyword}', category='{self.category.name if self.category else 'N/A'}')>"
