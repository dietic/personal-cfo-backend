from pydantic import BaseModel, validator
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

    @validator('statement_month', pre=True)
    def validate_statement_month(cls, v):
        if v is None or v == "":
            return None
        
        if isinstance(v, date):
            return v
            
        if isinstance(v, str):
            # Try to parse different date formats
            try:
                # Try YYYY-MM-DD format
                if len(v) == 10 and v.count('-') == 2:
                    return datetime.strptime(v, '%Y-%m-%d').date()
                # Try YYYY-MM format (add day 01)
                elif len(v) == 7 and v.count('-') == 1:
                    return datetime.strptime(f"{v}-01", '%Y-%m-%d').date()
                else:
                    # Handle month names
                    month_names = {
                        'january': 1, 'february': 2, 'march': 3, 'april': 4,
                        'may': 5, 'june': 6, 'july': 7, 'august': 8,
                        'september': 9, 'october': 10, 'november': 11, 'december': 12,
                        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                    }
                    month_name = v.lower().strip()
                    if month_name in month_names:
                        current_year = datetime.now().year
                        month_number = month_names[month_name]
                        return date(current_year, month_number, 1)
                    else:
                        raise ValueError(f"Invalid date format: '{v}'. Expected formats: YYYY-MM-DD, YYYY-MM, or month name (e.g., 'may', 'january')")
            except ValueError as e:
                if "Invalid date format" in str(e):
                    raise e
                else:
                    raise ValueError(f"Invalid date format: '{v}'. Expected formats: YYYY-MM-DD, YYYY-MM, or month name (e.g., 'may', 'january')")
        
        raise ValueError(f"Invalid date format: '{v}'. Expected string or date object")


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
