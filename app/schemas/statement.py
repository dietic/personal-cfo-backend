from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import uuid

class StatementBase(BaseModel):
    filename: str
    file_type: str

class StatementCreate(StatementBase):
    file_path: str
    statement_month: Optional[date] = None

class Statement(StatementBase):
    id: uuid.UUID
    user_id: uuid.UUID
    file_path: str
    statement_month: Optional[date] = None
    status: str
    is_processed: bool
    ai_insights: Optional[str] = None  # JSON string
    created_at: datetime
    
    class Config:
        from_attributes = True

class StatementProcess(BaseModel):
    statement_id: uuid.UUID
    transactions_found: int
    transactions_created: int
    ai_insights: Optional[Dict[str, Any]] = None

class StatementProcessRequest(BaseModel):
    card_id: Optional[uuid.UUID] = None
    card_name: Optional[str] = None
    statement_month: Optional[date] = None
