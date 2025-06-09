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
    extraction_status: str
    categorization_status: str
    retry_count: str  # JSON string
    error_message: Optional[str] = None
    is_processed: bool
    ai_insights: Optional[str] = None  # JSON string
    created_at: datetime
    
    class Config:
        from_attributes = True

class StatementProcess(BaseModel):
    statement_id: uuid.UUID
    transactions_found: int
    transactions_created: int
    alerts_created: Optional[int] = 0
    ai_insights: Optional[Dict[str, Any]] = None

class StatementProcessRequest(BaseModel):
    card_id: Optional[uuid.UUID] = None
    card_name: Optional[str] = None
    statement_month: Optional[date] = None


class StatementStatusResponse(BaseModel):
    statement_id: uuid.UUID
    status: str
    extraction_status: str
    categorization_status: str
    retry_count: Dict[str, int]
    error_message: Optional[str] = None
    progress_percentage: int  # 0-100
    current_step: str  # "uploading", "extracting", "categorizing", "completed"
    estimated_completion: Optional[str] = None  # Human readable time estimate


class ExtractionRequest(BaseModel):
    card_id: Optional[uuid.UUID] = None
    card_name: Optional[str] = None
    statement_month: Optional[date] = None


class ExtractionResponse(BaseModel):
    statement_id: uuid.UUID
    transactions_found: int
    status: str
    message: str


class CategorizationRequest(BaseModel):
    use_ai: bool = True
    use_keywords: bool = True


class CategorizationResponse(BaseModel):
    statement_id: uuid.UUID
    transactions_categorized: int
    ai_categorized: int
    keyword_categorized: int
    uncategorized: int
    status: str
    message: str


class RetryRequest(BaseModel):
    step: str  # "extraction" or "categorization"
