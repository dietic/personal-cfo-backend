from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')  # Hex color validation
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    id: uuid.UUID
    user_id: uuid.UUID
    is_default: bool
    keywords: List[str] = []  # Will be populated from relationship
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CategoryWithUsage(CategoryResponse):
    transaction_count: int = 0  # Number of transactions using this category


class CategoryKeywordMatch(BaseModel):
    category_id: uuid.UUID
    category_name: str
    matched_keywords: List[str]
    confidence: float  # 0.0 to 1.0
