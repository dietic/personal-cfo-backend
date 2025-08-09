from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.types import GUID

class UserKeywordRule(Base):
    __tablename__ = "user_keyword_rules"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    category_id = Column(GUID(), ForeignKey("categories.id"), nullable=True)

    # Comma-separated lists or JSON strings of keywords (as stored today)
    include_keywords = Column(Text, nullable=True)
    exclude_keywords = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
