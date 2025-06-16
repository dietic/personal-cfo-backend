from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
import uuid

class BudgetBase(BaseModel):
    category: str
    limit_amount: Decimal
    currency: str = "USD"  # Default to USD
    month: date  # First day of the month

class BudgetCreate(BudgetBase):
    pass

class BudgetUpdate(BaseModel):
    category: Optional[str] = None
    limit_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    month: Optional[date] = None

class Budget(BudgetBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class BudgetAlert(BaseModel):
    budget: Budget
    current_spending: Decimal
    percentage_used: float
    alert_type: str  # "warning" (>90%) or "exceeded" (>100%)
