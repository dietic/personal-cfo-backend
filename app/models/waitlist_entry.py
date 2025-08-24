import uuid
from sqlalchemy import Column, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.types import GUID

class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True, index=True)
    source = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('email', name='uq_waitlist_email'),
    )
