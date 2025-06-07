from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
import uuid

class RecurringServiceBase(BaseModel):
    name: str
    amount: Decimal
    due_date: date
    category: Optional[str] = None
    reminder_days: Optional[int] = 3

class RecurringServiceCreate(RecurringServiceBase):
    pass

class RecurringServiceUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[Decimal] = None
    due_date: Optional[date] = None
    category: Optional[str] = None
    reminder_days: Optional[int] = None

class RecurringService(RecurringServiceBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    
    class Config:
        from_attributes = True
