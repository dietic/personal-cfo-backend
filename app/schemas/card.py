from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
import uuid
from app.schemas.bank_provider import BankProviderSimple

class CardBase(BaseModel):
    card_name: str
    payment_due_date: Optional[date] = None
    bank_provider_id: Optional[uuid.UUID] = None     # Reference to BankProvider

class CardCreate(CardBase):
    pass

class CardUpdate(BaseModel):
    card_name: Optional[str] = None
    payment_due_date: Optional[date] = None
    bank_provider_id: Optional[uuid.UUID] = None

class Card(CardBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: Optional[datetime] = None  # Made optional to handle missing defaults

    # Full related entity details from API
    bank_provider: Optional[BankProviderSimple] = None

    class Config:
        from_attributes = True
