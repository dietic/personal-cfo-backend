"""
API endpoints for managing category keywords.
Provides REST API for CRUD operations on user-defined keywords.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_user_type
from app.models.user import User, UserTypeEnum
from app.services.keyword_service import KeywordService
from app.services.ai_keyword_service import AIKeywordService
from app.schemas.keyword_schemas import (
    KeywordCreate, KeywordUpdate, KeywordResponse, 
    KeywordSummaryResponse, CategorizationRequest,
    AIKeywordGenerationRequest, AIKeywordGenerationResponse, AIUsageStatsResponse,
    KeywordBulkDeleteRequest
)

router = APIRouter()


@router.get("/", response_model=List[KeywordResponse])
async def get_user_keywords(
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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


@router.delete("/bulk")
async def delete_keywords_bulk(
    payload: KeywordBulkDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete multiple keywords in a single request"""
    keyword_service = KeywordService(db)

    keyword_ids = [kid for kid in payload.keyword_ids if kid]
    if not keyword_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No keyword IDs provided"
        )

    deleted_count = keyword_service.remove_keywords_bulk(
        str(current_user.id), keyword_ids
    )

    return {
        "message": "Keywords deleted successfully",
        "deleted_count": deleted_count
    }


@router.delete("/{keyword_id}")
async def delete_keyword(
    keyword_id: str,
    current_user: User = Depends(get_current_active_user),
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

@router.delete("/bulk")
async def delete_keywords_bulk(
    payload: KeywordBulkDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete multiple keywords in a single request"""
    keyword_service = KeywordService(db)

    keyword_ids = [kid for kid in payload.keyword_ids if kid]
    if not keyword_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No keyword IDs provided"
        )

    deleted_count = keyword_service.remove_keywords_bulk(
        str(current_user.id), keyword_ids
    )

    return {
        "message": "Keywords deleted successfully",
        "deleted_count": deleted_count
    }


@router.get("/summary", response_model=KeywordSummaryResponse)
async def get_keywords_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a summary of keywords grouped by categories"""
    keyword_service = KeywordService(db)
    summary = keyword_service.get_keywords_summary(str(current_user.id))
    
    return KeywordSummaryResponse(summary=summary)


@router.post("/categorize")
async def categorize_transaction(
    request: CategorizationRequest,
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Seed default keywords for the current user"""
    keyword_service = KeywordService(db)
    keyword_service.seed_default_keywords(str(current_user.id))
    
    return {"message": "Default keywords seeded successfully"}


@router.post("/test-categorization")
async def test_keyword_categorization(
    descriptions: List[str],
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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


@router.post("/generate-ai-keywords/{category_id}", response_model=AIKeywordGenerationResponse)
async def generate_ai_keywords(
    category_id: str,
    ai_request: AIKeywordGenerationRequest,
    request: Request,
    current_user: User = Depends(require_user_type(UserTypeEnum.PLUS)),
    db: Session = Depends(get_db)
):
    """Generate AI-powered keywords for a category"""
    from app.models.category import Category
    from app.tasks.ai_tasks import generate_ai_keywords_task
    
    # Get the category
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == str(current_user.id)
    ).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check if category already has AI-generated keywords
    if category.ai_seeded_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI keywords have already been generated for this category"
        )
    
    # Check if this is a default category
    if category.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate AI keywords for default categories. Default categories already come with pre-defined keywords."
        )
    
    # Launch background task
    task = generate_ai_keywords_task.delay(
        str(current_user.id),
        str(category.id),
        ai_request.clear_existing
    )
    
    return AIKeywordGenerationResponse(
        message="AI keyword generation started in background. Keywords will be added shortly.",
        keywords_added=0,  # Will be updated when task completes
        category_id=category_id,
        category_name=category.name,
        task_id=task.id  # Include task ID for tracking
    )


@router.get("/task-status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get status of a background task"""
    from app.tasks.ai_tasks import generate_ai_keywords_task
    from celery.result import AsyncResult
    
    # Get task result
    task_result = AsyncResult(task_id, app=generate_ai_keywords_task.app)
    
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None,
        "successful": task_result.successful() if task_result.ready() else None
    }


@router.get("/ai-usage-stats", response_model=AIUsageStatsResponse)
async def get_ai_keyword_usage_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI keyword generation usage statistics"""
    ai_keyword_service = AIKeywordService(db)
    
    stats = ai_keyword_service.get_ai_usage_stats(current_user)
    
    return AIUsageStatsResponse(**stats)
