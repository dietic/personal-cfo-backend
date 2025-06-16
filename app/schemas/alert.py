from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

# Import the enums from the model to ensure consistency
from app.models.alert import AlertType, AlertSeverity


class AlertBase(BaseModel):
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str  # Changed from 'description' to 'message' to match DB


class AlertCreate(AlertBase):
    statement_id: Optional[uuid.UUID] = None


class Alert(AlertBase):
    id: uuid.UUID
    user_id: uuid.UUID
    statement_id: Optional[uuid.UUID] = None
    is_read: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AlertUpdate(BaseModel):
    is_read: Optional[bool] = None
