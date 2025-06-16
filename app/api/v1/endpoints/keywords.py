"""
API endpoints for managing category keywords.
Provides REST API for CRUD operations on user-defined keywords.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.keyword_service import KeywordService
from app.schemas.keyword_schemas import (
    KeywordCreate, KeywordUpdate, KeywordResponse, 
    KeywordSummaryResponse, CategorizationRequest
)

router = APIRouter()


@router.get("/", response_model=List[KeywordResponse])
async def get_user_keywords(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all keywords for the current user"""
    keyword_service = KeywordService(db)
    keywords = keyword_service.get_user_keywords(str(current_user.id))
    
    return [
        KeywordResponse(
            id=str(keyword.id),
            user_id=str(keyword.user_id),
            category_id=str(keyword.category_id),
            category_name=keyword.category.name if keyword.category else "Unknown",
            keyword=keyword.keyword,
            description=keyword.description,
            created_at=keyword.created_at,
            updated_at=keyword.updated_at
        ) for keyword in keywords
    ]


@router.get("/by-category/{category_id}", response_model=List[KeywordResponse])
async def get_keywords_by_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all keywords for a specific category"""
    keyword_service = KeywordService(db)
    keywords = keyword_service.get_keywords_by_category(str(current_user.id), category_id)
    
    return [
        KeywordResponse(
            id=str(keyword.id),
            user_id=str(keyword.user_id),
            category_id=str(keyword.category_id),
            category_name=keyword.category.name if keyword.category else "Unknown",
            keyword=keyword.keyword,
            description=keyword.description,
            created_at=keyword.created_at,
            updated_at=keyword.updated_at
        ) for keyword in keywords
    ]


@router.post("/", response_model=KeywordResponse)
async def create_keyword(
    keyword_data: KeywordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new keyword for a category"""
    keyword_service = KeywordService(db)
    
    try:
        keyword = keyword_service.add_keyword(
            user_id=str(current_user.id),
            category_id=keyword_data.category_id,
            keyword=keyword_data.keyword,
            description=keyword_data.description
        )
        
        return KeywordResponse(
            id=str(keyword.id),
            user_id=str(keyword.user_id),
            category_id=str(keyword.category_id),
            category_name=keyword.category.name if keyword.category else "Unknown",
            keyword=keyword.keyword,
            description=keyword.description,
            created_at=keyword.created_at,
            updated_at=keyword.updated_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    keyword_id: str,
    keyword_data: KeywordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a keyword"""
    keyword_service = KeywordService(db)
    
    try:
        keyword = keyword_service.update_keyword(
            user_id=str(current_user.id),
            keyword_id=keyword_id,
            keyword_text=keyword_data.keyword,
            description=keyword_data.description
        )
        
        if not keyword:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Keyword not found"
            )
        
        return KeywordResponse(
            id=str(keyword.id),
            user_id=str(keyword.user_id),
            category_id=str(keyword.category_id),
            category_name=keyword.category.name if keyword.category else "Unknown",
            keyword=keyword.keyword,
            description=keyword.description,
            created_at=keyword.created_at,
            updated_at=keyword.updated_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{keyword_id}")
async def delete_keyword(
    keyword_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a keyword"""
    keyword_service = KeywordService(db)
    
    success = keyword_service.remove_keyword(str(current_user.id), keyword_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keyword not found"
        )
    
    return {"message": "Keyword deleted successfully"}


@router.get("/summary", response_model=KeywordSummaryResponse)
async def get_keywords_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a summary of keywords grouped by categories"""
    keyword_service = KeywordService(db)
    summary = keyword_service.get_keywords_summary(str(current_user.id))
    
    return KeywordSummaryResponse(summary=summary)


@router.post("/categorize")
async def categorize_transaction(
    request: CategorizationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Categorize a transaction description using keywords"""
    keyword_service = KeywordService(db)
    
    category_id = keyword_service.categorize_transaction(
        user_id=str(current_user.id),
        transaction_description=request.description
    )
    
    return {
        "category_id": category_id,
        "matched": category_id is not None
    }


@router.post("/seed-defaults")
async def seed_default_keywords(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Seed default keywords for the current user"""
    keyword_service = KeywordService(db)
    keyword_service.seed_default_keywords(str(current_user.id))
    
    return {"message": "Default keywords seeded successfully"}


@router.post("/test-categorization")
async def test_keyword_categorization(
    descriptions: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test how transaction descriptions would be categorized using keywords"""
    from app.services.keyword_categorization_service import KeywordCategorizationService
    
    categorization_service = KeywordCategorizationService(db)
    previews = categorization_service.get_categorization_preview(
        str(current_user.id), descriptions
    )
    
    return {
        "test_results": previews,
        "summary": {
            "total_tested": len(descriptions),
            "would_categorize": len([p for p in previews if p['would_categorize']]),
            "would_be_uncategorized": len([p for p in previews if not p['would_categorize']])
        }
    }


@router.get("/coverage-stats")
async def get_keyword_coverage_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get statistics about keyword coverage for categories"""
    from app.services.keyword_categorization_service import KeywordCategorizationService
    
    categorization_service = KeywordCategorizationService(db)
    stats = categorization_service.get_coverage_statistics(str(current_user.id))
    
    return stats


@router.post("/categorize-transactions")
async def categorize_transactions_with_keywords(
    transaction_data: List[Dict[str, Any]],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Categorize a batch of transactions using keywords only (no AI)"""
    from app.services.keyword_categorization_service import KeywordCategorizationService
    
    categorization_service = KeywordCategorizationService(db)
    categorized_transactions = categorization_service.categorize_transactions_batch(
        str(current_user.id), transaction_data
    )
    
    return {
        "categorized_transactions": categorized_transactions,
        "summary": {
            "total_transactions": len(transaction_data),
            "categorized": len([t for t in categorized_transactions if t['category'] != 'Uncategorized']),
            "uncategorized": len([t for t in categorized_transactions if t['category'] == 'Uncategorized'])
        }
    }
