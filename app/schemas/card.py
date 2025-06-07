from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import uuid

class CardBase(BaseModel):
    card_name: str
    payment_due_date: Optional[date] = None
    network_provider: Optional[str] = None
    bank_provider: Optional[str] = None
    card_type: Optional[str] = None

class CardCreate(CardBase):
    pass

class CardUpdate(BaseModel):
    card_name: Optional[str] = None
    payment_due_date: Optional[date] = None
    network_provider: Optional[str] = None
    bank_provider: Optional[str] = None
    card_type: Optional[str] = None

class Card(CardBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    
    class Config:
        from_attributes = True
