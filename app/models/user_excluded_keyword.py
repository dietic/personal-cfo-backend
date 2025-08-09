from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base
from app.core.types import GUID


class UserExcludedKeyword(Base):
    """Per-user excluded transaction keyword.

    Any transaction whose merchant or description contains one of these keywords
    (case-insensitive, diacritics-insensitive) will be skipped during AI extraction.
    """
    __tablename__ = "user_excluded_keywords"
    __table_args__ = (
        UniqueConstraint("user_id", "keyword_normalized", name="uq_user_excluded_keyword_normalized"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    # Original keyword as entered by user
    keyword = Column(String(255), nullable=False)
    # Normalized (lowercased, diacritics-removed) for matching and uniqueness
    keyword_normalized = Column(String(255), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")
