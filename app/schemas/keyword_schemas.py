"""
Pydantic schemas for keyword management API.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class KeywordCreate(BaseModel):
    """Schema for creating a new keyword"""
    category_id: str = Field(..., description="ID of the category to add the keyword to")
    keyword: str = Field(..., min_length=1, max_length=255, description="The keyword text")
    description: Optional[str] = Field(None, description="Optional description for the keyword")


class KeywordUpdate(BaseModel):
    """Schema for updating a keyword"""
    keyword: Optional[str] = Field(None, min_length=1, max_length=255, description="The updated keyword text")
    description: Optional[str] = Field(None, description="Updated description for the keyword")


class KeywordResponse(BaseModel):
    """Schema for keyword response"""
    id: str
    user_id: str
    category_id: str
    category_name: str
    keyword: str
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class KeywordSummaryResponse(BaseModel):
    """Schema for keywords summary grouped by categories"""
    summary: Dict[str, Any]


class CategorizationRequest(BaseModel):
    """Schema for transaction categorization request"""
    description: str = Field(..., description="Transaction description to categorize")


class AIKeywordGenerationRequest(BaseModel):
    """Schema for AI keyword generation request"""
    clear_existing: bool = Field(False, description="Whether to clear existing keywords before generating new ones")


class AIKeywordGenerationResponse(BaseModel):
    """Schema for AI keyword generation response"""
    message: str
    keywords_added: int
    category_id: str
    category_name: str
    task_id: Optional[str] = Field(None, description="ID of the background task for tracking")


class AIUsageStatsResponse(BaseModel):
    """Schema for AI keyword usage statistics"""
    current_usage: int
    monthly_limit: int
    last_used: Optional[datetime]
    reset_at: Optional[datetime]
    remaining: int
    plan_tier: str


class KeywordBulkDeleteRequest(BaseModel):
    """Schema for bulk keyword deletion"""
    keyword_ids: List[str] = Field(..., description="List of keyword IDs to delete")
