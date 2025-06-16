from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import uuid
from datetime import datetime

class UserKeywordRule(BaseModel):
    __tablename__ = "user_keyword_rules"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False)
    keyword = Column(String(100), nullable=False)
    priority = Column(Integer, default=1)  # Higher priority = checked first
    is_active = Column(Boolean, default=True)
    match_type = Column(String(20), default="contains")  # contains, starts_with, ends_with, exact
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="keyword_rules")
    category = relationship("Category")
    
    def matches_description(self, description: str) -> bool:
        """Check if this keyword rule matches the given description"""
        if not self.is_active:
            return False
            
        desc_lower = description.lower()
        keyword_lower = self.keyword.lower()
        
        if self.match_type == "contains":
            return keyword_lower in desc_lower
        elif self.match_type == "starts_with":
            return desc_lower.startswith(keyword_lower)
        elif self.match_type == "ends_with":
            return desc_lower.endswith(keyword_lower)
        elif self.match_type == "exact":
            return desc_lower == keyword_lower
        else:
            return keyword_lower in desc_lower  # Default to contains
