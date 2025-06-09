from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class AlertType(str, Enum):
    SPENDING_LIMIT = "spending_limit"
    MERCHANT_WATCH = "merchant_watch"
    CATEGORY_BUDGET = "category_budget"
    UNUSUAL_SPENDING = "unusual_spending"
    LARGE_TRANSACTION = "large_transaction"
    NEW_MERCHANT = "new_merchant"
    BUDGET_EXCEEDED = "budget_exceeded"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertBase(BaseModel):
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    criteria: Optional[str] = None
    threshold: Optional[float] = None
    frequency: Optional[str] = None


class AlertCreate(AlertBase):
    statement_id: Optional[uuid.UUID] = None


class Alert(AlertBase):
    id: uuid.UUID
    user_id: uuid.UUID
    statement_id: Optional[uuid.UUID] = None
    is_active: bool
    is_read: bool
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AlertUpdate(BaseModel):
    is_read: Optional[bool] = None
    is_active: Optional[bool] = None
    acknowledged_at: Optional[datetime] = None
