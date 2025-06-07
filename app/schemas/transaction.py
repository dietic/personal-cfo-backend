from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
import uuid

class TransactionBase(BaseModel):
    merchant: str
    amount: Decimal
    currency: str = "USD"
    category: Optional[str] = None
    transaction_date: date
    tags: Optional[List[str]] = None
    description: Optional[str] = None

class TransactionCreate(TransactionBase):
    card_id: uuid.UUID

class TransactionUpdate(BaseModel):
    merchant: Optional[str] = None
    amount: Optional[Decimal] = None
    category: Optional[str] = None
    transaction_date: Optional[date] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None

class Transaction(TransactionBase):
    id: uuid.UUID
    card_id: uuid.UUID
    ai_confidence: Optional[Decimal] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class TransactionWithCard(Transaction):
    card: "Card"
    
    class Config:
        from_attributes = True

# Import here to avoid circular imports
from app.schemas.card import Card
TransactionWithCard.model_rebuild()
