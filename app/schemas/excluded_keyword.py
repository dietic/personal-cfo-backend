from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ExcludedKeywordCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)


class ExcludedKeywordResponse(BaseModel):
    id: str
    keyword: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ExcludedKeywordListResponse(BaseModel):
    items: List[ExcludedKeywordResponse]
