from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date, datetime
import uuid

class IncomeBase(BaseModel):
    amount: float = Field(..., gt=0, description="Income amount (must be positive)")
    currency: str = Field("USD", max_length=3, description="Currency code")
    description: str = Field(..., min_length=1, max_length=200, description="Income description")
    source: str = Field("General Income", min_length=1, max_length=100, description="Source of the income (employer, client, etc)")
    income_date: date = Field(..., description="Date of income")
    is_recurring: bool = Field(False, description="Whether this income recurs monthly")
    card_id: uuid.UUID = Field(..., description="ID of the card associated with this income")

class IncomeCreate(IncomeBase):
    pass

class IncomeUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0, description="Income amount (must be positive)")
    currency: Optional[str] = Field(None, max_length=3, description="Currency code")
    description: Optional[str] = Field(None, min_length=1, max_length=200, description="Income description")
    source: Optional[str] = Field(None, min_length=1, max_length=100, description="Source of the income (employer, client, etc)")
    income_date: Optional[date] = Field(None, description="Date of income")
    is_recurring: Optional[bool] = Field(None, description="Whether this income recurs monthly")
    recurring_day: Optional[int] = Field(None, ge=1, le=31, description="Day of month for recurrence (1-31)")
    card_id: Optional[uuid.UUID] = Field(None, description="ID of the card associated with this income")

class Income(IncomeBase):
    id: uuid.UUID
    user_id: uuid.UUID
    card_id: uuid.UUID
    recurring_day: Optional[int]
    last_processed_date: Optional[date]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True