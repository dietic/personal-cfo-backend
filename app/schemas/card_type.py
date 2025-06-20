from pydantic import BaseModel
from typing import Optional
import uuid

class CardTypeBase(BaseModel):
    name: str
    short_name: Optional[str] = None
    country: str = "GLOBAL"
    is_active: bool = True
    description: Optional[str] = None
    typical_interest_rate: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None

class CardTypeCreate(CardTypeBase):
    pass

class CardTypeUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    country: Optional[str] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    typical_interest_rate: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None

class CardType(CardTypeBase):
    id: uuid.UUID
    
    class Config:
        from_attributes = True

# Simple version for use in other schemas
class CardTypeSimple(BaseModel):
    id: uuid.UUID
    name: str
    short_name: Optional[str] = None
    country: str
    description: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    
    class Config:
        from_attributes = True
