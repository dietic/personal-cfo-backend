from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import uuid
from app.schemas.bank_provider import BankProviderSimple

class CardBase(BaseModel):
    card_name: str
    payment_due_date: Optional[date] = None
    network_provider: Optional[str] = None
    bank_provider_id: Optional[uuid.UUID] = None  # Reference to BankProvider
    card_type: Optional[str] = None

class CardCreate(CardBase):
    pass

class CardUpdate(BaseModel):
    card_name: Optional[str] = None
    payment_due_date: Optional[date] = None
    network_provider: Optional[str] = None
    bank_provider_id: Optional[uuid.UUID] = None
    card_type: Optional[str] = None

class Card(CardBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    
    # Include the full bank provider details for rich display
    bank_provider: Optional[BankProviderSimple] = None
    
    class Config:
        from_attributes = True
