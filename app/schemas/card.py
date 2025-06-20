from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
import uuid
from app.schemas.bank_provider import BankProviderSimple
from app.schemas.network_provider import NetworkProviderSimple
from app.schemas.card_type import CardTypeSimple

class CardBase(BaseModel):
    card_name: str
    payment_due_date: Optional[date] = None
    network_provider_id: Optional[uuid.UUID] = None  # Reference to NetworkProvider
    bank_provider_id: Optional[uuid.UUID] = None     # Reference to BankProvider
    card_type_id: Optional[uuid.UUID] = None         # Reference to CardType

class CardCreate(CardBase):
    pass

class CardUpdate(BaseModel):
    card_name: Optional[str] = None
    payment_due_date: Optional[date] = None
    network_provider_id: Optional[uuid.UUID] = None
    bank_provider_id: Optional[uuid.UUID] = None
    card_type_id: Optional[uuid.UUID] = None

class Card(CardBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: Optional[datetime] = None  # Made optional to handle missing defaults
    
    # Include the full related entity details for rich display
    bank_provider: Optional[BankProviderSimple] = None
    network_provider: Optional[NetworkProviderSimple] = None
    card_type: Optional[CardTypeSimple] = None  # Now maps correctly to the relationship
    
    class Config:
        from_attributes = True
